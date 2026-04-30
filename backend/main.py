"""
FastAPI application — async routes backed by AsyncSession, ARQ-driven
background processing, and a citation graph endpoint with centrality.

Endpoints follow cursor/eng/api.contract.md plus a few additions:
    POST /v1/ingest                — multipart upload, enqueues processing
    GET  /v1/documents/{id}/status — poll processing status
    GET  /v1/stats                 — aggregate metrics
    GET  /v1/graph                 — centrality + court/year filters
"""
import hashlib
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import networkx as nx
import structlog
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import AsyncSessionLocal, get_async_db
from backend.exceptions import (
    BadInputError,
    DuplicateError,
    NotFoundError,
    register_exception_handlers,
)
from backend.models import Citation as CitationModel
from backend.models import Document as DocumentModel
from backend.models import SemanticSimilarity
from backend.schemas import (
    Citation,
    CitationOutgoing,
    Document,
    DocumentDetailResponse,
    DocumentsResponse,
    DocumentStatus,
    GraphEdge,
    GraphNode,
    GraphResponse,
    HealthResponse,
    IngestResponse,
    RelatedCase,
    SearchHit,
    SearchRequest,
    SearchResponse,
    SimilarDocument,
    SimilarityEdge,
    StatsResponse,
)

logger = structlog.get_logger()


# --- Optional rate limiter (slowapi) -----------------------------------------

try:
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    limiter: Optional["Limiter"] = Limiter(key_func=get_remote_address)
except ImportError:  # pragma: no cover
    limiter = None
    RateLimitExceeded = None  # type: ignore


# --- Lifespan + app ----------------------------------------------------------


_redis_pool = None


async def _get_redis():
    global _redis_pool
    if _redis_pool is None:
        from arq import create_pool
        from arq.connections import RedisSettings

        _redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _redis_pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Bootstrap data dir
    os.makedirs(settings.pdf_storage_path, exist_ok=True)
    logger.info("API startup", pdf_path=settings.pdf_storage_path)
    yield
    global _redis_pool
    if _redis_pool is not None:
        try:
            await _redis_pool.close()
        except Exception:
            pass


app = FastAPI(
    title="Legal Citation Graph API",
    description="AI-assisted legal citation graph using eyecite",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

if limiter is not None:
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(_request, exc):  # pragma: no cover
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=429,
            content={"code": "rate_limited", "message": str(exc), "detail": None},
        )


# --- Health ------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
async def health_check():
    checks: dict[str, str] = {}
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        logger.warning("Health check: database failed", error=str(e))
        checks["database"] = "error"

    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await pool.ping()
        await pool.close()
        checks["redis"] = "ok"
    except Exception as e:
        logger.warning("Health check: redis failed", error=str(e))
        checks["redis"] = "error"

    status = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    return HealthResponse(status=status, checks=checks)


# --- Documents ---------------------------------------------------------------


@app.get("/v1/documents", response_model=DocumentsResponse)
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
):
    rows = await db.execute(select(DocumentModel).offset(skip).limit(limit))
    documents = rows.scalars().all()
    total = (await db.execute(select(func.count(DocumentModel.id)))).scalar_one()
    return DocumentsResponse(
        items=[Document.model_validate(d) for d in documents],
        total=total,
    )


@app.get("/v1/documents/{doc_id}", response_model=DocumentDetailResponse)
async def get_document_detail(doc_id: str, db: AsyncSession = Depends(get_async_db)):
    row = await db.execute(select(DocumentModel).where(DocumentModel.id == doc_id))
    document = row.scalar_one_or_none()
    if document is None:
        raise NotFoundError("Document not found", {"document_id": doc_id})

    citations_rows = await db.execute(
        select(CitationModel).where(CitationModel.from_doc_id == doc_id)
    )
    citations = citations_rows.scalars().all()

    return DocumentDetailResponse(
        document=Document.model_validate(document),
        citations=[Citation.model_validate(c) for c in citations],
    )


@app.get("/v1/documents/{doc_id}/pdf")
async def get_document_pdf(doc_id: str, db: AsyncSession = Depends(get_async_db)):
    row = await db.execute(select(DocumentModel).where(DocumentModel.id == doc_id))
    document = row.scalar_one_or_none()
    if document is None or not document.source_path:
        raise NotFoundError("PDF not found")
    if not os.path.exists(document.source_path):
        raise NotFoundError("PDF file missing on disk")

    def iter_file(path: str):
        with open(path, "rb") as fh:
            yield from fh

    filename = os.path.basename(document.source_path)
    return StreamingResponse(
        iter_file(document.source_path),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )


