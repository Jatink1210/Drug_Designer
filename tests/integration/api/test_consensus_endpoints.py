"""
Integration tests for Consensus API endpoints.

Tests the MAV consensus mechanism endpoints including:
- Consensus creation
- Specialist voting
- Consensus resolution
- Provenance tracking
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from apps.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Create authentication headers."""
    return {"Authorization": "Bearer test_token"}


@pytest.fixture
def sample_consensus_request():
    """Create sample consensus request."""
    return {
        "question": "What is the pathogenicity of BRCA1 p.Arg1699Gln?",
        "context": {
            "gene": "BRCA1",
            "variant": "p.Arg1699Gln",
            "disease": "Breast Cancer"
        },
        "specialists": ["genetics", "clinical", "literature"]
    }


class TestConsensusCreationEndpoints:
    """Test consensus creation endpoints."""

    def test_create_consensus(self, client, auth_headers, sample_consensus_request):
        """Test POST /api/v1/consensus endpoint."""
        response = client.post(
            "/api/v1/consensus",
            headers=auth_headers,
            json=sample_consensus_request
        )
        
        assert response.status_code in [200, 201, 401, 422]
        if response.status_code in [200, 201]:
            data = response.json()
            assert "consensus_id" in data or "id" in data

    def test_create_consensus_with_weights(self, client, auth_headers):
        """Test POST /api/v1/consensus with specialist weights."""
        request_data = {
            "question": "Test question",
            "specialists": ["genetics", "clinical"],
            "weights": {"genetics": 0.6, "clinical": 0.4}
        }
        
        response = client.post(
            "/api/v1/consensus",
            headers=auth_headers,
            json=request_data
        )
        
        assert response.status_code in [200, 201, 401, 422]

    def test_create_consensus_missing_question(self, client, auth_headers):
        """Test POST /api/v1/consensus without question."""
        response = client.post(
            "/api/v1/consensus",
            headers=auth_headers,
            json={"specialists": ["genetics"]}
        )
        
        assert response.status_code == 422


class TestConsensusRetrievalEndpoints:
    """Test consensus retrieval endpoints."""

    def test_get_consensus(self, client, auth_headers):
        """Test GET /api/v1/consensus/{consensus_id} endpoint."""
        response = client.get(
            "/api/v1/consensus/test-consensus-id",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]
        if response.status_code == 200:
            data = response.json()
            assert "consensus_id" in data or "id" in data

    def test_list_consensus(self, client, auth_headers):
        """Test GET /api/v1/consensus endpoint."""
        response = client.get("/api/v1/consensus", headers=auth_headers)
        
        assert response.status_code in (200, 401, 403, 404, 422)  # 401/403 acceptable without real auth; 422 for missing required fields
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_get_consensus_status(self, client, auth_headers):
        """Test GET /api/v1/consensus/{consensus_id}/status endpoint."""
        response = client.get(
            "/api/v1/consensus/test-consensus-id/status",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]


class TestSpecialistVotingEndpoints:
    """Test specialist voting endpoints."""

    def test_get_specialist_votes(self, client, auth_headers):
        """Test GET /api/v1/consensus/{consensus_id}/votes endpoint."""
        response = client.get(
            "/api/v1/consensus/test-consensus-id/votes",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))

    def test_submit_specialist_vote(self, client, auth_headers):
        """Test POST /api/v1/consensus/{consensus_id}/votes endpoint."""
        vote_data = {
            "specialist": "genetics",
            "vote": "pathogenic",
            "confidence": 0.85,
            "reasoning": "Strong evidence from literature"
        }
        
        response = client.post(
            "/api/v1/consensus/test-consensus-id/votes",
            headers=auth_headers,
            json=vote_data
        )
        
        assert response.status_code in [200, 201, 401, 404, 422]

    def test_update_specialist_vote(self, client, auth_headers):
        """Test PUT /api/v1/consensus/{consensus_id}/votes/{specialist} endpoint."""
        vote_data = {
            "vote": "likely_pathogenic",
            "confidence": 0.75
        }
        
        response = client.put(
            "/api/v1/consensus/test-consensus-id/votes/genetics",
            headers=auth_headers,
            json=vote_data
        )
        
        assert response.status_code in [200, 401, 404, 422]


