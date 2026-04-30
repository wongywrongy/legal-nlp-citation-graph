"""
Document processing service: orchestrates PDF extraction, citation parsing,
and deterministic candidate linking.

The LLM tie-break path lives in `backend.llm_resolver` and is invoked from
`_link_citations` only when deterministic matching produces multiple
candidates. There is no fuzzy "within ±N volumes" matching: an unresolved
citation stays unresolved.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict
from typing import Dict, List, Optional

import structlog
from sqlalchemy.orm import Session

from backend.citation_parser import CitationParser, ParsedCitation
from backend.config import settings
from backend.database import SessionLocal
from backend.models import Citation as CitationModel
from backend.models import Document as DocumentModel
from backend.pdf_processor import PDFProcessor

logger = structlog.get_logger()


_TITLE_PATTERNS = [
    re.compile(r"^[A-Z][A-Za-z\s&,\-\'\.]+(?:v\.|vs\.|versus)\s+[A-Z][A-Za-z\s&,\-\'\.]+$", re.IGNORECASE),
    re.compile(r"^(?:IN RE|IN THE MATTER OF)\s+[A-Z][A-Za-z\s&,\-\'\.]+$", re.IGNORECASE),
    re.compile(r"^(?:UNITED STATES|STATE OF|COMMONWEALTH OF)\s+[A-Z][A-Za-z\s&,\-\'\.]+$", re.IGNORECASE),
    re.compile(r"^(?:PEOPLE OF|CITY OF|COUNTY OF)\s+[A-Z][A-Za-z\s&,\-\'\.]+$", re.IGNORECASE),
]
_TITLE_NEGATIVE_PREFIXES = (
    "Page",
    "Date",
    "Docket",
    "Case",
    "No.",
    "Filed",
    "Decided",
    "Before",
    "Opinion",
)


class DocumentProcessor:
    """Synchronous orchestrator (Phase 2 introduces an async wrapper)."""

    def __init__(self) -> None:
        self.pdf_processor = PDFProcessor()
        self.citation_parser = CitationParser()
        self.logger = logger.bind(component="document_processor")

    # ---- Title extraction ----------------------------------------------------

    def _extract_document_title(self, file_path: str) -> str:
        try:
            text = self.pdf_processor.extract_first_page_text(file_path)
        except Exception as e:
            self.logger.warning("Failed to read first page", file_path=file_path, error=str(e))
            return os.path.basename(file_path).replace(".pdf", "")

        if not text:
            return os.path.basename(file_path).replace(".pdf", "")

        lines = [ln.strip() for ln in text.split("\n")]

        for line in lines[:15]:
            if 15 < len(line) < 300:
                for pat in _TITLE_PATTERNS:
                    if pat.match(line):
                        return line
                if line[:1].isupper() and not line.startswith(_TITLE_NEGATIVE_PREFIXES):
                    return line

        for line in lines:
            if (
                10 < len(line) < 200
                and line[:1].isupper()
                and not line.startswith(_TITLE_NEGATIVE_PREFIXES)
            ):
                return line[:150]

        return os.path.basename(file_path).replace(".pdf", "")

    # ---- Single-document pipeline -------------------------------------------

    def process_document(self, document_id: str) -> Dict:
        self.logger.info("Starting document processing", document_id=document_id)

        db = SessionLocal()
        try:
            document = (
                db.query(DocumentModel).filter(DocumentModel.id == document_id).first()
            )
            if document is None:
                raise ValueError(f"Document not found: {document_id}")
            if not document.source_path or not os.path.exists(document.source_path):
                raise ValueError(f"PDF file not found: {document.source_path}")

            self._maybe_refresh_title(db, document)

            full_text, page_spans = self.pdf_processor.extract_full_text(document.source_path)
            # Persist text so the embedding worker can pick it up without
            # re-parsing the PDF, and so /api/search can render snippets.
            if full_text and document.full_text != full_text:
                document.full_text = full_text
                db.commit()
            parsed = self.citation_parser.parse_from_full_text(full_text, page_spans)
            deduped = self._dedupe(parsed)

            stored = self._store_citations(db, document_id, deduped)
            linked = self._link_citations(db, stored)

            result = {
                "document_id": document_id,
                "pdf_pages": len(page_spans),
                "pdf_chars": len(full_text),
                "citations_found": len(parsed),
                "citations_stored": len(stored),
                "citations_linked": linked,
                "processing_status": "completed",
            }
            self.logger.info("Document processing completed", **result)
            return result
        except Exception as e:
            self.logger.error(
                "Document processing failed", document_id=document_id, error=str(e)
            )
            raise
        finally:
            db.close()

    def _maybe_refresh_title(self, db: Session, document: DocumentModel) -> None:
        current = document.title or ""
        looks_like_filename = (
            current.endswith(".pdf")
            or len(current) < 20
            or not any(c.isupper() for c in current[:10])
        )
        if not looks_like_filename:
            return
        new_title = self._extract_document_title(document.source_path)
        if new_title and new_title != current:
            document.title = new_title
            db.commit()
            self.logger.info(
                "Refreshed document title",
                doc_id=document.id,
                old_title=current,
                new_title=new_title,
            )

    @staticmethod
    def _dedupe(citations: List[ParsedCitation]) -> List[ParsedCitation]:
        seen = set()
        out: List[ParsedCitation] = []
        for c in citations:
            key = (c.normalized_key, c.page_number)
            if key in seen:
                continue
            seen.add(key)
            out.append(c)
        return out

    def _store_citations(
        self,
        db: Session,
        from_doc_id: str,
        parsed_citations: List[ParsedCitation],
    ) -> List[CitationModel]:
        stored: List[CitationModel] = []
        for parsed in parsed_citations:
            breakdown: Dict[str, float] = {"eyecite_base": parsed.confidence}
            if parsed.resolved_to_full:
                breakdown["resolved_to_full"] = 0.20
            citation = CitationModel(
                from_doc_id=from_doc_id,
                raw_text=parsed.raw_text,
                normalized_key=parsed.normalized_key,
                reporter=parsed.reporter,
                volume=parsed.volume,
                page=parsed.page,
                year=parsed.year,
                page_number=parsed.page_number,
                span_start=parsed.span_start,
                span_end=parsed.span_end,
                citation_type=parsed.citation_type,
                confidence=parsed.confidence,
                resolution_notes="[]",
                confidence_breakdown=breakdown,
            )
            db.add(citation)
            stored.append(citation)
        db.commit()
        for citation in stored:
            db.refresh(citation)
        self.logger.info(
            "Citations stored", document_id=from_doc_id, count=len(stored)
        )
        return stored

    # ---- Candidate resolution -----------------------------------------------

    def _link_citations(self, db: Session, citations: List[CitationModel]) -> int:
        """
        Stage 1: exact (reporter, volume, page) match → single candidate doc.
        Stage 2: if multiple, narrow by year.
        Stage 3: LLM tie-break — gated by `feature_llm_resolver`. Leaves
        citation unresolved when ambiguous and the resolver is off.
        Stage 4: CourtListener external lookup — gated by
        `feature_external_enrichment`. For citations still without a
        `to_doc_id` but with reporter/volume/page, fetch the case metadata
        from CourtListener and stash it in `citation.external_resolution`.
        The inspector renders these as "external" (link icon, "Not in
        corpus" pill) rather than the muted "fully unresolved" state.
        """
        from backend.llm_resolver import resolve_ambiguous_citation_sync  # local import to avoid cycle when LLM disabled

        linked = 0
        for citation in citations:
            if not (citation.reporter and citation.volume and citation.page):
                continue

            candidates = self._find_candidates(db, citation)
            if len(candidates) == 1:
                self._apply_match(citation, candidates[0], boost=0.15, note="Exact reporter/volume/page match")
                linked += 1
                continue

            if len(candidates) > 1 and citation.year is not None:
                year_filtered = [c for c in candidates if c.year == citation.year]
                if len(year_filtered) == 1:
                    self._apply_match(
                        citation, year_filtered[0], boost=0.10,
                        note="Reporter/volume/page + year match",
                    )
                    linked += 1
                    continue

            if len(candidates) > 1 and settings.feature_llm_resolver:
                resolution = resolve_ambiguous_citation_sync(citation, candidates)
                if (
                    resolution
                    and resolution.get("best_document_id")
                    and resolution.get("confidence", 0) >= 0.5
                ):
                    chosen = next(
                        (c for c in candidates if c.id == resolution["best_document_id"]),
                        None,
                    )
                    if chosen is not None:
                        citation.to_doc_id = chosen.id
                        citation.confidence = float(resolution["confidence"])
                        citation.resolution_notes = json.dumps(resolution.get("notes", []))
                        breakdown = dict(citation.confidence_breakdown or {})
                        breakdown["llm_resolved"] = float(resolution["confidence"])
                        citation.confidence_breakdown = breakdown
                        linked += 1

        # Stage 4: external (CourtListener) lookup for still-unresolved
        # citations that have full reporter/volume/page data. Runs AFTER
        # in-corpus stages so we never overwrite a real `to_doc_id` —
        # external resolution is a fallback, not a competitor.
        if settings.feature_external_enrichment:
            still_unresolved = [
                c
                for c in citations
                if c.to_doc_id is None
                and c.reporter
                and c.volume
                and c.page
                and c.external_resolution is None
            ]
            if still_unresolved:
                self._external_lookup(still_unresolved)

        db.commit()
        self.logger.info("Citation linking completed", linked=linked, total=len(citations))
        return linked

    @staticmethod
    def _external_lookup(citations: List[CitationModel]) -> None:
        """Async CourtListener lookup; populates `citation.external_resolution`.

        Runs `asyncio.run()` because the document processor sits on a
        worker thread (called via `asyncio.to_thread`), not on an event
        loop. Each citation is looked up serially to keep the rate-limit
        envelope simple — for a typical opinion this is 5–20 lookups.
        Failures are swallowed per-citation so one network blip doesn't
        block the whole batch.
        """
        import asyncio as _asyncio

        from backend.courtlistener import lookup_citation

        async def _run() -> None:
            for citation in citations:
                try:
                    meta = await lookup_citation(
                        citation.reporter, citation.volume, citation.page
                    )
                except Exception:
                    meta = None
                if not meta:
                    continue
                year_val: int | None = None
                date_filed = meta.get("date_filed")
                if date_filed:
                    try:
                        year_val = int(str(date_filed)[:4])
                    except ValueError:
                        year_val = None
                citation.external_resolution = {
                    "case_name": meta.get("case_name"),
                    "year": year_val,
                    "absolute_url": meta.get("absolute_url"),
                    "court": meta.get("court"),
                }

        _asyncio.run(_run())

    @staticmethod
    def _find_candidates(db: Session, citation: CitationModel) -> List[DocumentModel]:
        """
        Find documents in the corpus that appear to be the cited work.

        Heuristic: a document IS a candidate if it contains a citation matching
        the same (reporter, volume, page) — this catches cases where the
        cited document also self-references its reporter pinpoint in caption
        text. CourtListener enrichment (Phase 4) adds direct reporter metadata
        on Document for a stronger match later.
        """
        rows = (
            db.query(DocumentModel)
            .join(CitationModel, CitationModel.from_doc_id == DocumentModel.id)
            .filter(
                CitationModel.reporter == citation.reporter,
                CitationModel.volume == citation.volume,
                CitationModel.page == citation.page,
                DocumentModel.id != citation.from_doc_id,
            )
            .distinct()
            .all()
        )
        return rows

    @staticmethod
    def _apply_match(
        citation: CitationModel,
        document: DocumentModel,
        boost: float,
        note: str,
    ) -> None:
        citation.to_doc_id = document.id
        citation.confidence = min(citation.confidence + boost, 1.0)
        citation.resolution_notes = json.dumps([note])
        breakdown = dict(citation.confidence_breakdown or {})
        breakdown["match_boost"] = boost
        citation.confidence_breakdown = breakdown

    # ---- Batch ingestion -----------------------------------------------------

    def process_all_documents(self) -> Dict:
        db = SessionLocal()
        try:
            self._register_pdfs_from_disk(db)

            unprocessed = (
                db.query(DocumentModel)
                .filter(~DocumentModel.citations_from.any())
                .all()
            )

            results = []
            for doc in unprocessed:
                try:
                    results.append(self.process_document(doc.id))
                except Exception as e:
                    self.logger.error("Failed to process document", doc_id=doc.id, error=str(e))
                    results.append(
                        {"document_id": doc.id, "processing_status": "failed", "error": str(e)}
                    )

            summary = {
                "total_documents": len(unprocessed),
                "processed": sum(1 for r in results if r.get("processing_status") == "completed"),
                "failed": sum(1 for r in results if r.get("processing_status") == "failed"),
                "results": results,
            }
            self.logger.info("Batch processing completed", **summary)
            return summary
        finally:
            db.close()

    def _register_pdfs_from_disk(self, db: Session) -> None:
        path = settings.pdf_storage_path
        if not os.path.exists(path):
            return
        for filename in os.listdir(path):
            if not filename.lower().endswith(".pdf"):
                continue
            file_path = os.path.join(path, filename)
            with open(file_path, "rb") as f:
                fingerprint = hashlib.sha256(f.read()).hexdigest()
            existing = (
                db.query(DocumentModel)
                .filter(DocumentModel.fingerprint == fingerprint)
                .first()
            )
            if existing is not None:
                continue
            document = DocumentModel(
                title=self._extract_document_title(file_path),
                fingerprint=fingerprint,
                source_path=file_path,
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            self.logger.info(
                "Registered new PDF", filename=filename, doc_id=document.id
            )
