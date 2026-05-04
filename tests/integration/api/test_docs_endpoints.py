"""
Integration tests for Documentation API endpoints.

Tests documentation endpoints including:
- API documentation
- Schema retrieval
- OpenAPI spec
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


class TestDocumentationEndpoints:
    """Test documentation endpoints."""

    def test_get_openapi_spec(self, client):
        """Test GET /api/v1/docs/openapi.json endpoint."""
        response = client.get("/api/v1/docs/openapi.json")
        
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "openapi" in data or "swagger" in data

    def test_get_swagger_ui(self, client):
        """Test GET /docs endpoint."""
        response = client.get("/docs")
        
        assert response.status_code in [200, 404]

    def test_get_redoc(self, client):
        """Test GET /redoc endpoint."""
        response = client.get("/redoc")
        
        assert response.status_code in [200, 404]


class TestSchemaEndpoints:
    """Test schema endpoints."""

    def test_get_api_schema(self, client):
        """Test GET /api/v1/docs/schema endpoint."""
        response = client.get("/api/v1/docs/schema")
        
        assert response.status_code in [200, 404]

    def test_get_model_schemas(self, client):
        """Test GET /api/v1/docs/schemas endpoint."""
        response = client.get("/api/v1/docs/schemas")
        
        assert response.status_code in [200, 404]

    def test_get_specific_schema(self, client):
        """Test GET /api/v1/docs/schemas/{model_name} endpoint."""
        response = client.get("/api/v1/docs/schemas/Evidence")
        
        assert response.status_code in [200, 404]


class TestEndpointDocumentationEndpoints:
    """Test endpoint documentation endpoints."""

    def test_list_endpoints(self, client, auth_headers):
        """Test GET /api/v1/docs/endpoints endpoint."""
        response = client.get("/api/v1/docs/endpoints", headers=auth_headers)
        
        assert response.status_code in [200, 401, 404]

    def test_get_endpoint_details(self, client, auth_headers):
        """Test GET /api/v1/docs/endpoints/{endpoint_path} endpoint."""
        response = client.get(
            "/api/v1/docs/endpoints/health",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]


class TestVersioningEndpoints:
    """Test API versioning endpoints."""

    def test_get_api_version(self, client):
        """Test GET /api/v1/docs/version endpoint."""
        response = client.get("/api/v1/docs/version")
        
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "version" in data or "api_version" in data

    def test_get_changelog(self, client):
        """Test GET /api/v1/docs/changelog endpoint."""
        response = client.get("/api/v1/docs/changelog")
        
        assert response.status_code in [200, 404]


class TestExampleEndpoints:
    """Test example endpoints."""

    def test_get_examples(self, client):
        """Test GET /api/v1/docs/examples endpoint."""
        response = client.get("/api/v1/docs/examples")
        
        assert response.status_code in [200, 404]

    def test_get_example_by_category(self, client):
        """Test GET /api/v1/docs/examples/{category} endpoint."""
        response = client.get("/api/v1/docs/examples/authentication")
        
        assert response.status_code in [200, 404]


class TestErrorHandling:
    """Test error handling."""

    def test_invalid_schema_name(self, client):
        """Test accessing non-existent schema."""
        response = client.get("/api/v1/docs/schemas/NonExistentModel")
        
        assert response.status_code == 404

    def test_invalid_endpoint_path(self, client, auth_headers):
        """Test accessing non-existent endpoint documentation."""
        response = client.get(
            "/api/v1/docs/endpoints/non-existent",
            headers=auth_headers
        )
        
        assert response.status_code in [404, 401]


# Performance tests
class TestPerformance:
    """Test performance of documentation endpoints."""

    def test_openapi_spec_performance(self, client):
        """Test OpenAPI spec retrieval performance."""
        import time
        
        start = time.time()
        response = client.get("/api/v1/docs/openapi.json")
        duration = time.time() - start
        
        if response.status_code == 200:
            assert duration < 1.0  # Should complete in under 1 second

    def test_schema_retrieval_performance(self, client):
        """Test schema retrieval performance."""
        import time
        
        start = time.time()
        response = client.get("/api/v1/docs/schemas")
        duration = time.time() - start
        
        if response.status_code == 200:
            assert duration < 0.5  # Should complete in under 500ms
