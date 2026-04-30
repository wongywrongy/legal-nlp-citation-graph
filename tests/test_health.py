"""
Health check tests. Health probes the DB and Redis, so the test environment
will report `degraded` (Redis is not running). The shape of the response is
what matters — `status` is always present and `checks` lists subsystem state.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.health
@pytest.mark.smoke
@pytest.mark.fast
def test_health_endpoint_returns_200(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200


@pytest.mark.health
@pytest.mark.smoke
@pytest.mark.fast
def test_health_endpoint_shape(client: TestClient):
    response = client.get("/health")
    assert response.headers["content-type"] == "application/json"
    body = response.json()
    assert "status" in body and body["status"] in {"healthy", "degraded"}
    assert "checks" in body and isinstance(body["checks"], dict)
    # Database check must always be present and is `ok` against the temp DB.
    assert body["checks"].get("database") == "ok"
