"""
Integration tests for Clinical Workflow (10 stages)
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
        "email": "clinical@example.com",
        "password": "SecurePassword123!",
        "full_name": "Clinical User"
    })
    
    login_response = client.post("/api/v1/auth/login", json={
        "email": "clinical@example.com",
        "password": "SecurePassword123!"
    })
    
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_clinical_workflow_complete_10_stages(client, auth_headers):
    """Test complete 10-stage clinical workflow"""
    # Create clinical workflow
    create_response = client.post("/api/v1/clinical/workflow",
        json={
            "compound_id": "test_compound_001",
            "indication": "IPEX syndrome"
        },
        headers=auth_headers
    )
    
    assert create_response.status_code == 201
    workflow_id = create_response.json()["workflow_id"]
    
    # Stage 1: Preclinical Research
    stage1_response = client.post(f"/api/v1/clinical/workflow/{workflow_id}/stage/1",
        json={
            "stage_name": "preclinical_research",
            "data": {
                "in_vitro_studies": "completed",
                "in_vivo_studies": "completed",
                "toxicology": "passed"
            }
        },
        headers=auth_headers
    )
    assert stage1_response.status_code == 200
    
    # Stage 2: IND Application
    stage2_response = client.post(f"/api/v1/clinical/workflow/{workflow_id}/stage/2",
        json={
            "stage_name": "ind_application",
            "data": {
                "application_submitted": True,
                "fda_response": "approved"
            }
        },
        headers=auth_headers
    )
    assert stage2_response.status_code == 200
    
    # Stage 3: Phase I Clinical Trial
    stage3_response = client.post(f"/api/v1/clinical/workflow/{workflow_id}/stage/3",
        json={
            "stage_name": "phase_1",
            "data": {
                "participants": 30,
                "safety_profile": "acceptable",
                "dose_range": "10-100mg"
            }
        },
        headers=auth_headers
    )
    assert stage3_response.status_code == 200
    
    # Stage 4: Phase II Clinical Trial
    stage4_response = client.post(f"/api/v1/clinical/workflow/{workflow_id}/stage/4",
        json={
            "stage_name": "phase_2",
            "data": {
                "participants": 100,
                "efficacy": "demonstrated",
                "adverse_events": "manageable"
            }
        },
        headers=auth_headers
    )
    assert stage4_response.status_code == 200
    
    # Stage 5: Phase III Clinical Trial
    stage5_response = client.post(f"/api/v1/clinical/workflow/{workflow_id}/stage/5",
        json={
            "stage_name": "phase_3",
            "data": {
                "participants": 1000,
                "primary_endpoint_met": True,
                "statistical_significance": "p<0.001"
            }
        },
        headers=auth_headers
    )
    assert stage5_response.status_code == 200
    
    # Stage 6: NDA Submission
    stage6_response = client.post(f"/api/v1/clinical/workflow/{workflow_id}/stage/6",
        json={
            "stage_name": "nda_submission",
            "data": {
                "submission_date": "2026-01-15",
                "priority_review": True
            }
        },
        headers=auth_headers
    )
    assert stage6_response.status_code == 200
    
    # Stage 7: FDA Review
    stage7_response = client.post(f"/api/v1/clinical/workflow/{workflow_id}/stage/7",
        json={
            "stage_name": "fda_review",
            "data": {
                "review_status": "approved",
                "approval_date": "2026-07-15"
            }
        },
        headers=auth_headers
    )
    assert stage7_response.status_code == 200
    
    # Stage 8: Post-Market Surveillance
    stage8_response = client.post(f"/api/v1/clinical/workflow/{workflow_id}/stage/8",
        json={
            "stage_name": "post_market_surveillance",
            "data": {
                "adverse_event_reports": 50,
                "serious_adverse_events": 2
            }
        },
        headers=auth_headers
    )
    assert stage8_response.status_code == 200
    
    # Stage 9: Phase IV Studies
    stage9_response = client.post(f"/api/v1/clinical/workflow/{workflow_id}/stage/9",
        json={
            "stage_name": "phase_4",
            "data": {
                "long_term_efficacy": "maintained",
                "new_indications": ["related_condition"]
            }
        },
        headers=auth_headers
    )
    assert stage9_response.status_code == 200
    
    # Stage 10: Lifecycle Management
    stage10_response = client.post(f"/api/v1/clinical/workflow/{workflow_id}/stage/10",
        json={
            "stage_name": "lifecycle_management",
            "data": {
                "patent_status": "active",
                "market_performance": "strong"
            }
        },
        headers=auth_headers
    )
    assert stage10_response.status_code == 200
    
    # Get final workflow status
    final_response = client.get(f"/api/v1/clinical/workflow/{workflow_id}", headers=auth_headers)
    assert final_response.status_code == 200
    workflow = final_response.json()
    assert workflow["current_stage"] == 10
    assert workflow["status"] == "completed"


def test_workflow_stage_validation(client, auth_headers):
    """Test workflow stage validation"""
    # Create workflow
    create_response = client.post("/api/v1/clinical/workflow",
        json={"compound_id": "test_compound_002", "indication": "Test Disease"},
        headers=auth_headers
    )
    workflow_id = create_response.json()["workflow_id"]
    
    # Try to skip to stage 3 without completing stage 1
    response = client.post(f"/api/v1/clinical/workflow/{workflow_id}/stage/3",
        json={"stage_name": "phase_1", "data": {}},
        headers=auth_headers
    )
    
    assert response.status_code == 400
    assert "prerequisite" in response.json()["detail"].lower() or "order" in response.json()["detail"].lower()


def test_workflow_rollback(client, auth_headers):
    """Test workflow rollback"""
    # Create and progress workflow
    create_response = client.post("/api/v1/clinical/workflow",
        json={"compound_id": "test_compound_003", "indication": "Test Disease"},
        headers=auth_headers
    )
    workflow_id = create_response.json()["workflow_id"]
    
    # Complete stage 1
    client.post(f"/api/v1/clinical/workflow/{workflow_id}/stage/1",
        json={"stage_name": "preclinical_research", "data": {"status": "completed"}},
        headers=auth_headers
    )
    
    # Rollback to previous stage
    rollback_response = client.post(f"/api/v1/clinical/workflow/{workflow_id}/rollback",
        json={"target_stage": 0, "reason": "Data correction needed"},
        headers=auth_headers
    )
    
    assert rollback_response.status_code == 200


def test_workflow_parallel_execution(client, auth_headers):
    """Test parallel workflow execution"""
    # Create multiple workflows
    workflow_ids = []
    for i in range(3):
        response = client.post("/api/v1/clinical/workflow",
            json={"compound_id": f"compound_{i}", "indication": "Test Disease"},
            headers=auth_headers
        )
        workflow_ids.append(response.json()["workflow_id"])
    
    # Execute stage 1 for all workflows
    for wf_id in workflow_ids:
        response = client.post(f"/api/v1/clinical/workflow/{wf_id}/stage/1",
            json={"stage_name": "preclinical_research", "data": {}},
            headers=auth_headers
        )
        assert response.status_code == 200


def test_workflow_websocket_updates(client, auth_headers):
    """Test real-time workflow updates via WebSocket"""
    # Note: This is a placeholder for WebSocket testing
    # Actual WebSocket testing would require a different setup
    response = client.get("/api/v1/clinical/workflow/ws-info", headers=auth_headers)
    assert response.status_code == 200
    ws_info = response.json()
    assert "websocket_url" in ws_info


def test_workflow_audit_trail(client, auth_headers):
    """Test workflow audit trail"""
    # Create workflow
    create_response = client.post("/api/v1/clinical/workflow",
        json={"compound_id": "test_compound_audit", "indication": "Test Disease"},
        headers=auth_headers
    )
    workflow_id = create_response.json()["workflow_id"]
    
    # Complete stage 1
    client.post(f"/api/v1/clinical/workflow/{workflow_id}/stage/1",
        json={"stage_name": "preclinical_research", "data": {}},
        headers=auth_headers
    )
    
    # Get audit trail
    audit_response = client.get(f"/api/v1/clinical/workflow/{workflow_id}/audit", headers=auth_headers)
    assert audit_response.status_code == 200
    audit_trail = audit_response.json()
    assert len(audit_trail["events"]) > 0
    assert all("timestamp" in event for event in audit_trail["events"])
    assert all("user" in event for event in audit_trail["events"])


def test_workflow_export(client, auth_headers):
    """Test workflow export"""
    # Create workflow
    create_response = client.post("/api/v1/clinical/workflow",
        json={"compound_id": "test_compound_export", "indication": "Test Disease"},
        headers=auth_headers
    )
    workflow_id = create_response.json()["workflow_id"]
    
    # Export workflow
    export_response = client.get(f"/api/v1/clinical/workflow/{workflow_id}/export",
        headers=auth_headers
    )
    
    assert export_response.status_code == 200
    assert export_response.headers["content-type"] in ["application/json", "application/pdf"]


def test_workflow_performance(client, auth_headers):
    """Test workflow performance"""
    import time
    
    start = time.time()
    response = client.post("/api/v1/clinical/workflow",
        json={"compound_id": "perf_test", "indication": "Test Disease"},
        headers=auth_headers
    )
    duration = time.time() - start
    
    assert response.status_code == 201
    assert duration < 2.0  # Should complete in under 2 seconds
