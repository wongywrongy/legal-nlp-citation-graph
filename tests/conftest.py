import pytest
import tempfile
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.database import get_db
from backend.main import app
from backend.models import Base

@pytest.fixture
def test_db():
    """Create a temporary test database"""
    # Create temporary database file
    db_fd, db_path = tempfile.mkstemp()
    
    # Create test database engine
    test_engine = create_engine(f"sqlite:///{db_path}")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    
    # Create tables
    Base.metadata.create_all(bind=test_engine)
    
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    # Override dependency
    app.dependency_overrides[get_db] = override_get_db
    
    yield test_engine
    
    # Cleanup
    app.dependency_overrides.clear()
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture
def client(test_db):
    """Create test client with test database"""
    return TestClient(app)

@pytest.fixture
def sample_pdf_content():
    """Sample PDF content for testing"""
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n72 720 Td\n(Test PDF Content) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000111 00000 n \n0000000204 00000 n \ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n297\n%%EOF"

@pytest.fixture
def sample_citation_text():
    """Sample citation text for testing"""
    return "410 U.S. 113 (1973)"

@pytest.fixture
def test_document_data():
    """Sample document data for testing"""
    return {
        "title": "Test Legal Document",
        "fingerprint": "test_fingerprint_123",
        "source_path": "/test/path/document.pdf",
        "court": "U.S. Supreme Court",
        "year": 1973,
        "docket": "71-1234"
    }

@pytest.fixture
def test_citation_data():
    """Sample citation data for testing"""
    return {
        "raw_text": "410 U.S. 113 (1973)",
        "normalized_key": "US_410_113_1973",
        "reporter": "U.S.",
        "volume": 410,
        "page": 113,
        "year": 1973,
        "confidence": 0.95
    }
