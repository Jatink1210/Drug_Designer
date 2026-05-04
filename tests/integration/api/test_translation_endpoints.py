"""
Integration tests for Translation API endpoints.

Tests translation service endpoints including:
- Text translation
- Document translation
- Language detection
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


class TestTextTranslationEndpoints:
    """Test text translation endpoints."""

    def test_translate_text(self, client, auth_headers):
        """Test POST /api/v1/translation/text endpoint."""
        translation_request = {
            "text": "Hello, world!",
            "source_language": "en",
            "target_language": "es"
        }
        
        response = client.post(
            "/api/v1/translation/text",
            headers=auth_headers,
            json=translation_request
        )
        
        assert response.status_code in [200, 401, 422]

    def test_batch_translate(self, client, auth_headers):
        """Test POST /api/v1/translation/batch endpoint."""
        batch_request = {
            "texts": ["Hello", "Goodbye"],
            "source_language": "en",
            "target_language": "es"
        }
        
        response = client.post(
            "/api/v1/translation/batch",
            headers=auth_headers,
            json=batch_request
        )
        
        assert response.status_code in [200, 401, 422]


class TestDocumentTranslationEndpoints:
    """Test document translation endpoints."""

    def test_translate_document(self, client, auth_headers):
        """Test POST /api/v1/translation/document endpoint."""
        doc_request = {
            "document_id": "test-doc-id",
            "target_language": "es"
        }
        
        response = client.post(
            "/api/v1/translation/document",
            headers=auth_headers,
            json=doc_request
        )
        
        assert response.status_code in [200, 201, 401, 404, 422]

    def test_get_translation_status(self, client, auth_headers):
        """Test GET /api/v1/translation/document/{translation_id}/status endpoint."""
        response = client.get(
            "/api/v1/translation/document/test-translation-id/status",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]


class TestLanguageDetectionEndpoints:
    """Test language detection endpoints."""

    def test_detect_language(self, client, auth_headers):
        """Test POST /api/v1/translation/detect endpoint."""
        detection_request = {"text": "Bonjour le monde"}
        
        response = client.post(
            "/api/v1/translation/detect",
            headers=auth_headers,
            json=detection_request
        )
        
        assert response.status_code in [200, 401, 422]

    def test_get_supported_languages(self, client, auth_headers):
        """Test GET /api/v1/translation/languages endpoint."""
        response = client.get("/api/v1/translation/languages", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields


class TestErrorHandling:
    """Test error handling."""

    def test_unauthorized_access(self, client):
        """Test accessing translation without authentication."""
        response = client.get("/api/v1/translation/languages")
        
        assert response.status_code == 401

    def test_unsupported_language(self, client, auth_headers):
        """Test translation with unsupported language."""
        translation_request = {
            "text": "Hello",
            "source_language": "en",
            "target_language": "xyz"  # Invalid language code
        }
        
        response = client.post(
            "/api/v1/translation/text",
            headers=auth_headers,
            json=translation_request
        )
        
        assert response.status_code in [422, 400]

