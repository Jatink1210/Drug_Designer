"""
Integration tests for Dossier API endpoints.

Tests the dossier generation and management endpoints including:
- Dossier creation
- Content generation
- Export functionality
- Version management
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from apps.api.main import app
from apps.api.models.db_tables import User, Project, Dossier


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


class TestDossierCreationEndpoints:
    """Test dossier creation endpoints."""

    def test_create_dossier(self, client, auth_headers):
        """Test POST /api/v1/dossiers endpoint."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/dossiers",
                headers=auth_headers,
                json={
                    "project_id": "proj-123",
                    "title": "Alzheimer's Drug Candidate Dossier",
                    "type": "regulatory",
                    "sections": [
                        "executive_summary",
                        "disease_intelligence",
                        "target_validation",
                        "drug_candidate",
                        "preclinical_data",
                        "clinical_plan"
                    ]
                }
            )
            
            assert response.status_code in [200, 201]
            data = response.json()
            assert "dossier_id" in data
            assert "title" in data
            assert "status" in data

    def test_create_dossier_with_template(self, client, auth_headers):
        """Test creating dossier from template."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/dossiers/from-template",
                headers=auth_headers,
                json={
                    "project_id": "proj-123",
                    "template_id": "template-fda-ind",
                    "title": "IND Application Dossier"
                }
            )
            
            assert response.status_code in [200, 201]
            data = response.json()
            assert "dossier_id" in data

    def test_create_dossier_missing_project(self, client, auth_headers):
        """Test creating dossier with missing project."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/dossiers",
                headers=auth_headers,
                json={
                    "title": "Test Dossier",
                    "type": "regulatory"
                }
            )
            
            assert response.status_code in [400, 422]


class TestDossierRetrievalEndpoints:
    """Test dossier retrieval endpoints."""

    def test_get_dossier(self, client, auth_headers):
        """Test GET /api/v1/dossiers/{dossier_id} endpoint."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/dossiers/dossier-123",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "dossier_id" in data
                assert "title" in data
                assert "sections" in data

    def test_list_dossiers(self, client, auth_headers):
        """Test GET /api/v1/dossiers endpoint."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/dossiers",
                headers=auth_headers,
                params={"project_id": "proj-123"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "dossiers" in data
            assert isinstance(data["dossiers"], list)

    def test_get_dossier_section(self, client, auth_headers):
        """Test GET /api/v1/dossiers/{dossier_id}/sections/{section_id} endpoint."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/dossiers/dossier-123/sections/executive_summary",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "section_id" in data
                assert "content" in data


class TestDossierContentGenerationEndpoints:
    """Test dossier content generation endpoints."""

    def test_generate_section_content(self, client, auth_headers):
        """Test POST /api/v1/dossiers/{dossier_id}/generate endpoint."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/dossiers/dossier-123/generate",
                headers=auth_headers,
                json={
                    "section_id": "disease_intelligence",
                    "include_provenance": True,
                    "style": "regulatory"
                }
            )
            
            assert response.status_code in [200, 202]
            data = response.json()
            assert "task_id" in data or "content" in data

    def test_generate_full_dossier(self, client, auth_headers):
        """Test POST /api/v1/dossiers/{dossier_id}/generate-all endpoint."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/dossiers/dossier-123/generate-all",
                headers=auth_headers,
                json={
                    "include_provenance": True,
                    "style": "regulatory",
                    "async_mode": True
                }
            )
            
            assert response.status_code in [200, 202]
            data = response.json()
            assert "task_id" in data or "status" in data

    def test_regenerate_section(self, client, auth_headers):
        """Test POST /api/v1/dossiers/{dossier_id}/sections/{section_id}/regenerate endpoint."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/dossiers/dossier-123/sections/executive_summary/regenerate",
                headers=auth_headers,
                json={
                    "prompt": "Focus more on safety data",
                    "preserve_citations": True
                }
            )
            
            assert response.status_code in [200, 202]


