"""
Integration tests for Scenario API endpoints.

Tests the scenario management endpoints including:
- Scenario creation and configuration
- Scenario execution
- Scenario comparison
- What-if analysis
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import datetime

from apps.api.main import app
from apps.api.models.db_tables import User, Project, Scenario


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


class TestScenarioCreationEndpoints:
    """Test scenario creation endpoints."""

    def test_create_scenario(self, client, auth_headers):
        """Test POST /api/v1/scenarios endpoint."""
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/scenarios",
                headers=auth_headers,
                json={
                    "project_id": "proj-123",
                    "name": "High Affinity Scenario",
                    "description": "Optimize for high target affinity",
                    "parameters": {
                        "target_affinity_threshold": 8.0,
                        "selectivity_ratio": 100,
                        "admet_filters": ["lipinski", "veber"]
                    }
                }
            )
            
            assert response.status_code in [200, 201]
            data = response.json()
            assert "scenario_id" in data
            assert "name" in data

    def test_create_scenario_from_template(self, client, auth_headers):
        """Test POST /api/v1/scenarios/from-template endpoint."""
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/scenarios/from-template",
                headers=auth_headers,
                json={
                    "project_id": "proj-123",
                    "template_id": "template-lead-optimization",
                    "name": "Lead Optimization Scenario"
                }
            )
            
            assert response.status_code in [200, 201]

    def test_clone_scenario(self, client, auth_headers):
        """Test POST /api/v1/scenarios/{scenario_id}/clone endpoint."""
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/scenarios/scenario-123/clone",
                headers=auth_headers,
                json={"name": "Cloned Scenario"}
            )
            
            assert response.status_code in [200, 201, 404]


class TestScenarioRetrievalEndpoints:
    """Test scenario retrieval endpoints."""

    def test_get_scenario(self, client, auth_headers):
        """Test GET /api/v1/scenarios/{scenario_id} endpoint."""
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/scenarios/scenario-123",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "scenario_id" in data
                assert "name" in data
                assert "parameters" in data

    def test_list_scenarios(self, client, auth_headers):
        """Test GET /api/v1/scenarios endpoint."""
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/scenarios",
                headers=auth_headers,
                params={"project_id": "proj-123"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "scenarios" in data
            assert isinstance(data["scenarios"], list)

    def test_get_scenario_templates(self, client, auth_headers):
        """Test GET /api/v1/scenarios/templates endpoint."""
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/scenarios/templates",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "templates" in data
            assert isinstance(data["templates"], list)


class TestScenarioExecutionEndpoints:
    """Test scenario execution endpoints."""

    def test_execute_scenario(self, client, auth_headers):
        """Test POST /api/v1/scenarios/{scenario_id}/execute endpoint."""
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/scenarios/scenario-123/execute",
                headers=auth_headers,
                json={"async_mode": True}
            )
            
            assert response.status_code in [200, 202, 404]
            if response.status_code in [200, 202]:
                data = response.json()
                assert "run_id" in data or "task_id" in data

    def test_get_scenario_results(self, client, auth_headers):
        """Test GET /api/v1/scenarios/{scenario_id}/results endpoint."""
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/scenarios/scenario-123/results",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "results" in data

    def test_get_scenario_metrics(self, client, auth_headers):
        """Test GET /api/v1/scenarios/{scenario_id}/metrics endpoint."""
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/scenarios/scenario-123/metrics",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]


class TestScenarioUpdateEndpoints:
    """Test scenario update endpoints."""

    def test_update_scenario(self, client, auth_headers):
        """Test PATCH /api/v1/scenarios/{scenario_id} endpoint."""
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.patch(
                "/api/v1/scenarios/scenario-123",
                headers=auth_headers,
                json={
                    "name": "Updated Scenario Name",
                    "parameters": {
                        "target_affinity_threshold": 9.0
                    }
                }
            )
            
            assert response.status_code in [200, 404]

    def test_update_scenario_parameters(self, client, auth_headers):
        """Test PATCH /api/v1/scenarios/{scenario_id}/parameters endpoint."""
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.patch(
                "/api/v1/scenarios/scenario-123/parameters",
                headers=auth_headers,
                json={
                    "target_affinity_threshold": 9.5,
                    "selectivity_ratio": 150
                }
            )
            
            assert response.status_code in [200, 404]


class TestScenarioComparisonEndpoints:
    """Test scenario comparison endpoints."""

    def test_compare_scenarios(self, client, auth_headers):
        """Test POST /api/v1/scenarios/compare endpoint."""
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/scenarios/compare",
                headers=auth_headers,
                json={
                    "scenario_ids": ["scenario-123", "scenario-456", "scenario-789"],
                    "metrics": ["affinity", "selectivity", "admet_score"]
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "comparison" in data

    def test_get_scenario_diff(self, client, auth_headers):
        """Test GET /api/v1/scenarios/{scenario_id}/diff/{other_scenario_id} endpoint."""
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/scenarios/scenario-123/diff/scenario-456",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "differences" in data


class TestWhatIfAnalysisEndpoints:
    """Test what-if analysis endpoints."""

    def test_run_what_if_analysis(self, client, auth_headers):
        """Test POST /api/v1/scenarios/{scenario_id}/what-if endpoint."""
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/scenarios/scenario-123/what-if",
                headers=auth_headers,
                json={
                    "parameter_variations": {
                        "target_affinity_threshold": [7.0, 8.0, 9.0, 10.0],
                        "selectivity_ratio": [50, 100, 150, 200]
                    }
                }
            )
            
            assert response.status_code in [200, 202]
            data = response.json()
            assert "analysis_id" in data or "task_id" in data

    def test_get_what_if_results(self, client, auth_headers):
        """Test GET /api/v1/scenarios/what-if/{analysis_id}/results endpoint."""
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/scenarios/what-if/analysis-123/results",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]


class TestScenarioOptimizationEndpoints:
    """Test scenario optimization endpoints."""

    def test_optimize_scenario(self, client, auth_headers):
        """Test POST /api/v1/scenarios/{scenario_id}/optimize endpoint."""
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/scenarios/scenario-123/optimize",
                headers=auth_headers,
                json={
                    "objective": "maximize_affinity",
                    "constraints": {
                        "admet_score_min": 0.7,
                        "selectivity_ratio_min": 100
                    },
                    "algorithm": "bayesian_optimization"
                }
            )
            
            assert response.status_code in [200, 202]

    def test_get_optimization_progress(self, client, auth_headers):
        """Test GET /api/v1/scenarios/optimize/{optimization_id}/progress endpoint."""
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/scenarios/optimize/opt-123/progress",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]


class TestAuthorizationAndErrors:
    """Test authorization and error handling."""

    def test_unauthorized_access(self, client):
        """Test access without authentication."""
        response = client.get("/api/v1/scenarios/scenario-123")
        assert response.status_code == 401

    def test_delete_scenario(self, client, auth_headers):
        """Test DELETE /api/v1/scenarios/{scenario_id} endpoint."""
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.delete(
                "/api/v1/scenarios/scenario-123",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 204, 404]

    def test_invalid_parameters(self, client, auth_headers):
        """Test creating scenario with invalid parameters."""
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/scenarios",
                headers=auth_headers,
                json={
                    "project_id": "proj-123",
                    "name": "Test",
                    "parameters": {
                        "invalid_param": "value"
                    }
                }
            )
            
            assert response.status_code in [400, 422]


# Performance tests
class TestPerformance:
    """Test performance of scenario endpoints."""

    def test_scenario_execution_performance(self, client, auth_headers):
        """Test scenario execution performance."""
        import time
        
        with patch("apps.api.routers.scenarios.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            start = time.time()
            response = client.post(
                "/api/v1/scenarios/scenario-123/execute",
                headers=auth_headers,
                json={"async_mode": True}
            )
            duration = time.time() - start
            
            assert response.status_code in [200, 202, 404]
            # Async execution should return quickly
            if response.status_code == 202:
                assert duration < 2.0
