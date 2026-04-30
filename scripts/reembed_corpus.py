"""
Re-embed every document in the corpus using the current embed_text()
implementation, then refresh that document's semantic_similarity rows.

Use after upgrading the embedding strategy (e.g., the Phase 1 chunked +
mean-pooled rollout) so existing documents pick up the new vectors without
re-ingesting their PDFs.

Usage (inside the backend container):
    docker compose -f docker-compose.dev.yml exec backend \\
        python scripts/reembed_corpus.py [--all] [--limit N]

    --all      Re-embed every document, including ones missing full_text
               (they'll be skipped if no text is available).
    --limit N  Stop after N documents (useful for spot-checks).

Idempotent — running twice produces identical output for the same corpus.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
import uuid
from datetime import datetime

import structlog

# Allow running via `python scripts/reembed_corpus.py` from repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, select

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.embeddings import embed_text, top_k_for_document
from backend.models import Document, SemanticSimilarity

logger = structlog.get_logger()


async def _select_documents(session, all_docs: bool, limit: int | None):
    stmt = select(Document)
    if not all_docs:
        stmt = stmt.where(Document.embedding.isnot(None))
    stmt = stmt.order_by(Document.created_at.asc())
    if limit:
        stmt = stmt.limit(limit)
    rows = await session.execute(stmt)
    return rows.scalars().all()


async def _refresh_neighbors(session, document_id: str) -> int:
    """Mirror of workers.embed_document_job neighbor refresh."""
    neighbors = await top_k_for_document(
        session, document_id, k=settings.embedding_top_k
    )

    await session.execute(
        delete(SemanticSimilarity).where(
            (SemanticSimilarity.source_id == document_id)
            | (SemanticSimilarity.target_id == document_id)
        )
    )

    rows_to_insert = []
    now = datetime.utcnow()
    for other_id, score in neighbors:
        rows_to_insert.append(
            {
                "id": str(uuid.uuid4()),
                "source_id": document_id,
                "target_id": other_id,
                "similarity_score": score,
                "created_at": now,
            }
        )
        rows_to_insert.append(
            {
                "id": str(uuid.uuid4()),
                "source_id": other_id,
                "target_id": document_id,
                "similarity_score": score,
                "created_at": now,
            }
        )
    if rows_to_insert:
        await session.execute(SemanticSimilarity.__table__.insert(), rows_to_insert)
    await session.commit()
    return len(neighbors)


async def _reembed_one(session, doc: Document) -> tuple[str, int]:
    if not doc.full_text:
        return ("skip:no_text", 0)
    vec = embed_text(doc.full_text)
    if not vec:
        return ("skip:empty_vector", 0)
    doc.embedding = vec
    doc.embedded_at = datetime.utcnow()
    await session.commit()
    neighbors = await _refresh_neighbors(session, doc.id)
    return ("ok", neighbors)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Include docs without an existing embedding.")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if not settings.feature_embeddings:
        print("FEATURE_EMBEDDINGS is disabled — nothing to do.", file=sys.stderr)
        return
    if not settings.database_url_sync.startswith("postgresql"):
        print("Re-embedding requires Postgres + pgvector.", file=sys.stderr)
        sys.exit(1)

    async with AsyncSessionLocal() as session:
        docs = await _select_documents(session, args.all, args.limit)

    total = len(docs)
    if total == 0:
        print("No documents to re-embed.")
        return

    print(f"Re-embedding {total} document(s) using {settings.embedding_model}")
    started = time.monotonic()
    counters = {"ok": 0, "skip:no_text": 0, "skip:empty_vector": 0}

    for idx, doc in enumerate(docs, start=1):
        # Use a fresh session per doc so a single failure doesn't poison the
        # transaction state for the remaining documents.
        async with AsyncSessionLocal() as session:
            attached = await session.merge(doc)
            try:
                status, neighbors = await _reembed_one(session, attached)
            except Exception as e:  # pragma: no cover
                await session.rollback()
                logger.warning("Re-embed failed", doc_id=doc.id, error=str(e))
                continue
        counters[status] = counters.get(status, 0) + 1
        elapsed = time.monotonic() - started
        rate = idx / elapsed if elapsed > 0 else 0
        print(
            f"[{idx}/{total}] {doc.id[:8]}… {status:>16}  "
            f"neighbors={neighbors:>3}  ({rate:.1f} docs/s, "
            f"{(total - idx) / rate:.0f}s remaining)" if rate > 0 else
            f"[{idx}/{total}] {doc.id[:8]}… {status}"
        )

    elapsed = time.monotonic() - started
    print(
        f"\nDone in {elapsed:.1f}s — "
        f"{counters['ok']} re-embedded, "
        f"{counters['skip:no_text']} skipped (no text), "
        f"{counters['skip:empty_vector']} skipped (empty vector)"
    )


if __name__ == "__main__":
    asyncio.run(main())