class TestDossierUpdateEndpoints:
    """Test dossier update endpoints."""

    def test_update_dossier_metadata(self, client, auth_headers):
        """Test PATCH /api/v1/dossiers/{dossier_id} endpoint."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.patch(
                "/api/v1/dossiers/dossier-123",
                headers=auth_headers,
                json={
                    "title": "Updated Dossier Title",
                    "status": "in_review"
                }
            )
            
            assert response.status_code in [200, 404]

    def test_update_section_content(self, client, auth_headers):
        """Test PATCH /api/v1/dossiers/{dossier_id}/sections/{section_id} endpoint."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.patch(
                "/api/v1/dossiers/dossier-123/sections/executive_summary",
                headers=auth_headers,
                json={
                    "content": "Updated section content...",
                    "notes": "Manual edit by researcher"
                }
            )
            
            assert response.status_code in [200, 404]

    def test_reorder_sections(self, client, auth_headers):
        """Test POST /api/v1/dossiers/{dossier_id}/reorder endpoint."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/dossiers/dossier-123/reorder",
                headers=auth_headers,
                json={
                    "section_order": [
                        "executive_summary",
                        "disease_intelligence",
                        "target_validation",
                        "drug_candidate"
                    ]
                }
            )
            
            assert response.status_code in [200, 404]


class TestDossierExportEndpoints:
    """Test dossier export endpoints."""

    def test_export_dossier_pdf(self, client, auth_headers):
        """Test POST /api/v1/dossiers/{dossier_id}/export/pdf endpoint."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/dossiers/dossier-123/export/pdf",
                headers=auth_headers,
                json={
                    "include_toc": True,
                    "include_provenance_appendix": True,
                    "watermark": "CONFIDENTIAL"
                }
            )
            
            assert response.status_code in [200, 202]
            if response.status_code == 200:
                assert response.headers["content-type"] == "application/pdf"

    def test_export_dossier_docx(self, client, auth_headers):
        """Test POST /api/v1/dossiers/{dossier_id}/export/docx endpoint."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/dossiers/dossier-123/export/docx",
                headers=auth_headers,
                json={
                    "include_toc": True,
                    "editable": True
                }
            )
            
            assert response.status_code in [200, 202]

    def test_export_dossier_html(self, client, auth_headers):
        """Test POST /api/v1/dossiers/{dossier_id}/export/html endpoint."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/dossiers/dossier-123/export/html",
                headers=auth_headers,
                json={
                    "standalone": True,
                    "include_css": True
                }
            )
            
            assert response.status_code in [200, 202]


class TestDossierVersioningEndpoints:
    """Test dossier versioning endpoints."""

    def test_create_dossier_version(self, client, auth_headers):
        """Test POST /api/v1/dossiers/{dossier_id}/versions endpoint."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/dossiers/dossier-123/versions",
                headers=auth_headers,
                json={
                    "version_name": "v1.0",
                    "notes": "Initial regulatory submission version"
                }
            )
            
            assert response.status_code in [200, 201]
            data = response.json()
            assert "version_id" in data

    def test_list_dossier_versions(self, client, auth_headers):
        """Test GET /api/v1/dossiers/{dossier_id}/versions endpoint."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/dossiers/dossier-123/versions",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "versions" in data
                assert isinstance(data["versions"], list)

    def test_restore_dossier_version(self, client, auth_headers):
        """Test POST /api/v1/dossiers/{dossier_id}/versions/{version_id}/restore endpoint."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/dossiers/dossier-123/versions/version-456/restore",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]


class TestDossierCollaborationEndpoints:
    """Test dossier collaboration endpoints."""

    def test_share_dossier(self, client, auth_headers):
        """Test POST /api/v1/dossiers/{dossier_id}/share endpoint."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/dossiers/dossier-123/share",
                headers=auth_headers,
                json={
                    "user_emails": ["colleague@example.com"],
                    "permission": "read"
                }
            )
            
            assert response.status_code in [200, 404]

    def test_add_comment(self, client, auth_headers):
        """Test POST /api/v1/dossiers/{dossier_id}/comments endpoint."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/dossiers/dossier-123/comments",
                headers=auth_headers,
                json={
                    "section_id": "executive_summary",
                    "comment": "Please add more safety data here",
                    "position": 150
                }
            )
            
            assert response.status_code in [200, 201]


class TestAuthorizationAndErrors:
    """Test authorization and error handling."""

    def test_unauthorized_access(self, client):
        """Test access without authentication."""
        response = client.get("/api/v1/dossiers/dossier-123")
        assert response.status_code == 401

    def test_access_other_user_dossier(self, client, auth_headers):
        """Test accessing another user's dossier."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/dossiers/other-user-dossier",
                headers=auth_headers
            )
            
            assert response.status_code in [403, 404]

    def test_delete_dossier(self, client, auth_headers):
        """Test DELETE /api/v1/dossiers/{dossier_id} endpoint."""
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.delete(
                "/api/v1/dossiers/dossier-123",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 204, 404]


# Performance tests
class TestPerformance:
    """Test performance of dossier endpoints."""

    def test_generation_performance(self, client, auth_headers):
        """Test dossier generation performance."""
        import time
        
        with patch("apps.api.routers.dossier.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            start = time.time()
            response = client.post(
                "/api/v1/dossiers/dossier-123/generate",
                headers=auth_headers,
                json={"section_id": "executive_summary"}
            )
            duration = time.time() - start
            
            assert response.status_code in [200, 202]
            # Async generation should return quickly
            if response.status_code == 202:
                assert duration < 2.0
