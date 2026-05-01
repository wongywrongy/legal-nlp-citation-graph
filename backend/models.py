"""
Data models following cursor/eng/data.models.md specification.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - pgvector optional in some envs
    Vector = None  # type: ignore

Base = declarative_base()


# pgvector on postgres; LargeBinary on sqlite (test-only fallback so the
# schema can be created in conftest's temp DB without the extension).
if Vector is not None:
    EMBEDDING_TYPE = Vector(768).with_variant(LargeBinary(), "sqlite")
else:  # pragma: no cover
    EMBEDDING_TYPE = LargeBinary()


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    fingerprint = Column(String, nullable=False, unique=True)
    source_path = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    court = Column(String, nullable=True, index=True)
    year = Column(Integer, nullable=True, index=True)
    docket = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Phase 3: full extracted text + embedding for semantic search.
    full_text = Column(Text, nullable=True)
    embedding = Column(EMBEDDING_TYPE, nullable=True)
    embedded_at = Column(DateTime, nullable=True)

    # Track A — explicit failure flag for the extraction pipeline.
    # NULL = healthy (derive processing/completed from embedded_at).
    # 'extraction_failed' = pdf_processor produced <500 chars of body
    # text; the worker chain skips embedding + enrichment.
    # Future failure modes can land additional values here.
    status = Column(String, nullable=True)

    # Track A — per-page char offsets into `full_text`. Populated by
    # pdf_processor when it stitches PyMuPDF4LLM page chunks together.
    # Shape: [{"page": int, "start": int, "end": int}, ...]
    page_offsets = Column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
    )

    citations_from = relationship(
        "Citation",
        foreign_keys="Citation.from_doc_id",
        back_populates="from_document",
    )
    citations_to = relationship(
        "Citation",
        foreign_keys="Citation.to_doc_id",
        back_populates="to_document",
    )


class Citation(Base):
    __tablename__ = "citations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    from_doc_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    to_doc_id = Column(String, ForeignKey("documents.id"), nullable=True, index=True)

    raw_text = Column(Text, nullable=False)
    normalized_key = Column(String, nullable=False, index=True)

    reporter = Column(String, nullable=True)
    volume = Column(Integer, nullable=True)
    page = Column(Integer, nullable=True)
    year = Column(Integer, nullable=True)

    page_number = Column(Integer, nullable=True)
    span_start = Column(Integer, nullable=True)
    span_end = Column(Integer, nullable=True)

    citation_type = Column(String, nullable=False, default="full")
    confidence = Column(Float, nullable=False, default=0.0)
    resolution_notes = Column(Text, nullable=True)
    confidence_breakdown = Column(JSON, nullable=True)

    # CourtListener-resolved metadata for citations that didn't match an
    # in-corpus document (to_doc_id null) but did resolve via the external
    # enrichment lookup. Shape: {case_name, year, absolute_url, court}.
    # JSONB on postgres for forward-compat (GIN indexing if we ever need
    # it); JSON on sqlite via with_variant for the test schema.
    external_resolution = Column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow)

    from_document = relationship(
        "Document",
        foreign_keys=[from_doc_id],
        back_populates="citations_from",
    )
    to_document = relationship(
        "Document",
        foreign_keys=[to_doc_id],
        back_populates="citations_to",
    )


Index("ix_citations_resolution", Citation.reporter, Citation.volume, Citation.page)


class SemanticSimilarity(Base):
    """
    Pre-computed top-k semantic neighbors per document.

    Populated by the embed_document_job worker; consumed by /api/similar/{id}.
    Rows are written symmetrically (source→target and target→source) so a
    lookup keyed on `source_id` returns the full neighborhood without joins.
    """

    __tablename__ = "semantic_similarity"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id = Column(
        String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_id = Column(
        String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    similarity_score = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("source_id", "target_id", name="uq_semantic_pair"),
        CheckConstraint("source_id <> target_id", name="ck_semantic_self"),
        CheckConstraint(
            "similarity_score >= 0 AND similarity_score <= 1",
            name="ck_semantic_score_range",
        ),
        Index(
            "ix_semantic_source_score",
            "source_id",
            "similarity_score",
        ),
    )
