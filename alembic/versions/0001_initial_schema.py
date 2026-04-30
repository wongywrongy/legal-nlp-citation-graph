"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("fingerprint", sa.String(), nullable=False, unique=True),
        sa.Column("source_path", sa.String(), nullable=True),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("court", sa.String(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("docket", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_documents_court", "documents", ["court"])
    op.create_index("ix_documents_year", "documents", ["year"])

    op.create_table(
        "citations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("from_doc_id", sa.String(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("to_doc_id", sa.String(), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("normalized_key", sa.String(), nullable=False),
        sa.Column("reporter", sa.String(), nullable=True),
        sa.Column("volume", sa.Integer(), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("span_start", sa.Integer(), nullable=True),
        sa.Column("span_end", sa.Integer(), nullable=True),
        sa.Column("citation_type", sa.String(), nullable=False, server_default="full"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("confidence_breakdown", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_citations_normalized_key", "citations", ["normalized_key"])
    op.create_index("ix_citations_from_doc", "citations", ["from_doc_id"])
    op.create_index("ix_citations_to_doc", "citations", ["to_doc_id"])
    op.create_index(
        "ix_citations_resolution",
        "citations",
        ["reporter", "volume", "page"],
    )


def downgrade() -> None:
    op.drop_index("ix_citations_resolution", table_name="citations")
    op.drop_index("ix_citations_to_doc", table_name="citations")
    op.drop_index("ix_citations_from_doc", table_name="citations")
    op.drop_index("ix_citations_normalized_key", table_name="citations")
    op.drop_table("citations")
    op.drop_index("ix_documents_year", table_name="documents")
    op.drop_index("ix_documents_court", table_name="documents")
    op.drop_table("documents")
