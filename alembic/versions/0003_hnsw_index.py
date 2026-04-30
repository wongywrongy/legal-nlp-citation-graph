"""hnsw replaces ivfflat on documents.embedding

Revision ID: 0003_hnsw
Revises: 0002_pgvector
Create Date: 2026-04-29

Notes:
- The pgvector index lives on `documents.embedding`. The semantic_similarity
  table stores pre-computed cosine *scores* (regular floats), not vectors, so
  it has no ivfflat or HNSW index to migrate; its existing btree indexes on
  (source_id), (target_id), and (source_id, similarity_score DESC) are kept.
- HNSW (added in pgvector 0.5) generally has better recall and steadier
  latency than ivfflat as the corpus grows, and does not require the
  per-list tuning ivfflat does (`lists` parameter).
- Postgres-only: SQLite (test fallback) doesn't have either index type, so
  the migration is a no-op there.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0003_hnsw"
down_revision: Union[str, None] = "0002_pgvector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_HNSW_PARAMS = "m = 16, ef_construction = 64"


def _is_postgres(bind) -> bool:
    return bind.dialect.name == "postgresql"


def upgrade() -> None:
    bind = op.get_bind()
    if not _is_postgres(bind):
        return

    # Drop the ivfflat index from 0002 if it exists. IF EXISTS keeps the
    # migration idempotent on environments where the prior index was already
    # rebuilt manually.
    op.execute("DROP INDEX IF EXISTS ix_documents_embedding")
    op.execute(
        f"CREATE INDEX IF NOT EXISTS ix_documents_embedding "
        f"ON documents USING hnsw (embedding vector_cosine_ops) "
        f"WITH ({_HNSW_PARAMS})"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _is_postgres(bind):
        return

    op.execute("DROP INDEX IF EXISTS ix_documents_embedding")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_embedding "
        "ON documents USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )
