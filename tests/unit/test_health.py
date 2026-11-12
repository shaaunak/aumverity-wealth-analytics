from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_returns_metadata():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app_name"] == "AUMVERITY"
    assert data["reporting_currency"] == "USD"
    assert data["data_classification"] == "SYNTHETIC"
    assert "calculation_version" in data
    assert "timestamp_utc" in data


def test_ready_endpoint_when_db_connected():
    with patch("app.api.routes.health.check_database_connection", return_value=(True, None)):
        response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"


def test_ready_endpoint_when_db_disconnected():
    with patch(
        "app.api.routes.health.check_database_connection",
        return_value=(False, "connection refused"),
    ):
        response = client.get("/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not_ready"
    assert data["database"] == "disconnected"
    assert data["detail"] == "connection refused"
