"""
ARQ worker definitions for background PDF processing.

Run with:
    arq backend.workers.WorkerSettings

Stage logs are emitted via `backend.progress.stage`. To follow ingest
progress for one doc:

    docker compose -f docker-compose.dev.yml logs -f worker | grep '\\[pipeline\\]'

`on_startup` pre-warms the embedding (and optionally cross-encoder) model
so the first job after a worker boot doesn't pay the silent ~5–10s
weights load — that delay used to look identical to "stuck" in logs.
"""
from __future__ import annotations

import asyncio
import time
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
from backend.progress import stage, step

logger = structlog.get_logger()


async def process_pdf_job(ctx, document_id: str):
    """Top-level ingest entrypoint. The inner `process_document_async`
    already emits its own stage(...) lines, so this wrapper just chains
    follow-up jobs (enrich + embed). We log only a `chained` step so the
    user can see a single doc's full lifecycle in the worker output.

    Track A.4 — extraction_failed gating: the inner processor raises
    `ExtractionFailedError` AND sets `documents.status = 'extraction_failed'`
    when the PDF produced too little text. We catch the exception here
    so the ARQ job itself doesn't retry indefinitely, and we skip the
    chained embed + enrich jobs (no point embedding empty text).
    """
    from backend.exceptions import ExtractionFailedError

    try:
        result = await process_document_async(document_id)
    except ExtractionFailedError as e:
        # Already logged by the processor. Don't enqueue downstream.
        step(
            "skip_downstream",
            doc=document_id,
            reason="extraction_failed",
            chars=e.chars,
        )
        return {"document_id": document_id, "status": "extraction_failed"}

    chained = []
    if settings.feature_external_enrichment:
        try:
            await ctx["redis"].enqueue_job("enrich_document_job", document_id)
            chained.append("enrich")
        except Exception as e:
            logger.warning(
                "Failed to enqueue enrich_document_job",
                doc_id=document_id,
                error=str(e),
            )
    if settings.feature_embeddings:
        try:
            await ctx["redis"].enqueue_job("embed_document_job", document_id)
            chained.append("embed")
        except Exception as e:
            logger.warning(
                "Failed to enqueue embed_document_job",
                doc_id=document_id,
                error=str(e),
            )
    if chained:
        step("chained", doc=document_id, jobs="+".join(chained))
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

        with stage("embed", doc=document_id, chars=len(doc.full_text)) as s:
            # Run embed_text in a thread so the asyncio loop is free to
            # service other ARQ jobs concurrently. sentence-transformers
            # releases the GIL during numpy ops, so up to 4 docs can
            # embed in parallel under our default max_jobs=4 setting.
            t = time.perf_counter()
            vec = await asyncio.to_thread(embed_text, doc.full_text)
            s.step("embed_text", dim=len(vec) if vec else 0, elapsed=time.perf_counter() - t)

            if not vec:
                return {"document_id": document_id, "skipped": "empty_vector"}

            doc.embedding = vec
            doc.embedded_at = datetime.utcnow()
            await session.commit()

            t = time.perf_counter()
            neighbors: List[Tuple[str, float]] = await top_k_for_document(
                session, document_id, k=settings.embedding_top_k
            )
            now = datetime.utcnow()
            s.step("neighbors", k=len(neighbors), elapsed=time.perf_counter() - t)

            # Drop forward rows whose target is no longer in the new top-K.
            # Bounded to source_id = document_id so other workers' rows
            # stay untouched.
            t = time.perf_counter()
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

            # Symmetric upsert. ON CONFLICT (source_id, target_id) updates
            # the score in place — concurrent jobs that happen to write
            # the same pair just converge to the latest value.
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
            s.step(
                "write_neighbors",
                rows=len(rows_to_upsert),
                elapsed=time.perf_counter() - t,
            )

        return {
            "document_id": document_id,
            "neighbors": len(neighbors),
            "embedded_at": doc.embedded_at.isoformat(),
        }


async def _on_startup(ctx) -> None:
    """Pre-warm the embedding (and cross-encoder) model so the first job
    after a worker boot doesn't have a silent ~5–10s weights-load stall.

    Without this the first user-visible "embed" stage looks identical to
    "the worker is hung" — both produce no output for several seconds.
    """
    from backend.embeddings import warmup_models

    logger.info("worker booting — warming models")
    try:
        # Run in a thread; weight-loading is sync and would block the loop.
        await asyncio.to_thread(warmup_models)
    except Exception as e:
        logger.warning("model warmup failed (will retry lazily)", error=str(e))
    logger.info("worker ready", max_jobs=4)


class WorkerSettings:
    functions = [
        process_pdf_job,
        process_all_job,
        enrich_document_job,
        embed_document_job,
    ]
    on_startup = _on_startup
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 4
    job_timeout = 300


async def enqueue_document(redis, document_id: str):
    """Helper used by API routes to enqueue a job."""
    return await redis.enqueue_job("process_pdf_job", document_id)
