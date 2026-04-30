"""
PDF text extraction using PyMuPDF (fitz).

Returns the full document text plus a list of page spans so downstream
consumers (eyecite, the citation parser) can operate on a single string
while still resolving character offsets back to source page numbers.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Tuple

import fitz  # PyMuPDF
import structlog

logger = structlog.get_logger()


@dataclass
class PageSpan:
    """One page's text plus its char offset within the full-document string."""

    page_number: int
    text: str
    char_offset: int


class PDFProcessor:
    def __init__(self) -> None:
        self.logger = logger.bind(component="pdf_processor")

    def extract_full_text(self, file_path: str) -> Tuple[str, List[PageSpan]]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        doc = fitz.open(file_path)
        full_text_parts: List[str] = []
        page_spans: List[PageSpan] = []
        offset = 0

        try:
            for page_index in range(doc.page_count):
                page = doc.load_page(page_index)
                text = page.get_text("text") or ""
                page_spans.append(
                    PageSpan(
                        page_number=page_index + 1,
                        text=text,
                        char_offset=offset,
                    )
                )
                full_text_parts.append(text)
                offset += len(text)
        finally:
            doc.close()

        full_text = "".join(full_text_parts)
        self.logger.info(
            "Extracted PDF",
            file_path=file_path,
            pages=len(page_spans),
            chars=len(full_text),
        )
        return full_text, page_spans

    @staticmethod
    def resolve_page_number(char_pos: int, page_spans: List[PageSpan]) -> int:
        """Map a character offset in the full text back to a page number."""
        if not page_spans:
            return 1
        for span in reversed(page_spans):
            if char_pos >= span.char_offset:
                return span.page_number
        return page_spans[0].page_number

    def extract_first_page_text(self, file_path: str) -> str:
        """Used by title extraction; returns the first page's plain text."""
        if not os.path.exists(file_path):
            return ""
        doc = fitz.open(file_path)
        try:
            if doc.page_count == 0:
                return ""
            return doc.load_page(0).get_text("text") or ""
        finally:
            doc.close()
