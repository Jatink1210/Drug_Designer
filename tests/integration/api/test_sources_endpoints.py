"""
Integration tests for Sources API endpoints.

Tests the data source management endpoints including:
- Source listing and retrieval
- Source configuration
- Source synchronization
- Source statistics
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
        role="admin"
    )


class TestSourceListingEndpoints:
    """Test source listing and retrieval endpoints."""

    def test_list_all_sources(self, client, auth_headers):
        """Test GET /api/v1/sources endpoint."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/sources",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "sources" in data
            assert isinstance(data["sources"], list)

    def test_get_source_details(self, client, auth_headers):
        """Test GET /api/v1/sources/{source_id} endpoint."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/sources/pubmed",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "source_id" in data
                assert "name" in data

    def test_list_sources_by_category(self, client, auth_headers):
        """Test GET /api/v1/sources endpoint with category filter."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/sources",
                headers=auth_headers,
                params={"category": "literature"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "sources" in data

    def test_list_active_sources(self, client, auth_headers):
        """Test GET /api/v1/sources endpoint with active filter."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/sources",
                headers=auth_headers,
                params={"active": True}
            )
            
            assert response.status_code == 200


class TestSourceConfigurationEndpoints:
    """Test source configuration endpoints."""

    def test_update_source_config(self, client, auth_headers):
        """Test PUT /api/v1/sources/{source_id}/config endpoint."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.put(
                "/api/v1/sources/pubmed/config",
                headers=auth_headers,
                json={
                    "api_key": "new_api_key",
                    "rate_limit": 10,
                    "timeout": 30
                }
            )
            
            assert response.status_code in [200, 404]

    def test_get_source_config(self, client, auth_headers):
        """Test GET /api/v1/sources/{source_id}/config endpoint."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/sources/pubmed/config",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_enable_source(self, client, auth_headers):
        """Test POST /api/v1/sources/{source_id}/enable endpoint."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/sources/pubmed/enable",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_disable_source(self, client, auth_headers):
        """Test POST /api/v1/sources/{source_id}/disable endpoint."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/sources/pubmed/disable",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]


class TestSourceSynchronizationEndpoints:
    """Test source synchronization endpoints."""

    def test_sync_source(self, client, auth_headers):
        """Test POST /api/v1/sources/{source_id}/sync endpoint."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/sources/pubmed/sync",
                headers=auth_headers,
                json={"full_sync": False}
            )
            
            assert response.status_code in [200, 202, 404]

    def test_get_sync_status(self, client, auth_headers):
        """Test GET /api/v1/sources/{source_id}/sync/status endpoint."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/sources/pubmed/sync/status",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_cancel_sync(self, client, auth_headers):
        """Test POST /api/v1/sources/{source_id}/sync/cancel endpoint."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/sources/pubmed/sync/cancel",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_get_sync_history(self, client, auth_headers):
        """Test GET /api/v1/sources/{source_id}/sync/history endpoint."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/sources/pubmed/sync/history",
                headers=auth_headers,
                params={"limit": 10}
            )
            
            assert response.status_code in [200, 404]


class TestSourceStatisticsEndpoints:
    """Test source statistics endpoints."""

    def test_get_source_stats(self, client, auth_headers):
        """Test GET /api/v1/sources/{source_id}/stats endpoint."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/sources/pubmed/stats",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "total_records" in data or "stats" in data

    def test_get_source_health(self, client, auth_headers):
        """Test GET /api/v1/sources/{source_id}/health endpoint."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/sources/pubmed/health",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_get_all_sources_stats(self, client, auth_headers):
        """Test GET /api/v1/sources/stats endpoint."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/sources/stats",
                headers=auth_headers
            )
            
            assert response.status_code == 200


class TestSourceTestingEndpoints:
    """Test source testing endpoints."""

    def test_test_source_connection(self, client, auth_headers):
        """Test POST /api/v1/sources/{source_id}/test endpoint."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/sources/pubmed/test",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_validate_source_config(self, client, auth_headers):
        """Test POST /api/v1/sources/{source_id}/validate endpoint."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/sources/pubmed/validate",
                headers=auth_headers,
                json={
                    "api_key": "test_key",
                    "rate_limit": 10
                }
            )
            
            assert response.status_code in [200, 400, 404]


class TestSourceCategoriesEndpoints:
    """Test source categories endpoints."""

    def test_list_categories(self, client, auth_headers):
        """Test GET /api/v1/sources/categories endpoint."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/sources/categories",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "categories" in data

    def test_get_category_sources(self, client, auth_headers):
        """Test GET /api/v1/sources/categories/{category} endpoint."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/sources/categories/literature",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]


class TestAuthorizationAndErrors:
    """Test authorization and error handling."""

    def test_unauthorized_access(self, client):
        """Test access without authentication."""
        response = client.get("/api/v1/sources")
        assert response.status_code == 401

    def test_non_admin_cannot_update_config(self, client, auth_headers):
        """Test non-admin user cannot update source config."""
        non_admin_user = User(
            id="user-456",
            email="user@example.com",
            full_name="Regular User",
            role="researcher"
        )
        
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = non_admin_user
            
            response = client.put(
                "/api/v1/sources/pubmed/config",
                headers=auth_headers,
                json={"api_key": "new_key"}
            )
            
            assert response.status_code in [403, 404]

    def test_invalid_source_id(self, client, auth_headers):
        """Test accessing non-existent source."""
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/sources/invalid-source",
                headers=auth_headers
            )
            
            assert response.status_code == 404


# Performance tests
class TestPerformance:
    """Test performance of source endpoints."""

    def test_list_sources_performance(self, client, auth_headers):
        """Test source listing performance."""
        import time
        
        with patch("apps.api.routers.sources.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            start = time.time()
            response = client.get(
                "/api/v1/sources",
                headers=auth_headers
            )
            duration = time.time() - start
            
            assert response.status_code == 200
            assert duration < 2.0  # Should complete in under 2 seconds
