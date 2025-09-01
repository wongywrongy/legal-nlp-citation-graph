"""
Database Model Tests - Test data models and relationships
"""
import pytest
from sqlalchemy.orm import Session
from backend.models import Document, Citation, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.mark.unit
@pytest.mark.database
@pytest.mark.fast
def test_document_model_creation():
    """Test that Document model can be created with required fields"""
    document = Document(
        title="Test Document",
        fingerprint="test_fingerprint_123",
        source_path="/test/path/document.pdf"
    )
    
    assert document.title == "Test Document"
    assert document.fingerprint == "test_fingerprint_123"
    assert document.source_path == "/test/path/document.pdf"
    assert document.processed == 0  # Default value
    assert document.id is not None

@pytest.mark.unit
@pytest.mark.database
@pytest.mark.fast
def test_document_model_optional_fields():
    """Test that Document model handles optional fields correctly"""
    document = Document(
        title="Test Document",
        fingerprint="test_fingerprint_123",
        source_path="/test/path/document.pdf",
        court="U.S. Supreme Court",
        year=1973,
        docket="71-1234"
    )
    
    assert document.court == "U.S. Supreme Court"
    assert document.year == 1973
    assert document.docket == "71-1234"

@pytest.mark.unit
@pytest.mark.database
@pytest.mark.fast
def test_citation_model_creation():
    """Test that Citation model can be created with required fields"""
    citation = Citation(
        from_doc_id="doc_123",
        raw_text="410 U.S. 113 (1973)",
        normalized_key="US_410_113_1973"
    )
    
    assert citation.from_doc_id == "doc_123"
    assert citation.raw_text == "410 U.S. 113 (1973)"
    assert citation.normalized_key == "US_410_113_1973"
    assert citation.confidence == 0.0  # Default value
    assert citation.id is not None

@pytest.mark.unit
@pytest.mark.database
@pytest.mark.fast
def test_citation_model_optional_fields():
    """Test that Citation model handles optional fields correctly"""
    citation = Citation(
        from_doc_id="doc_123",
        raw_text="410 U.S. 113 (1973)",
        normalized_key="US_410_113_1973",
        reporter="U.S.",
        volume=410,
        page=113,
        year=1973,
        confidence=0.95
    )
    
    assert citation.reporter == "U.S."
    assert citation.volume == 410
    assert citation.page == 113
    assert citation.year == 1973
    assert citation.confidence == 0.95

@pytest.mark.unit
@pytest.mark.database
@pytest.mark.fast
def test_document_citation_relationship():
    """Test that Document and Citation models can be related"""
    # Create document
    document = Document(
        title="Test Document",
        fingerprint="test_fingerprint_123",
        source_path="/test/path/document.pdf"
    )
    
    # Create citation
    citation = Citation(
        from_doc_id=document.id,
        raw_text="410 U.S. 113 (1973)",
        normalized_key="US_410_113_1973"
    )
    
    # Test relationship
    assert citation.from_doc_id == document.id

@pytest.mark.unit
@pytest.mark.database
@pytest.mark.fast
def test_model_validation():
    """Test that models validate data correctly"""
    # Test with invalid data types
    with pytest.raises(Exception):
        Document(
            title=123,  # Should be string
            fingerprint="test",
            source_path="/test/path"
        )

@pytest.mark.unit
@pytest.mark.database
@pytest.mark.fast
def test_model_defaults():
    """Test that models have correct default values"""
    document = Document(
        title="Test Document",
        fingerprint="test_fingerprint_123",
        source_path="/test/path/document.pdf"
    )
    
    citation = Citation(
        from_doc_id="doc_123",
        raw_text="Test citation",
        normalized_key="test_key"
    )
    
    # Check default values
    assert document.processed == 0
    assert citation.confidence == 0.0
    assert document.created_at is not None
