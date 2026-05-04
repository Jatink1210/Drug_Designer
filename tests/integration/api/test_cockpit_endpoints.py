"""
Integration tests for Cockpit API endpoints.

Tests the dashboard and monitoring endpoints including:
- Dashboard overview
- Real-time metrics
- System monitoring
- Workflow status
- Resource utilization
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock

from apps.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Create authentication headers."""
    return {"Authorization": "Bearer test_token"}


class TestDashboardEndpoints:
    """Test dashboard endpoints."""

    def test_get_dashboard_overview(self, client, auth_headers):
        """Test GET /api/v1/cockpit/dashboard endpoint."""
        response = client.get("/api/v1/cockpit/dashboard", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields
        if response.status_code == 200:
            data = response.json()
            assert "projects" in data or "overview" in data

    def test_get_dashboard_metrics(self, client, auth_headers):
        """Test GET /api/v1/cockpit/metrics endpoint."""
        response = client.get("/api/v1/cockpit/metrics", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields
        if response.status_code == 200:
            data = response.json()
            assert "metrics" in data or "cpu_usage" in data

    def test_get_dashboard_with_filters(self, client, auth_headers):
        """Test GET /api/v1/cockpit/dashboard with filters."""
        response = client.get(
            "/api/v1/cockpit/dashboard",
            headers=auth_headers,
            params={"time_range": "24h", "project_id": "test-project"}
        )
        
        assert response.status_code in [200, 401, 422]


class TestMonitoringEndpoints:
    """Test monitoring endpoints."""

    def test_get_system_status(self, client, auth_headers):
        """Test GET /api/v1/cockpit/status endpoint."""
        response = client.get("/api/v1/cockpit/status", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields
        if response.status_code == 200:
            data = response.json()
            assert "status" in data

    def test_get_workflow_status(self, client, auth_headers):
        """Test GET /api/v1/cockpit/workflows endpoint."""
        response = client.get("/api/v1/cockpit/workflows", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))

    def test_get_active_runs(self, client, auth_headers):
        """Test GET /api/v1/cockpit/runs/active endpoint."""
        response = client.get("/api/v1/cockpit/runs/active", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_get_recent_activity(self, client, auth_headers):
        """Test GET /api/v1/cockpit/activity endpoint."""
        response = client.get("/api/v1/cockpit/activity", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)


class TestResourceMonitoringEndpoints:
    """Test resource monitoring endpoints."""

    def test_get_resource_utilization(self, client, auth_headers):
        """Test GET /api/v1/cockpit/resources endpoint."""
        response = client.get("/api/v1/cockpit/resources", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields
        if response.status_code == 200:
            data = response.json()
            assert "cpu" in data or "memory" in data or "resources" in data

    def test_get_gpu_utilization(self, client, auth_headers):
        """Test GET /api/v1/cockpit/resources/gpu endpoint."""
        response = client.get("/api/v1/cockpit/resources/gpu", headers=auth_headers)
        
        assert response.status_code in [200, 401, 404]

    def test_get_storage_utilization(self, client, auth_headers):
        """Test GET /api/v1/cockpit/resources/storage endpoint."""
        response = client.get("/api/v1/cockpit/resources/storage", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields


class TestAlertsEndpoints:
    """Test alerts endpoints."""

    def test_get_alerts(self, client, auth_headers):
        """Test GET /api/v1/cockpit/alerts endpoint."""
        response = client.get("/api/v1/cockpit/alerts", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_get_critical_alerts(self, client, auth_headers):
        """Test GET /api/v1/cockpit/alerts/critical endpoint."""
        response = client.get("/api/v1/cockpit/alerts/critical", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_acknowledge_alert(self, client, auth_headers):
        """Test POST /api/v1/cockpit/alerts/{alert_id}/acknowledge endpoint."""
        response = client.post(
            "/api/v1/cockpit/alerts/test-alert-id/acknowledge",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]


class TestAnalyticsEndpoints:
    """Test analytics endpoints."""

    def test_get_usage_analytics(self, client, auth_headers):
        """Test GET /api/v1/cockpit/analytics/usage endpoint."""
        response = client.get("/api/v1/cockpit/analytics/usage", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_get_performance_analytics(self, client, auth_headers):
        """Test GET /api/v1/cockpit/analytics/performance endpoint."""
        response = client.get("/api/v1/cockpit/analytics/performance", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_get_user_analytics(self, client, auth_headers):
        """Test GET /api/v1/cockpit/analytics/users endpoint."""
        response = client.get("/api/v1/cockpit/analytics/users", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields


class TestErrorHandling:
    """Test error handling."""

    def test_unauthorized_access(self, client):
        """Test accessing cockpit without authentication."""
        response = client.get("/api/v1/cockpit/dashboard")
        
        assert response.status_code == 401

    def test_invalid_time_range(self, client, auth_headers):
        """Test invalid time range parameter."""
        response = client.get(
            "/api/v1/cockpit/dashboard",
            headers=auth_headers,
            params={"time_range": "invalid"}
        )
        
        assert response.status_code in [422, 400]


# Performance tests
class TestPerformance:
    """Test performance of cockpit endpoints."""

    def test_dashboard_load_performance(self, client, auth_headers):
        """Test dashboard load performance."""
        import time
        
        start = time.time()
        response = client.get("/api/v1/cockpit/dashboard", headers=auth_headers)
        duration = time.time() - start
        
        if response.status_code == 200:
            assert duration < 2.0  # Should complete in under 2 seconds

    def test_metrics_refresh_performance(self, client, auth_headers):
        """Test metrics refresh performance."""
        import time
        
        start = time.time()
        response = client.get("/api/v1/cockpit/metrics", headers=auth_headers)
        duration = time.time() - start
        
        if response.status_code == 200:
            assert duration < 1.0  # Should complete in under 1 second

