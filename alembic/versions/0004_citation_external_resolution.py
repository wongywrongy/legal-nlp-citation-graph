"""citations.external_resolution JSONB

Revision ID: 0004_external_resolution
Revises: 0003_hnsw
Create Date: 2026-04-29

Notes:
- Adds a single nullable JSONB column on `citations` to hold metadata for
  citations that didn't resolve to an in-corpus document but DID resolve to
  a CourtListener record (case_name, year, absolute_url, etc.).
- Inspector renders citations in three states:
    1. resolved      → to_doc_id is set, link inside the graph
    2. external      → to_doc_id null, external_resolution non-null;
                       show "Not in corpus" pill + external link icon
    3. fully unresolved → both null; render raw_text in muted italic
- Sqlite test fallback: JSONB → JSON. SQLAlchemy's `JSON` type stays
  portable; the actual JSONB Postgres benefits (GIN indexing) aren't
  required here because lookups are always keyed on citation id.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0004_external_resolution"
down_revision: Union[str, None] = "0003_hnsw"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgres(bind) -> bool:
    return bind.dialect.name == "postgresql"


def upgrade() -> None:
    bind = op.get_bind()
    if _is_postgres(bind):
        op.add_column(
            "citations",
            sa.Column(
                "external_resolution",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )
    else:
        # sqlite fallback for the unit-test schema build.
        op.add_column(
            "citations",
            sa.Column("external_resolution", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("citations", "external_resolution")
