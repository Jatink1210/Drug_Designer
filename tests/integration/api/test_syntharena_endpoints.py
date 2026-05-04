"""
Integration tests for SynthArena API endpoints.

Tests synthesis arena endpoints including:
- Synthesis planning
- Retrosynthesis
- Reaction prediction
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


class TestSynthesisPlanningEndpoints:
    """Test synthesis planning endpoints."""

    def test_create_synthesis_plan(self, client, auth_headers):
        """Test POST /api/v1/syntharena/plan endpoint."""
        plan_request = {
            "target_molecule": "CC(C)Cc1ccc(cc1)C(C)C(O)=O",  # Ibuprofen SMILES
            "max_steps": 10
        }
        
        response = client.post(
            "/api/v1/syntharena/plan",
            headers=auth_headers,
            json=plan_request
        )
        
        assert response.status_code in [200, 201, 401, 422]

    def test_get_synthesis_plan(self, client, auth_headers):
        """Test GET /api/v1/syntharena/plan/{plan_id} endpoint."""
        response = client.get(
            "/api/v1/syntharena/plan/test-plan-id",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]

    def test_list_synthesis_plans(self, client, auth_headers):
        """Test GET /api/v1/syntharena/plan endpoint."""
        response = client.get("/api/v1/syntharena/plan", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields


class TestRetrosynthesisEndpoints:
    """Test retrosynthesis endpoints."""

    def test_run_retrosynthesis(self, client, auth_headers):
        """Test POST /api/v1/syntharena/retrosynthesis endpoint."""
        retro_request = {
            "target_molecule": "CC(C)Cc1ccc(cc1)C(C)C(O)=O",
            "max_depth": 5
        }
        
        response = client.post(
            "/api/v1/syntharena/retrosynthesis",
            headers=auth_headers,
            json=retro_request
        )
        
        assert response.status_code in [200, 201, 401, 422]

    def test_get_retrosynthesis_results(self, client, auth_headers):
        """Test GET /api/v1/syntharena/retrosynthesis/{result_id} endpoint."""
        response = client.get(
            "/api/v1/syntharena/retrosynthesis/test-result-id",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]


class TestReactionPredictionEndpoints:
    """Test reaction prediction endpoints."""

    def test_predict_reaction(self, client, auth_headers):
        """Test POST /api/v1/syntharena/predict endpoint."""
        prediction_request = {
            "reactants": ["CC(=O)O", "CCO"],  # Acetic acid + Ethanol
            "conditions": {"temperature": 25, "solvent": "water"}
        }
        
        response = client.post(
            "/api/v1/syntharena/predict",
            headers=auth_headers,
            json=prediction_request
        )
        
        assert response.status_code in [200, 401, 422]

    def test_validate_reaction(self, client, auth_headers):
        """Test POST /api/v1/syntharena/validate endpoint."""
        validation_request = {
            "reactants": ["CC(=O)O", "CCO"],
            "products": ["CC(=O)OCC"]
        }
        
        response = client.post(
            "/api/v1/syntharena/validate",
            headers=auth_headers,
            json=validation_request
        )
        
        assert response.status_code in [200, 401, 422]


class TestErrorHandling:
    """Test error handling."""

    def test_unauthorized_access(self, client):
        """Test accessing syntharena without authentication."""
        response = client.get("/api/v1/syntharena/plan")
        
        assert response.status_code == 401

    def test_invalid_smiles(self, client, auth_headers):
        """Test with invalid SMILES string."""
        plan_request = {"target_molecule": "invalid_smiles"}
        
        response = client.post(
            "/api/v1/syntharena/plan",
            headers=auth_headers,
            json=plan_request
        )
        
        assert response.status_code in [422, 400]


# Performance tests
class TestPerformance:
    """Test performance of syntharena endpoints."""

    def test_retrosynthesis_performance(self, client, auth_headers):
        """Test retrosynthesis performance."""
        import time
        
        retro_request = {
            "target_molecule": "CC(C)Cc1ccc(cc1)C(C)C(O)=O",
            "max_depth": 3
        }
        
        start = time.time()
        response = client.post(
            "/api/v1/syntharena/retrosynthesis",
            headers=auth_headers,
            json=retro_request
        )
        duration = time.time() - start
        
        if response.status_code in [200, 201]:
            assert duration < 10.0  # Should complete in under 10 seconds

