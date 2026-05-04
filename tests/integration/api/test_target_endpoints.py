"""
Integration tests for target discovery and analysis endpoints
"""

import pytest
from fastapi.testclient import TestClient
from apps.api.main import app
from apps.api.core.db import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


TEST_DATABASE_URL = "postgresql://test:test@localhost:5432/drug_designer_test"
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def client():
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
    client.post("/api/v1/auth/register", json={
        "email": "target@example.com",
        "password": "SecurePassword123!",
        "full_name": "Target User"
    })
    
    login_response = client.post("/api/v1/auth/login", json={
        "email": "target@example.com",
        "password": "SecurePassword123!"
    })
    
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_discover_targets(client, auth_headers):
    """Test target discovery"""
    response = client.post("/api/v1/target/discover", json={
        "disease": "IPEX syndrome",
        "limit": 20
    }, headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "targets" in data
    assert len(data["targets"]) > 0


def test_get_target_by_id(client, auth_headers):
    """Test getting target details"""
    # First discover targets
    discover_response = client.post("/api/v1/target/discover", json={
        "disease": "IPEX syndrome",
        "limit": 1
    }, headers=auth_headers)
    
    target_id = discover_response.json()["targets"][0]["id"]
    
    # Get target details
    response = client.get(f"/api/v1/target/{target_id}", headers=auth_headers)
    
    assert response.status_code == 200
    target = response.json()
    assert target["id"] == target_id
    assert "gene_symbol" in target


def test_bulk_score_targets(client, auth_headers):
    """Test bulk target scoring"""
    response = client.post("/api/v1/targets/bulk-score", json={
        "target_ids": ["target_001", "target_002", "target_003"],
        "scoring_criteria": {
            "druggability": 0.3,
            "genetic_evidence": 0.3,
            "expression": 0.2,
            "safety": 0.2
        }
    }, headers=auth_headers)
    
    assert response.status_code == 200
    result = response.json()
    assert "targets" in result
    assert len(result["targets"]) == 3


def test_prioritize_targets(client, auth_headers):
    """Test target prioritization"""
    response = client.post("/api/v1/target/prioritize", json={
        "disease": "IPEX syndrome",
        "criteria": {
            "druggability": 0.7,
            "genetic_evidence": 0.8,
            "expression_specificity": 0.6
        },
        "limit": 10
    }, headers=auth_headers)
    
    assert response.status_code == 200
    targets = response.json()["targets"]
    assert len(targets) > 0
    # Verify sorted by priority
    scores = [t["priority_score"] for t in targets]
    assert scores == sorted(scores, reverse=True)


def test_validate_target(client, auth_headers):
    """Test target validation"""
    response = client.post("/api/v1/target/validate", json={
        "target_gene": "FOXP3",
        "disease": "IPEX syndrome",
        "validation_criteria": ["genetic_evidence", "expression_data"]
    }, headers=auth_headers)
    
    assert response.status_code == 200
    validation = response.json()
    assert "validation_score" in validation


def test_get_target_structure(client, auth_headers):
    """Test getting target protein structure"""
    response = client.get("/api/v1/target/FOXP3/structure", headers=auth_headers)
    
    assert response.status_code == 200
    structure = response.json()
    assert "pdb_id" in structure or "predicted_structure" in structure


def test_predict_druggability(client, auth_headers):
    """Test druggability prediction"""
    response = client.post("/api/v1/target/FOXP3/druggability", json={},
        headers=auth_headers)
    
    assert response.status_code == 200
    druggability = response.json()
    assert "druggability_score" in druggability
    assert 0 <= druggability["druggability_score"] <= 1


def test_get_target_expression(client, auth_headers):
    """Test target expression data"""
    response = client.post("/api/v1/target/expression", json={
        "gene_symbol": "FOXP3",
        "tissues": ["blood", "spleen"],
        "databases": ["gtex"]
    }, headers=auth_headers)
    
    assert response.status_code == 200
    expression = response.json()
    assert "tissue_expression" in expression


def test_target_safety_assessment(client, auth_headers):
    """Test target safety assessment"""
    response = client.post("/api/v1/target/safety", json={
        "target_gene": "FOXP3",
        "assessment_types": ["knockout_phenotype", "tissue_specificity"]
    }, headers=auth_headers)
    
    assert response.status_code == 200
    safety = response.json()
    assert "safety_score" in safety


def test_target_interactions(client, auth_headers):
    """Test protein-protein interactions"""
    response = client.post("/api/v1/target/interactions", json={
        "target_gene": "FOXP3",
        "interaction_types": ["physical", "genetic"],
        "databases": ["string"]
    }, headers=auth_headers)
    
    assert response.status_code == 200
    interactions = response.json()
    assert "interactions" in interactions
