"""
Integration test for truthful pause endpoint.

This test verifies that the POST /api/v1/consensus/truthful-pause endpoint
correctly handles conflict resolution.
"""

import asyncio
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from models.db_tables import ConsensusResult, EvidenceBundleRecord, Base
from models.user import User, Project
from services.agency.truthful_pause import truthful_pause_service


async def test_truthful_pause():
    """Test the truthful pause service."""
    
    # Create in-memory SQLite database for testing
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Create test user
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            hashed_password="test_hash",
            display_name="Test User",
            role="owner"
        )
        session.add(user)
        
        # Create test project
        project = Project(
            id=str(uuid.uuid4()),
            title="Test Project",
            owner_id=user.id
        )
        session.add(project)
        
        # Create test evidence bundle
        bundle = EvidenceBundleRecord(
            id=str(uuid.uuid4()),
            project_id=project.id,
            title="Test Evidence Bundle",
            created_by=user.id
        )
        session.add(bundle)
        
        # Create test consensus result in conflict state
        consensus = ConsensusResult(
            id=str(uuid.uuid4()),
            claim="Test claim for consensus",
            evidence_bundle_id=bundle.id,
            jury_size=5,
            status="conflict",
            votes={
                "votes": [
                    {"agent_id": "agent1", "verdict": "verified", "confidence": 0.8},
                    {"agent_id": "agent2", "verdict": "contradicted", "confidence": 0.7},
                    {"agent_id": "agent3", "verdict": "verified", "confidence": 0.6},
                    {"agent_id": "agent4", "verdict": "contradicted", "confidence": 0.9},
                    {"agent_id": "agent5", "verdict": "insufficient", "confidence": 0.5}
                ]
            },
            consensus_trace={
                "votes": [
                    {"agent_id": "agent1", "verdict": "verified", "confidence": 0.8},
                    {"agent_id": "agent2", "verdict": "contradicted", "confidence": 0.7},
                    {"agent_id": "agent3", "verdict": "verified", "confidence": 0.6},
                    {"agent_id": "agent4", "verdict": "contradicted", "confidence": 0.9},
                    {"agent_id": "agent5", "verdict": "insufficient", "confidence": 0.5}
                ],
                "vote_summary": {
                    "verified": 2,
                    "contradicted": 2,
                    "insufficient": 1
                }
            }
        )
        session.add(consensus)
        await session.commit()
        
        print(f"✓ Created test consensus in conflict state: {consensus.id}")
        
        # Test 1: Accept verified decision
        print("\nTest 1: Accept verified decision")
        result = await truthful_pause_service(
            db=session,
            user_id=user.id,
            consensus_id=consensus.id,
            human_decision="accept_verified",
            rationale="Expert review confirms the claim is verified"
        )
        
        # Verify the result
        assert result["data"]["consensus_id"] == consensus.id
        assert result["data"]["new_status"] == "verified"
        assert result["data"]["final_verdict"] == "verified"
        assert result["data"]["human_decision"] == "accept_verified"
        assert result["data"]["rationale"] == "Expert review confirms the claim is verified"
        assert result["data"]["resolved_by"] == user.id
        assert "complete_audit_trail" in result["data"]
        
        print(f"✓ Consensus updated to: {result['data']['new_status']}")
        print(f"✓ Final verdict: {result['data']['final_verdict']}")
        print(f"✓ Audit trail includes truthful_pause_resolution")
        
        # Verify database was updated
        await session.refresh(consensus)
        assert consensus.status == "verified"
        assert consensus.votes["final_verdict"] == "verified"
        assert consensus.votes["human_override"] == True
        assert consensus.votes["human_decision"] == "accept_verified"
        assert "truthful_pause_resolution" in consensus.consensus_trace
        
        print("✓ Database correctly updated")
        
        # Test 2: Try to resolve already resolved consensus (should fail)
        print("\nTest 2: Try to resolve already resolved consensus")
        try:
            await truthful_pause_service(
                db=session,
                user_id=user.id,
                consensus_id=consensus.id,
                human_decision="accept_contradicted",
                rationale="This should fail"
            )
            print("✗ Should have raised an exception")
            assert False
        except Exception as e:
            assert "not in conflict state" in str(e)
            print(f"✓ Correctly rejected: {str(e)}")
        
        # Test 3: Create another consensus for accept_contradicted
        print("\nTest 3: Accept contradicted decision")
        consensus2 = ConsensusResult(
            id=str(uuid.uuid4()),
            claim="Another test claim",
            evidence_bundle_id=bundle.id,
            jury_size=3,
            status="conflict",
            votes={"votes": []},
            consensus_trace={"votes": [], "vote_summary": {}}
        )
        session.add(consensus2)
        await session.commit()
        
        result2 = await truthful_pause_service(
            db=session,
            user_id=user.id,
            consensus_id=consensus2.id,
            human_decision="accept_contradicted",
            rationale="Evidence shows contradiction"
        )
        
        assert result2["data"]["new_status"] == "contradicted"
        assert result2["data"]["final_verdict"] == "contradicted"
        print(f"✓ Consensus updated to: {result2['data']['new_status']}")
        
        # Test 4: Request more evidence
        print("\nTest 4: Request more evidence")
        consensus3 = ConsensusResult(
            id=str(uuid.uuid4()),
            claim="Third test claim",
            evidence_bundle_id=bundle.id,
            jury_size=3,
            status="conflict",
            votes={"votes": []},
            consensus_trace={"votes": [], "vote_summary": {}}
        )
        session.add(consensus3)
        await session.commit()
        
        result3 = await truthful_pause_service(
            db=session,
            user_id=user.id,
            consensus_id=consensus3.id,
            human_decision="request_more_evidence",
            rationale="Need additional studies"
        )
        
        assert result3["data"]["new_status"] == "pending_evidence"
        assert result3["data"]["final_verdict"] == "insufficient_evidence"
        print(f"✓ Consensus updated to: {result3['data']['new_status']}")
        
        print("\n" + "="*60)
        print("All tests passed! ✓")
        print("="*60)


if __name__ == "__main__":
    asyncio.run(test_truthful_pause())
