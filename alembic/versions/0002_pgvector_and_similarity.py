"""pgvector + semantic_similarity

Revision ID: 0002_pgvector
Revises: 0001_initial
Create Date: 2026-04-29

Adds:
- CREATE EXTENSION vector (postgres only)
- documents.full_text       — extracted body text used for embeddings
- documents.embedding       — VECTOR(768) — all-mpnet-base-v2
- documents.embedded_at     — timestamp of last embedding
- semantic_similarity table — pre-computed top-k neighbors per doc
- ivfflat cosine index on documents.embedding (TODO: switch to hnsw on pgvector >= 0.6)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_pgvector"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgres(bind) -> bool:
    return bind.dialect.name == "postgresql"


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = _is_postgres(bind)

    if is_pg:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        from pgvector.sqlalchemy import Vector

        embedding_col = sa.Column("embedding", Vector(768), nullable=True)
    else:
        embedding_col = sa.Column("embedding", sa.LargeBinary(), nullable=True)

    op.add_column("documents", sa.Column("full_text", sa.Text(), nullable=True))
    op.add_column("documents", embedding_col)
    op.add_column(
        "documents", sa.Column("embedded_at", sa.DateTime(), nullable=True)
    )

    op.create_table(
        "semantic_similarity",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "source_id",
            sa.String(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_id",
            sa.String(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("source_id", "target_id", name="uq_semantic_pair"),
        sa.CheckConstraint("source_id <> target_id", name="ck_semantic_self"),
        sa.CheckConstraint(
            "similarity_score >= 0 AND similarity_score <= 1",
            name="ck_semantic_score_range",
        ),
    )
    op.create_index(
        "ix_semantic_similarity_source_id",
        "semantic_similarity",
        ["source_id"],
    )
    op.create_index(
        "ix_semantic_similarity_target_id",
        "semantic_similarity",
        ["target_id"],
    )
    op.create_index(
        "ix_semantic_source_score",
        "semantic_similarity",
        ["source_id", "similarity_score"],
    )

    if is_pg:
        # ivfflat is broadly compatible (pgvector >= 0.5).
        # Switch to hnsw on pgvector >= 0.6 for faster queries.
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_documents_embedding "
            "ON documents USING ivfflat (embedding vector_cosine_ops) "
            "WITH (lists = 100)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = _is_postgres(bind)

    if is_pg:
        op.execute("DROP INDEX IF EXISTS ix_documents_embedding")

    op.drop_index("ix_semantic_source_score", table_name="semantic_similarity")
    op.drop_index(
        "ix_semantic_similarity_target_id", table_name="semantic_similarity"
    )
    op.drop_index(
        "ix_semantic_similarity_source_id", table_name="semantic_similarity"
    )
    op.drop_table("semantic_similarity")
    op.drop_column("documents", "embedded_at")
    op.drop_column("documents", "embedding")
    op.drop_column("documents", "full_text")
    # Don't drop the extension — other DBs/tables may use it.
