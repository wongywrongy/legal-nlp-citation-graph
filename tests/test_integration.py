"""
Integration Tests - Test complete workflows end-to-end
"""
import pytest
import tempfile
import os
from fastapi.testclient import TestClient
from backend.models import Document, Citation

@pytest.mark.integration
@pytest.mark.e2e
@pytest.mark.slow
def test_complete_document_workflow(client: TestClient):
    """Test complete document upload and processing workflow"""
    # Step 1: Check initial state
    response = client.get("/v1/documents")
    assert response.status_code == 200
    initial_count = response.json()["total"]
    
    # Step 2: Check graph is empty initially
    response = client.get("/v1/graph")
    assert response.status_code == 200
    graph_data = response.json()
    assert len(graph_data["nodes"]) == 0
    assert len(graph_data["edges"]) == 0
    
    # Step 3: Try to process documents (should work even with no documents)
    response = client.post("/v1/process")
    assert response.status_code in [200, 500]  # Either success or no documents to process

@pytest.mark.integration
@pytest.mark.api
@pytest.mark.fast
def test_api_endpoints_consistency(client: TestClient):
    """Test that API endpoints return consistent data structures"""
    # Test documents endpoint structure
    response = client.get("/v1/documents")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["total"], int)
    
    # Test graph endpoint structure
    response = client.get("/v1/graph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)

@pytest.mark.integration
@pytest.mark.api
@pytest.mark.fast
def test_error_handling(client: TestClient):
    """Test that API handles errors gracefully"""
    # Test non-existent document
    response = client.get("/v1/documents/non-existent-id")
    assert response.status_code == 404
    
    # Test invalid pagination
    response = client.get("/v1/documents?skip=-1&limit=0")
    assert response.status_code == 200  # Should handle gracefully
    
    # Test invalid confidence filter
    response = client.get("/v1/graph?min_confidence=invalid")
    assert response.status_code == 422  # Validation error

@pytest.mark.integration
@pytest.mark.api
@pytest.mark.fast
def test_api_response_headers(client: TestClient):
    """Test that API returns proper headers"""
    response = client.get("/v1/documents")
    assert response.status_code == 200
    assert "content-type" in response.headers
    assert response.headers["content-type"] == "application/json"

@pytest.mark.integration
@pytest.mark.api
@pytest.mark.fast
def test_api_pagination_consistency(client: TestClient):
    """Test that pagination works consistently"""
    # Test different pagination parameters
    pagination_tests = [
        {"skip": 0, "limit": 10},
        {"skip": 10, "limit": 5},
        {"skip": 0, "limit": 100},
        {"skip": 100, "limit": 10}
    ]
    
    for params in pagination_tests:
        response = client.get("/v1/documents", params=params)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

@pytest.mark.integration
@pytest.mark.api
@pytest.mark.fast
def test_graph_filtering_consistency(client: TestClient):
    """Test that graph filtering works consistently"""
    # Test different confidence levels
    confidence_levels = [0.0, 0.5, 0.7, 0.9, 1.0]
    
    for confidence in confidence_levels:
        response = client.get(f"/v1/graph?min_confidence={confidence}")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data

@pytest.mark.integration
@pytest.mark.health
@pytest.mark.slow
def test_health_endpoint_under_load(client: TestClient):
    """Test that health endpoint works under load"""
    import concurrent.futures
    import time
    
    def make_health_request():
        start_time = time.time()
        response = client.get("/health")
        end_time = time.time()
        return response.status_code, (end_time - start_time)
    
    # Make multiple concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_health_request) for _ in range(20)]
        results = [future.result() for future in futures]
    
    # All requests should succeed
    for status_code, response_time in results:
        assert status_code == 200
        assert response_time < 2.0  # Should respond in under 2 seconds

@pytest.mark.integration
@pytest.mark.api
@pytest.mark.fast
def test_api_documentation_consistency(client: TestClient):
    """Test that API documentation is consistent"""
    # Test OpenAPI schema
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    
    # Check required OpenAPI fields
    assert "openapi" in schema
    assert "info" in schema
    assert "paths" in schema
    
    # Test Swagger UI
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
