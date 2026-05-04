"""
Integration tests for evidence search and retrieval endpoints
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
        "email": "evidence@example.com",
        "password": "SecurePassword123!",
        "full_name": "Evidence User"
    })
    
    login_response = client.post("/api/v1/auth/login", json={
        "email": "evidence@example.com",
        "password": "SecurePassword123!"
    })
    
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_search_evidence(client, auth_headers):
    """Test evidence search"""
    response = client.post("/api/v1/evidence/search", json={
        "query": "FOXP3 mutations",
        "sources": ["pubmed", "clinvar"],
        "limit": 50
    }, headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) > 0


def test_search_evidence_with_filters(client, auth_headers):
    """Test evidence search with filters"""
    response = client.post("/api/v1/evidence/search", json={
        "query": "FOXP3",
        "sources": ["pubmed"],
        "filters": {
            "publication_year": {"min": 2020, "max": 2024},
            "evidence_type": ["genetic", "clinical"]
        },
        "limit": 20
    }, headers=auth_headers)
    
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) > 0


def test_get_evidence_by_id(client, auth_headers):
    """Test getting evidence by ID"""
    # First search for evidence
    search_response = client.post("/api/v1/evidence/search", json={
        "query": "FOXP3",
        "sources": ["pubmed"],
        "limit": 1
    }, headers=auth_headers)
    
    evidence_id = search_response.json()["results"][0]["id"]
    
    # Get evidence details
    response = client.get(f"/api/v1/evidence/{evidence_id}", headers=auth_headers)
    
    assert response.status_code == 200
    evidence = response.json()
    assert evidence["id"] == evidence_id


def test_bulk_evidence_import(client, auth_headers):
    """Test bulk evidence import"""
    response = client.post("/api/v1/evidence/bulk-import", json={
        "evidence_items": [
            {
                "source": "pubmed",
                "external_id": "PMID:12345678",
                "title": "Test Article 1",
                "abstract": "Test abstract 1",
                "evidence_type": "literature"
            },
            {
                "source": "clinvar",
                "external_id": "VCV000123456",
                "title": "Test Variant 1",
                "description": "Test variant description",
                "evidence_type": "genetic"
            }
        ]
    }, headers=auth_headers)
    
    assert response.status_code == 200
    result = response.json()
    assert "imported_count" in result
    assert result["imported_count"] == 2


def test_evidence_aggregation(client, auth_headers):
    """Test evidence aggregation"""
    response = client.post("/api/v1/evidence/aggregate", json={
        "query": "FOXP3 mutations",
        "sources": ["pubmed", "clinvar", "omim"],
        "aggregate_by": "evidence_type"
    }, headers=auth_headers)
    
    assert response.status_code == 200
    aggregated = response.json()
    assert "genetic_evidence" in aggregated or "literature_evidence" in aggregated


def test_evidence_provenance(client, auth_headers):
    """Test evidence provenance tracking"""
    # Search for evidence
    search_response = client.post("/api/v1/evidence/search", json={
        "query": "FOXP3",
        "sources": ["pubmed"],
        "limit": 1
    }, headers=auth_headers)
    
    evidence_id = search_response.json()["results"][0]["id"]
    
    # Get provenance
    response = client.get(f"/api/v1/evidence/{evidence_id}/provenance", headers=auth_headers)
    
    assert response.status_code == 200
    provenance = response.json()
    assert "source" in provenance
    assert "timestamp" in provenance
    assert "retrieval_method" in provenance


def test_evidence_citation(client, auth_headers):
    """Test evidence citation generation"""
    # Search for evidence
    search_response = client.post("/api/v1/evidence/search", json={
        "query": "FOXP3",
        "sources": ["pubmed"],
        "limit": 1
    }, headers=auth_headers)
    
    evidence_id = search_response.json()["results"][0]["id"]
    
    # Get citation
    response = client.get(f"/api/v1/evidence/{evidence_id}/citation?format=apa", headers=auth_headers)
    
    assert response.status_code == 200
    citation = response.json()
    assert "citation_text" in citation
    assert len(citation["citation_text"]) > 0


def test_evidence_export(client, auth_headers):
    """Test evidence export"""
    # Search for evidence
    search_response = client.post("/api/v1/evidence/search", json={
        "query": "FOXP3",
        "sources": ["pubmed"],
        "limit": 5
    }, headers=auth_headers)
    
    evidence_ids = [e["id"] for e in search_response.json()["results"]]
    
    # Export evidence
    response = client.post("/api/v1/evidence/export", json={
        "evidence_ids": evidence_ids,
        "format": "json"
    }, headers=auth_headers)
    
    assert response.status_code == 200


def test_evidence_validation(client, auth_headers):
    """Test evidence validation"""
    response = client.post("/api/v1/evidence/validate", json={
        "evidence_id": "test_evidence_001",
        "validation_criteria": ["source_reliability", "data_completeness", "citation_accuracy"]
    }, headers=auth_headers)
    
    assert response.status_code == 200
    validation = response.json()
    assert "validation_score" in validation
    assert "validation_details" in validation


def test_evidence_search_performance(client, auth_headers):
    """Test evidence search performance"""
    import time
    
    start = time.time()
    response = client.post("/api/v1/evidence/search", json={
        "query": "FOXP3",
        "sources": ["pubmed"],
        "limit": 10
    }, headers=auth_headers)
    duration = time.time() - start
    
    assert response.status_code == 200
    assert duration < 3.0  # Should complete in under 3 seconds
