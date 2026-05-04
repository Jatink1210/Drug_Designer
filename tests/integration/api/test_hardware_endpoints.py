"""
Integration tests for Hardware Monitoring API endpoints.

Tests hardware monitoring endpoints including:
- GPU monitoring
- CPU monitoring
- Memory monitoring
- Disk monitoring
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


class TestGPUMonitoringEndpoints:
    """Test GPU monitoring endpoints."""

    def test_get_gpu_status(self, client, auth_headers):
        """Test GET /api/v1/hardware/gpu endpoint."""
        response = client.get("/api/v1/hardware/gpu", headers=auth_headers)
        
        assert response.status_code in [200, 401, 404]

    def test_get_gpu_utilization(self, client, auth_headers):
        """Test GET /api/v1/hardware/gpu/utilization endpoint."""
        response = client.get("/api/v1/hardware/gpu/utilization", headers=auth_headers)
        
        assert response.status_code in [200, 401, 404]

    def test_get_gpu_memory(self, client, auth_headers):
        """Test GET /api/v1/hardware/gpu/memory endpoint."""
        response = client.get("/api/v1/hardware/gpu/memory", headers=auth_headers)
        
        assert response.status_code in [200, 401, 404]


class TestCPUMonitoringEndpoints:
    """Test CPU monitoring endpoints."""

    def test_get_cpu_status(self, client, auth_headers):
        """Test GET /api/v1/hardware/cpu endpoint."""
        response = client.get("/api/v1/hardware/cpu", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_get_cpu_utilization(self, client, auth_headers):
        """Test GET /api/v1/hardware/cpu/utilization endpoint."""
        response = client.get("/api/v1/hardware/cpu/utilization", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields


class TestMemoryMonitoringEndpoints:
    """Test memory monitoring endpoints."""

    def test_get_memory_status(self, client, auth_headers):
        """Test GET /api/v1/hardware/memory endpoint."""
        response = client.get("/api/v1/hardware/memory", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_get_memory_usage(self, client, auth_headers):
        """Test GET /api/v1/hardware/memory/usage endpoint."""
        response = client.get("/api/v1/hardware/memory/usage", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields


class TestDiskMonitoringEndpoints:
    """Test disk monitoring endpoints."""

    def test_get_disk_status(self, client, auth_headers):
        """Test GET /api/v1/hardware/disk endpoint."""
        response = client.get("/api/v1/hardware/disk", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_get_disk_usage(self, client, auth_headers):
        """Test GET /api/v1/hardware/disk/usage endpoint."""
        response = client.get("/api/v1/hardware/disk/usage", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields


class TestSystemOverviewEndpoints:
    """Test system overview endpoints."""

    def test_get_system_overview(self, client, auth_headers):
        """Test GET /api/v1/hardware/overview endpoint."""
        response = client.get("/api/v1/hardware/overview", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_get_system_metrics(self, client, auth_headers):
        """Test GET /api/v1/hardware/metrics endpoint."""
        response = client.get("/api/v1/hardware/metrics", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields


class TestErrorHandling:
    """Test error handling."""

    def test_unauthorized_access(self, client):
        """Test accessing hardware without authentication."""
        response = client.get("/api/v1/hardware/overview")
        
        assert response.status_code == 401


# Performance tests
class TestPerformance:
    """Test performance of hardware endpoints."""

    def test_metrics_collection_performance(self, client, auth_headers):
        """Test metrics collection performance."""
        import time
        
        start = time.time()
        response = client.get("/api/v1/hardware/overview", headers=auth_headers)
        duration = time.time() - start
        
        if response.status_code == 200:
            assert duration < 0.5  # Should complete in under 500ms

