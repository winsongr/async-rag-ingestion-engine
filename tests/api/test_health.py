from fastapi.testclient import TestClient
from unittest.mock import patch
from src.main import app

client = TestClient(app)


def test_health_live():
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch("src.api.health.check_all_infrastructure")
def test_health_ready_success(mock_check):
    mock_check.return_value = {"database": True, "redis": True, "qdrant": True}

    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"database": "ok", "redis": "ok", "qdrant": "ok"}


@patch("src.api.health.check_all_infrastructure")
def test_health_ready_unhealthy_dependency(mock_check):
    # Simulate DB down
    mock_check.return_value = {"database": False, "redis": True}

    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json() == {"database": "error", "redis": "ok"}
