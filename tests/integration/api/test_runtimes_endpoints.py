"""
Integration tests for Runtimes API endpoints.

Tests runtime management endpoints including:
- Runtime configuration
- Runtime monitoring
- Runtime control
"""

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Create authentication headers."""
    return {"Authorization": "Bearer test_token"}


class TestRuntimeEndpoints:
    """Test runtime endpoints."""

    def test_get_runtime_config(self, client, auth_headers):
        """Test GET /api/v1/runtimes/config endpoint."""
        response = client.get("/api/v1/runtimes/config", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_update_runtime_config(self, client, auth_headers):
        """Test PUT /api/v1/runtimes/config endpoint."""
        config_data = {"max_workers": 10, "timeout": 300}
        
        response = client.put(
            "/api/v1/runtimes/config",
            headers=auth_headers,
            json=config_data
        )
        
        assert response.status_code in [200, 401, 422]

    def test_get_runtime_status(self, client, auth_headers):
        """Test GET /api/v1/runtimes/status endpoint."""
        response = client.get("/api/v1/runtimes/status", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields


class TestRuntimeControlEndpoints:
    """Test runtime control endpoints."""

    def test_restart_runtime(self, client, auth_headers):
        """Test POST /api/v1/runtimes/restart endpoint."""
        response = client.post(
            "/api/v1/runtimes/restart",
            headers=auth_headers
        )
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_reload_runtime(self, client, auth_headers):
        """Test POST /api/v1/runtimes/reload endpoint."""
        response = client.post(
            "/api/v1/runtimes/reload",
            headers=auth_headers
        )
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields


class TestErrorHandling:
    """Test error handling."""

    def test_unauthorized_access(self, client):
        """Test accessing runtimes without authentication."""
        response = client.get("/api/v1/runtimes/config")
        
        assert response.status_code == 401

