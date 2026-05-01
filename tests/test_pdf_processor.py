"""
Tests for PyMuPDF-backed PDFProcessor: extracts text + maps offsets to pages.
"""
from __future__ import annotations

import pytest

from backend.pdf_processor import PDFProcessor


@pytest.mark.unit
@pytest.mark.fast
def test_extracts_full_text_from_single_page(roe_pdf):
    full_text, spans = PDFProcessor().extract_full_text(str(roe_pdf))
    assert "Roe v. Wade" in full_text
    assert "410 U.S. 113" in full_text
    assert len(spans) == 1
    assert spans[0].page_number == 1
    assert spans[0].char_offset == 0


@pytest.mark.unit
@pytest.mark.fast
def test_extracts_multi_page_with_offsets(multi_citation_pdf):
    full_text, spans = PDFProcessor().extract_full_text(str(multi_citation_pdf))
    assert len(spans) == 2
    assert spans[0].char_offset == 0
    assert spans[1].char_offset == len(spans[0].text)
    assert "Brown v. Board" in full_text
    assert "Marbury" in full_text


@pytest.mark.unit
@pytest.mark.fast
def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        PDFProcessor().extract_full_text("/no/such/file.pdf")


# ---- _strip_markdown ----------------------------------------------------
#
# pymupdf4llm produces structured Markdown; the extractor strips it back
# to plain text before storing in `documents.full_text`. These tests pin
# the contract: paragraph breaks survive, inline syntax does not.

from backend.pdf_processor import _strip_markdown  # noqa: E402  test-only import


@pytest.mark.unit
@pytest.mark.fast
def test_strip_markdown_removes_heading_marker():
    assert _strip_markdown("## Title\n\nBody text\n") == "Title\n\nBody text\n"


@pytest.mark.unit
@pytest.mark.fast
def test_strip_markdown_removes_bold_and_italic():
    assert _strip_markdown("**bold** and *italic*") == "bold and italic"
    assert _strip_markdown("__alt bold__ and _alt italic_") == "alt bold and alt italic"


@pytest.mark.unit
@pytest.mark.fast
def test_strip_markdown_keeps_paragraph_breaks():
    md = "First para.\n\nSecond para.\n"
    # Eyecite uses double newlines for span context — must be preserved.
    assert _strip_markdown(md) == md


@pytest.mark.unit
@pytest.mark.fast
def test_strip_markdown_drops_image_refs_and_keeps_link_text():
    assert _strip_markdown("See ![alt](image.png) and [Roe](#roe).") == "See  and Roe."


@pytest.mark.unit
@pytest.mark.fast
def test_strip_markdown_drops_horizontal_rules():
    md = "Above\n\n---\n\nBelow"
    out = _strip_markdown(md)
    assert "Above" in out and "Below" in out and "---" not in out


@pytest.mark.unit
@pytest.mark.fast
def test_is_extraction_sufficient_thresholds():
    # 500 chars is the cutoff; below it, the document gets flagged as
    # extraction_failed and the worker chain skips embedding.
    assert PDFProcessor.is_extraction_sufficient("a" * 500) is True
    assert PDFProcessor.is_extraction_sufficient("a" * 499) is False
    assert PDFProcessor.is_extraction_sufficient("") is False
