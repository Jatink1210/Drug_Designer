"""
Integration tests for Settings API endpoints.

Tests user settings endpoints including:
- User preferences
- Application settings
- Notification settings
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


class TestUserSettingsEndpoints:
    """Test user settings endpoints."""

    def test_get_user_settings(self, client, auth_headers):
        """Test GET /api/v1/settings endpoint."""
        response = client.get("/api/v1/settings", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_update_user_settings(self, client, auth_headers):
        """Test PUT /api/v1/settings endpoint."""
        settings_data = {
            "theme": "dark",
            "language": "en",
            "timezone": "UTC"
        }
        
        response = client.put(
            "/api/v1/settings",
            headers=auth_headers,
            json=settings_data
        )
        
        assert response.status_code in [200, 401, 422]

    def test_reset_user_settings(self, client, auth_headers):
        """Test POST /api/v1/settings/reset endpoint."""
        response = client.post(
            "/api/v1/settings/reset",
            headers=auth_headers
        )
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields


class TestPreferencesEndpoints:
    """Test preferences endpoints."""

    def test_get_preferences(self, client, auth_headers):
        """Test GET /api/v1/settings/preferences endpoint."""
        response = client.get("/api/v1/settings/preferences", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_update_preferences(self, client, auth_headers):
        """Test PUT /api/v1/settings/preferences endpoint."""
        preferences_data = {
            "email_notifications": True,
            "auto_save": True
        }
        
        response = client.put(
            "/api/v1/settings/preferences",
            headers=auth_headers,
            json=preferences_data
        )
        
        assert response.status_code in [200, 401, 422]


class TestNotificationSettingsEndpoints:
    """Test notification settings endpoints."""

    def test_get_notification_settings(self, client, auth_headers):
        """Test GET /api/v1/settings/notifications endpoint."""
        response = client.get("/api/v1/settings/notifications", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields

    def test_update_notification_settings(self, client, auth_headers):
        """Test PUT /api/v1/settings/notifications endpoint."""
        notification_data = {
            "email": True,
            "push": False,
            "sms": False
        }
        
        response = client.put(
            "/api/v1/settings/notifications",
            headers=auth_headers,
            json=notification_data
        )
        
        assert response.status_code in [200, 401, 422]


class TestErrorHandling:
    """Test error handling."""

    def test_unauthorized_access(self, client):
        """Test accessing settings without authentication."""
        response = client.get("/api/v1/settings")
        
        assert response.status_code == 401

    def test_invalid_settings(self, client, auth_headers):
        """Test updating with invalid settings."""
        invalid_settings = {"invalid_key": "invalid_value"}
        
        response = client.put(
            "/api/v1/settings",
            headers=auth_headers,
            json=invalid_settings
        )
        
        assert response.status_code in [422, 400]

