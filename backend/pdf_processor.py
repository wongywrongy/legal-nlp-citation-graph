"""
PDF text extraction backed by PyMuPDF4LLM.

Why PyMuPDF4LLM (Track A): the prior implementation walked PyMuPDF span
records by hand, sorted by position, and concatenated. On many SCOTUS
opinions that produced footnotes interleaved into body text and dropped
column-break boundaries. PyMuPDF4LLM uses PyMuPDF's layout GNN to
extract structured Markdown — body text and footnotes are correctly
separated, and headers/page numbers don't bleed into prose. Native PDFs
run in ~120 ms; OCR is triggered automatically on scanned pages, so the
caller never has to choose.

This module returns plain text (Markdown stripped) plus a list of
`PageSpan` records so eyecite can resolve a citation's character offset
back to a source page. The public `extract_full_text(file_path) ->
tuple[str, list[PageSpan]]` signature is unchanged from the prior
implementation, so `document_processor.py` doesn't need touching.

Quality guard (Track A.4): if the stripped text is shorter than
`_MIN_BODY_CHARS` (500), the caller (`document_processor`) flips the
document's status to `'extraction_failed'` and the worker chain skips
embedding + enrichment. 500 chars is roughly one paragraph — any real
court opinion clears that easily.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pymupdf4llm
import structlog

logger = structlog.get_logger()


# Minimum body length the rest of the pipeline requires. Below this we
# flag the document as extraction_failed; embedding/enrichment skip.
_MIN_BODY_CHARS = 500


@dataclass
class PageSpan:
    """One page's text plus its char offset within the full-document string."""

    page_number: int
    text: str
    char_offset: int


# ---- Markdown stripping --------------------------------------------------
#
# pymupdf4llm.to_markdown() returns Markdown — headings, bold/italic,
# horizontal rules, image refs, link syntax. We never store Markdown in
# `documents.full_text` (it would corrupt eyecite's span detection and
# leave artefacts in /api/search snippets). _strip_markdown produces
# plain text while preserving paragraph breaks, which eyecite uses to
# infer citation boundaries. A small set of regexes is sufficient — no
# external Markdown parser.

_RE_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_RE_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_RE_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)
_RE_HR = re.compile(r"^\s{0,3}([-*_]){3,}\s*$", re.MULTILINE)
_RE_BOLD_STAR = re.compile(r"\*\*([^*]+?)\*\*")
_RE_BOLD_UNDERSCORE = re.compile(r"__([^_]+?)__")
_RE_ITALIC_STAR = re.compile(r"(?<!\*)\*([^*\n]+?)\*(?!\*)")
_RE_ITALIC_UNDERSCORE = re.compile(r"(?<!_)_([^_\n]+?)_(?!_)")


def _strip_markdown(md: str) -> str:
    """Remove Markdown syntax while preserving paragraph structure.

    Order matters: image refs first (they look like links), then links,
    then heading markers (single newlines after stripping become part of
    paragraph flow), then HR rules (turn into blank lines), then
    bold/italic markers (longest-first to avoid '**foo**' being eaten
    by the italic rule). We deliberately do NOT collapse single
    newlines — eyecite uses whitespace context for citation span
    detection, and rejoining lines mid-paragraph corrupts that.
    """
    if not md:
        return ""
    # Drop image references entirely (alt text isn't useful for legal text).
    md = _RE_IMAGE.sub("", md)
    # Replace links with their visible text.
    md = _RE_LINK.sub(r"\1", md)
    # Strip heading markers, keeping the heading text.
    md = _RE_HEADING.sub("", md)
    # Drop horizontal rules — they sit on their own line, so removing
    # the marker leaves a blank line which is fine.
    md = _RE_HR.sub("", md)
    # Strip bold + italic markers, longest first.
    md = _RE_BOLD_STAR.sub(r"\1", md)
    md = _RE_BOLD_UNDERSCORE.sub(r"\1", md)
    md = _RE_ITALIC_STAR.sub(r"\1", md)
    md = _RE_ITALIC_UNDERSCORE.sub(r"\1", md)
    return md


def _extract_chunks(file_path: str) -> List[dict]:
    """Run pymupdf4llm in page-chunked mode.

    Wrapped so the caller can mock this in tests. Returns the raw chunk
    list; callers strip Markdown + build offsets.
    """
    return pymupdf4llm.to_markdown(file_path, page_chunks=True)


