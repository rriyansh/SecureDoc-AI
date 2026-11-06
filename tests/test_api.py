"""Tests for the API endpoints."""

from fastapi.testclient import TestClient

from api.main import app


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_query():
    client = TestClient(app)
    response = client.post("/query", json={"question": "hello"})
    assert response.status_code == 200
    assert "answer" in response.json()
