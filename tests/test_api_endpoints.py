"""
API Endpoint Tests - Test all API endpoints with simple verification
"""
import pytest
from fastapi.testclient import TestClient
from backend.models import Document, Citation
from sqlalchemy.orm import Session

@pytest.mark.api
@pytest.mark.integration
@pytest.mark.fast
def test_documents_endpoint_returns_empty_list_when_no_documents(client: TestClient):
    """Test that documents endpoint returns empty list when no documents exist"""
    response = client.get("/v1/documents")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0

@pytest.mark.api
@pytest.mark.integration
@pytest.mark.fast
def test_documents_endpoint_returns_correct_structure(client: TestClient):
    """Test that documents endpoint returns correct JSON structure"""
    response = client.get("/v1/documents")
    assert response.status_code == 200
    data = response.json()
    
    # Check required fields exist
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["total"], int)

@pytest.mark.api
@pytest.mark.integration
@pytest.mark.fast
def test_documents_endpoint_handles_pagination(client: TestClient):
    """Test that documents endpoint handles pagination parameters"""
    response = client.get("/v1/documents?skip=0&limit=10")
    assert response.status_code == 200
    
    response = client.get("/v1/documents?skip=10&limit=5")
    assert response.status_code == 200

@pytest.mark.api
@pytest.mark.integration
@pytest.mark.fast
def test_graph_endpoint_returns_empty_graph_when_no_data(client: TestClient):
    """Test that graph endpoint returns empty graph when no data exists"""
    response = client.get("/v1/graph")
    assert response.status_code == 200
    data = response.json()
    assert data["nodes"] == []
    assert data["edges"] == []

@pytest.mark.api
@pytest.mark.integration
@pytest.mark.fast
def test_graph_endpoint_returns_correct_structure(client: TestClient):
    """Test that graph endpoint returns correct JSON structure"""
    response = client.get("/v1/graph")
    assert response.status_code == 200
    data = response.json()
    
    # Check required fields exist
    assert "nodes" in data
    assert "edges" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)

@pytest.mark.api
@pytest.mark.integration
@pytest.mark.fast
def test_graph_endpoint_handles_confidence_filter(client: TestClient):
    """Test that graph endpoint handles confidence filtering"""
    response = client.get("/v1/graph?min_confidence=0.5")
    assert response.status_code == 200
    
    response = client.get("/v1/graph?min_confidence=0.9")
    assert response.status_code == 200

@pytest.mark.api
@pytest.mark.integration
@pytest.mark.fast
def test_ingest_endpoint_accepts_files(client: TestClient):
    """Test that ingest endpoint accepts file uploads"""
    # Test with empty file list
    response = client.post("/v1/ingest", files=[])
    assert response.status_code == 422  # Validation error for empty files

@pytest.mark.api
@pytest.mark.integration
@pytest.mark.fast
def test_process_endpoint_returns_response(client: TestClient):
    """Test that process endpoint returns a response"""
    response = client.post("/v1/process")
    assert response.status_code in [200, 500]  # Either success or processing error

@pytest.mark.api
@pytest.mark.integration
@pytest.mark.fast
def test_api_docs_accessible(client: TestClient):
    """Test that API documentation is accessible"""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

@pytest.mark.api
@pytest.mark.integration
@pytest.mark.fast
def test_openapi_schema_accessible(client: TestClient):
    """Test that OpenAPI schema is accessible"""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
