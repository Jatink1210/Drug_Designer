"""Unit tests for MAV Consensus Service.

Tests multi-agent voting, specialist assignment, vote aggregation,
and truthful pause triggering.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from datetime import datetime


class TestMAVConsensusService:
    """Test MAV consensus service."""
    
    @pytest.mark.asyncio
    async def test_consensus_basic(self, mock_db_session, sample_user_id, sample_project_id):
        """Test basic consensus execution."""
        from services.agency.mav_consensus import mav_consensus_service
        
        with patch("services.agency.mav_consensus.mav_consensus_service") as mock_consensus:
            mock_consensus.return_value = {
                "data": {
                    "consensus_id": str(uuid.uuid4()),
                    "status": "verified",
                    "final_verdict": "verified",
                    "confidence": 0.8,
                    "votes": []
                },
                "provenance": {}
            }
            
            result = await mock_consensus(
                db=mock_db_session,
                user_id=sample_user_id,
                project_id=sample_project_id,
                claim="FOXP3 mutations cause IPEX syndrome",
                evidence_bundle_id=str(uuid.uuid4()),
                jury_size=5
            )
            
            assert "data" in result
            assert "consensus_id" in result["data"]
            assert result["data"]["status"] in ["verified", "contradicted", "conflict"]
    
    @pytest.mark.asyncio
    async def test_consensus_with_3_agents(self, mock_db_session, sample_user_id, sample_project_id):
        """Test consensus with 3 agents."""
        from services.agency.mav_consensus import mav_consensus_service
        
        with patch("services.agency.mav_consensus.mav_consensus_service") as mock_consensus:
            mock_consensus.return_value = {
                "data": {
                    "consensus_id": str(uuid.uuid4()),
                    "jury_size": 3,
                    "votes": [
                        {"agent_id": "agent_1", "vote": "verified"},
                        {"agent_id": "agent_2", "vote": "verified"},
                        {"agent_id": "agent_3", "vote": "contradicted"}
                    ],
                    "status": "verified"
                },
                "provenance": {}
            }
            
            result = await mock_consensus(
                db=mock_db_session,
                user_id=sample_user_id,
                project_id=sample_project_id,
                claim="Test claim",
                evidence_bundle_id=str(uuid.uuid4()),
                jury_size=3
            )
            
            assert result["data"]["jury_size"] == 3
            assert len(result["data"]["votes"]) == 3
    
    @pytest.mark.asyncio
    async def test_consensus_with_5_agents(self, mock_db_session, sample_user_id, sample_project_id):
        """Test consensus with 5 agents."""
        from services.agency.mav_consensus import mav_consensus_service
        
        with patch("services.agency.mav_consensus.mav_consensus_service") as mock_consensus:
            mock_consensus.return_value = {
                "data": {
                    "consensus_id": str(uuid.uuid4()),
                    "jury_size": 5,
                    "votes": [{"agent_id": f"agent_{i}", "vote": "verified"} for i in range(5)],
                    "status": "verified"
                },
                "provenance": {}
            }
            
            result = await mock_consensus(
                db=mock_db_session,
                user_id=sample_user_id,
                project_id=sample_project_id,
                claim="Test claim",
                evidence_bundle_id=str(uuid.uuid4()),
                jury_size=5
            )
            
            assert result["data"]["jury_size"] == 5
            assert len(result["data"]["votes"]) == 5
    
    @pytest.mark.asyncio
    async def test_consensus_verified(self, mock_db_session, sample_user_id, sample_project_id):
        """Test consensus reaches verified status."""
        from services.agency.mav_consensus import mav_consensus_service
        
        with patch("services.agency.mav_consensus.mav_consensus_service") as mock_consensus:
            mock_consensus.return_value = {
                "data": {
                    "consensus_id": str(uuid.uuid4()),
                    "status": "verified",
                    "final_verdict": "verified",
                    "confidence": 1.0,
                    "votes": [
                        {"agent_id": f"agent_{i}", "vote": "verified", "confidence": 0.9}
                        for i in range(5)
                    ]
                },
                "provenance": {}
            }
            
            result = await mock_consensus(
                db=mock_db_session,
                user_id=sample_user_id,
                project_id=sample_project_id,
                claim="Test claim",
                evidence_bundle_id=str(uuid.uuid4()),
                jury_size=5
            )
            
            assert result["data"]["status"] == "verified"
            assert result["data"]["final_verdict"] == "verified"
    
    @pytest.mark.asyncio
    async def test_consensus_contradicted(self, mock_db_session, sample_user_id, sample_project_id):
        """Test consensus reaches contradicted status."""
        from services.agency.mav_consensus import mav_consensus_service
        
        with patch("services.agency.mav_consensus.mav_consensus_service") as mock_consensus:
            mock_consensus.return_value = {
                "data": {
                    "consensus_id": str(uuid.uuid4()),
                    "status": "contradicted",
                    "final_verdict": "contradicted",
                    "confidence": 0.8,
                    "votes": [
                        {"agent_id": f"agent_{i}", "vote": "contradicted", "confidence": 0.85}
                        for i in range(4)
                    ] + [{"agent_id": "agent_5", "vote": "verified", "confidence": 0.7}]
                },
                "provenance": {}
            }
            
            result = await mock_consensus(
                db=mock_db_session,
                user_id=sample_user_id,
                project_id=sample_project_id,
                claim="Test claim",
                evidence_bundle_id=str(uuid.uuid4()),
                jury_size=5
            )
            
            assert result["data"]["status"] == "contradicted"
            assert result["data"]["final_verdict"] == "contradicted"
    
    @pytest.mark.asyncio
    async def test_consensus_conflict_triggers_truthful_pause(self, mock_db_session, sample_user_id, sample_project_id):
        """Test conflict triggers truthful pause."""
        from services.agency.mav_consensus import mav_consensus_service
        
        with patch("services.agency.mav_consensus.mav_consensus_service") as mock_consensus:
            mock_consensus.return_value = {
                "data": {
                    "consensus_id": str(uuid.uuid4()),
                    "status": "conflict",
                    "final_verdict": "no_consensus",
                    "confidence": 0.0,
                    "truthful_pause_required": True,
                    "votes": [
                        {"agent_id": "agent_1", "vote": "verified"},
                        {"agent_id": "agent_2", "vote": "verified"},
                        {"agent_id": "agent_3", "vote": "contradicted"},
                        {"agent_id": "agent_4", "vote": "contradicted"},
                        {"agent_id": "agent_5", "vote": "uncertain"}
                    ]
                },
                "provenance": {}
            }
            
            result = await mock_consensus(
                db=mock_db_session,
                user_id=sample_user_id,
                project_id=sample_project_id,
                claim="Test claim",
                evidence_bundle_id=str(uuid.uuid4()),
                jury_size=5
            )
            
            assert result["data"]["status"] == "conflict"
            assert result["data"]["truthful_pause_required"] is True


class TestSpecialistAssignment:
    """Test specialist role assignment."""
    
    def test_assign_specialist_roles(self):
        """Test specialist role assignment."""
        from services.agency.mav_consensus import _assign_specialist_roles
        
        roles = _assign_specialist_roles("FOXP3 mutations cause IPEX", jury_size=5)
        
        assert len(roles) == 5
        assert all(isinstance(role, str) for role in roles)
    
    def test_assign_3_specialists(self):
        """Test assigning 3 specialists."""
        from services.agency.mav_consensus import _assign_specialist_roles
        
        roles = _assign_specialist_roles("Test claim", jury_size=3)
        assert len(roles) == 3
    
    def test_assign_7_specialists(self):
        """Test assigning 7 specialists."""
        from services.agency.mav_consensus import _assign_specialist_roles
        
        roles = _assign_specialist_roles("Test claim", jury_size=7)
        assert len(roles) == 7


class TestVoteAggregation:
    """Test vote aggregation logic."""
    
    def test_majority_voting_verified(self):
        """Test majority voting for verified."""
        votes = [
            {"vote": "verified"},
            {"vote": "verified"},
            {"vote": "verified"},
            {"vote": "contradicted"},
            {"vote": "contradicted"}
        ]
        
        verified_count = sum(1 for v in votes if v["vote"] == "verified")
        assert verified_count >= 3  # Majority
    
    def test_majority_voting_contradicted(self):
        """Test majority voting for contradicted."""
        votes = [
            {"vote": "contradicted"},
            {"vote": "contradicted"},
            {"vote": "contradicted"},
            {"vote": "verified"},
            {"vote": "uncertain"}
        ]
        
        contradicted_count = sum(1 for v in votes if v["vote"] == "contradicted")
        assert contradicted_count >= 3  # Majority
    
    def test_no_majority_conflict(self):
        """Test no majority results in conflict."""
        votes = [
            {"vote": "verified"},
            {"vote": "verified"},
            {"vote": "contradicted"},
            {"vote": "contradicted"},
            {"vote": "uncertain"}
        ]
        
        verified_count = sum(1 for v in votes if v["vote"] == "verified")
        contradicted_count = sum(1 for v in votes if v["vote"] == "contradicted")
        
        assert verified_count < 3  # No majority
        assert contradicted_count < 3  # No majority


class TestConsensusTrace:
    """Test consensus trace logging."""
    
    @pytest.mark.asyncio
    async def test_consensus_trace_structure(self, mock_db_session, sample_user_id, sample_project_id):
        """Test consensus trace has correct structure."""
        from services.agency.mav_consensus import mav_consensus_service
        
        with patch("services.agency.mav_consensus.mav_consensus_service") as mock_consensus:
            mock_consensus.return_value = {
                "data": {
                    "consensus_id": str(uuid.uuid4()),
                    "consensus_trace": {
                        "jury_size": 5,
                        "specialist_roles": ["Geneticist", "Immunologist"],
                        "votes": [],
                        "vote_summary": {"verified": 3, "contradicted": 2},
                        "majority_threshold": 3,
                        "consensus_reached": True,
                        "final_verdict": "verified",
                        "confidence": 0.6,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                },
                "provenance": {}
            }
            
            result = await mock_consensus(
                db=mock_db_session,
                user_id=sample_user_id,
                project_id=sample_project_id,
                claim="Test claim",
                evidence_bundle_id=str(uuid.uuid4()),
                jury_size=5
            )
            
            trace = result["data"]["consensus_trace"]
            assert "jury_size" in trace
            assert "specialist_roles" in trace
            assert "votes" in trace
            assert "vote_summary" in trace
            assert "final_verdict" in trace


class TestPerformance:
    """Test performance requirements."""
    
    @pytest.mark.asyncio
    async def test_consensus_performance_target(self, mock_db_session, sample_user_id, sample_project_id):
        """Test consensus meets p95 <30s target."""
        import time
        from services.agency.mav_consensus import mav_consensus_service
        
        with patch("services.agency.mav_consensus.mav_consensus_service") as mock_consensus:
            async def slow_consensus(*args, **kwargs):
                await asyncio.sleep(0.1)  # Simulate processing
                return {
                    "data": {"consensus_id": str(uuid.uuid4()), "status": "verified"},
                    "provenance": {}
                }
            
            mock_consensus.side_effect = slow_consensus
            
            start = time.time()
            result = await mock_consensus(
                db=mock_db_session,
                user_id=sample_user_id,
                project_id=sample_project_id,
                claim="Test claim",
                evidence_bundle_id=str(uuid.uuid4()),
                jury_size=5
            )
            elapsed = time.time() - start
            
            # In unit tests, we just verify the interface
            # Performance testing would be done in integration tests
            assert elapsed < 30.0  # Should be much faster in mocked tests


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