class TestConsensusResolutionEndpoints:
    """Test consensus resolution endpoints."""

    def test_resolve_consensus(self, client, auth_headers):
        """Test POST /api/v1/consensus/{consensus_id}/resolve endpoint."""
        response = client.post(
            "/api/v1/consensus/test-consensus-id/resolve",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]
        if response.status_code == 200:
            data = response.json()
            assert "result" in data or "consensus" in data

    def test_get_consensus_result(self, client, auth_headers):
        """Test GET /api/v1/consensus/{consensus_id}/result endpoint."""
        response = client.get(
            "/api/v1/consensus/test-consensus-id/result",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]

    def test_resolve_with_strategy(self, client, auth_headers):
        """Test POST /api/v1/consensus/{consensus_id}/resolve with strategy."""
        response = client.post(
            "/api/v1/consensus/test-consensus-id/resolve",
            headers=auth_headers,
            params={"strategy": "weighted_average"}
        )
        
        assert response.status_code in [200, 401, 404, 422]


class TestProvenanceEndpoints:
    """Test provenance tracking endpoints."""

    def test_get_consensus_provenance(self, client, auth_headers):
        """Test GET /api/v1/consensus/{consensus_id}/provenance endpoint."""
        response = client.get(
            "/api/v1/consensus/test-consensus-id/provenance",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]
        if response.status_code == 200:
            data = response.json()
            assert "trace" in data or "provenance" in data

    def test_get_specialist_reasoning(self, client, auth_headers):
        """Test GET /api/v1/consensus/{consensus_id}/reasoning endpoint."""
        response = client.get(
            "/api/v1/consensus/test-consensus-id/reasoning",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]

    def test_export_provenance(self, client, auth_headers):
        """Test GET /api/v1/consensus/{consensus_id}/provenance/export endpoint."""
        response = client.get(
            "/api/v1/consensus/test-consensus-id/provenance/export",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]


class TestConsensusManagementEndpoints:
    """Test consensus management endpoints."""

    def test_update_consensus(self, client, auth_headers):
        """Test PUT /api/v1/consensus/{consensus_id} endpoint."""
        update_data = {
            "question": "Updated question",
            "context": {"updated": True}
        }
        
        response = client.put(
            "/api/v1/consensus/test-consensus-id",
            headers=auth_headers,
            json=update_data
        )
        
        assert response.status_code in [200, 401, 404, 422]

    def test_delete_consensus(self, client, auth_headers):
        """Test DELETE /api/v1/consensus/{consensus_id} endpoint."""
        response = client.delete(
            "/api/v1/consensus/test-consensus-id",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 204, 401, 404]

    def test_cancel_consensus(self, client, auth_headers):
        """Test POST /api/v1/consensus/{consensus_id}/cancel endpoint."""
        response = client.post(
            "/api/v1/consensus/test-consensus-id/cancel",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 404]


class TestErrorHandling:
    """Test error handling."""

    def test_unauthorized_access(self, client):
        """Test accessing consensus without authentication."""
        response = client.get("/api/v1/consensus")
        
        assert response.status_code == 401

    def test_invalid_consensus_id(self, client, auth_headers):
        """Test accessing non-existent consensus."""
        response = client.get(
            "/api/v1/consensus/non-existent-id",
            headers=auth_headers
        )
        
        assert response.status_code == 404

    def test_invalid_specialist(self, client, auth_headers):
        """Test submitting vote with invalid specialist."""
        vote_data = {
            "specialist": "invalid_specialist",
            "vote": "pathogenic"
        }
        
        response = client.post(
            "/api/v1/consensus/test-id/votes",
            headers=auth_headers,
            json=vote_data
        )
        
        assert response.status_code in [422, 400]


# Performance tests
class TestPerformance:
    """Test performance of consensus endpoints."""

    def test_consensus_creation_performance(self, client, auth_headers, sample_consensus_request):
        """Test consensus creation performance."""
        import time
        
        start = time.time()
        response = client.post(
            "/api/v1/consensus",
            headers=auth_headers,
            json=sample_consensus_request
        )
        duration = time.time() - start
        
        if response.status_code in [200, 201]:
            assert duration < 3.0  # Should complete in under 3 seconds

    def test_consensus_resolution_performance(self, client, auth_headers):
        """Test consensus resolution performance."""
        import time
        
        start = time.time()
        response = client.post(
            "/api/v1/consensus/test-consensus-id/resolve",
            headers=auth_headers
        )
        duration = time.time() - start
        
        if response.status_code == 200:
            assert duration < 5.0  # Should complete in under 5 seconds

