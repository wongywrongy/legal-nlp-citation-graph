"""
Pydantic schemas for API requests/responses (cursor/eng/api.contract.md).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentBase(BaseModel):
    title: str
    court: Optional[str] = None
    year: Optional[int] = None
    docket: Optional[str] = None


class Document(DocumentBase):
    id: str
    fingerprint: str
    source_path: Optional[str] = None
    source_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CitationBase(BaseModel):
    raw_text: str
    normalized_key: str
    reporter: Optional[str] = None
    volume: Optional[int] = None
    page: Optional[int] = None
    year: Optional[int] = None
    page_number: Optional[int] = None
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    citation_type: str = "full"
    confidence: float = 0.0
    resolution_notes: Optional[str] = None
    confidence_breakdown: Optional[Dict[str, Any]] = None


class Citation(CitationBase):
    id: str
    from_doc_id: str
    to_doc_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentsResponse(BaseModel):
    items: List[Document]
    total: int


class DocumentDetailResponse(BaseModel):
    document: Document
    citations: List[Citation]


class GraphNode(BaseModel):
    id: str
    label: str
    meta: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    confidence: float


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class IngestResponse(BaseModel):
    document_id: str
    status: str


class DocumentStatus(BaseModel):
    document_id: str
    status: str  # pending | processing | completed | failed
    citations_count: int = 0
    linked_citations: int = 0


class StatsResponse(BaseModel):
    total_documents: int
    total_citations: int
    resolved_citations: int
    unresolved_citations: int
    resolution_rate: float
    avg_confidence: float


class HealthResponse(BaseModel):
    status: str
    checks: Dict[str, str] = Field(default_factory=dict)


class APIError(BaseModel):
    code: str
    message: str
    detail: Optional[Dict[str, Any]] = None


# --- Semantic search / similarity --------------------------------------------


class SimilarDocument(BaseModel):
    doc_id: str
    title: str
    court: Optional[str] = None
    year: Optional[int] = None
    similarity_score: float


class SearchHit(BaseModel):
    doc_id: str
    title: str
    court: Optional[str] = None
    year: Optional[int] = None
    similarity_score: float
    snippet: Optional[str] = None
    # "biencoder" — only the bi-encoder ran (cross-encoder disabled or
    # candidate pool of size 1).
    # "crossencoder" — cross-encoder produced the final ordering;
    # similarity_score is the cross-encoder logit, not a cosine similarity.
    # "lexical" — title/full_text ILIKE fallback because the bi-encoder
    # was uncertain. similarity_score is 0.0 (ordering-only signal).
    scored_by: str = "biencoder"


class SearchRequest(BaseModel):
    q: str
    limit: int = Field(default=10, ge=1, le=100)
    min_similarity: float = Field(default=0.5, ge=0.0, le=1.0)


class SearchResponse(BaseModel):
    query: str
    hits: List[SearchHit]


class SimilarityEdge(BaseModel):
    source_id: str
    target_id: str
    similarity_score: float


# --- Related cases (for the inspector panel's Cites / Cited-by sections) ----


class RelatedCase(BaseModel):
    """
    Enriched view of a citation row with the related document's summary
    fields embedded. Used by /v1/documents/{id}/cites-out and
    /v1/documents/{id}/cited-by so the inspector panel can render rows
    without N+1 follow-up fetches per row.
    """

    # The Citation row id; same value as the GraphEdge.id when it appears
    # as a graph edge.
    citation_id: str
    # The related document's id (the *other* end of the citation; for
    # cites-out this is the resolved target, for cited-by it's the source).
    doc_id: str
    title: str
    court: Optional[str] = None
    year: Optional[int] = None
    confidence: float
    citation_type: str = "full"


class CitationOutgoing(BaseModel):
    """
    A polymorphic outgoing citation row that captures all three resolution
    states the inspector needs to render:

    - state="resolved": the cited work is in the corpus. `doc_id`, `title`,
      `court`, `year` are populated; the inspector renders a
      graph-clickable row.
    - state="external": CourtListener resolved the cite but the work is
      not in our corpus. `external_*` fields are populated; the inspector
      shows a "Not in corpus" pill and an external-link icon.
    - state="unresolved": neither in-corpus nor external resolution found;
      the inspector renders `raw_text` in muted italic.

    Used by /v1/documents/{id}/citations. The narrower /v1/.../cites-out
    endpoint still exists and continues to return only `state="resolved"`
    rows for backward compatibility.
    """

    citation_id: str
    raw_text: str
    citation_type: str = "full"
    confidence: float
    state: str  # "resolved" | "external" | "unresolved"

    # Populated when state == "resolved"
    doc_id: Optional[str] = None
    title: Optional[str] = None
    court: Optional[str] = None
    year: Optional[int] = None

    # Populated when state == "external"
    external_case_name: Optional[str] = None
    external_year: Optional[int] = None
    external_court: Optional[str] = None
    external_url: Optional[str] = None


# --- Track B: neighborhood graph + CourtListener entry-point shapes -------


class NeighborhoodNodeData(BaseModel):
    """One node in a neighborhood graph response.

    Distinct shape from the corpus `GraphNode` (see /v1/graph) so both
    response types can evolve independently. Track B's neighborhood
    payload pins `focal=true` on the case the user is exploring; the
    frontend reads that flag to render the focal node larger + with a
    border ring.

    `status` surfaces Track A's `documents.status` value so the graph
    page can show the "Extracting citations…" status bar without an
    extra round-trip.
    """

    id: str
    title: str
    court: Optional[str] = None
    year: Optional[int] = None
    size: int = 1
    color: Optional[str] = None
    focal: bool = False
    status: Optional[str] = None


class NeighborhoodCitationEdge(BaseModel):
    source: str
    target: str
    confidence: float
    citation_type: str = "full"


class NeighborhoodSemanticEdge(BaseModel):
    source: str
    target: str
    similarity_score: float


class NeighborhoodGraph(BaseModel):
    focal_id: str
    nodes: List[NeighborhoodNodeData]
    citation_edges: List[NeighborhoodCitationEdge]
    semantic_edges: List[NeighborhoodSemanticEdge]


class CourtListenerHit(BaseModel):
    """A single hit from `/v1/courtlistener/search`.

    Maps the relevant subset of CourtListener's /api/search/?type=o
    response so the frontend dropdown has just what it needs to render
    + ingest. `cl_id` is the cluster id the ingest endpoint uses.
    """

    cl_id: int
    case_name: str
    court: Optional[str] = None
    year: Optional[int] = None
    citation_string: Optional[str] = None
    absolute_url: str
