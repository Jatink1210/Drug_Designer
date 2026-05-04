"""
Integration tests for Reports API endpoints.

Tests the report generation endpoints including:
- Report creation
- Report templates
- Report export
- Report scheduling
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


class TestReportCreationEndpoints:
    """Test report creation endpoints."""

    def test_create_report(self, client, auth_headers):
        """Test POST /api/v1/reports endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/reports",
                headers=auth_headers,
                json={
                    "title": "Drug Discovery Report",
                    "type": "project_summary",
                    "project_id": "project-123"
                }
            )
            
            assert response.status_code in [200, 201, 202]

    def test_list_reports(self, client, auth_headers):
        """Test GET /api/v1/reports endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/reports",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "reports" in data

    def test_get_report(self, client, auth_headers):
        """Test GET /api/v1/reports/{report_id} endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/reports/report-123",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_update_report(self, client, auth_headers):
        """Test PUT /api/v1/reports/{report_id} endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.put(
                "/api/v1/reports/report-123",
                headers=auth_headers,
                json={"title": "Updated Report"}
            )
            
            assert response.status_code in [200, 404]

    def test_delete_report(self, client, auth_headers):
        """Test DELETE /api/v1/reports/{report_id} endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.delete(
                "/api/v1/reports/report-123",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 204, 404]


class TestReportTemplateEndpoints:
    """Test report template endpoints."""

    def test_list_templates(self, client, auth_headers):
        """Test GET /api/v1/reports/templates endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/reports/templates",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "templates" in data

    def test_get_template(self, client, auth_headers):
        """Test GET /api/v1/reports/templates/{template_id} endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/reports/templates/template-123",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_create_from_template(self, client, auth_headers):
        """Test POST /api/v1/reports/from-template endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/reports/from-template",
                headers=auth_headers,
                json={
                    "template_id": "template-123",
                    "project_id": "project-123",
                    "parameters": {"include_graphs": True}
                }
            )
            
            assert response.status_code in [200, 201, 202]


class TestReportExportEndpoints:
    """Test report export endpoints."""

    def test_export_pdf(self, client, auth_headers):
        """Test GET /api/v1/reports/{report_id}/export/pdf endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/reports/report-123/export/pdf",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_export_docx(self, client, auth_headers):
        """Test GET /api/v1/reports/{report_id}/export/docx endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/reports/report-123/export/docx",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_export_html(self, client, auth_headers):
        """Test GET /api/v1/reports/{report_id}/export/html endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/reports/report-123/export/html",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_export_with_options(self, client, auth_headers):
        """Test POST /api/v1/reports/{report_id}/export endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/reports/report-123/export",
                headers=auth_headers,
                json={
                    "format": "pdf",
                    "include_appendix": True,
                    "include_raw_data": False
                }
            )
            
            assert response.status_code in [200, 202, 404]


class TestReportSectionEndpoints:
    """Test report section endpoints."""

    def test_get_report_sections(self, client, auth_headers):
        """Test GET /api/v1/reports/{report_id}/sections endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/reports/report-123/sections",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_add_section(self, client, auth_headers):
        """Test POST /api/v1/reports/{report_id}/sections endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/reports/report-123/sections",
                headers=auth_headers,
                json={
                    "title": "Results",
                    "content": "Analysis results...",
                    "order": 1
                }
            )
            
            assert response.status_code in [200, 201, 404]

    def test_update_section(self, client, auth_headers):
        """Test PUT /api/v1/reports/{report_id}/sections/{section_id} endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.put(
                "/api/v1/reports/report-123/sections/section-1",
                headers=auth_headers,
                json={"content": "Updated content"}
            )
            
            assert response.status_code in [200, 404]

    def test_delete_section(self, client, auth_headers):
        """Test DELETE /api/v1/reports/{report_id}/sections/{section_id} endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.delete(
                "/api/v1/reports/report-123/sections/section-1",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 204, 404]


class TestReportSchedulingEndpoints:
    """Test report scheduling endpoints."""

    def test_schedule_report(self, client, auth_headers):
        """Test POST /api/v1/reports/schedule endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/reports/schedule",
                headers=auth_headers,
                json={
                    "template_id": "template-123",
                    "project_id": "project-123",
                    "frequency": "weekly",
                    "recipients": ["user@example.com"]
                }
            )
            
            assert response.status_code in [200, 201]

    def test_list_scheduled_reports(self, client, auth_headers):
        """Test GET /api/v1/reports/scheduled endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/reports/scheduled",
                headers=auth_headers
            )
            
            assert response.status_code == 200

    def test_cancel_scheduled_report(self, client, auth_headers):
        """Test DELETE /api/v1/reports/scheduled/{schedule_id} endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.delete(
                "/api/v1/reports/scheduled/schedule-123",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 204, 404]


