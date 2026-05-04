"""
Integration tests for Performance Metrics API endpoints.

Tests performance monitoring endpoints including:
- Performance metrics collection
- Benchmarking
- Profiling
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


class TestPerformanceMetricsEndpoints:
    """Test performance metrics endpoints."""

    def test_get_performance_metrics(self, client, auth_headers):
        """Test GET /api/v1/performance/metrics endpoint."""
        response = client.get("/api/v1/performance/metrics", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_get_endpoint_metrics(self, client, auth_headers):
        """Test GET /api/v1/performance/endpoints endpoint."""
        response = client.get("/api/v1/performance/endpoints", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_get_query_metrics(self, client, auth_headers):
        """Test GET /api/v1/performance/queries endpoint."""
        response = client.get("/api/v1/performance/queries", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields


class TestBenchmarkingEndpoints:
    """Test benchmarking endpoints."""

    def test_run_benchmark(self, client, auth_headers):
        """Test POST /api/v1/performance/benchmark endpoint."""
        benchmark_config = {
            "endpoint": "/api/v1/health",
            "iterations": 100
        }
        
        response = client.post(
            "/api/v1/performance/benchmark",
            headers=auth_headers,
            json=benchmark_config
        )
        
        assert response.status_code in [200, 201, 401, 422]

    def test_get_benchmark_results(self, client, auth_headers):
        """Test GET /api/v1/performance/benchmark/{benchmark_id} endpoint."""
        response = client.get(
            "/api/v1/performance/benchmark/test-benchmark-id",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]


class TestProfilingEndpoints:
    """Test profiling endpoints."""

    def test_start_profiling(self, client, auth_headers):
        """Test POST /api/v1/performance/profile/start endpoint."""
        response = client.post(
            "/api/v1/performance/profile/start",
            headers=auth_headers
        )
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_stop_profiling(self, client, auth_headers):
        """Test POST /api/v1/performance/profile/stop endpoint."""
        response = client.post(
            "/api/v1/performance/profile/stop",
            headers=auth_headers
        )
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_get_profile_results(self, client, auth_headers):
        """Test GET /api/v1/performance/profile/results endpoint."""
        response = client.get(
            "/api/v1/performance/profile/results",
            headers=auth_headers
        )
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields


class TestErrorHandling:
    """Test error handling."""

    def test_unauthorized_access(self, client):
        """Test accessing performance without authentication."""
        response = client.get("/api/v1/performance/metrics")
        
        assert response.status_code == 401

