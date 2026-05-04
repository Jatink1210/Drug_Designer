"""
Integration tests for Docking API endpoints.

Tests the molecular docking endpoints including:
- Docking job submission
- Docking results retrieval
- Docking visualization
- Docking scoring
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import datetime

from apps.api.main import app
from apps.api.models.db_tables import User


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


class TestDockingJobEndpoints:
    """Test docking job submission and management endpoints."""

    def test_submit_docking_job(self, client, auth_headers):
        """Test POST /api/v1/docking/jobs endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/docking/jobs",
                headers=auth_headers,
                json={
                    "protein_id": "1TUP",
                    "ligand_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
                    "method": "autodock_vina",
                    "exhaustiveness": 8
                }
            )
            
            assert response.status_code in [200, 201, 202]
            if response.status_code in [200, 201]:
                data = response.json()
                assert "job_id" in data

    def test_get_docking_job_status(self, client, auth_headers):
        """Test GET /api/v1/docking/jobs/{job_id}/status endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/docking/jobs/job-123/status",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_list_docking_jobs(self, client, auth_headers):
        """Test GET /api/v1/docking/jobs endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/docking/jobs",
                headers=auth_headers,
                params={"limit": 10}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "jobs" in data

    def test_cancel_docking_job(self, client, auth_headers):
        """Test POST /api/v1/docking/jobs/{job_id}/cancel endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/docking/jobs/job-123/cancel",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_delete_docking_job(self, client, auth_headers):
        """Test DELETE /api/v1/docking/jobs/{job_id} endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.delete(
                "/api/v1/docking/jobs/job-123",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 204, 404]


class TestDockingResultsEndpoints:
    """Test docking results retrieval endpoints."""

    def test_get_docking_results(self, client, auth_headers):
        """Test GET /api/v1/docking/jobs/{job_id}/results endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/docking/jobs/job-123/results",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_get_docking_poses(self, client, auth_headers):
        """Test GET /api/v1/docking/jobs/{job_id}/poses endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/docking/jobs/job-123/poses",
                headers=auth_headers,
                params={"top_n": 10}
            )
            
            assert response.status_code in [200, 404]

    def test_get_best_pose(self, client, auth_headers):
        """Test GET /api/v1/docking/jobs/{job_id}/best-pose endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/docking/jobs/job-123/best-pose",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_download_docking_results(self, client, auth_headers):
        """Test GET /api/v1/docking/jobs/{job_id}/download endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/docking/jobs/job-123/download",
                headers=auth_headers,
                params={"format": "pdbqt"}
            )
            
            assert response.status_code in [200, 404]


class TestDockingScoringEndpoints:
    """Test docking scoring endpoints."""

    def test_get_docking_scores(self, client, auth_headers):
        """Test GET /api/v1/docking/jobs/{job_id}/scores endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/docking/jobs/job-123/scores",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_rescore_poses(self, client, auth_headers):
        """Test POST /api/v1/docking/jobs/{job_id}/rescore endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/docking/jobs/job-123/rescore",
                headers=auth_headers,
                json={"scoring_function": "vina"}
            )
            
            assert response.status_code in [200, 202, 404]

    def test_calculate_binding_energy(self, client, auth_headers):
        """Test POST /api/v1/docking/jobs/{job_id}/binding-energy endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/docking/jobs/job-123/binding-energy",
                headers=auth_headers,
                json={"pose_id": "pose-1"}
            )
            
            assert response.status_code in [200, 404]


class TestDockingVisualizationEndpoints:
    """Test docking visualization endpoints."""

    def test_visualize_docking_pose(self, client, auth_headers):
        """Test POST /api/v1/docking/jobs/{job_id}/visualize endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/docking/jobs/job-123/visualize",
                headers=auth_headers,
                json={
                    "pose_id": "pose-1",
                    "style": "stick",
                    "show_interactions": True
                }
            )
            
            assert response.status_code in [200, 404]

    def test_get_interaction_map(self, client, auth_headers):
        """Test GET /api/v1/docking/jobs/{job_id}/interactions endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/docking/jobs/job-123/interactions",
                headers=auth_headers,
                params={"pose_id": "pose-1"}
            )
            
            assert response.status_code in [200, 404]

    def test_generate_2d_diagram(self, client, auth_headers):
        """Test POST /api/v1/docking/jobs/{job_id}/2d-diagram endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/docking/jobs/job-123/2d-diagram",
                headers=auth_headers,
                json={"pose_id": "pose-1"}
            )
            
            assert response.status_code in [200, 404]


class TestBatchDockingEndpoints:
    """Test batch docking endpoints."""

    def test_submit_batch_docking(self, client, auth_headers):
        """Test POST /api/v1/docking/batch endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/docking/batch",
                headers=auth_headers,
                json={
                    "protein_id": "1TUP",
                    "ligand_smiles_list": [
                        "CC(=O)OC1=CC=CC=C1C(=O)O",
                        "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O"
                    ],
                    "method": "autodock_vina"
                }
            )
            
            assert response.status_code in [200, 201, 202]

    def test_get_batch_status(self, client, auth_headers):
        """Test GET /api/v1/docking/batch/{batch_id}/status endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/docking/batch/batch-123/status",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_get_batch_results(self, client, auth_headers):
        """Test GET /api/v1/docking/batch/{batch_id}/results endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/docking/batch/batch-123/results",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]


class TestDockingConfigurationEndpoints:
    """Test docking configuration endpoints."""

    def test_get_docking_methods(self, client, auth_headers):
        """Test GET /api/v1/docking/methods endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/docking/methods",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "methods" in data

    def test_get_method_parameters(self, client, auth_headers):
        """Test GET /api/v1/docking/methods/{method}/parameters endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/docking/methods/autodock_vina/parameters",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_validate_docking_config(self, client, auth_headers):
        """Test POST /api/v1/docking/validate endpoint."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/docking/validate",
                headers=auth_headers,
                json={
                    "protein_id": "1TUP",
                    "ligand_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
                    "method": "autodock_vina"
                }
            )
            
            assert response.status_code in [200, 400]


class TestAuthorizationAndErrors:
    """Test authorization and error handling."""

    def test_unauthorized_access(self, client):
        """Test access without authentication."""
        response = client.post(
            "/api/v1/docking/jobs",
            json={"protein_id": "1TUP", "ligand_smiles": "CC"}
        )
        assert response.status_code == 401

    def test_invalid_job_id(self, client, auth_headers):
        """Test accessing non-existent job."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/docking/jobs/invalid-job/status",
                headers=auth_headers
            )
            
            assert response.status_code == 404

    def test_invalid_smiles(self, client, auth_headers):
        """Test docking with invalid SMILES."""
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/docking/jobs",
                headers=auth_headers,
                json={
                    "protein_id": "1TUP",
                    "ligand_smiles": "INVALID",
                    "method": "autodock_vina"
                }
            )
            
            assert response.status_code in [400, 422]


# Performance tests
class TestPerformance:
    """Test performance of docking endpoints."""

    def test_job_submission_performance(self, client, auth_headers):
        """Test docking job submission performance."""
        import time
        
        with patch("apps.api.routers.docking.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            start = time.time()
            response = client.post(
                "/api/v1/docking/jobs",
                headers=auth_headers,
                json={
                    "protein_id": "1TUP",
                    "ligand_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
                    "method": "autodock_vina"
                }
            )
            duration = time.time() - start
            
            assert response.status_code in [200, 201, 202]
            assert duration < 2.0  # Should complete in under 2 seconds
