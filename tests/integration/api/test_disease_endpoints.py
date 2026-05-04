"""
Integration tests for disease search and analysis endpoints
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
        "email": "disease@example.com",
        "password": "SecurePassword123!",
        "full_name": "Disease User"
    })
    
    login_response = client.post("/api/v1/auth/login", json={
        "email": "disease@example.com",
        "password": "SecurePassword123!"
    })
    
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_search_diseases(client, auth_headers):
    """Test disease search"""
    response = client.post("/api/v1/disease/search", json={
        "query": "IPEX syndrome",
        "limit": 10
    }, headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) > 0


def test_get_disease_by_id(client, auth_headers):
    """Test getting disease details"""
    # First search
    search_response = client.post("/api/v1/disease/search", json={
        "query": "IPEX syndrome",
        "limit": 1
    }, headers=auth_headers)
    
    disease_id = search_response.json()["results"][0]["id"]
    
    # Get details
    response = client.get(f"/api/v1/disease/{disease_id}", headers=auth_headers)
    
    assert response.status_code == 200
    disease = response.json()
    assert disease["id"] == disease_id
    assert "name" in disease


def test_disease_pathway_analysis(client, auth_headers):
    """Test disease pathway analysis"""
    response = client.post("/api/v1/disease/pathway-analysis", json={
        "disease": "IPEX syndrome",
        "genes": ["FOXP3", "IL2"],
        "databases": ["kegg", "reactome"]
    }, headers=auth_headers)
    
    assert response.status_code == 200
    pathways = response.json()["pathways"]
    assert len(pathways) > 0


def test_disease_biomarkers(client, auth_headers):
    """Test biomarker discovery"""
    response = client.post("/api/v1/disease/biomarkers", json={
        "disease": "IPEX syndrome",
        "biomarker_types": ["genetic", "protein"]
    }, headers=auth_headers)
    
    assert response.status_code == 200
    biomarkers = response.json()["biomarkers"]
    assert len(biomarkers) > 0


def test_disease_similarity(client, auth_headers):
    """Test disease similarity analysis"""
    response = client.post("/api/v1/disease/similarity", json={
        "disease": "IPEX syndrome",
        "similarity_metrics": ["genetic", "phenotypic"],
        "limit": 10
    }, headers=auth_headers)
    
    assert response.status_code == 200
    similar = response.json()["similar_diseases"]
    assert len(similar) > 0


def test_disease_phenotypes(client, auth_headers):
    """Test disease phenotype retrieval"""
    response = client.get("/api/v1/disease/IPEX_syndrome/phenotypes",
        headers=auth_headers)
    
    assert response.status_code == 200
    phenotypes = response.json()["phenotypes"]
    assert len(phenotypes) > 0


def test_disease_genetics(client, auth_headers):
    """Test disease genetic information"""
    response = client.get("/api/v1/disease/IPEX_syndrome/genetics",
        headers=auth_headers)
    
    assert response.status_code == 200
    genetics = response.json()
    assert "genes" in genetics
    assert "variants" in genetics
