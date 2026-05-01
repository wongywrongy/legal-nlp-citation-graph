"""
CourtListener API client.

Used both for FEATURE_EXTERNAL_ENRICHMENT (backfilling court/docket/year on
ingested documents) and for the seed script in `scripts/seed.py`. The
list_opinions() helper is unrelated to the enrichment feature flag — the
seed script gates itself.

API docs: https://www.courtlistener.com/api/rest/v3/
"""
from __future__ import annotations

import asyncio
from typing import Iterable, List, Optional

import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger()

BASE_URL = "https://www.courtlistener.com/api/rest/v4"


def _auth_headers() -> dict:
    headers = {"Accept": "application/json"}
    if settings.courtlistener_api_key:
        headers["Authorization"] = f"Token {settings.courtlistener_api_key}"
    return headers


async def list_opinions(
    court: str = "scotus",
    page_size: int = 20,
    order_by: str = "-id",
    max_results: int = 50,
    topic: Optional[str] = None,
    after_date: Optional[str] = None,
    before_date: Optional[str] = None,
) -> List[dict]:
    """
    List opinions filtered by court, optionally restricted to a free-text
    topic and a minimum filing date. Walks pages until `max_results` is hit.

    Args:
        court: CourtListener court slug (e.g. "scotus", "ca9", "ca2").
        page_size: items per page (CourtListener caps at 20 for anonymous,
            higher with an API key — keep <= 20 to be safe).
        order_by: CourtListener v4 uses `order_by` (NOT `ordering` — that
            name is rejected as an unknown filter). Prefix with `-` for
            descending. `-id` gives newest-ingested first.
        max_results: cap on the total number of opinions returned.
        topic: optional free-text query (CourtListener's `q` parameter
            performs full-text search across plain_text).
        after_date: optional ISO date string ("YYYY-MM-DD"); restricts to
            cluster.date_filed >= this date.
        before_date: optional ISO date string ("YYYY-MM-DD"); restricts to
            cluster.date_filed <= this date. Combined with `after_date`,
            this lets the historical-spread seed walk one decade at a time.

    Returns the raw opinion records — callers pull `plain_text`,
    `download_url`, `cluster` etc. as needed. 429 responses trigger a 30s
    backoff and retry. Network errors break the loop and return what was
    fetched so far.

    Reference: https://www.courtlistener.com/help/api/rest/ (v4).
    """
    params: List[tuple[str, str]] = [
        ("cluster__docket__court", court),
        ("order_by", order_by),
        ("page_size", str(page_size)),
    ]
    if topic:
        params.append(("q", topic))
    if after_date:
        params.append(("cluster__date_filed__gte", after_date))
    if before_date:
        params.append(("cluster__date_filed__lte", before_date))

    # httpx.QueryParams handles percent-encoding (spaces in topics, etc.).
    # We pass it as the `params` arg of the first request so encoding is
    # applied; subsequent pages use the server-supplied `next` URL verbatim.
    out: List[dict] = []
    url: Optional[str] = f"{BASE_URL}/opinions/"
    next_params: Optional[httpx.QueryParams] = httpx.QueryParams(params)

    async with httpx.AsyncClient(timeout=30.0, headers=_auth_headers()) as client:
        while url and len(out) < max_results:
            try:
                # First request uses the params dict (httpx encodes); after
                # the first page we use the server's `next` URL which already
                # contains all encoded params, so next_params=None.
                resp = await client.get(url, params=next_params)
            except httpx.RequestError as e:
                logger.warning("CourtListener list error", error=str(e))
                break

            if resp.status_code == 429:
                logger.warning("CourtListener rate-limited; backing off 30s")
                await asyncio.sleep(30)
                continue
            if resp.status_code != 200:
                logger.warning(
                    "CourtListener list failed",
                    status=resp.status_code,
                    body=resp.text[:200],
                )
                break

            payload = resp.json()
            for record in payload.get("results", []):
                out.append(record)
                if len(out) >= max_results:
                    break
            url = payload.get("next") if len(out) < max_results else None
            next_params = None  # follow next-page URL verbatim
    return out


async def fetch_cluster(url: str) -> Optional[dict]:
    """Fetch a cluster record by URL (returned in opinion.cluster)."""
    async with httpx.AsyncClient(timeout=30.0, headers=_auth_headers()) as client:
        try:
            resp = await client.get(url)
        except httpx.RequestError as e:
            logger.warning("CourtListener cluster error", error=str(e))
            return None
    if resp.status_code != 200:
        return None
    return resp.json()


