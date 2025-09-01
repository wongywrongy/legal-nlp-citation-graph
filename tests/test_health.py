"""
Health Check Tests - These tests should ALWAYS pass and verify basic system functionality
"""
import pytest
from fastapi.testclient import TestClient

@pytest.mark.health
@pytest.mark.smoke
@pytest.mark.fast
def test_health_endpoint_always_works(client: TestClient):
    """Test that the health endpoint always returns success"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.health
@pytest.mark.smoke
@pytest.mark.fast
def test_health_endpoint_returns_json(client: TestClient):
    """Test that health endpoint returns valid JSON"""
    response = client.get("/health")
    assert response.headers["content-type"] == "application/json"

@pytest.mark.health
@pytest.mark.smoke
@pytest.mark.fast
def test_health_endpoint_fast_response(client: TestClient):
    """Test that health endpoint responds quickly"""
    import time
    start_time = time.time()
    response = client.get("/health")
    end_time = time.time()
    
    assert response.status_code == 200
    assert (end_time - start_time) < 1.0  # Should respond in under 1 second

@pytest.mark.health
@pytest.mark.smoke
@pytest.mark.fast
def test_health_endpoint_consistent_response(client: TestClient):
    """Test that health endpoint always returns the same response"""
    response1 = client.get("/health")
    response2 = client.get("/health")
    response3 = client.get("/health")
    
    assert response1.json() == response2.json() == response3.json() == {"status": "ok"}

@pytest.mark.health
@pytest.mark.smoke
@pytest.mark.fast
def test_health_endpoint_handles_multiple_requests(client: TestClient):
    """Test that health endpoint can handle multiple simultaneous requests"""
    import concurrent.futures
    
    def make_request():
        return client.get("/health")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(make_request) for _ in range(5)]
        responses = [future.result() for future in futures]
    
    for response in responses:
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
