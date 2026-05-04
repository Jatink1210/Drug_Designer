"""
Integration tests for Run API endpoints.

Tests the workflow run endpoints including:
- Run creation and execution
- Run status monitoring
- Run results retrieval
- Run cancellation
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import datetime

from apps.api.main import app
from apps.api.models.db_tables import User, Project, Run


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Mock authentication headers."""
    return {"Authorization": "Bearer test_token"}


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    return User(
        id="user-123",
        email="test@example.com",
        full_name="Test User",
        role="researcher"
    )


class TestRunCreationEndpoints:
    """Test run creation endpoints."""

    def test_create_run(self, client, auth_headers):
        """Test POST /api/v1/runs endpoint."""
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/runs",
                headers=auth_headers,
                json={
                    "project_id": "proj-123",
                    "workflow_type": "disease_intelligence",
                    "parameters": {
                        "disease_name": "Alzheimer's Disease",
                        "depth": "comprehensive"
                    }
                }
            )
            
            assert response.status_code in [200, 201]
            data = response.json()
            assert "run_id" in data
            assert "status" in data
            assert data["status"] == "queued"

    def test_create_run_with_invalid_workflow(self, client, auth_headers):
        """Test creating run with invalid workflow type."""
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/runs",
                headers=auth_headers,
                json={
                    "project_id": "proj-123",
                    "workflow_type": "invalid_workflow",
                    "parameters": {}
                }
            )
            
            assert response.status_code in [400, 422]

    def test_create_batch_runs(self, client, auth_headers):
        """Test POST /api/v1/runs/batch endpoint."""
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/runs/batch",
                headers=auth_headers,
                json={
                    "project_id": "proj-123",
                    "runs": [
                        {
                            "workflow_type": "disease_intelligence",
                            "parameters": {"disease_name": "Alzheimer's"}
                        },
                        {
                            "workflow_type": "target_prioritization",
                            "parameters": {"disease_id": "disease-123"}
                        }
                    ]
                }
            )
            
            assert response.status_code in [200, 201]
            data = response.json()
            assert "run_ids" in data
            assert len(data["run_ids"]) == 2


class TestRunExecutionEndpoints:
    """Test run execution endpoints."""

    def test_start_run(self, client, auth_headers):
        """Test POST /api/v1/runs/{run_id}/start endpoint."""
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/runs/run-123/start",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert data["status"] in ["running", "queued"]

    def test_pause_run(self, client, auth_headers):
        """Test POST /api/v1/runs/{run_id}/pause endpoint."""
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/runs/run-123/pause",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_resume_run(self, client, auth_headers):
        """Test POST /api/v1/runs/{run_id}/resume endpoint."""
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/runs/run-123/resume",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_cancel_run(self, client, auth_headers):
        """Test POST /api/v1/runs/{run_id}/cancel endpoint."""
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/runs/run-123/cancel",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert data["status"] == "cancelled"

    def test_retry_failed_run(self, client, auth_headers):
        """Test POST /api/v1/runs/{run_id}/retry endpoint."""
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/runs/run-123/retry",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]


class TestRunStatusEndpoints:
    """Test run status monitoring endpoints."""

    def test_get_run_status(self, client, auth_headers):
        """Test GET /api/v1/runs/{run_id}/status endpoint."""
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/runs/run-123/status",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "status" in data
                assert "progress" in data

    def test_get_run_details(self, client, auth_headers):
        """Test GET /api/v1/runs/{run_id} endpoint."""
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/runs/run-123",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "run_id" in data
                assert "workflow_type" in data
                assert "created_at" in data

    def test_list_runs(self, client, auth_headers):
        """Test GET /api/v1/runs endpoint."""
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/runs",
                headers=auth_headers,
                params={"project_id": "proj-123"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "runs" in data
            assert isinstance(data["runs"], list)

    def test_get_run_logs(self, client, auth_headers):
        """Test GET /api/v1/runs/{run_id}/logs endpoint."""
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/runs/run-123/logs",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "logs" in data
                assert isinstance(data["logs"], list)


class TestRunResultsEndpoints:
    """Test run results retrieval endpoints."""

    def test_get_run_results(self, client, auth_headers):
        """Test GET /api/v1/runs/{run_id}/results endpoint."""
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/runs/run-123/results",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "results" in data

    def test_get_run_artifacts(self, client, auth_headers):
        """Test GET /api/v1/runs/{run_id}/artifacts endpoint."""
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/runs/run-123/artifacts",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "artifacts" in data
                assert isinstance(data["artifacts"], list)

    def test_download_run_artifact(self, client, auth_headers):
        """Test GET /api/v1/runs/{run_id}/artifacts/{artifact_id}/download endpoint."""
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/runs/run-123/artifacts/artifact-456/download",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]


class TestRunMetricsEndpoints:
    """Test run metrics endpoints."""

    def test_get_run_metrics(self, client, auth_headers):
        """Test GET /api/v1/runs/{run_id}/metrics endpoint."""
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/runs/run-123/metrics",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "metrics" in data

    def test_get_run_performance(self, client, auth_headers):
        """Test GET /api/v1/runs/{run_id}/performance endpoint."""
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/runs/run-123/performance",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "duration" in data
                assert "resource_usage" in data


class TestRunComparisonEndpoints:
    """Test run comparison endpoints."""

    def test_compare_runs(self, client, auth_headers):
        """Test POST /api/v1/runs/compare endpoint."""
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/runs/compare",
                headers=auth_headers,
                json={
                    "run_ids": ["run-123", "run-456", "run-789"]
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "comparison" in data


class TestAuthorizationAndErrors:
    """Test authorization and error handling."""

    def test_unauthorized_access(self, client):
        """Test access without authentication."""
        response = client.get("/api/v1/runs/run-123")
        assert response.status_code == 401

    def test_delete_run(self, client, auth_headers):
        """Test DELETE /api/v1/runs/{run_id} endpoint."""
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.delete(
                "/api/v1/runs/run-123",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 204, 404]


# Performance tests
class TestPerformance:
    """Test performance of run endpoints."""

    def test_list_runs_performance(self, client, auth_headers):
        """Test list runs endpoint performance."""
        import time
        
        with patch("apps.api.routers.runs.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            start = time.time()
            response = client.get(
                "/api/v1/runs",
                headers=auth_headers,
                params={"limit": 100}
            )
            duration = time.time() - start
            
            assert response.status_code == 200
            assert duration < 3.0  # Should complete in under 3 seconds
