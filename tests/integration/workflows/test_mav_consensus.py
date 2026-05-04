"""
Integration tests for MAV (Multi-Agent Voting) Consensus Workflow
"""

import pytest
from fastapi.testclient import TestClient
from apps.api.main import app
from apps.api.core.db import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# Test database setup
TEST_DATABASE_URL = "postgresql://test:test@localhost:5432/drug_designer_test"
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def client():
    """Test client fixture"""
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    """Authenticated headers fixture"""
    client.post("/api/v1/auth/register", json={
        "email": "mav@example.com",
        "password": "SecurePassword123!",
        "full_name": "MAV User"
    })
    
    login_response = client.post("/api/v1/auth/login", json={
        "email": "mav@example.com",
        "password": "SecurePassword123!"
    })
    
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_mav_consensus_workflow_complete(client, auth_headers):
    """Test complete MAV consensus workflow"""
    # Step 1: Create MAV session
    create_response = client.post("/api/v1/mav/session",
        json={
            "question": "What is the best target for IPEX syndrome?",
            "agents": ["geneticist", "immunologist", "drug_designer", "clinician"],
            "voting_method": "weighted"
        },
        headers=auth_headers
    )
    
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]
    
    # Step 2: Get agent responses
    responses_response = client.get(f"/api/v1/mav/session/{session_id}/responses", headers=auth_headers)
    assert responses_response.status_code == 200
    responses = responses_response.json()["responses"]
    assert len(responses) == 4  # One per agent
    
    # Step 3: Collect votes
    votes_response = client.get(f"/api/v1/mav/session/{session_id}/votes", headers=auth_headers)
    assert votes_response.status_code == 200
    votes = votes_response.json()["votes"]
    assert len(votes) == 4
    
    # Step 4: Calculate consensus
    consensus_response = client.post(f"/api/v1/mav/session/{session_id}/consensus",
        json={},
        headers=auth_headers
    )
    
    assert consensus_response.status_code == 200
    consensus = consensus_response.json()
    assert "consensus_answer" in consensus
    assert "confidence_score" in consensus
    assert "agreement_level" in consensus
    assert 0 <= consensus["confidence_score"] <= 1
    
    # Step 5: Get provenance trace
    provenance_response = client.get(f"/api/v1/mav/session/{session_id}/provenance", headers=auth_headers)
    assert provenance_response.status_code == 200
    provenance = provenance_response.json()
    assert "agent_contributions" in provenance
    assert "reasoning_chain" in provenance


def test_mav_weighted_voting(client, auth_headers):
    """Test weighted voting mechanism"""
    response = client.post("/api/v1/mav/session",
        json={
            "question": "What is the optimal dose?",
            "agents": ["pharmacologist", "clinician", "toxicologist"],
            "voting_method": "weighted",
            "agent_weights": {
                "pharmacologist": 0.4,
                "clinician": 0.4,
                "toxicologist": 0.2
            }
        },
        headers=auth_headers
    )
    
    assert response.status_code == 201
    session_id = response.json()["session_id"]
    
    # Get consensus with weights applied
    consensus_response = client.post(f"/api/v1/mav/session/{session_id}/consensus",
        json={},
        headers=auth_headers
    )
    
    assert consensus_response.status_code == 200
    consensus = consensus_response.json()
    assert "weighted_score" in consensus


def test_mav_majority_voting(client, auth_headers):
    """Test majority voting mechanism"""
    response = client.post("/api/v1/mav/session",
        json={
            "question": "Should we proceed to Phase II?",
            "agents": ["agent1", "agent2", "agent3", "agent4", "agent5"],
            "voting_method": "majority"
        },
        headers=auth_headers
    )
    
    assert response.status_code == 201
    session_id = response.json()["session_id"]
    
    consensus_response = client.post(f"/api/v1/mav/session/{session_id}/consensus",
        json={},
        headers=auth_headers
    )
    
    assert consensus_response.status_code == 200
    consensus = consensus_response.json()
    assert "majority_vote" in consensus


def test_mav_unanimous_requirement(client, auth_headers):
    """Test unanimous voting requirement"""
    response = client.post("/api/v1/mav/session",
        json={
            "question": "Is this compound safe?",
            "agents": ["safety_expert1", "safety_expert2", "safety_expert3"],
            "voting_method": "unanimous"
        },
        headers=auth_headers
    )
    
    assert response.status_code == 201
    session_id = response.json()["session_id"]
    
    consensus_response = client.post(f"/api/v1/mav/session/{session_id}/consensus",
        json={},
        headers=auth_headers
    )
    
    assert consensus_response.status_code == 200
    consensus = consensus_response.json()
    assert "unanimous" in consensus


