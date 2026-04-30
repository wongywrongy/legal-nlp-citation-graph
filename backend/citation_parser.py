"""
Citation parsing using `eyecite` as the single source of truth.

`eyecite` recognizes hundreds of reporters, parallel citations, short-form
references, and id./supra. references. Everything that follows in the pipeline
(deduplication, candidate matching, LLM tie-break) operates on the structured
output of this module — there is no regex fallback.

Phase 2 enhancement: `eyecite.resolve_citations()` is run over the citation
list to link short/supra/id forms back to their canonical full citation. When
a short form resolves to a full parent, this module copies the parent's
reporter/volume/page/year/case_name onto the short form so they share the
same `normalized_key` (which the deterministic matcher in `document_processor`
uses for linking). Resolved short forms also receive a +0.20 confidence boost.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import structlog
from eyecite import clean_text, get_citations, resolve_citations
from eyecite.models import (
    FullCaseCitation,
    IdCitation,
    ShortCaseCitation,
    SupraCitation,
)

from backend.pdf_processor import PageSpan, PDFProcessor

logger = structlog.get_logger()


@dataclass
class ParsedCitation:
    raw_text: str
    normalized_key: str
    reporter: Optional[str] = None
    volume: Optional[int] = None
    page: Optional[int] = None
    year: Optional[int] = None
    case_name: Optional[str] = None
    page_number: Optional[int] = None
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    confidence: float = 0.0
    citation_type: str = "full"
    resolved_to_full: bool = False


# Baseline confidence by citation type — exact full citations are highly
# trustworthy; short/supra/id refs are weaker signals on their own.
_BASE_CONFIDENCE = {
    "full": 0.85,
    "short": 0.55,
    "supra": 0.45,
    "id": 0.40,
}

# Confidence boost when a short/supra/id citation is successfully linked back
# to a FullCaseCitation parent by eyecite.resolve_citations().
_RESOLVED_BOOST = 0.20
_MAX_RESOLVED_CONFIDENCE = 0.95


class CitationParser:
    def __init__(self) -> None:
        self.logger = logger.bind(component="citation_parser")
        self._pdf_processor = PDFProcessor()

    def parse_from_full_text(
        self,
        full_text: str,
        page_spans: List[PageSpan],
    ) -> List[ParsedCitation]:
        cleaned = clean_text(full_text, ["html", "all_whitespace"])
        try:
            citations = get_citations(cleaned)
        except Exception as e:
            self.logger.error("eyecite failed", error=str(e))
            return []

        parents = self._resolve_parents(citations)

        parsed: List[ParsedCitation] = []
        for citation in citations:
            try:
                parent = parents.get(id(citation))
                converted = self._convert(citation, page_spans, parent)
                if converted is not None:
                    parsed.append(converted)
            except Exception as e:
                self.logger.warning(
                    "Failed to convert citation",
                    citation=str(citation),
                    error=str(e),
                )

        self.logger.info(
            "Parsed citations",
            total=len(parsed),
            full=sum(1 for c in parsed if c.citation_type == "full"),
            short=sum(1 for c in parsed if c.citation_type == "short"),
            resolved=sum(1 for c in parsed if c.resolved_to_full),
        )
        return parsed

    @staticmethod
    def _resolve_parents(citations) -> Dict[int, FullCaseCitation]:
        """
        Build {id(citation): parent_full_citation} via eyecite.resolve_citations.

        eyecite returns a dict[Resource, list[CitationBase]] where each Resource
        wraps the canonical FullCaseCitation. We invert it so per-citation
        lookup is O(1) without re-walking the resolution map.
        """
        parents: Dict[int, FullCaseCitation] = {}
        try:
            resolutions = resolve_citations(citations)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("resolve_citations failed", error=str(e))
            return parents

        for resource, members in resolutions.items():
            full = getattr(resource, "citation", None)
            if not isinstance(full, FullCaseCitation):
                continue
            for member in members:
                if member is full:
                    continue
                parents[id(member)] = full
        return parents

    def _convert(
        self,
        citation,
        page_spans: List[PageSpan],
        parent: Optional[FullCaseCitation],
    ) -> Optional[ParsedCitation]:
        span_start, span_end = self._span(citation)
        page_number = (
            self._pdf_processor.resolve_page_number(span_start, page_spans)
            if span_start is not None
            else None
        )

        if isinstance(citation, FullCaseCitation):
            return self._convert_full(citation, span_start, span_end, page_number)
        if isinstance(citation, ShortCaseCitation):
            return self._convert_short(
                citation, span_start, span_end, page_number, parent
            )
        if isinstance(citation, SupraCitation):
            return self._convert_short_like(
                citation, "supra", span_start, span_end, page_number, parent
            )
        if isinstance(citation, IdCitation):
            return self._convert_short_like(
                citation, "id", span_start, span_end, page_number, parent
            )
        return None

    @staticmethod
    def _span(citation) -> tuple[Optional[int], Optional[int]]:
        token = getattr(citation, "token", None)
        if token is None:
            return None, None
        start = getattr(token, "start", None)
        end = getattr(token, "end", None)
        return start, end

    def _convert_full(
        self,
        citation: FullCaseCitation,
        span_start: Optional[int],
        span_end: Optional[int],
        page_number: Optional[int],
    ) -> ParsedCitation:
        groups = citation.groups or {}
        reporter = (
            citation.corrected_reporter()
            or groups.get("reporter")
        )
        volume = self._coerce_int(groups.get("volume"))
        page = self._coerce_int(groups.get("page"))

        metadata = getattr(citation, "metadata", None)
        year = self._coerce_int(getattr(metadata, "year", None)) if metadata else None
        case_name = self._extract_case_name(metadata)

        normalized_key = self._normalized_key(reporter, volume, page, year)
        raw_text = self._raw_text(citation)

        return ParsedCitation(
            raw_text=raw_text,
            normalized_key=normalized_key,
            reporter=reporter,
            volume=volume,
            page=page,
            year=year,
            case_name=case_name,
            page_number=page_number,
            span_start=span_start,
            span_end=span_end,
            confidence=_BASE_CONFIDENCE["full"],
            citation_type="full",
        )

    def _convert_short(
        self,
        citation: ShortCaseCitation,
        span_start: Optional[int],
        span_end: Optional[int],
        page_number: Optional[int],
        parent: Optional[FullCaseCitation],
    ) -> ParsedCitation:
        groups = citation.groups or {}
        reporter = citation.corrected_reporter() or groups.get("reporter")
        volume = self._coerce_int(groups.get("volume"))
        page = self._coerce_int(groups.get("page"))
        year, case_name = None, None

        if parent is not None:
            inherited = self._inherit_from_parent(parent)
            # Use explicit None checks rather than truthiness — empty strings
            # from malformed eyecite output should still inherit, and the
            # behaviour stays consistent across reporter/volume/page.
            if reporter is None or reporter == "":
                reporter = inherited["reporter"]
            if volume is None:
                volume = inherited["volume"]
            if page is None:
                page = inherited["page"]
            year = inherited["year"]
            case_name = inherited["case_name"]

        normalized_key = self._normalized_key(reporter, volume, page, year)
        confidence = _BASE_CONFIDENCE["short"]
        resolved = parent is not None
        if resolved:
            confidence = min(confidence + _RESOLVED_BOOST, _MAX_RESOLVED_CONFIDENCE)
        return ParsedCitation(
            raw_text=self._raw_text(citation),
            normalized_key=normalized_key,
            reporter=reporter,
            volume=volume,
            page=page,
            year=year,
            case_name=case_name,
            page_number=page_number,
            span_start=span_start,
            span_end=span_end,
            confidence=confidence,
            citation_type="short",
            resolved_to_full=resolved,
        )

    def _convert_short_like(
        self,
        citation,
        kind: str,
        span_start: Optional[int],
        span_end: Optional[int],
        page_number: Optional[int],
        parent: Optional[FullCaseCitation],
    ) -> ParsedCitation:
        raw = self._raw_text(citation)
        reporter = volume = page = year = None
        case_name = None
        normalized_key = raw.strip().lower()

        if parent is not None:
            inherited = self._inherit_from_parent(parent)
            reporter = inherited["reporter"]
            volume = inherited["volume"]
            page = inherited["page"]
            year = inherited["year"]
            case_name = inherited["case_name"]
            normalized_key = self._normalized_key(reporter, volume, page, year)

        confidence = _BASE_CONFIDENCE[kind]
        resolved = parent is not None
        if resolved:
            confidence = min(confidence + _RESOLVED_BOOST, _MAX_RESOLVED_CONFIDENCE)
        return ParsedCitation(
            raw_text=raw,
            normalized_key=normalized_key,
            reporter=reporter,
            volume=volume,
            page=page,
            year=year,
            case_name=case_name,
            page_number=page_number,
            span_start=span_start,
            span_end=span_end,
            confidence=confidence,
            citation_type=kind,
            resolved_to_full=resolved,
        )

    @classmethod
    def _inherit_from_parent(cls, parent: FullCaseCitation) -> Dict[str, Optional[object]]:
        groups = parent.groups or {}
        reporter = parent.corrected_reporter() or groups.get("reporter")
        metadata = getattr(parent, "metadata", None)
        return {
            "reporter": reporter,
            "volume": cls._coerce_int(groups.get("volume")),
            "page": cls._coerce_int(groups.get("page")),
            "year": cls._coerce_int(getattr(metadata, "year", None)) if metadata else None,
            "case_name": cls._extract_case_name(metadata),
        }

    @staticmethod
    def _normalized_key(
        reporter: Optional[str],
        volume: Optional[int],
        page: Optional[int],
        year: Optional[int],
    ) -> str:
        parts = [
            (reporter or "?").replace(" ", "_"),
            str(volume) if volume is not None else "?",
            str(page) if page is not None else "?",
        ]
        if year is not None:
            parts.append(str(year))
        return "_".join(parts)

    @staticmethod
    def _raw_text(citation) -> str:
        for method in ("corrected_citation_full", "corrected_citation"):
            fn = getattr(citation, method, None)
            if callable(fn):
                try:
                    value = fn()
                    if value:
                        return value
                except Exception:
                    pass
        token = getattr(citation, "token", None)
        if token is not None and hasattr(token, "data"):
            return token.data
        return str(citation)

    @staticmethod
    def _extract_case_name(metadata) -> Optional[str]:
        if metadata is None:
            return None
        plaintiff = getattr(metadata, "plaintiff", None)
        defendant = getattr(metadata, "defendant", None)
        if plaintiff and defendant:
            return f"{plaintiff} v. {defendant}"
        return getattr(metadata, "case_name", None)

    @staticmethod
    def _coerce_int(value) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