@app.get("/v1/documents/{doc_id}/status", response_model=DocumentStatus)
async def get_document_status(doc_id: str, db: AsyncSession = Depends(get_async_db)):
    row = await db.execute(select(DocumentModel).where(DocumentModel.id == doc_id))
    document = row.scalar_one_or_none()
    if document is None:
        raise NotFoundError("Document not found", {"document_id": doc_id})

    total = (
        await db.execute(
            select(func.count(CitationModel.id)).where(
                CitationModel.from_doc_id == doc_id
            )
        )
    ).scalar_one()
    linked = (
        await db.execute(
            select(func.count(CitationModel.id)).where(
                CitationModel.from_doc_id == doc_id,
                CitationModel.to_doc_id.isnot(None),
            )
        )
    ).scalar_one()

    if total == 0:
        status_value = "processing"
    else:
        status_value = "completed"

    return DocumentStatus(
        document_id=doc_id,
        status=status_value,
        citations_count=total,
        linked_citations=linked,
    )


@app.get("/v1/documents/{doc_id}/full-text")
async def get_document_full_text(
    doc_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Return the document's extracted body text. Used by the inspector's
    "View full text" sheet so users can read the opinion without leaving
    the graph + inspector flow. Kept on a separate route to avoid
    bloating /v1/documents/{id} with a potentially large field.
    """
    row = await db.execute(
        select(DocumentModel).where(DocumentModel.id == doc_id)
    )
    document = row.scalar_one_or_none()
    if document is None:
        raise NotFoundError("Document not found", {"document_id": doc_id})
    return {
        "document_id": document.id,
        "title": document.title,
        "full_text": document.full_text or "",
    }


@app.get("/v1/documents/{doc_id}/summary")
async def get_document_summary(
    doc_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Return a short snippet of the document's body text suitable for the
    inspector's Summary section. We deliberately keep this on a separate
    route (rather than baking full_text into the existing
    /v1/documents/{id} shape) so existing clients see no schema change.
    """
    row = await db.execute(
        select(DocumentModel.id, DocumentModel.full_text, DocumentModel.title)
        .where(DocumentModel.id == doc_id)
    )
    record = row.first()
    if record is None:
        raise NotFoundError("Document not found", {"document_id": doc_id})

    _, full_text, title = record
    cleaned = " ".join((full_text or "").split())
    # First ~480 chars is roughly 3-4 sentences for typical legal prose.
    snippet = cleaned[:480]
    if len(cleaned) > 480:
        snippet = snippet.rstrip(",.;:") + "…"
    return {"document_id": doc_id, "title": title, "snippet": snippet}


@app.get(
    "/v1/documents/{doc_id}/cites-out",
    response_model=list[RelatedCase],
)
async def get_document_cites_out(
    doc_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Citations going OUT from this document, joined to the resolved target's
    summary fields. Returned ordered by confidence DESC so the inspector can
    show the strongest links first. Pagination via offset/limit lets the
    frontend lazy-load the long tail.
    """
    src_row = await db.execute(select(DocumentModel).where(DocumentModel.id == doc_id))
    if src_row.scalar_one_or_none() is None:
        raise NotFoundError("Document not found", {"document_id": doc_id})

    rows = await db.execute(
        select(CitationModel, DocumentModel)
        .join(DocumentModel, DocumentModel.id == CitationModel.to_doc_id)
        .where(
            CitationModel.from_doc_id == doc_id,
            CitationModel.to_doc_id.isnot(None),
        )
        .order_by(CitationModel.confidence.desc())
        .offset(offset)
        .limit(limit)
    )
    return [
        RelatedCase(
            citation_id=cite.id,
            doc_id=target.id,
            title=target.title,
            court=target.court,
            year=target.year,
            confidence=cite.confidence,
            citation_type=cite.citation_type,
        )
        for cite, target in rows.all()
    ]


@app.get(
    "/v1/documents/{doc_id}/citations",
    response_model=list[CitationOutgoing],
)
async def get_document_all_citations(
    doc_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_db),
):
    """
    All outgoing citations from this document in three states:

    - resolved: cited work is in the corpus (clickable in the graph).
    - external: CourtListener resolved the cite but the work isn't in the
      corpus — the row gets a "Not in corpus" pill and an external link.
    - unresolved: neither path produced a hit; rendered as muted raw_text.

    This endpoint complements the narrower `/cites-out` (which only returns
    resolved rows) by giving the inspector the data it needs to render
    every citation a document makes, with state-aware affordances.
    """
    src_row = await db.execute(select(DocumentModel).where(DocumentModel.id == doc_id))
    if src_row.scalar_one_or_none() is None:
        raise NotFoundError("Document not found", {"document_id": doc_id})

    # Outer join so we keep citations whose to_doc_id is null. Order by
    # confidence DESC then state so resolved rows surface above external,
    # external above unresolved (we approximate this by sorting on a
    # case expression).
    state_rank = case(
        (CitationModel.to_doc_id.isnot(None), 0),
        (CitationModel.external_resolution.isnot(None), 1),
        else_=2,
    )
    rows = await db.execute(
        select(CitationModel, DocumentModel)
        .outerjoin(DocumentModel, DocumentModel.id == CitationModel.to_doc_id)
        .where(CitationModel.from_doc_id == doc_id)
        .order_by(state_rank.asc(), CitationModel.confidence.desc())
        .offset(offset)
        .limit(limit)
    )

    out: list[CitationOutgoing] = []
    for cite, target in rows.all():
        if target is not None:
            out.append(
                CitationOutgoing(
                    citation_id=cite.id,
                    raw_text=cite.raw_text,
                    citation_type=cite.citation_type,
                    confidence=cite.confidence,
                    state="resolved",
                    doc_id=target.id,
                    title=target.title,
                    court=target.court,
                    year=target.year,
                )
            )
            continue

        ext = cite.external_resolution or {}
        if ext:
            out.append(
                CitationOutgoing(
                    citation_id=cite.id,
                    raw_text=cite.raw_text,
                    citation_type=cite.citation_type,
                    confidence=cite.confidence,
                    state="external",
                    external_case_name=ext.get("case_name"),
                    external_year=ext.get("year"),
                    external_court=ext.get("court"),
                    external_url=ext.get("absolute_url"),
                )
            )
            continue

        out.append(
            CitationOutgoing(
                citation_id=cite.id,
                raw_text=cite.raw_text,
                citation_type=cite.citation_type,
                confidence=cite.confidence,
                state="unresolved",
            )
        )
    return out


@app.get(
    "/v1/documents/{doc_id}/cited-by",
    response_model=list[RelatedCase],
)
async def get_document_cited_by(
    doc_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Reverse citations: every citation row whose target is this document,
    joined to the source's summary fields so the inspector panel can render
    "Cited by" rows in one round-trip.
    """
    target_row = await db.execute(select(DocumentModel).where(DocumentModel.id == doc_id))
    if target_row.scalar_one_or_none() is None:
        raise NotFoundError("Document not found", {"document_id": doc_id})

    rows = await db.execute(
        select(CitationModel, DocumentModel)
        .join(DocumentModel, DocumentModel.id == CitationModel.from_doc_id)
        .where(CitationModel.to_doc_id == doc_id)
        .order_by(CitationModel.confidence.desc())
        .offset(offset)
        .limit(limit)
    )
    return [
        RelatedCase(
            citation_id=cite.id,
            doc_id=source.id,
            title=source.title,
            court=source.court,
            year=source.year,
            confidence=cite.confidence,
            citation_type=cite.citation_type,
        )
        for cite, source in rows.all()
    ]


# --- Ingest + processing -----------------------------------------------------


_INGEST_RATE_LIMIT = "10/minute"


async def _ingest_pdf_impl(file: UploadFile, db: AsyncSession) -> IngestResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise BadInputError("Only PDF files are accepted")

    content = await file.read()
    if not content:
        raise BadInputError("Uploaded file is empty")

    fingerprint = hashlib.sha256(content).hexdigest()

    existing_row = await db.execute(
        select(DocumentModel).where(DocumentModel.fingerprint == fingerprint)
    )
    existing = existing_row.scalar_one_or_none()
    if existing is not None:
        raise DuplicateError(
            "Document already ingested",
            {"document_id": existing.id, "fingerprint": fingerprint},
        )

    os.makedirs(settings.pdf_storage_path, exist_ok=True)
    safe_name = os.path.basename(file.filename)
    dest_path = os.path.join(settings.pdf_storage_path, f"{fingerprint[:12]}_{safe_name}")
    with open(dest_path, "wb") as fh:
        fh.write(content)

    document = DocumentModel(
        title=safe_name.replace(".pdf", ""),
        fingerprint=fingerprint,
        source_path=dest_path,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    try:
        redis = await _get_redis()
        await redis.enqueue_job("process_pdf_job", document.id)
        status_value = "queued"
    except Exception as e:
        logger.warning(
            "Failed to enqueue processing job", doc_id=document.id, error=str(e)
        )
        status_value = "queued_failed"

    return IngestResponse(document_id=document.id, status=status_value)


if limiter is not None:

    @app.post("/v1/ingest", response_model=IngestResponse)
    @limiter.limit(_INGEST_RATE_LIMIT)
    async def ingest_pdf(
        request: Request,  # noqa: ARG001  required by slowapi
        file: UploadFile = File(...),
        db: AsyncSession = Depends(get_async_db),
    ):
        return await _ingest_pdf_impl(file, db)

else:

    @app.post("/v1/ingest", response_model=IngestResponse)
    async def ingest_pdf(
        file: UploadFile = File(...),
        db: AsyncSession = Depends(get_async_db),
    ):
        return await _ingest_pdf_impl(file, db)


@app.post("/v1/process")
async def process_all_documents():
    try:
        redis = await _get_redis()
        job = await redis.enqueue_job("process_all_job")
        return {"status": "queued", "job_id": getattr(job, "job_id", None)}
    except Exception as e:
        logger.error("Failed to enqueue batch process", error=str(e))
        raise HTTPException(status_code=503, detail=f"Queue unavailable: {e}")


@app.post("/v1/process/{doc_id}")
async def process_single_document(doc_id: str, db: AsyncSession = Depends(get_async_db)):
    row = await db.execute(select(DocumentModel).where(DocumentModel.id == doc_id))
    if row.scalar_one_or_none() is None:
        raise NotFoundError("Document not found", {"document_id": doc_id})

    try:
        redis = await _get_redis()
        job = await redis.enqueue_job("process_pdf_job", doc_id)
        return {"status": "queued", "job_id": getattr(job, "job_id", None)}
    except Exception as e:
        logger.error("Failed to enqueue job", doc_id=doc_id, error=str(e))
        raise HTTPException(status_code=503, detail=f"Queue unavailable: {e}")


# --- Graph -------------------------------------------------------------------


@app.get("/v1/graph", response_model=GraphResponse)
async def get_citation_graph(
    min_confidence: float = Query(
        default=settings.min_confidence_default, ge=0.0, le=1.0
    ),
    court: Optional[str] = Query(default=None),
    year_min: Optional[int] = Query(default=None),
    year_max: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
):
    doc_q = select(DocumentModel)
    if court:
        doc_q = doc_q.where(DocumentModel.court == court)
    if year_min is not None:
        doc_q = doc_q.where(DocumentModel.year >= year_min)
    if year_max is not None:
        doc_q = doc_q.where(DocumentModel.year <= year_max)

    docs = (await db.execute(doc_q)).scalars().all()
    doc_ids = {d.id for d in docs}

    edge_q = select(CitationModel).where(
        CitationModel.confidence >= min_confidence,
        CitationModel.to_doc_id.isnot(None),
    )
    citations = (await db.execute(edge_q)).scalars().all()
    citations = [
        c for c in citations if c.from_doc_id in doc_ids and c.to_doc_id in doc_ids
    ]

    graph = nx.DiGraph()
    for d in docs:
        graph.add_node(d.id)
    for c in citations:
        graph.add_edge(c.from_doc_id, c.to_doc_id, weight=c.confidence)

    centrality = nx.in_degree_centrality(graph) if graph.number_of_nodes() else {}

    nodes = [
        GraphNode(
            id=d.id,
            label=d.title,
            meta={
                "court": d.court,
                "year": d.year,
                "docket": d.docket,
                "centrality": round(centrality.get(d.id, 0.0), 4),
            },
        )
        for d in docs
    ]
    edges = [
        GraphEdge(
            id=c.id,
            source=c.from_doc_id,
            target=c.to_doc_id,
            confidence=c.confidence,
        )
        for c in citations
    ]
    return GraphResponse(nodes=nodes, edges=edges)


# --- Stats -------------------------------------------------------------------


@app.get("/v1/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_async_db)):
    total_documents = (
        await db.execute(select(func.count(DocumentModel.id)))
    ).scalar_one()
    total_citations = (
        await db.execute(select(func.count(CitationModel.id)))
    ).scalar_one()
    resolved = (
        await db.execute(
            select(func.count(CitationModel.id)).where(
                CitationModel.to_doc_id.isnot(None)
            )
        )
    ).scalar_one()
    unresolved = total_citations - resolved
    avg_confidence = (
        await db.execute(select(func.coalesce(func.avg(CitationModel.confidence), 0.0)))
    ).scalar_one()
    rate = (resolved / total_citations) if total_citations else 0.0

    return StatsResponse(
        total_documents=total_documents,
        total_citations=total_citations,
        resolved_citations=resolved,
        unresolved_citations=unresolved,
        resolution_rate=round(rate, 4),
        avg_confidence=round(float(avg_confidence or 0.0), 4),
    )


# --- Semantic similarity / search (/api prefix) ------------------------------


def _snippet(text: Optional[str], length: int = 240) -> Optional[str]:
    if not text:
        return None
    cleaned = " ".join(text.split())
    return cleaned[:length] + ("…" if len(cleaned) > length else "")


@app.get("/api/similar/{doc_id}", response_model=list[SimilarDocument])
async def get_similar_documents(
    doc_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    min_similarity: float = Query(default=0.0, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_async_db),
):
    src_row = await db.execute(select(DocumentModel).where(DocumentModel.id == doc_id))
    if src_row.scalar_one_or_none() is None:
        raise NotFoundError("Document not found", {"document_id": doc_id})

    rows = await db.execute(
        select(SemanticSimilarity, DocumentModel)
        .join(DocumentModel, DocumentModel.id == SemanticSimilarity.target_id)
        .where(
            SemanticSimilarity.source_id == doc_id,
            SemanticSimilarity.similarity_score >= min_similarity,
        )
        .order_by(SemanticSimilarity.similarity_score.desc())
        .limit(limit)
    )
    return [
        SimilarDocument(
            doc_id=document.id,
            title=document.title,
            court=document.court,
            year=document.year,
            similarity_score=edge.similarity_score,
        )
        for edge, document in rows.all()
    ]


# Threshold below which the bi-encoder is considered "uncertain" and the
# lexical fallback takes over. Cosine similarity for normalized mpnet
# embeddings on a confident match typically lands above 0.55; proper-noun
# queries like "Riley" or "Miranda" embed poorly and stay <0.4 even when
# the document title literally contains the term — that's exactly the
# case lexical search rescues.
_LEXICAL_FALLBACK_THRESHOLD = 0.5


async def _lexical_search(
    db: AsyncSession, q: str, limit: int
) -> list[SearchHit]:
    """ILIKE fallback when the bi-encoder is uncertain or unavailable.

    Matches against `title` and `full_text`. Title hits are surfaced first
    via a CASE expression so a query that literally appears in a title
    doesn't get buried under longer documents that mention it once.
    """
    stripped = q.strip()
    if not stripped:
        return []

    # Defang LIKE wildcards in the user's query so "100%" doesn't match
    # everything. Backslash is the SQL ESCAPE character we register below.
    escaped = (
        stripped.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    pattern = f"%{escaped}%"

    title_match = case(
        (DocumentModel.title.ilike(pattern, escape="\\"), 1),
        else_=0,
    )

    stmt = (
        select(DocumentModel)
        .where(
            or_(
                DocumentModel.title.ilike(pattern, escape="\\"),
                DocumentModel.full_text.ilike(pattern, escape="\\"),
            )
        )
        .order_by(title_match.desc(), DocumentModel.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        SearchHit(
            doc_id=doc.id,
            title=doc.title,
            court=doc.court,
            year=doc.year,
            # Lexical hits don't have a meaningful similarity in [0,1] —
            # report 0 so the client treats them as ordering-only signals
            # and the badge ("Title match") tells the user what happened.
            similarity_score=0.0,
            snippet=_snippet(doc.full_text),
            scored_by="lexical",
        )
        for doc in rows
    ]


@app.post("/api/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    response: Response,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Three-stage hybrid search:

    1. Bi-encoder retrieves a candidate pool of `search_candidate_pool` docs
       (default 20) ranked by cosine similarity to the embedded query.
    2. If `feature_cross_encoder` is on, the cross-encoder scores each
       (query, snippet) pair and re-ranks. Final results are truncated to
       `request.limit`.
    3. Lexical fallback (ILIKE on title + full_text) when the bi-encoder
       returns nothing or every candidate scored below the fallback
       threshold — covers proper-noun and short-token queries that embed
       poorly ("Riley", "Miranda", a docket number).

    The response includes an `X-Search-Mode` header ("biencoder",
    "crossencoder", or "lexical") so the client can label which path
    produced the ordering.
    """
    response.headers["X-Search-Mode"] = "biencoder"

    # Local imports — keeps both models lazy so non-search routes don't pay
    # the load cost on import.
    candidates: list = []
    embeddings_available = (
        settings.feature_embeddings
        and settings.database_url_sync.startswith("postgresql")
    )

    if embeddings_available:
        from backend.embeddings import (
            cross_encoder_score,
            embed_text,
            top_k_for_query,
        )

        vec = embed_text(request.q)
        if vec:
            # Stage 1: bi-encoder retrieval — over-fetch so the
            # cross-encoder has a meaningful pool to re-rank.
            pool_size = max(request.limit, settings.search_candidate_pool)
            candidates = await top_k_for_query(
                db, vec, k=pool_size, min_score=request.min_similarity
            )

    # Decide whether the embedding path is "good enough". Trigger lexical
    # fallback when (a) embeddings disabled / no vector, (b) bi-encoder
    # returned zero candidates, or (c) every candidate's cosine is below
    # the fallback threshold.
    bi_uncertain = not candidates or all(
        score < _LEXICAL_FALLBACK_THRESHOLD for _doc, score in candidates
    )

    if bi_uncertain:
        lexical_hits = await _lexical_search(db, request.q, request.limit)
        if lexical_hits:
            response.headers["X-Search-Mode"] = "lexical"
            return SearchResponse(query=request.q, hits=lexical_hits)
        # Lexical also empty: fall through with whatever (possibly empty)
        # candidates we have so the user sees the closest semantic guesses
        # rather than a flat "no results".

    if not candidates:
        return SearchResponse(query=request.q, hits=[])

    # Stage 2: optional cross-encoder re-rank.
    if (
        embeddings_available
        and settings.feature_cross_encoder
        and len(candidates) > 1
    ):
        snippets = [_snippet(doc.full_text, length=512) or doc.title for doc, _ in candidates]
        try:
            ce_scores = cross_encoder_score(request.q, snippets)
        except Exception as e:
            logger.warning("cross-encoder failed; falling back to biencoder", error=str(e))
            ce_scores = []

        if ce_scores:
            ranked = sorted(
                zip(candidates, ce_scores),
                key=lambda pair: pair[1],
                reverse=True,
            )[: request.limit]
            response.headers["X-Search-Mode"] = "crossencoder"
            hits = [
                SearchHit(
                    doc_id=doc.id,
                    title=doc.title,
                    court=doc.court,
                    year=doc.year,
                    similarity_score=float(ce_score),
                    snippet=_snippet(doc.full_text),
                    scored_by="crossencoder",
                )
                for ((doc, _bi_score), ce_score) in ranked
            ]
            return SearchResponse(query=request.q, hits=hits)

    hits = [
        SearchHit(
            doc_id=document.id,
            title=document.title,
            court=document.court,
            year=document.year,
            similarity_score=score,
            snippet=_snippet(document.full_text),
            scored_by="biencoder",
        )
        for document, score in candidates[: request.limit]
    ]
    return SearchResponse(query=request.q, hits=hits)


@app.get("/api/similar-edges", response_model=list[SimilarityEdge])
async def get_similar_edges(
    min_similarity: float = Query(default=0.75, ge=0.0, le=1.0),
    limit: int = Query(default=2000, ge=1, le=20000),
    db: AsyncSession = Depends(get_async_db),
):
    """
    All semantic similarity edges above a threshold, for the graph renderer.
    Returns each pair once (lexicographically smaller id first) so the
    frontend doesn't double-count symmetric duplicates.
    """
    rows = await db.execute(
        select(SemanticSimilarity)
        .where(
            SemanticSimilarity.similarity_score >= min_similarity,
            SemanticSimilarity.source_id < SemanticSimilarity.target_id,
        )
        .order_by(SemanticSimilarity.similarity_score.desc())
        .limit(limit)
    )
    return [
        SimilarityEdge(
            source_id=edge.source_id,
            target_id=edge.target_id,
            similarity_score=edge.similarity_score,
        )
        for edge in rows.scalars().all()
    ]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.api_port)
