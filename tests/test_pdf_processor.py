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
