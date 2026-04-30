"""
Unit tests for the eyecite-backed citation parser.
"""
from __future__ import annotations

import pytest

from backend.citation_parser import CitationParser
from backend.pdf_processor import PageSpan, PDFProcessor


@pytest.mark.unit
@pytest.mark.fast
def test_parser_initialises():
    parser = CitationParser()
    assert parser is not None


@pytest.mark.unit
@pytest.mark.fast
def test_parses_full_us_citation():
    text = "Roe v. Wade, 410 U.S. 113 (1973)."
    spans = [PageSpan(page_number=1, text=text, char_offset=0)]

    parsed = CitationParser().parse_from_full_text(text, spans)
    fulls = [p for p in parsed if p.citation_type == "full"]
    assert fulls, "expected at least one full citation"

    citation = fulls[0]
    assert citation.reporter == "U.S."
    assert citation.volume == 410
    assert citation.page == 113
    assert citation.year == 1973
    assert citation.confidence >= 0.5
    assert citation.page_number == 1


@pytest.mark.unit
@pytest.mark.fast
def test_normalised_key_includes_year_when_present():
    text = "See 384 U.S. 436 (1966)."
    spans = [PageSpan(page_number=1, text=text, char_offset=0)]

    parsed = CitationParser().parse_from_full_text(text, spans)
    fulls = [p for p in parsed if p.citation_type == "full"]
    assert fulls
    assert fulls[0].normalized_key.endswith("_1966")


@pytest.mark.unit
@pytest.mark.fast
def test_returns_empty_when_no_citations():
    text = "This paragraph has no legal citation in it whatsoever."
    spans = [PageSpan(page_number=1, text=text, char_offset=0)]

    assert CitationParser().parse_from_full_text(text, spans) == []


@pytest.mark.unit
@pytest.mark.fast
def test_resolve_page_number_uses_offsets():
    spans = [
        PageSpan(page_number=1, text="aaa", char_offset=0),
        PageSpan(page_number=2, text="bbbb", char_offset=3),
        PageSpan(page_number=3, text="ccccc", char_offset=7),
    ]
    assert PDFProcessor.resolve_page_number(0, spans) == 1
    assert PDFProcessor.resolve_page_number(2, spans) == 1
    assert PDFProcessor.resolve_page_number(3, spans) == 2
    assert PDFProcessor.resolve_page_number(7, spans) == 3
    assert PDFProcessor.resolve_page_number(99, spans) == 3


# ---- Resolution: short / supra / id forms inherit from full parent ---------


@pytest.mark.unit
@pytest.mark.fast
def test_short_form_inherits_normalized_key_from_full_parent():
    text = (
        "Roe v. Wade, 410 U.S. 113 (1973), changed the landscape. "
        "Years later, courts revisited Roe, 410 U.S. at 152, on the question of viability."
    )
    spans = [PageSpan(page_number=1, text=text, char_offset=0)]
    parsed = CitationParser().parse_from_full_text(text, spans)

    fulls = [p for p in parsed if p.citation_type == "full"]
    shorts = [p for p in parsed if p.citation_type == "short"]
    assert fulls and shorts, "expected one full and one short citation"

    full = fulls[0]
    short = shorts[0]
    assert short.resolved_to_full is True
    assert short.reporter == full.reporter
    assert short.volume == full.volume
    # short cites point to a pinpoint page; the inherited normalized_key includes year.
    assert short.normalized_key.startswith(full.normalized_key.rsplit("_", 1)[0])
    assert short.confidence > 0.7  # base 0.55 + boost 0.20


@pytest.mark.unit
@pytest.mark.fast
def test_supra_form_inherits_from_full_parent():
    text = (
        "We begin with Brown v. Board of Education, 347 U.S. 483 (1954). "
        "As Brown, supra, makes clear, separate is inherently unequal."
    )
    spans = [PageSpan(page_number=1, text=text, char_offset=0)]
    parsed = CitationParser().parse_from_full_text(text, spans)

    fulls = [p for p in parsed if p.citation_type == "full"]
    supras = [p for p in parsed if p.citation_type == "supra"]
    if not supras:
        pytest.skip("eyecite version did not extract a supra reference for this text")

    full = fulls[0]
    supra = supras[0]
    assert supra.resolved_to_full is True
    assert supra.reporter == full.reporter
    assert supra.normalized_key == full.normalized_key
    assert supra.confidence > _BASE_CONFIDENCE_FOR_SUPRA  # base + boost


@pytest.mark.unit
@pytest.mark.fast
def test_id_form_inherits_from_full_parent():
    text = (
        "We begin with Marbury v. Madison, 5 U.S. 137 (1803). "
        "Id. at 177 (Marshall, C.J.)."
    )
    spans = [PageSpan(page_number=1, text=text, char_offset=0)]
    parsed = CitationParser().parse_from_full_text(text, spans)

    fulls = [p for p in parsed if p.citation_type == "full"]
    ids = [p for p in parsed if p.citation_type == "id"]
    if not ids:
        pytest.skip("eyecite version did not extract an id. reference for this text")

    full = fulls[0]
    id_cite = ids[0]
    assert id_cite.resolved_to_full is True
    assert id_cite.normalized_key == full.normalized_key


# Local copy so tests don't reach into module internals if they're refactored.
_BASE_CONFIDENCE_FOR_SUPRA = 0.45
