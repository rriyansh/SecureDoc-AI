"""Tests for the API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from api.main import app
from src.auth import api_key_manager


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Create headers with valid API key."""
    key = api_key_manager.create_key("Test User", ["read", "write"])
    return {"X-API-Key": key}


class TestHealthEndpoints:
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_v1_health(self, client):
        response = client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_readiness(self, client):
        response = client.get("/v1/ready")
        assert response.status_code == 200
        data = response.json()
        assert "ready" in data
        assert "checks" in data


class TestQueryEndpoints:
    def test_query_unauthorized(self, client):
        response = client.post("/v1/query", json={"question": "test"})
        assert response.status_code == 401

    def test_query_with_api_key(self, client, auth_headers):
        with patch("api.routes.query.SecureRAGPipeline.query") as mock_query:
            mock_query.return_value = "Test answer"
            response = client.post("/v1/query", json={"question": "What is the policy?"}, headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            assert data["answer"] == "Test answer"

    def test_query_validation(self, client, auth_headers):
        # Empty question
        response = client.post("/v1/query", json={"question": ""}, headers=auth_headers)
        assert response.status_code == 422

        # Too long question
        response = client.post("/v1/query", json={"question": "a" * 3000}, headers=auth_headers)
        assert response.status_code == 422

    def test_query_with_params(self, client, auth_headers):
        with patch("api.routes.query.SecureRAGPipeline.query") as mock_query:
            mock_query.return_value = "Test answer"
            response = client.post(
                "/v1/query",
                json={"question": "test", "use_cache": False, "use_rewrite": False},
                headers=auth_headers,
            )
            assert response.status_code == 200

    def test_batch_query(self, client, auth_headers):
        with patch("api.routes.query.SecureRAGPipeline.query") as mock_query:
            mock_query.return_value = "Test answer"
            response = client.post(
                "/v1/query/batch",
                json={"questions": ["q1", "q2"], "use_cache": True},
                headers=auth_headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 2


class TestAdminEndpoints:
    def test_admin_requires_admin_scope(self, client):
        key = api_key_manager.create_key("Regular User", ["read"])
        headers = {"X-API-Key": key}
        response = client.get("/v1/admin/api-keys", headers=headers)
        assert response.status_code == 403

    def test_create_api_key(self, client):
        admin_key = api_key_manager.create_key("Admin", ["admin"])
        headers = {"X-API-Key": admin_key}
        response = client.post(
            "/v1/admin/api-keys",
            json={"name": "New Key", "scopes": ["read"]},
            headers=headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert "plaintext_key" in data
        assert data["name"] == "New Key"

    def test_list_api_keys(self, client):
        admin_key = api_key_manager.create_key("Admin", ["admin"])
        headers = {"X-API-Key": admin_key}
        response = client.get("/v1/admin/api-keys", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "keys" in data

    def test_revoke_api_key(self, client):
        admin_key = api_key_manager.create_key("Admin", ["admin"])
        headers = {"X-API-Key": admin_key}
        # Create a key to revoke
        create_resp = client.post(
            "/v1/admin/api-keys",
            json={"name": "To Revoke", "scopes": ["read"]},
            headers=headers,
        )
        key_id = create_resp.json()["key_id"]

        response = client.delete(f"/v1/admin/api-keys/{key_id}", headers=headers)
        assert response.status_code == 204

    def test_cache_stats(self, client):
        admin_key = api_key_manager.create_key("Admin", ["admin"])
        headers = {"X-API-Key": admin_key}
        response = client.get("/v1/admin/cache/stats", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "exact" in data
        assert "semantic" in data

    def test_clear_cache(self, client):
        admin_key = api_key_manager.create_key("Admin", ["admin"])
        headers = {"X-API-Key": admin_key}
        response = client.post("/v1/admin/cache/clear", headers=headers)
        assert response.status_code == 204

    def test_rate_limit_status(self, client, auth_headers):
        response = client.get("/v1/admin/rate-limit/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "limit" in data
        assert "remaining" in data


class TestMetricsEndpoint:
    def test_metrics_requires_admin(self, client):
        key = api_key_manager.create_key("Regular", ["read"])
        headers = {"X-API-Key": key}
        response = client.get("/v1/metrics", headers=headers)
        assert response.status_code == 403

    def test_metrics_admin(self, client):
        admin_key = api_key_manager.create_key("Admin", ["admin"])
        headers = {"X-API-Key": admin_key}
        response = client.get("/v1/metrics", headers=headers)
        assert response.status_code == 200
        assert "http_requests_total" in response.text


class TestRateLimiting:
    def test_rate_limit_headers(self, client, auth_headers):
        response = client.post("/v1/query", json={"question": "test"}, headers=auth_headers)
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers

    def test_rate_limit_exceeded(self, client):
        # Create a key with very low limit for testing
        from src.rate_limiter import api_rate_limiter
        api_rate_limiter.set_limit("test_rl", 1, 0)

        # Need to mock the user identification to use our test key
        with patch("api.dependencies.get_current_user") as mock_user:
            mock_user.return_value = {"user_id": "test_rl", "auth_method": "api_key"}
            response = client.post("/v1/query", json={"question": "test1"})
            assert response.status_code == 200
            response = client.post("/v1/query", json={"question": "test2"})
            assert response.status_code == 429


class TestRequestID:
    def test_request_id_header(self, client, auth_headers):
        response = client.post("/v1/query", json={"question": "test"}, headers=auth_headers)
        assert "X-Request-ID" in response.headers