def test_mav_disagreement_handling(client, auth_headers):
    """Test handling of agent disagreement"""
    response = client.post("/api/v1/mav/session",
        json={
            "question": "What is the mechanism of action?",
            "agents": ["expert1", "expert2", "expert3"],
            "voting_method": "weighted",
            "disagreement_threshold": 0.3
        },
        headers=auth_headers
    )
    
    assert response.status_code == 201
    session_id = response.json()["session_id"]
    
    consensus_response = client.post(f"/api/v1/mav/session/{session_id}/consensus",
        json={},
        headers=auth_headers
    )
    
    assert consensus_response.status_code == 200
    consensus = consensus_response.json()
    
    if "disagreement_detected" in consensus and consensus["disagreement_detected"]:
        assert "conflicting_opinions" in consensus
        assert "resolution_strategy" in consensus


def test_mav_confidence_scoring(client, auth_headers):
    """Test confidence score calculation"""
    response = client.post("/api/v1/mav/session",
        json={
            "question": "What is the predicted efficacy?",
            "agents": ["predictor1", "predictor2", "predictor3"]
        },
        headers=auth_headers
    )
    
    session_id = response.json()["session_id"]
    
    consensus_response = client.post(f"/api/v1/mav/session/{session_id}/consensus",
        json={},
        headers=auth_headers
    )
    
    consensus = consensus_response.json()
    assert "confidence_score" in consensus
    assert "confidence_breakdown" in consensus
    assert 0 <= consensus["confidence_score"] <= 1


def test_mav_agent_expertise_weighting(client, auth_headers):
    """Test automatic expertise-based weighting"""
    response = client.post("/api/v1/mav/session",
        json={
            "question": "What is the best synthesis route?",
            "agents": ["chemist", "process_engineer", "analyst"],
            "auto_weight_by_expertise": True
        },
        headers=auth_headers
    )
    
    assert response.status_code == 201
    session_id = response.json()["session_id"]
    
    # Get agent weights
    weights_response = client.get(f"/api/v1/mav/session/{session_id}/weights", headers=auth_headers)
    assert weights_response.status_code == 200
    weights = weights_response.json()["weights"]
    assert len(weights) == 3
    assert all(0 <= w <= 1 for w in weights.values())


def test_mav_iterative_refinement(client, auth_headers):
    """Test iterative consensus refinement"""
    response = client.post("/api/v1/mav/session",
        json={
            "question": "What is the optimal formulation?",
            "agents": ["formulator1", "formulator2", "formulator3"],
            "max_iterations": 3
        },
        headers=auth_headers
    )
    
    session_id = response.json()["session_id"]
    
    # Run multiple consensus rounds
    for iteration in range(3):
        consensus_response = client.post(f"/api/v1/mav/session/{session_id}/consensus",
            json={"iteration": iteration},
            headers=auth_headers
        )
        assert consensus_response.status_code == 200


def test_mav_provenance_tracking(client, auth_headers):
    """Test detailed provenance tracking"""
    response = client.post("/api/v1/mav/session",
        json={
            "question": "What is the target validation score?",
            "agents": ["validator1", "validator2"]
        },
        headers=auth_headers
    )
    
    session_id = response.json()["session_id"]
    
    # Get provenance
    provenance_response = client.get(f"/api/v1/mav/session/{session_id}/provenance", headers=auth_headers)
    assert provenance_response.status_code == 200
    provenance = provenance_response.json()
    
    assert "agent_contributions" in provenance
    assert "reasoning_chain" in provenance
    assert "evidence_sources" in provenance
    assert "timestamps" in provenance


def test_mav_export_consensus(client, auth_headers):
    """Test consensus export"""
    response = client.post("/api/v1/mav/session",
        json={
            "question": "Test question",
            "agents": ["agent1", "agent2"]
        },
        headers=auth_headers
    )
    
    session_id = response.json()["session_id"]
    
    # Calculate consensus
    client.post(f"/api/v1/mav/session/{session_id}/consensus", json={}, headers=auth_headers)
    
    # Export
    export_response = client.get(f"/api/v1/mav/session/{session_id}/export",
        headers=auth_headers
    )
    
    assert export_response.status_code == 200
    assert export_response.headers["content-type"] in ["application/json", "application/pdf"]


def test_mav_session_history(client, auth_headers):
    """Test MAV session history"""
    # Create multiple sessions
    for i in range(3):
        client.post("/api/v1/mav/session",
            json={"question": f"Question {i}", "agents": ["agent1", "agent2"]},
            headers=auth_headers
        )
    
    # Get history
    history_response = client.get("/api/v1/mav/sessions", headers=auth_headers)
    assert history_response.status_code == 200
    sessions = history_response.json()["sessions"]
    assert len(sessions) >= 3


def test_mav_performance(client, auth_headers):
    """Test MAV consensus performance"""
    import time
    
    start = time.time()
    response = client.post("/api/v1/mav/session",
        json={
            "question": "Performance test",
            "agents": ["agent1", "agent2", "agent3"]
        },
        headers=auth_headers
    )
    duration = time.time() - start
    
    assert response.status_code == 201
    assert duration < 3.0  # Should complete in under 3 seconds
