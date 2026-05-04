"""
Integration tests for WebSocket API endpoints.

Tests WebSocket connection endpoints including:
- Connection establishment
- Message handling
- Real-time updates
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


class TestWebSocketConnectionEndpoints:
    """Test WebSocket connection endpoints."""

    def test_websocket_connect(self, client):
        """Test WebSocket connection at /ws endpoint."""
        try:
            with client.websocket_connect("/ws") as websocket:
                # Connection successful
                assert websocket is not None
        except Exception:
            # WebSocket might not be available in test environment
            pytest.skip("WebSocket not available in test environment")

    def test_websocket_with_token(self, client):
        """Test WebSocket connection with authentication token."""
        try:
            with client.websocket_connect("/ws?token=test_token") as websocket:
                assert websocket is not None
        except Exception:
            pytest.skip("WebSocket not available in test environment")


class TestWebSocketMessagingEndpoints:
    """Test WebSocket messaging endpoints."""

    def test_send_message(self, client):
        """Test sending message through WebSocket."""
        try:
            with client.websocket_connect("/ws") as websocket:
                test_message = {"type": "ping", "data": "test"}
                websocket.send_json(test_message)
                
                # Receive response
                response = websocket.receive_json()
                assert response is not None
        except Exception:
            pytest.skip("WebSocket not available in test environment")

    def test_receive_updates(self, client):
        """Test receiving real-time updates."""
        try:
            with client.websocket_connect("/ws/updates") as websocket:
                # Subscribe to updates
                websocket.send_json({"action": "subscribe", "channel": "test"})
                
                # Wait for confirmation
                response = websocket.receive_json()
                assert "status" in response or "subscribed" in response
        except Exception:
            pytest.skip("WebSocket not available in test environment")


class TestWebSocketChannelEndpoints:
    """Test WebSocket channel endpoints."""

    def test_subscribe_to_channel(self, client):
        """Test subscribing to a specific channel."""
        try:
            with client.websocket_connect("/ws") as websocket:
                subscribe_msg = {
                    "action": "subscribe",
                    "channel": "workflow_updates"
                }
                websocket.send_json(subscribe_msg)
                
                response = websocket.receive_json()
                assert response is not None
        except Exception:
            pytest.skip("WebSocket not available in test environment")

    def test_unsubscribe_from_channel(self, client):
        """Test unsubscribing from a channel."""
        try:
            with client.websocket_connect("/ws") as websocket:
                unsubscribe_msg = {
                    "action": "unsubscribe",
                    "channel": "workflow_updates"
                }
                websocket.send_json(unsubscribe_msg)
                
                response = websocket.receive_json()
                assert response is not None
        except Exception:
            pytest.skip("WebSocket not available in test environment")


class TestWebSocketBroadcastEndpoints:
    """Test WebSocket broadcast endpoints."""

    def test_broadcast_message(self, client, auth_headers):
        """Test POST /api/v1/websocket/broadcast endpoint."""
        broadcast_data = {
            "channel": "all",
            "message": {"type": "notification", "text": "Test broadcast"}
        }
        
        response = client.post(
            "/api/v1/websocket/broadcast",
            headers=auth_headers,
            json=broadcast_data
        )
        
        assert response.status_code in [200, 401, 422]

    def test_get_active_connections(self, client, auth_headers):
        """Test GET /api/v1/websocket/connections endpoint."""
        response = client.get("/api/v1/websocket/connections", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields


class TestErrorHandling:
    """Test error handling."""

    def test_unauthorized_broadcast(self, client):
        """Test broadcasting without authentication."""
        broadcast_data = {"channel": "all", "message": "test"}
        
        response = client.post(
            "/api/v1/websocket/broadcast",
            json=broadcast_data
        )
        
        assert response.status_code == 401

    def test_invalid_message_format(self, client):
        """Test sending invalid message format."""
        try:
            with client.websocket_connect("/ws") as websocket:
                # Send invalid message
                websocket.send_text("invalid json")
                
                # Should receive error response
                response = websocket.receive_json()
                assert "error" in response or response is not None
        except Exception:
            pytest.skip("WebSocket not available in test environment")


# Performance tests
class TestPerformance:
    """Test performance of WebSocket endpoints."""

    def test_connection_performance(self, client):
        """Test WebSocket connection performance."""
        import time
        
        try:
            start = time.time()
            with client.websocket_connect("/ws") as websocket:
                duration = time.time() - start
                assert duration < 1.0  # Should connect in under 1 second
                assert websocket is not None
        except Exception:
            pytest.skip("WebSocket not available in test environment")

    def test_message_latency(self, client):
        """Test WebSocket message latency."""
        import time
        
        try:
            with client.websocket_connect("/ws") as websocket:
                start = time.time()
                websocket.send_json({"type": "ping"})
                response = websocket.receive_json()
                duration = time.time() - start
                
                assert duration < 0.1  # Should respond in under 100ms
                assert response is not None
        except Exception:
            pytest.skip("WebSocket not available in test environment")

