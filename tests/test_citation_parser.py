"""
Citation Parser Tests - Test citation parsing functionality
"""
import pytest
from backend.citation_parser import CitationParser

@pytest.mark.unit
@pytest.mark.fast
def test_citation_parser_initialization():
    """Test that CitationParser can be initialized"""
    parser = CitationParser()
    assert parser is not None
    assert isinstance(parser, CitationParser)

@pytest.mark.unit
@pytest.mark.fast
def test_parse_simple_citation():
    """Test parsing a simple citation"""
    parser = CitationParser()
    text = "410 U.S. 113 (1973)"
    
    citations = parser.parse_citations(text)
    
    assert len(citations) == 1
    citation = citations[0]
    assert citation["raw_text"] == "410 U.S. 113 (1973)"
    assert citation["reporter"] == "U.S."
    assert citation["volume"] == 410
    assert citation["page"] == 113
    assert citation["year"] == 1973

@pytest.mark.unit
@pytest.mark.fast
def test_parse_citation_without_year():
    """Test parsing a citation without year"""
    parser = CitationParser()
    text = "123 Cal. 456"
    
    citations = parser.parse_citations(text)
    
    assert len(citations) == 1
    citation = citations[0]
    assert citation["raw_text"] == "123 Cal. 456"
    assert citation["reporter"] == "Cal."
    assert citation["volume"] == 123
    assert citation["page"] == 456
    assert citation["year"] is None

@pytest.mark.unit
@pytest.mark.fast
def test_parse_multiple_citations():
    """Test parsing multiple citations in one text"""
    parser = CitationParser()
    text = "See 410 U.S. 113 (1973) and 123 Cal. 456"
    
    citations = parser.parse_citations(text)
    
    assert len(citations) == 2
    
    # First citation
    assert citations[0]["reporter"] == "U.S."
    assert citations[0]["volume"] == 410
    
    # Second citation
    assert citations[1]["reporter"] == "Cal."
    assert citations[1]["volume"] == 123

@pytest.mark.unit
@pytest.mark.fast
def test_parse_no_citations():
    """Test parsing text with no citations"""
    parser = CitationParser()
    text = "This is just regular text with no citations."
    
    citations = parser.parse_citations(text)
    
    assert len(citations) == 0

@pytest.mark.unit
@pytest.mark.fast
def test_citation_confidence_default():
    """Test that citations have default confidence"""
    parser = CitationParser()
    text = "410 U.S. 113 (1973)"
    
    citations = parser.parse_citations(text)
    
    assert len(citations) == 1
    assert citations[0]["confidence"] == 0.6  # Default confidence

@pytest.mark.unit
@pytest.mark.fast
def test_citation_normalized_key():
    """Test that citations generate normalized keys"""
    parser = CitationParser()
    text = "410 U.S. 113 (1973)"
    
    citations = parser.parse_citations(text)
    
    assert len(citations) == 1
    citation = citations[0]
    assert "normalized_key" in citation
    assert isinstance(citation["normalized_key"], str)

@pytest.mark.unit
@pytest.mark.fast
def test_citation_span_positions():
    """Test that citations have span positions"""
    parser = CitationParser()
    text = "410 U.S. 113 (1973)"
    
    citations = parser.parse_citations(text)
    
    assert len(citations) == 1
    citation = citations[0]
    assert "span_start" in citation
    assert "span_end" in citation
    assert isinstance(citation["span_start"], int)
    assert isinstance(citation["span_end"], int)

@pytest.mark.unit
@pytest.mark.fast
def test_parser_handles_edge_cases():
    """Test that parser handles edge cases gracefully"""
    parser = CitationParser()
    
    # Empty text
    citations = parser.parse_citations("")
    assert len(citations) == 0
    
    # Very long text
    long_text = "A" * 10000 + "410 U.S. 113 (1973)" + "B" * 10000
    citations = parser.parse_citations(long_text)
    assert len(citations) == 1