class TestReportSharingEndpoints:
    """Test report sharing endpoints."""

    def test_share_report(self, client, auth_headers):
        """Test POST /api/v1/reports/{report_id}/share endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/reports/report-123/share",
                headers=auth_headers,
                json={
                    "user_ids": ["user-456", "user-789"],
                    "permission": "read"
                }
            )
            
            assert response.status_code in [200, 404]

    def test_get_shared_users(self, client, auth_headers):
        """Test GET /api/v1/reports/{report_id}/shared endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/reports/report-123/shared",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_revoke_access(self, client, auth_headers):
        """Test DELETE /api/v1/reports/{report_id}/share/{user_id} endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.delete(
                "/api/v1/reports/report-123/share/user-456",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 204, 404]


class TestReportGenerationEndpoints:
    """Test report generation endpoints."""

    def test_generate_summary_report(self, client, auth_headers):
        """Test POST /api/v1/reports/generate/summary endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/reports/generate/summary",
                headers=auth_headers,
                json={"project_id": "project-123"}
            )
            
            assert response.status_code in [200, 202]

    def test_generate_analysis_report(self, client, auth_headers):
        """Test POST /api/v1/reports/generate/analysis endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/reports/generate/analysis",
                headers=auth_headers,
                json={
                    "project_id": "project-123",
                    "analysis_type": "target_prioritization"
                }
            )
            
            assert response.status_code in [200, 202]

    def test_generate_progress_report(self, client, auth_headers):
        """Test POST /api/v1/reports/generate/progress endpoint."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/reports/generate/progress",
                headers=auth_headers,
                json={
                    "project_id": "project-123",
                    "date_range": {"start": "2026-01-01", "end": "2026-04-23"}
                }
            )
            
            assert response.status_code in [200, 202]


class TestAuthorizationAndErrors:
    """Test authorization and error handling."""

    def test_unauthorized_access(self, client):
        """Test access without authentication."""
        response = client.get("/api/v1/reports")
        assert response.status_code == 401

    def test_invalid_report_id(self, client, auth_headers):
        """Test accessing non-existent report."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/reports/invalid-report",
                headers=auth_headers
            )
            
            assert response.status_code == 404

    def test_invalid_template_id(self, client, auth_headers):
        """Test creating report with invalid template."""
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/reports/from-template",
                headers=auth_headers,
                json={
                    "template_id": "invalid-template",
                    "project_id": "project-123"
                }
            )
            
            assert response.status_code in [400, 404, 422]


# Performance tests
class TestPerformance:
    """Test performance of report endpoints."""

    def test_report_generation_performance(self, client, auth_headers):
        """Test report generation performance."""
        import time
        
        with patch("apps.api.routers.reports.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            start = time.time()
            response = client.post(
                "/api/v1/reports/generate/summary",
                headers=auth_headers,
                json={"project_id": "project-123"}
            )
            duration = time.time() - start
            
            assert response.status_code in [200, 202]
            assert duration < 3.0  # Should complete in under 3 seconds
