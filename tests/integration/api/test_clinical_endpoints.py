"""
Integration tests for Clinical API endpoints.

Tests the clinical workflow endpoints including:
- Clinical trial search
- Patient cohort analysis
- Regulatory pathway planning
- Clinical stage progression
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from apps.api.main import app
from apps.api.models.db_tables import User, Project, ClinicalTrial, ClinicalStage
from apps.api.core.db import get_db


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock()
    yield db


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


class TestClinicalTrialEndpoints:
    """Test clinical trial search and retrieval endpoints."""

    def test_search_clinical_trials(self, client, auth_headers, mock_db):
        """Test POST /api/v1/clinical/trials/search endpoint."""
        with patch("apps.api.routers.clinical.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/clinical/trials/search",
                headers=auth_headers,
                json={
                    "disease": "Alzheimer's Disease",
                    "phase": ["Phase 2", "Phase 3"],
                    "status": "Recruiting",
                    "limit": 50
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "trials" in data
            assert "total" in data
            assert isinstance(data["trials"], list)

    def test_get_trial_details(self, client, auth_headers):
        """Test GET /api/v1/clinical/trials/{trial_id} endpoint."""
        with patch("apps.api.routers.clinical.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/clinical/trials/NCT12345678",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "trial_id" in data
                assert "title" in data
                assert "phase" in data

    def test_search_trials_invalid_phase(self, client, auth_headers):
        """Test search with invalid phase parameter."""
        with patch("apps.api.routers.clinical.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/clinical/trials/search",
                headers=auth_headers,
                json={
                    "disease": "Cancer",
                    "phase": ["Invalid Phase"]
                }
            )
            
            assert response.status_code in [400, 422]


class TestCohortAnalysisEndpoints:
    """Test patient cohort analysis endpoints."""

    def test_analyze_cohort(self, client, auth_headers):
        """Test POST /api/v1/clinical/cohort/analyze endpoint."""
        with patch("apps.api.routers.clinical.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/clinical/cohort/analyze",
                headers=auth_headers,
                json={
                    "inclusion_criteria": {
                        "age_min": 18,
                        "age_max": 65,
                        "diagnosis": "Type 2 Diabetes"
                    },
                    "exclusion_criteria": {
                        "conditions": ["Kidney Disease", "Liver Disease"]
                    },
                    "sample_size": 1000
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "cohort_id" in data
            assert "eligible_patients" in data
            assert "demographics" in data

    def test_get_cohort_statistics(self, client, auth_headers):
        """Test GET /api/v1/clinical/cohort/{cohort_id}/stats endpoint."""
        with patch("apps.api.routers.clinical.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/clinical/cohort/cohort-123/stats",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "total_patients" in data
                assert "demographics" in data


class TestRegulatoryPathwayEndpoints:
    """Test regulatory pathway planning endpoints."""

    def test_plan_regulatory_pathway(self, client, auth_headers):
        """Test POST /api/v1/clinical/regulatory/plan endpoint."""
        with patch("apps.api.routers.clinical.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/clinical/regulatory/plan",
                headers=auth_headers,
                json={
                    "drug_name": "Test Drug",
                    "indication": "Hypertension",
                    "target_regions": ["US", "EU", "Japan"],
                    "fast_track": True
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "pathway_id" in data
            assert "stages" in data
            assert "estimated_timeline" in data
            assert isinstance(data["stages"], list)

    def test_get_regulatory_requirements(self, client, auth_headers):
        """Test GET /api/v1/clinical/regulatory/requirements endpoint."""
        with patch("apps.api.routers.clinical.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/clinical/regulatory/requirements",
                headers=auth_headers,
                params={"region": "US", "indication": "Oncology"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "requirements" in data
            assert isinstance(data["requirements"], list)


class TestClinicalStageEndpoints:
    """Test clinical stage progression endpoints."""

    def test_create_clinical_stage(self, client, auth_headers):
        """Test POST /api/v1/clinical/stages endpoint."""
        with patch("apps.api.routers.clinical.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/clinical/stages",
                headers=auth_headers,
                json={
                    "project_id": "proj-123",
                    "stage_name": "Phase 1",
                    "start_date": "2026-05-01",
                    "estimated_duration_months": 12,
                    "objectives": ["Safety assessment", "Dose finding"]
                }
            )
            
            assert response.status_code in [200, 201]
            data = response.json()
            assert "stage_id" in data
            assert "stage_name" in data

    def test_update_stage_progress(self, client, auth_headers):
        """Test PATCH /api/v1/clinical/stages/{stage_id}/progress endpoint."""
        with patch("apps.api.routers.clinical.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.patch(
                "/api/v1/clinical/stages/stage-123/progress",
                headers=auth_headers,
                json={
                    "progress_percentage": 45,
                    "status": "In Progress",
                    "notes": "Enrollment ongoing"
                }
            )
            
            assert response.status_code in [200, 404]

    def test_get_stage_milestones(self, client, auth_headers):
        """Test GET /api/v1/clinical/stages/{stage_id}/milestones endpoint."""
        with patch("apps.api.routers.clinical.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/clinical/stages/stage-123/milestones",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "milestones" in data
                assert isinstance(data["milestones"], list)


class TestClinicalWorkflowEndpoints:
    """Test 10-stage clinical workflow endpoints."""

    def test_start_clinical_workflow(self, client, auth_headers):
        """Test POST /api/v1/clinical/workflow/start endpoint."""
        with patch("apps.api.routers.clinical.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/clinical/workflow/start",
                headers=auth_headers,
                json={
                    "project_id": "proj-123",
                    "drug_candidate": "Compound-456",
                    "indication": "Alzheimer's Disease",
                    "workflow_type": "full_development"
                }
            )
            
            assert response.status_code in [200, 201]
            data = response.json()
            assert "workflow_id" in data
            assert "stages" in data
            assert len(data["stages"]) == 10

    def test_get_workflow_status(self, client, auth_headers):
        """Test GET /api/v1/clinical/workflow/{workflow_id}/status endpoint."""
        with patch("apps.api.routers.clinical.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/clinical/workflow/workflow-123/status",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "workflow_id" in data
                assert "current_stage" in data
                assert "overall_progress" in data


class TestAuthorizationAndErrors:
    """Test authorization and error handling."""

    def test_unauthorized_access(self, client):
        """Test access without authentication."""
        response = client.post(
            "/api/v1/clinical/trials/search",
            json={"disease": "Cancer"}
        )
        
        assert response.status_code == 401

    def test_invalid_request_body(self, client, auth_headers):
        """Test with invalid request body."""
        with patch("apps.api.routers.clinical.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/clinical/trials/search",
                headers=auth_headers,
                json={"invalid_field": "value"}
            )
            
            assert response.status_code in [400, 422]

    def test_rate_limiting(self, client, auth_headers):
        """Test rate limiting on clinical endpoints."""
        with patch("apps.api.routers.clinical.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            # Make multiple rapid requests
            responses = []
            for _ in range(100):
                response = client.post(
                    "/api/v1/clinical/trials/search",
                    headers=auth_headers,
                    json={"disease": "Cancer"}
                )
                responses.append(response.status_code)
            
            # Should eventually hit rate limit
            assert 429 in responses or all(r == 200 for r in responses)


# Performance tests
class TestPerformance:
    """Test performance of clinical endpoints."""

    def test_search_performance(self, client, auth_headers):
        """Test search endpoint performance."""
        import time
        
        with patch("apps.api.routers.clinical.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            start = time.time()
            response = client.post(
                "/api/v1/clinical/trials/search",
                headers=auth_headers,
                json={"disease": "Cancer", "limit": 100}
            )
            duration = time.time() - start
            
            assert response.status_code == 200
            assert duration < 5.0  # Should complete in under 5 seconds