async def search_cases(query: str, limit: int = 8) -> List[dict]:
    """Free-text case lookup against CourtListener's search endpoint.

    Used by /v1/courtlistener/search to power the entry-point search
    bar. CourtListener's /api/rest/v4/search/ endpoint already ranks by
    relevance, so we just take the top `limit` and map the relevant
    fields out. Anonymous queries are heavily rate-limited; setting
    `COURTLISTENER_API_KEY` in `.env` raises the cap. The frontend's
    400 ms debounce + `limit=8` keeps each lookup well under the
    anonymous quota in practice.

    Returns a list of dicts with the shape:
      cl_id, case_name, court, year, citation_string, absolute_url
    Empty list on failure (network error, rate limit, no results) —
    callers should surface "no results" rather than raise.
    """
    query = (query or "").strip()
    if not query:
        return []

    url = f"{BASE_URL}/search/"
    params = {"q": query, "type": "o"}

    async with httpx.AsyncClient(timeout=15.0, headers=_auth_headers()) as client:
        try:
            resp = await client.get(url, params=params)
        except httpx.RequestError as e:
            logger.warning("CourtListener search error", error=str(e), q=query)
            return []

    if resp.status_code != 200:
        logger.warning(
            "CourtListener search non-200",
            status=resp.status_code,
            q=query,
            body=resp.text[:200],
        )
        return []

    payload = resp.json()
    raw_results = payload.get("results") or []
    out: List[dict] = []
    for hit in raw_results[:limit]:
        # CourtListener v4 nests cluster fields directly on the hit.
        # `cluster_id` is the canonical cluster id we use for ingest.
        # Some hits return citation as a list ("citation" array of
        # strings) — pick the first or stitch a "vol reporter page"
        # tuple from the hit's volume/reporter/page if present.
        cluster_id = hit.get("cluster_id")
        if cluster_id is None:
            continue
        case_name = hit.get("caseName") or hit.get("case_name") or ""
        if not case_name:
            continue

        # Year extraction: prefer dateFiled, fall back to dateArgued.
        year_val: Optional[int] = None
        for k in ("dateFiled", "dateArgued"):
            d = hit.get(k)
            if d:
                try:
                    year_val = int(str(d)[:4])
                    break
                except ValueError:
                    pass

        # Citation string: CL returns `citation` as a list of strings
        # for matched citations; pick the first.
        citation_string: Optional[str] = None
        cites = hit.get("citation")
        if isinstance(cites, list) and cites:
            citation_string = str(cites[0])
        elif isinstance(cites, str):
            citation_string = cites

        out.append(
            {
                "cl_id": int(cluster_id),
                "case_name": case_name,
                "court": hit.get("court") or hit.get("court_id"),
                "year": year_val,
                "citation_string": citation_string,
                "absolute_url": hit.get("absolute_url") or "",
            }
        )
    return out


def synthesize_pdf(path: str, title: str, body: str) -> None:
    """Render plain text to a multi-page PDF for the existing pipeline.

    Extracted from `scripts/seed.py::_build_pdf` so the
    `/v1/courtlistener/ingest/{cl_id}` endpoint can reuse it without
    importing a script module. Behaviour identical: ~2800-char chunks
    per page using PyMuPDF's `insert_textbox`. Synthetic PDFs may
    extract weakly via pymupdf4llm — that's why the seed path also
    writes `full_text=body` directly so the worker can fall back to
    the existing column when extraction comes up short (see
    document_processor's quality guard).
    """
    import fitz  # PyMuPDF — already a dep

    doc = fitz.open()
    text = f"{title}\n\n{body}".strip()
    chunk_size = 2800
    cursor = 0
    while cursor < len(text):
        page = doc.new_page()
        rect = fitz.Rect(72, 72, page.rect.width - 72, page.rect.height - 72)
        chunk = text[cursor : cursor + chunk_size]
        page.insert_textbox(rect, chunk, fontsize=10, fontname="helv")
        cursor += chunk_size
    if doc.page_count == 0:
        doc.new_page()
    doc.save(path)
    doc.close()


async def fetch_opinion(url: str) -> Optional[dict]:
    """Fetch a single opinion record by URL.

    Used by the landmark seeder: clusters surface a list of `sub_opinions`
    URLs but we need each opinion's `plain_text` to ingest it.
    """
    async with httpx.AsyncClient(timeout=30.0, headers=_auth_headers()) as client:
        try:
            resp = await client.get(url)
        except httpx.RequestError as e:
            logger.warning("CourtListener opinion fetch error", error=str(e))
            return None
    if resp.status_code != 200:
        return None
    return resp.json()


