"""
Integration tests for Catalog API endpoints.

Tests the model catalog endpoints including:
- Model listing and search
- Model details
- Model versions
- Model deployment
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


class TestModelListingEndpoints:
    """Test model listing and search endpoints."""

    def test_list_models(self, client, auth_headers):
        """Test GET /api/v1/catalog/models endpoint."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/catalog/models",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "models" in data

    def test_search_models(self, client, auth_headers):
        """Test POST /api/v1/catalog/models/search endpoint."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/catalog/models/search",
                headers=auth_headers,
                json={
                    "query": "protein",
                    "filters": {"type": "ml_model"}
                }
            )
            
            assert response.status_code == 200

    def test_filter_models_by_type(self, client, auth_headers):
        """Test GET /api/v1/catalog/models endpoint with type filter."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/catalog/models",
                headers=auth_headers,
                params={"type": "protein_structure"}
            )
            
            assert response.status_code == 200

    def test_filter_models_by_category(self, client, auth_headers):
        """Test GET /api/v1/catalog/models endpoint with category filter."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/catalog/models",
                headers=auth_headers,
                params={"category": "drug_discovery"}
            )
            
            assert response.status_code == 200


class TestModelDetailsEndpoints:
    """Test model details endpoints."""

    def test_get_model_details(self, client, auth_headers):
        """Test GET /api/v1/catalog/models/{model_id} endpoint."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/catalog/models/esm2",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_get_model_metadata(self, client, auth_headers):
        """Test GET /api/v1/catalog/models/{model_id}/metadata endpoint."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/catalog/models/esm2/metadata",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_get_model_schema(self, client, auth_headers):
        """Test GET /api/v1/catalog/models/{model_id}/schema endpoint."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/catalog/models/esm2/schema",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_get_model_documentation(self, client, auth_headers):
        """Test GET /api/v1/catalog/models/{model_id}/docs endpoint."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/catalog/models/esm2/docs",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]


class TestModelVersionEndpoints:
    """Test model version endpoints."""

    def test_list_model_versions(self, client, auth_headers):
        """Test GET /api/v1/catalog/models/{model_id}/versions endpoint."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/catalog/models/esm2/versions",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_get_version_details(self, client, auth_headers):
        """Test GET /api/v1/catalog/models/{model_id}/versions/{version} endpoint."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/catalog/models/esm2/versions/1.0.0",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_get_latest_version(self, client, auth_headers):
        """Test GET /api/v1/catalog/models/{model_id}/versions/latest endpoint."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/catalog/models/esm2/versions/latest",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]


class TestModelDeploymentEndpoints:
    """Test model deployment endpoints."""

    def test_deploy_model(self, client, auth_headers):
        """Test POST /api/v1/catalog/models/{model_id}/deploy endpoint."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/catalog/models/esm2/deploy",
                headers=auth_headers,
                json={"environment": "production"}
            )
            
            assert response.status_code in [200, 202, 404]

    def test_get_deployment_status(self, client, auth_headers):
        """Test GET /api/v1/catalog/models/{model_id}/deployment endpoint."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/catalog/models/esm2/deployment",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_undeploy_model(self, client, auth_headers):
        """Test DELETE /api/v1/catalog/models/{model_id}/deploy endpoint."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.delete(
                "/api/v1/catalog/models/esm2/deploy",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 204, 404]


class TestModelCategoriesEndpoints:
    """Test model categories endpoints."""

    def test_list_categories(self, client, auth_headers):
        """Test GET /api/v1/catalog/categories endpoint."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/catalog/categories",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "categories" in data

    def test_get_category_models(self, client, auth_headers):
        """Test GET /api/v1/catalog/categories/{category}/models endpoint."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/catalog/categories/protein_structure/models",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]


class TestModelBenchmarkEndpoints:
    """Test model benchmark endpoints."""

    def test_get_model_benchmarks(self, client, auth_headers):
        """Test GET /api/v1/catalog/models/{model_id}/benchmarks endpoint."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/catalog/models/esm2/benchmarks",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_compare_models(self, client, auth_headers):
        """Test POST /api/v1/catalog/models/compare endpoint."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.post(
                "/api/v1/catalog/models/compare",
                headers=auth_headers,
                json={
                    "model_ids": ["esm2", "molformer"],
                    "metrics": ["accuracy", "speed"]
                }
            )
            
            assert response.status_code == 200


class TestModelUsageEndpoints:
    """Test model usage endpoints."""

    def test_get_model_usage_stats(self, client, auth_headers):
        """Test GET /api/v1/catalog/models/{model_id}/usage endpoint."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/catalog/models/esm2/usage",
                headers=auth_headers
            )
            
            assert response.status_code in [200, 404]

    def test_get_popular_models(self, client, auth_headers):
        """Test GET /api/v1/catalog/models/popular endpoint."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/catalog/models/popular",
                headers=auth_headers,
                params={"limit": 10}
            )
            
            assert response.status_code == 200


class TestAuthorizationAndErrors:
    """Test authorization and error handling."""

    def test_unauthorized_access(self, client):
        """Test access without authentication."""
        response = client.get("/api/v1/catalog/models")
        assert response.status_code == 401

    def test_invalid_model_id(self, client, auth_headers):
        """Test accessing non-existent model."""
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            response = client.get(
                "/api/v1/catalog/models/invalid-model",
                headers=auth_headers
            )
            
            assert response.status_code == 404


# Performance tests
class TestPerformance:
    """Test performance of catalog endpoints."""

    def test_model_listing_performance(self, client, auth_headers):
        """Test model listing performance."""
        import time
        
        with patch("apps.api.routers.catalog.get_current_user") as mock_auth:
            mock_auth.return_value = mock_user()
            
            start = time.time()
            response = client.get(
                "/api/v1/catalog/models",
                headers=auth_headers
            )
            duration = time.time() - start
            
            assert response.status_code == 200
            assert duration < 1.0  # Should complete in under 1 second
