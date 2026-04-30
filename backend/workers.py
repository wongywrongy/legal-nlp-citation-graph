"""
ARQ worker definitions for background PDF processing.

Run with:
    arq backend.workers.WorkerSettings
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Tuple

import structlog
from arq.connections import RedisSettings
from sqlalchemy import and_, delete, not_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.async_processor import process_all_documents_async, process_document_async
from backend.config import settings
from backend.courtlistener import enrich_document
from backend.database import AsyncSessionLocal
from backend.models import Document, SemanticSimilarity

logger = structlog.get_logger()


async def process_pdf_job(ctx, document_id: str):
    result = await process_document_async(document_id)
    # Chain enrichment + embedding so the document arrives at the dashboard
    # fully populated without callers having to enqueue extra jobs.
    if settings.feature_external_enrichment:
        try:
            await ctx["redis"].enqueue_job("enrich_document_job", document_id)
        except Exception as e:
            logger.warning(
                "Failed to enqueue enrich_document_job",
                doc_id=document_id,
                error=str(e),
            )
    if settings.feature_embeddings:
        try:
            await ctx["redis"].enqueue_job("embed_document_job", document_id)
        except Exception as e:
            logger.warning(
                "Failed to enqueue embed_document_job",
                doc_id=document_id,
                error=str(e),
            )
    return result


async def process_all_job(ctx):
    return await process_all_documents_async()


async def enrich_document_job(ctx, document_id: str):
    return await enrich_document(document_id)


async def embed_document_job(ctx, document_id: str):
    """
    Compute the document embedding and refresh its top-k semantic neighbors.

    Idempotent and race-resistant:
        - The vector update is a single in-place column write.
        - Neighbor refresh is a postgres UPSERT (ON CONFLICT DO UPDATE) on
          (source_id, target_id), so two embed_document_job runs that touch
          overlapping pairs converge instead of clobbering each other.
        - Stale rows for *this* source are deleted only when their target is
          no longer in the new top-K. The delete is bounded to source_id =
          document_id so it can't race with a concurrent job for a different
          document.

    Skipped on sqlite or when FEATURE_EMBEDDINGS=false.
    """
    if not settings.feature_embeddings:
        return {"document_id": document_id, "skipped": "feature_disabled"}
    if not settings.database_url_sync.startswith("postgresql"):
        return {"document_id": document_id, "skipped": "non_postgres"}

    # Local import so the worker doesn't pay the model load cost unless
    # this code path actually runs.
    from backend.embeddings import embed_text, top_k_for_document

    async with AsyncSessionLocal() as session:
        row = await session.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = row.scalar_one_or_none()
        if doc is None:
            return {"document_id": document_id, "skipped": "not_found"}
        if not doc.full_text:
            logger.info("Document has no full_text — skipping embed", doc_id=document_id)
            return {"document_id": document_id, "skipped": "no_text"}

        vec = embed_text(doc.full_text)
        if not vec:
            return {"document_id": document_id, "skipped": "empty_vector"}

        doc.embedding = vec
        doc.embedded_at = datetime.utcnow()
        await session.commit()

        neighbors: List[Tuple[str, float]] = await top_k_for_document(
            session, document_id, k=settings.embedding_top_k
        )
        now = datetime.utcnow()

        # Drop forward rows whose target is no longer in the new top-K.
        # Bounded to source_id = document_id so other workers' rows stay
        # untouched.
        new_target_ids = [tid for tid, _ in neighbors]
        if new_target_ids:
            await session.execute(
                delete(SemanticSimilarity).where(
                    and_(
                        SemanticSimilarity.source_id == document_id,
                        not_(SemanticSimilarity.target_id.in_(new_target_ids)),
                    )
                )
            )
        else:
            await session.execute(
                delete(SemanticSimilarity).where(
                    SemanticSimilarity.source_id == document_id
                )
            )

        # Symmetric upsert. ON CONFLICT (source_id, target_id) updates the
        # score in place — concurrent jobs that happen to write the same
        # pair just converge to the latest value.
        rows_to_upsert: list[dict] = []
        for other_id, score in neighbors:
            rows_to_upsert.append(
                {
                    "id": str(uuid.uuid4()),
                    "source_id": document_id,
                    "target_id": other_id,
                    "similarity_score": score,
                    "created_at": now,
                }
            )
            rows_to_upsert.append(
                {
                    "id": str(uuid.uuid4()),
                    "source_id": other_id,
                    "target_id": document_id,
                    "similarity_score": score,
                    "created_at": now,
                }
            )
        if rows_to_upsert:
            stmt = pg_insert(SemanticSimilarity).values(rows_to_upsert)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_semantic_pair",
                set_={
                    "similarity_score": stmt.excluded.similarity_score,
                    "created_at": stmt.excluded.created_at,
                },
            )
            await session.execute(stmt)
        await session.commit()

        logger.info(
            "Document embedded",
            doc_id=document_id,
            neighbors=len(neighbors),
        )
        return {
            "document_id": document_id,
            "neighbors": len(neighbors),
            "embedded_at": doc.embedded_at.isoformat(),
        }


class WorkerSettings:
    functions = [
        process_pdf_job,
        process_all_job,
        enrich_document_job,
        embed_document_job,
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 4
    job_timeout = 300


async def enqueue_document(redis, document_id: str):
    """Helper used by API routes to enqueue a job."""
    return await redis.enqueue_job("process_pdf_job", document_id)
