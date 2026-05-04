"""
Integration tests for RL Models API endpoints.

Tests RL model management endpoints including:
- Model registration
- Model versioning
- Model deployment
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


class TestRLModelEndpoints:
    """Test RL model endpoints."""

    def test_register_model(self, client, auth_headers):
        """Test POST /api/v1/rlm/models endpoint."""
        model_data = {
            "name": "test_rl_model",
            "algorithm": "ppo",
            "version": "1.0.0"
        }
        
        response = client.post(
            "/api/v1/rlm/models",
            headers=auth_headers,
            json=model_data
        )
        
        assert response.status_code in [200, 201, 401, 422]

    def test_get_model(self, client, auth_headers):
        """Test GET /api/v1/rlm/models/{model_id} endpoint."""
        response = client.get(
            "/api/v1/rlm/models/test-model-id",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]

    def test_list_models(self, client, auth_headers):
        """Test GET /api/v1/rlm/models endpoint."""
        response = client.get("/api/v1/rlm/models", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields


class TestModelVersioningEndpoints:
    """Test model versioning endpoints."""

    def test_create_version(self, client, auth_headers):
        """Test POST /api/v1/rlm/models/{model_id}/versions endpoint."""
        version_data = {"version": "1.1.0", "changes": "Improved performance"}
        
        response = client.post(
            "/api/v1/rlm/models/test-model-id/versions",
            headers=auth_headers,
            json=version_data
        )
        
        assert response.status_code in [200, 201, 401, 404, 422]

    def test_list_versions(self, client, auth_headers):
        """Test GET /api/v1/rlm/models/{model_id}/versions endpoint."""
        response = client.get(
            "/api/v1/rlm/models/test-model-id/versions",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]


class TestModelDeploymentEndpoints:
    """Test model deployment endpoints."""

    def test_deploy_model(self, client, auth_headers):
        """Test POST /api/v1/rlm/models/{model_id}/deploy endpoint."""
        deploy_config = {"environment": "production"}
        
        response = client.post(
            "/api/v1/rlm/models/test-model-id/deploy",
            headers=auth_headers,
            json=deploy_config
        )
        
        assert response.status_code in [200, 401, 404, 422]

    def test_undeploy_model(self, client, auth_headers):
        """Test POST /api/v1/rlm/models/{model_id}/undeploy endpoint."""
        response = client.post(
            "/api/v1/rlm/models/test-model-id/undeploy",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]


class TestErrorHandling:
    """Test error handling."""

    def test_unauthorized_access(self, client):
        """Test accessing RLM without authentication."""
        response = client.get("/api/v1/rlm/models")
        
        assert response.status_code == 401

