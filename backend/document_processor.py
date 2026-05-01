"""
Document processing service: orchestrates PDF extraction, citation parsing,
and deterministic candidate linking.

The LLM tie-break path lives in `backend.llm_resolver` and is invoked from
`_link_citations` only when deterministic matching produces multiple
candidates. There is no fuzzy "within ±N volumes" matching: an unresolved
citation stays unresolved.

Stage logs go through `backend.progress` so the worker output reads as a
clear narrative of what's happening — see that module's docstring for the
log shape.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections import defaultdict
from dataclasses import asdict
from typing import Dict, List, Optional, Tuple

import structlog
from sqlalchemy.orm import Session

from backend.citation_parser import CitationParser, ParsedCitation
from backend.config import settings
from backend.database import SessionLocal
from backend.exceptions import ExtractionFailedError
from backend.models import Citation as CitationModel
from backend.models import Document as DocumentModel
from backend.pdf_processor import PDFProcessor
from backend.progress import stage

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
        db = SessionLocal()
        try:
            document = (
                db.query(DocumentModel).filter(DocumentModel.id == document_id).first()
            )
            if document is None:
                raise ValueError(f"Document not found: {document_id}")
            if not document.source_path or not os.path.exists(document.source_path):
                raise ValueError(f"PDF file not found: {document.source_path}")

            # On retry: clear any prior failure flag so a successful
            # re-extraction can transition the doc back to healthy.
            # POST /v1/process/{id} re-runs this method; the worker
            # chain reads `status` and skips embed if it's still set
            # post-extraction.
            if document.status == "extraction_failed":
                document.status = None
                db.commit()

            with stage("process", doc=document_id, title=document.title) as s:
                # Stage 1: PDF text extraction.
                t = time.perf_counter()
                full_text, page_spans = self.pdf_processor.extract_full_text(
                    document.source_path
                )
                s.step(
                    "parse_pdf",
                    pages=len(page_spans),
                    chars=len(full_text),
                    elapsed=time.perf_counter() - t,
                )

                # Quality guard: anything below ~one paragraph is almost
                # certainly a failed extraction (scanned PDF without OCR
                # text, corrupt fonts, image-only doc). Flip status,
                # commit, raise — the worker catches and skips downstream.
                #
                # Edge case: synthetic seed PDFs and prior pre-pymupdf4llm
                # ingests sometimes have a healthy `full_text` already
                # (seed.py writes `body` directly before processing).
                # When the new extractor underperforms but the column
                # already contains enough text, keep the existing text
                # and skip the failure flag — we'd rather over-extract
                # than tag a doc that already has good content.
                if not self.pdf_processor.is_extraction_sufficient(full_text):
                    existing = document.full_text or ""
                    if self.pdf_processor.is_extraction_sufficient(existing):
                        s.step(
                            "extraction_kept_existing",
                            new_chars=len(full_text.strip()),
                            existing_chars=len(existing.strip()),
                        )
                        # Use the existing text so downstream stages run.
                        full_text = existing
                        # `page_spans` may be wrong for the existing
                        # text, but eyecite has been working fine off
                        # the same data on prior runs — the spans are
                        # only used to label citations with a page
                        # number; misalignment degrades that label, not
                        # citation discovery itself.
                    else:
                        chars = len(full_text.strip())
                        s.step(
                            "extraction_failed",
                            chars=chars,
                            title=document.title,
                        )
                        document.status = "extraction_failed"
                        db.commit()
                        raise ExtractionFailedError(document_id, chars)

                # Re-extract title from the existing first-page text so we
                # don't open the PDF a second time. `_maybe_refresh_title`
                # was the last call site needing a separate read.
                first_page_text = page_spans[0].text if page_spans else ""
                self._maybe_refresh_title(db, document, first_page_text)

                # Persist full_text + page_offsets once; the worker's
                # embed stage reads full_text, the inspector reads
                # page_offsets to map citation char ranges → page #.
                if full_text and document.full_text != full_text:
                    document.full_text = full_text
                    document.page_offsets = self.pdf_processor.extract_page_offsets(
                        page_spans
                    )
                    db.commit()

                # Stage 2: citation parsing (eyecite + resolve_citations).
                t = time.perf_counter()
                parsed = self.citation_parser.parse_from_full_text(full_text, page_spans)
                deduped = self._dedupe(parsed)
                s.step(
                    "parse_cites",
                    found=len(parsed),
                    deduped=len(deduped),
                    elapsed=time.perf_counter() - t,
                )

                # Stage 3: persist.
                stored = self._store_citations(db, document_id, deduped)
                s.step("store_cites", stored=len(stored), dropped=len(deduped) - len(stored))

                # Stage 4: link to in-corpus targets (and optionally external).
                t = time.perf_counter()
                linked = self._link_citations(db, stored)
                s.step(
                    "link_cites",
                    linked=linked,
                    unresolved=len(stored) - linked,
                    elapsed=time.perf_counter() - t,
                )

            return {
                "document_id": document_id,
                "pdf_pages": len(page_spans),
                "pdf_chars": len(full_text),
                "citations_found": len(parsed),
                "citations_stored": len(stored),
                "citations_linked": linked,
                "processing_status": "completed",
            }
        finally:
            db.close()

    def _maybe_refresh_title(
        self,
        db: Session,
        document: DocumentModel,
        first_page_text: str,
    ) -> None:
        """Re-derive the title from page 1 if the current one looks placeholder.

        Reuses `first_page_text` already pulled by `extract_full_text` —
        previously this re-opened the PDF, doubling I/O on every reprocess.
        """
        current = document.title or ""
        looks_like_filename = (
            current.endswith(".pdf")
            or len(current) < 20
            or not any(c.isupper() for c in current[:10])
        )
        if not looks_like_filename:
            return
        new_title = self._title_from_page_text(first_page_text, document.source_path)
        if new_title and new_title != current:
            document.title = new_title
            db.commit()
            self.logger.info(
                "Refreshed document title",
                doc_id=document.id,
                old_title=current,
                new_title=new_title,
            )

    def _title_from_page_text(self, text: str, source_path: Optional[str]) -> str:
        """Same heuristics as the prior `_extract_document_title` but on already-extracted text."""
        if not text:
            return os.path.basename(source_path or "").replace(".pdf", "")
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
        return os.path.basename(source_path or "").replace(".pdf", "")

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

        # Batch candidate lookup once for all citations with full reporter
        # data — replaces the prior N+1 (one JOIN per citation). For a
        # 50-cite opinion this collapses 50 queries into 1.
        candidate_index = self._batch_find_candidates(db, citations)

        linked = 0
        for citation in citations:
            if not (citation.reporter and citation.volume and citation.page):
                continue

            candidates = candidate_index.get(
                (citation.reporter, citation.volume, citation.page), []
            )
            # Self-reference filter: a doc can't cite itself in the graph.
            candidates = [c for c in candidates if c.id != citation.from_doc_id]
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
        """Async CourtListener lookup with bounded concurrency.

        Runs `asyncio.run()` because the document processor sits on a
        worker thread (called via `asyncio.to_thread`), not on an event
        loop. Lookups run with a concurrency cap (semaphore=4) — much
        faster than the prior serial loop (20 cites × 1s ≈ 20s → ~5s)
        without blowing past CourtListener's rate limits.
        Failures are swallowed per-citation so one network blip doesn't
        block the whole batch.
        """
        import asyncio as _asyncio

        from backend.courtlistener import lookup_citation

        sem = _asyncio.Semaphore(4)

        async def _one(citation: CitationModel) -> None:
            async with sem:
                try:
                    meta = await lookup_citation(
                        citation.reporter, citation.volume, citation.page
                    )
                except Exception:
                    meta = None
            if not meta:
                return
            year_val: Optional[int] = None
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

        async def _run() -> None:
            await _asyncio.gather(*(_one(c) for c in citations))

        _asyncio.run(_run())

    @staticmethod
    def _batch_find_candidates(
        db: Session,
        citations: List[CitationModel],
    ) -> Dict[Tuple[str, int, int], List[DocumentModel]]:
        """One query that returns the candidate set for every (reporter, volume, page) tuple.

        Heuristic for what counts as a candidate is unchanged: a document
        is a candidate if any of its own citations match the same reporter
        triple — this handles the case where a cited work's caption text
        contains its own pinpoint reference.

        Returns a dict keyed by (reporter, volume, page) so the caller can
        do an O(1) lookup per citation. Self-reference filtering is left
        to the caller because it's per-citation.
        """
        triples = {
            (c.reporter, c.volume, c.page)
            for c in citations
            if c.reporter and c.volume is not None and c.page is not None
        }
        if not triples:
            return {}

        # Pull every Citation+Document row for any matching triple in one
        # round-trip. We can't use SQL `IN` against composite tuples
        # portably, so we OR the per-triple AND clauses. Postgres planner
        # collapses this efficiently because each clause hits the
        # (reporter, volume, page) compound index.
        from sqlalchemy import and_, or_

        clauses = [
            and_(
                CitationModel.reporter == r,
                CitationModel.volume == v,
                CitationModel.page == p,
            )
            for (r, v, p) in triples
        ]
        rows = (
            db.query(DocumentModel, CitationModel.reporter, CitationModel.volume, CitationModel.page)
            .join(CitationModel, CitationModel.from_doc_id == DocumentModel.id)
            .filter(or_(*clauses))
            .distinct()
            .all()
        )

        index: Dict[Tuple[str, int, int], List[DocumentModel]] = defaultdict(list)
        seen: Dict[Tuple[str, int, int], set] = defaultdict(set)
        for doc, reporter, volume, page in rows:
            key = (reporter, volume, page)
            if doc.id in seen[key]:
                continue
            seen[key].add(doc.id)
            index[key].append(doc)
        return index

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
            # Stream-hash so a 50MB brief doesn't sit in memory while we
            # decide whether it's a duplicate.
            sha = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(64 * 1024), b""):
                    sha.update(chunk)
            fingerprint = sha.hexdigest()
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
