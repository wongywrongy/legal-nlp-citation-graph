"""documents.status + documents.page_offsets

Revision ID: 0005_status_offsets
Revises: 0004_external_resolution
Create Date: 2026-04-30

Adds two nullable columns on `documents`:

- `status` (text) — overrides the derived "processing/completed" state for
  failure cases. Currently the only meaningful value is `'extraction_failed'`,
  set when `pdf_processor.extract_full_text()` produces less than 500
  characters of body text after Markdown stripping (a real opinion is
  always at least one paragraph). NULL means "use derived status from
  embedded_at" — that is the healthy path. Future failure states (e.g.
  `'embedding_failed'`) can be added without further schema work.

- `page_offsets` (JSONB on Postgres / JSON on SQLite) — a list of
  `{"page": int, "start": int, "end": int}` records. PyMuPDF4LLM's
  `to_markdown(page_chunks=True)` returns one chunk per page; the
  extractor concatenates the stripped chunks into `full_text` and
  records each page's character span here so the inspector can map a
  citation's `span_start` back to a source page number after the fact.

Both columns are nullable + no backfill is performed. Documents already
in the corpus continue to behave as before until they are reprocessed.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0005_status_offsets"
down_revision: Union[str, None] = "0004_external_resolution"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgres(bind) -> bool:
    return bind.dialect.name == "postgresql"


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column(
        "documents",
        sa.Column("status", sa.String(), nullable=True),
    )
    if _is_postgres(bind):
        op.add_column(
            "documents",
            sa.Column(
                "page_offsets",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )
    else:
        op.add_column(
            "documents",
            sa.Column("page_offsets", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("documents", "page_offsets")
    op.drop_column("documents", "status")
