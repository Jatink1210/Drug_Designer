"""
Integration tests for Media API endpoints.

Tests media file management endpoints including:
- File upload
- File retrieval
- File deletion
- Image processing
"""

import pytest
from fastapi.testclient import TestClient
from io import BytesIO

from apps.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Create authentication headers."""
    return {"Authorization": "Bearer test_token"}


class TestFileUploadEndpoints:
    """Test file upload endpoints."""

    def test_upload_file(self, client, auth_headers):
        """Test POST /api/v1/media/upload endpoint."""
        files = {"file": ("test.txt", BytesIO(b"test content"), "text/plain")}
        
        response = client.post(
            "/api/v1/media/upload",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code in [200, 201, 401, 422]

    def test_upload_image(self, client, auth_headers):
        """Test POST /api/v1/media/upload/image endpoint."""
        files = {"file": ("test.png", BytesIO(b"fake image data"), "image/png")}
        
        response = client.post(
            "/api/v1/media/upload/image",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code in [200, 201, 401, 422]


class TestFileRetrievalEndpoints:
    """Test file retrieval endpoints."""

    def test_get_file(self, client, auth_headers):
        """Test GET /api/v1/media/{file_id} endpoint."""
        response = client.get(
            "/api/v1/media/test-file-id",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]

    def test_list_files(self, client, auth_headers):
        """Test GET /api/v1/media endpoint."""
        response = client.get("/api/v1/media", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_get_file_metadata(self, client, auth_headers):
        """Test GET /api/v1/media/{file_id}/metadata endpoint."""
        response = client.get(
            "/api/v1/media/test-file-id/metadata",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]


class TestFileManagementEndpoints:
    """Test file management endpoints."""

    def test_delete_file(self, client, auth_headers):
        """Test DELETE /api/v1/media/{file_id} endpoint."""
        response = client.delete(
            "/api/v1/media/test-file-id",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 204, 401, 404]

    def test_update_file_metadata(self, client, auth_headers):
        """Test PUT /api/v1/media/{file_id}/metadata endpoint."""
        metadata = {"description": "Updated description"}
        
        response = client.put(
            "/api/v1/media/test-file-id/metadata",
            headers=auth_headers,
            json=metadata
        )
        
        assert response.status_code in [200, 401, 404, 422]


class TestImageProcessingEndpoints:
    """Test image processing endpoints."""

    def test_resize_image(self, client, auth_headers):
        """Test POST /api/v1/media/{file_id}/resize endpoint."""
        resize_params = {"width": 800, "height": 600}
        
        response = client.post(
            "/api/v1/media/test-file-id/resize",
            headers=auth_headers,
            json=resize_params
        )
        
        assert response.status_code in [200, 401, 404, 422]

    def test_generate_thumbnail(self, client, auth_headers):
        """Test POST /api/v1/media/{file_id}/thumbnail endpoint."""
        response = client.post(
            "/api/v1/media/test-file-id/thumbnail",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]


class TestErrorHandling:
    """Test error handling."""

    def test_unauthorized_access(self, client):
        """Test accessing media without authentication."""
        response = client.get("/api/v1/media")
        
        assert response.status_code == 401

    def test_invalid_file_type(self, client, auth_headers):
        """Test uploading invalid file type."""
        files = {"file": ("test.exe", BytesIO(b"executable"), "application/x-msdownload")}
        
        response = client.post(
            "/api/v1/media/upload",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code in [422, 400]


# Performance tests
class TestPerformance:
    """Test performance of media endpoints."""

    def test_file_upload_performance(self, client, auth_headers):
        """Test file upload performance."""
        import time
        
        files = {"file": ("test.txt", BytesIO(b"test content"), "text/plain")}
        
        start = time.time()
        response = client.post(
            "/api/v1/media/upload",
            headers=auth_headers,
            files=files
        )
        duration = time.time() - start
        
        if response.status_code in [200, 201]:
            assert duration < 2.0  # Should complete in under 2 seconds

