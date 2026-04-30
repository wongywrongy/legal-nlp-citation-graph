"""
Database model tests.
"""
from __future__ import annotations

import pytest

from backend.models import Citation, Document


@pytest.mark.unit
@pytest.mark.database
@pytest.mark.fast
def test_document_required_fields():
    document = Document(
        title="Test Document",
        fingerprint="test_fingerprint_123",
        source_path="/test/path/document.pdf",
    )
    assert document.title == "Test Document"
    assert document.fingerprint == "test_fingerprint_123"
    assert document.source_path == "/test/path/document.pdf"
    assert document.id is not None


@pytest.mark.unit
@pytest.mark.database
@pytest.mark.fast
def test_document_optional_fields():
    document = Document(
        title="Test Document",
        fingerprint="test_fingerprint_123",
        source_path="/test/path/document.pdf",
        court="U.S. Supreme Court",
        year=1973,
        docket="71-1234",
    )
    assert document.court == "U.S. Supreme Court"
    assert document.year == 1973
    assert document.docket == "71-1234"


@pytest.mark.unit
@pytest.mark.database
@pytest.mark.fast
def test_citation_required_fields():
    citation = Citation(
        from_doc_id="doc_123",
        raw_text="410 U.S. 113 (1973)",
        normalized_key="U.S._410_113_1973",
    )
    assert citation.from_doc_id == "doc_123"
    assert citation.raw_text == "410 U.S. 113 (1973)"
    assert citation.normalized_key == "U.S._410_113_1973"
    assert citation.id is not None
    assert citation.citation_type == "full"  # default
    assert citation.confidence == 0.0  # default


@pytest.mark.unit
@pytest.mark.database
@pytest.mark.fast
def test_citation_optional_fields():
    citation = Citation(
        from_doc_id="doc_123",
        raw_text="410 U.S. 113 (1973)",
        normalized_key="U.S._410_113_1973",
        reporter="U.S.",
        volume=410,
        page=113,
        year=1973,
        confidence=0.95,
        confidence_breakdown={"eyecite_base": 0.85, "match_boost": 0.1},
    )
    assert citation.reporter == "U.S."
    assert citation.confidence == 0.95
    assert citation.confidence_breakdown == {"eyecite_base": 0.85, "match_boost": 0.1}


@pytest.mark.unit
@pytest.mark.database
@pytest.mark.fast
def test_document_citation_link():
    document = Document(
        title="Test Document",
        fingerprint="test_fingerprint_123",
        source_path="/test/path/document.pdf",
    )
    citation = Citation(
        from_doc_id=document.id,
        raw_text="410 U.S. 113 (1973)",
        normalized_key="U.S._410_113_1973",
    )
    assert citation.from_doc_id == document.id
