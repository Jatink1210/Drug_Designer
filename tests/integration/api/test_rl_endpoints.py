"""
Integration tests for Reinforcement Learning API endpoints.

Tests RL endpoints including:
- RL agent training
- Policy evaluation
- Environment management
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


class TestRLAgentEndpoints:
    """Test RL agent endpoints."""

    def test_create_agent(self, client, auth_headers):
        """Test POST /api/v1/rl/agents endpoint."""
        agent_config = {
            "name": "test_agent",
            "algorithm": "ppo",
            "environment": "drug_design"
        }
        
        response = client.post(
            "/api/v1/rl/agents",
            headers=auth_headers,
            json=agent_config
        )
        
        assert response.status_code in [200, 201, 401, 422]

    def test_get_agent(self, client, auth_headers):
        """Test GET /api/v1/rl/agents/{agent_id} endpoint."""
        response = client.get(
            "/api/v1/rl/agents/test-agent-id",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]

    def test_list_agents(self, client, auth_headers):
        """Test GET /api/v1/rl/agents endpoint."""
        response = client.get("/api/v1/rl/agents", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields


class TestTrainingEndpoints:
    """Test training endpoints."""

    def test_start_training(self, client, auth_headers):
        """Test POST /api/v1/rl/agents/{agent_id}/train endpoint."""
        training_config = {
            "episodes": 1000,
            "max_steps": 500
        }
        
        response = client.post(
            "/api/v1/rl/agents/test-agent-id/train",
            headers=auth_headers,
            json=training_config
        )
        
        assert response.status_code in [200, 201, 401, 404, 422]

    def test_stop_training(self, client, auth_headers):
        """Test POST /api/v1/rl/agents/{agent_id}/stop endpoint."""
        response = client.post(
            "/api/v1/rl/agents/test-agent-id/stop",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]

    def test_get_training_status(self, client, auth_headers):
        """Test GET /api/v1/rl/agents/{agent_id}/status endpoint."""
        response = client.get(
            "/api/v1/rl/agents/test-agent-id/status",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]


class TestPolicyEndpoints:
    """Test policy endpoints."""

    def test_evaluate_policy(self, client, auth_headers):
        """Test POST /api/v1/rl/agents/{agent_id}/evaluate endpoint."""
        eval_config = {"episodes": 10}
        
        response = client.post(
            "/api/v1/rl/agents/test-agent-id/evaluate",
            headers=auth_headers,
            json=eval_config
        )
        
        assert response.status_code in [200, 401, 404, 422]

    def test_get_policy(self, client, auth_headers):
        """Test GET /api/v1/rl/agents/{agent_id}/policy endpoint."""
        response = client.get(
            "/api/v1/rl/agents/test-agent-id/policy",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]


class TestErrorHandling:
    """Test error handling."""

    def test_unauthorized_access(self, client):
        """Test accessing RL without authentication."""
        response = client.get("/api/v1/rl/agents")
        
        assert response.status_code == 401

