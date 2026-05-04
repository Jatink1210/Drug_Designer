"""
Integration tests for Health API endpoints.

Tests the health check endpoints including:
- System health
- Component health
- Readiness checks
- Liveness checks
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from apps.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealthCheckEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client):
        """Test GET /api/v1/health endpoint."""
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

    def test_readiness_check(self, client):
        """Test GET /api/v1/health/ready endpoint."""
        response = client.get("/api/v1/health/ready")
        
        assert response.status_code in [200, 503]
        data = response.json()
        assert "ready" in data

    def test_liveness_check(self, client):
        """Test GET /api/v1/health/live endpoint."""
        response = client.get("/api/v1/health/live")
        
        assert response.status_code == 200
        data = response.json()
        assert "alive" in data
        assert data["alive"] is True


class TestComponentHealthEndpoints:
    """Test component health endpoints."""

    def test_database_health(self, client):
        """Test GET /api/v1/health/database endpoint."""
        response = client.get("/api/v1/health/database")
        
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data

    def test_redis_health(self, client):
        """Test GET /api/v1/health/redis endpoint."""
        response = client.get("/api/v1/health/redis")
        
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data

    def test_vector_store_health(self, client):
        """Test GET /api/v1/health/vector-store endpoint."""
        response = client.get("/api/v1/health/vector-store")
        
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data

    def test_ml_models_health(self, client):
        """Test GET /api/v1/health/ml-models endpoint."""
        response = client.get("/api/v1/health/ml-models")
        
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data


class TestDetailedHealthEndpoints:
    """Test detailed health endpoints."""

    def test_detailed_health(self, client):
        """Test GET /api/v1/health/detailed endpoint."""
        response = client.get("/api/v1/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        assert "components" in data
        assert "timestamp" in data

    def test_health_with_checks(self, client):
        """Test GET /api/v1/health endpoint with checks parameter."""
        response = client.get(
            "/api/v1/health",
            params={"checks": "database,redis"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "checks" in data


class TestMetricsEndpoints:
    """Test metrics endpoints."""

    def test_get_metrics(self, client):
        """Test GET /api/v1/health/metrics endpoint."""
        response = client.get("/api/v1/health/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert "cpu_usage" in data or "metrics" in data

    def test_get_system_info(self, client):
        """Test GET /api/v1/health/system endpoint."""
        response = client.get("/api/v1/health/system")
        
        assert response.status_code == 200
        data = response.json()
        assert "version" in data or "system" in data


class TestDependencyHealthEndpoints:
    """Test dependency health endpoints."""

    def test_check_all_dependencies(self, client):
        """Test GET /api/v1/health/dependencies endpoint."""
        response = client.get("/api/v1/health/dependencies")
        
        assert response.status_code == 200
        data = response.json()
        assert "dependencies" in data

    def test_check_external_services(self, client):
        """Test GET /api/v1/health/external endpoint."""
        response = client.get("/api/v1/health/external")
        
        assert response.status_code in [200, 503]
        data = response.json()
        assert "services" in data or "status" in data


# Performance tests
class TestPerformance:
    """Test performance of health endpoints."""

    def test_health_check_performance(self, client):
        """Test health check performance."""
        import time
        
        start = time.time()
        response = client.get("/api/v1/health")
        duration = time.time() - start
        
        assert response.status_code == 200
        assert duration < 0.5  # Should complete in under 500ms