async def find_cluster_by_name(
    case_name: str,
    year: int,
    court: str = "scotus",
) -> Optional[dict]:
    """Find a single cluster (case) by partial case-name match within a year.

    Used by `scripts/seed.py --landmarks` — for each (name, year) we look up
    the matching SCOTUS cluster and ingest the lead opinion. Tolerant by
    design: case_name__icontains lets "Brown v. Board" find "Brown v.
    Board of Education of Topeka" without exact-string matching.

    Returns the first cluster in the response (CourtListener orders by
    decision date by default, so the most authoritative version wins for
    cases that have multiple cluster variants — corrections, slip
    opinions, etc.).
    """
    url = f"{BASE_URL}/clusters/"
    params = {
        "case_name__icontains": case_name,
        "docket__court": court,
        "date_filed__year": str(year),
        "page_size": "5",
    }
    async with httpx.AsyncClient(timeout=30.0, headers=_auth_headers()) as client:
        try:
            resp = await client.get(url, params=params)
        except httpx.RequestError as e:
            logger.warning(
                "CourtListener cluster search error",
                error=str(e),
                case=case_name,
            )
            return None
    if resp.status_code != 200:
        logger.warning(
            "CourtListener cluster search failed",
            status=resp.status_code,
            case=case_name,
            year=year,
            body=resp.text[:200],
        )
        return None
    payload = resp.json()
    results = payload.get("results") or []
    return results[0] if results else None


async def lookup_citation(
    reporter: str, volume: int, page: int
) -> Optional[dict]:
    """Look up an opinion by citation. Returns metadata or None."""
    if not settings.feature_external_enrichment:
        return None

    citation = f"{volume} {reporter} {page}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{BASE_URL}/opinions/",
                params={"citation": citation},
                headers=_auth_headers(),
            )
    except httpx.RequestError as e:
        logger.warning("CourtListener network error", error=str(e))
        return None

    if resp.status_code != 200:
        logger.warning(
            "CourtListener lookup failed",
            status=resp.status_code,
            citation=citation,
        )
        return None

    payload = resp.json()
    results = payload.get("results") or []
    if not results:
        return None

    top = results[0]
    return {
        "court": top.get("court"),
        "date_filed": top.get("date_filed"),
        "case_name": top.get("case_name"),
        "docket_number": top.get("docket_number"),
        "absolute_url": top.get("absolute_url"),
    }


async def enrich_document(document_id: str) -> Optional[dict]:
    """
    Look up enrichment metadata for a document by inspecting its strongest
    full-text citation. The first FullCaseCitation extracted from the PDF
    typically appears in the caption and identifies the case itself.
    """
    if not settings.feature_external_enrichment:
        return None

    from sqlalchemy import select

    from backend.database import AsyncSessionLocal
    from backend.models import Citation as CitationModel
    from backend.models import Document as DocumentModel

    async with AsyncSessionLocal() as session:
        doc_row = await session.execute(
            select(DocumentModel).where(DocumentModel.id == document_id)
        )
        document = doc_row.scalar_one_or_none()
        if document is None:
            return None

        citation_row = await session.execute(
            select(CitationModel)
            .where(
                CitationModel.from_doc_id == document_id,
                CitationModel.citation_type == "full",
                CitationModel.reporter.isnot(None),
                CitationModel.volume.isnot(None),
                CitationModel.page.isnot(None),
            )
            .order_by(CitationModel.span_start)
            .limit(1)
        )
        citation = citation_row.scalar_one_or_none()
        if citation is None:
            return None

        meta = await lookup_citation(citation.reporter, citation.volume, citation.page)
        if meta is None:
            return None

        updated_fields: dict[str, str | int | None] = {}
        if not document.court and meta.get("court"):
            document.court = str(meta["court"])
            updated_fields["court"] = document.court
        if not document.docket and meta.get("docket_number"):
            document.docket = str(meta["docket_number"])
            updated_fields["docket"] = document.docket
        if not document.year and meta.get("date_filed"):
            try:
                document.year = int(str(meta["date_filed"])[:4])
                updated_fields["year"] = document.year
            except ValueError:
                pass

        if updated_fields:
            await session.commit()
            logger.info(
                "Document enriched from CourtListener",
                doc_id=document_id,
                fields=list(updated_fields.keys()),
            )
        return updated_fields or None
