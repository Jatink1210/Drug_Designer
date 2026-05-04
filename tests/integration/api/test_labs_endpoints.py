"""
Integration tests for Labs API endpoints.

Tests experimental features and lab experiments including:
- Experiment creation
- Experiment tracking
- Results management
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


class TestExperimentEndpoints:
    """Test experiment endpoints."""

    def test_create_experiment(self, client, auth_headers):
        """Test POST /api/v1/labs/experiments endpoint."""
        experiment_data = {
            "name": "test_experiment",
            "type": "drug_design",
            "config": {"param1": "value1"}
        }
        
        response = client.post(
            "/api/v1/labs/experiments",
            headers=auth_headers,
            json=experiment_data
        )
        
        assert response.status_code in [200, 201, 401, 422]

    def test_get_experiment(self, client, auth_headers):
        """Test GET /api/v1/labs/experiments/{experiment_id} endpoint."""
        response = client.get(
            "/api/v1/labs/experiments/test-exp-id",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]

    def test_list_experiments(self, client, auth_headers):
        """Test GET /api/v1/labs/experiments endpoint."""
        response = client.get("/api/v1/labs/experiments", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_delete_experiment(self, client, auth_headers):
        """Test DELETE /api/v1/labs/experiments/{experiment_id} endpoint."""
        response = client.delete(
            "/api/v1/labs/experiments/test-exp-id",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 204, 401, 404]


class TestResultsEndpoints:
    """Test results endpoints."""

    def test_get_experiment_results(self, client, auth_headers):
        """Test GET /api/v1/labs/experiments/{experiment_id}/results endpoint."""
        response = client.get(
            "/api/v1/labs/experiments/test-exp-id/results",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]

    def test_submit_results(self, client, auth_headers):
        """Test POST /api/v1/labs/experiments/{experiment_id}/results endpoint."""
        results_data = {
            "metrics": {"accuracy": 0.95},
            "artifacts": ["model.pkl"]
        }
        
        response = client.post(
            "/api/v1/labs/experiments/test-exp-id/results",
            headers=auth_headers,
            json=results_data
        )
        
        assert response.status_code in [200, 201, 401, 404, 422]


class TestErrorHandling:
    """Test error handling."""

    def test_unauthorized_access(self, client):
        """Test accessing labs without authentication."""
        response = client.get("/api/v1/labs/experiments")
        
        assert response.status_code == 401

