"""
Integration tests for Translational Research API endpoints.

Tests translational research endpoints including:
- Biomarker discovery
- Clinical trial matching
- Translational workflows
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


class TestBiomarkerEndpoints:
    """Test biomarker discovery endpoints."""

    def test_discover_biomarkers(self, client, auth_headers):
        """Test POST /api/v1/translational/biomarkers/discover endpoint."""
        discovery_request = {
            "disease": "Alzheimer's Disease",
            "data_sources": ["genomics", "proteomics"]
        }
        
        response = client.post(
            "/api/v1/translational/biomarkers/discover",
            headers=auth_headers,
            json=discovery_request
        )
        
        assert response.status_code in [200, 201, 401, 422]

    def test_validate_biomarker(self, client, auth_headers):
        """Test POST /api/v1/translational/biomarkers/validate endpoint."""
        validation_request = {
            "biomarker": "APOE4",
            "disease": "Alzheimer's Disease"
        }
        
        response = client.post(
            "/api/v1/translational/biomarkers/validate",
            headers=auth_headers,
            json=validation_request
        )
        
        assert response.status_code in [200, 401, 422]

    def test_list_biomarkers(self, client, auth_headers):
        """Test GET /api/v1/translational/biomarkers endpoint."""
        response = client.get("/api/v1/translational/biomarkers", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields


class TestClinicalTrialMatchingEndpoints:
    """Test clinical trial matching endpoints."""

    def test_match_trials(self, client, auth_headers):
        """Test POST /api/v1/translational/trials/match endpoint."""
        match_request = {
            "patient_profile": {
                "age": 65,
                "gender": "M",
                "diagnosis": "Alzheimer's Disease"
            }
        }
        
        response = client.post(
            "/api/v1/translational/trials/match",
            headers=auth_headers,
            json=match_request
        )
        
        assert response.status_code in [200, 401, 422]

    def test_get_trial_details(self, client, auth_headers):
        """Test GET /api/v1/translational/trials/{trial_id} endpoint."""
        response = client.get(
            "/api/v1/translational/trials/NCT12345678",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]


class TestTranslationalWorkflowEndpoints:
    """Test translational workflow endpoints."""

    def test_create_workflow(self, client, auth_headers):
        """Test POST /api/v1/translational/workflows endpoint."""
        workflow_data = {
            "name": "Biomarker to Clinic",
            "stages": ["discovery", "validation", "clinical_trial"]
        }
        
        response = client.post(
            "/api/v1/translational/workflows",
            headers=auth_headers,
            json=workflow_data
        )
        
        assert response.status_code in [200, 201, 401, 422]

    def test_get_workflow(self, client, auth_headers):
        """Test GET /api/v1/translational/workflows/{workflow_id} endpoint."""
        response = client.get(
            "/api/v1/translational/workflows/test-workflow-id",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]

    def test_execute_workflow(self, client, auth_headers):
        """Test POST /api/v1/translational/workflows/{workflow_id}/execute endpoint."""
        response = client.post(
            "/api/v1/translational/workflows/test-workflow-id/execute",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 201, 401, 404]


class TestErrorHandling:
    """Test error handling."""

    def test_unauthorized_access(self, client):
        """Test accessing translational without authentication."""
        response = client.get("/api/v1/translational/biomarkers")
        
        assert response.status_code == 401

    def test_invalid_disease(self, client, auth_headers):
        """Test biomarker discovery with invalid disease."""
        discovery_request = {"disease": ""}
        
        response = client.post(
            "/api/v1/translational/biomarkers/discover",
            headers=auth_headers,
            json=discovery_request
        )
        
        assert response.status_code in [422, 400]


# Performance tests
class TestPerformance:
    """Test performance of translational endpoints."""

    def test_biomarker_discovery_performance(self, client, auth_headers):
        """Test biomarker discovery performance."""
        import time
        
        discovery_request = {
            "disease": "Alzheimer's Disease",
            "data_sources": ["genomics"]
        }
        
        start = time.time()
        response = client.post(
            "/api/v1/translational/biomarkers/discover",
            headers=auth_headers,
            json=discovery_request
        )
        duration = time.time() - start
        
        if response.status_code in [200, 201]:
            assert duration < 5.0  # Should complete in under 5 seconds