class PDFProcessor:
    def __init__(self) -> None:
        self.logger = logger.bind(component="pdf_processor")

    def extract_full_text(
        self, file_path: str
    ) -> Tuple[str, List[PageSpan]]:
        """Extract clean plain text + per-page offsets from a PDF.

        Returns the same `(full_text, page_spans)` tuple the prior
        implementation did, so `document_processor` doesn't change. An
        additional outcome — the page_offsets list in serialisable form
        — is exposed via `extract_page_offsets()` for storage on
        `documents.page_offsets`.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        try:
            chunks = _extract_chunks(file_path)
        except Exception as e:
            # PyMuPDF4LLM raises various extraction errors (corrupt PDF,
            # missing fonts, etc.). Surface them with file context so
            # the worker log explains what happened to which doc.
            self.logger.warning(
                "pymupdf4llm extraction failed", file_path=file_path, error=str(e)
            )
            raise

        parts: List[str] = []
        spans: List[PageSpan] = []
        cursor = 0

        for chunk in chunks:
            page_number = self._chunk_page_number(chunk)
            raw_md = chunk.get("text", "") if isinstance(chunk, dict) else ""
            plain = _strip_markdown(raw_md)
            # Empty pages still get a zero-width span so subsequent
            # offsets remain accurate. This matters for citations that
            # land on the last page after a blank page.
            spans.append(
                PageSpan(
                    page_number=page_number,
                    text=plain,
                    char_offset=cursor,
                )
            )
            parts.append(plain)
            cursor += len(plain)

        full_text = "".join(parts)

        self.logger.info(
            "Extracted PDF",
            file_path=file_path,
            pages=len(spans),
            chars=len(full_text),
        )
        return full_text, spans

    @staticmethod
    def extract_page_offsets(
        page_spans: List[PageSpan],
    ) -> List[dict]:
        """Serialise PageSpan records for `documents.page_offsets` JSONB.

        The frontend can map a citation's `span_start` to a page number
        without re-parsing the PDF. Stored alongside the citation linker
        because it's only useful in conjunction with `full_text`.
        """
        return [
            {
                "page": s.page_number,
                "start": s.char_offset,
                "end": s.char_offset + len(s.text),
            }
            for s in page_spans
        ]

    @staticmethod
    def is_extraction_sufficient(full_text: str) -> bool:
        """Heuristic: any real opinion has at least one paragraph (~500 chars).

        Documents that fail this check are tagged `status='extraction_failed'`
        upstream and the worker skips embedding + enrichment.
        """
        return len(full_text.strip()) >= _MIN_BODY_CHARS

    @staticmethod
    def resolve_page_number(
        char_pos: int, page_spans: List[PageSpan]
    ) -> int:
        """Map a character offset in the full text back to a page number."""
        if not page_spans:
            return 1
        for span in reversed(page_spans):
            if char_pos >= span.char_offset:
                return span.page_number
        return page_spans[0].page_number

    def extract_first_page_text(self, file_path: str) -> str:
        """First-page text only. Used by the title fallback path.

        Goes through the same PyMuPDF4LLM pipeline + Markdown strip so
        the title heuristics see consistent text whether they read page
        1 alone or alongside the rest of the document.
        """
        if not os.path.exists(file_path):
            return ""
        try:
            chunks = _extract_chunks(file_path)
        except Exception as e:
            self.logger.warning(
                "first-page extract failed", file_path=file_path, error=str(e)
            )
            return ""
        if not chunks:
            return ""
        first = chunks[0] if isinstance(chunks[0], dict) else {}
        return _strip_markdown(first.get("text", ""))

    @staticmethod
    def _chunk_page_number(chunk: dict) -> int:
        """Pick the page number out of a chunk metadata dict.

        pymupdf4llm 0.0.17 puts it at `metadata.page` already 1-indexed
        (verified empirically — the first page is `page: 1`, not `0`).
        Older preview builds exposed `page_number` flat on the chunk.
        Tolerate either; default to 1 when missing.
        """
        if not isinstance(chunk, dict):
            return 1
        meta = chunk.get("metadata") or {}
        if "page" in meta:
            try:
                return int(meta["page"])
            except (TypeError, ValueError):
                pass
        if "page_number" in chunk:
            try:
                return int(chunk["page_number"])
            except (TypeError, ValueError):
                pass
        return 1
