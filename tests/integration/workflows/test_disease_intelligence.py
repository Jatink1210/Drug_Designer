"""
Integration tests for Disease Intelligence Workflow
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
    # Register and login
    client.post("/api/v1/auth/register", json={
        "email": "workflow@example.com",
        "password": "SecurePassword123!",
        "full_name": "Workflow User"
    })
    
    login_response = client.post("/api/v1/auth/login", json={
        "email": "workflow@example.com",
        "password": "SecurePassword123!"
    })
    
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_disease_intelligence_workflow_complete(client, auth_headers):
    """Test complete disease intelligence workflow"""
    # Step 1: Search for disease
    disease_response = client.post("/api/v1/disease/search", 
        json={"query": "IPEX syndrome", "limit": 10},
        headers=auth_headers
    )
    
    assert disease_response.status_code == 200
    diseases = disease_response.json()["results"]
    assert len(diseases) > 0
    disease_id = diseases[0]["id"]
    
    # Step 2: Get disease details
    detail_response = client.get(f"/api/v1/disease/{disease_id}", headers=auth_headers)
    assert detail_response.status_code == 200
    disease_details = detail_response.json()
    assert "name" in disease_details
    assert "description" in disease_details
    
    # Step 3: Discover targets for disease
    target_response = client.post("/api/v1/target/discover",
        json={"disease": "IPEX syndrome", "limit": 20},
        headers=auth_headers
    )
    
    assert target_response.status_code == 200
    targets = target_response.json()["targets"]
    assert len(targets) > 0
    assert "FOXP3" in [t["gene_symbol"] for t in targets]
    
    # Step 4: Search for evidence
    evidence_response = client.post("/api/v1/evidence/search",
        json={
            "query": "FOXP3 mutations IPEX",
            "sources": ["pubmed", "clinvar"],
            "limit": 50
        },
        headers=auth_headers
    )
    
    assert evidence_response.status_code == 200
    evidence = evidence_response.json()["results"]
    assert len(evidence) > 0
    
    # Step 5: Build knowledge graph
    graph_response = client.post("/api/v1/graph/build",
        json={
            "disease_id": disease_id,
            "target_ids": [t["id"] for t in targets[:5]],
            "evidence_ids": [e["id"] for e in evidence[:10]]
        },
        headers=auth_headers
    )
    
    assert graph_response.status_code == 200
    graph = graph_response.json()
    assert "nodes" in graph
    assert "edges" in graph
    assert len(graph["nodes"]) > 0


def test_disease_search_with_filters(client, auth_headers):
    """Test disease search with filters"""
    response = client.post("/api/v1/disease/search",
        json={
            "query": "syndrome",
            "filters": {
                "category": "genetic",
                "prevalence": "rare"
            },
            "limit": 20
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) > 0


def test_target_prioritization(client, auth_headers):
    """Test target prioritization"""
    response = client.post("/api/v1/target/prioritize",
        json={
            "disease": "IPEX syndrome",
            "criteria": {
                "druggability": 0.7,
                "genetic_evidence": 0.8,
                "expression_specificity": 0.6
            },
            "limit": 10
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    targets = response.json()["targets"]
    assert len(targets) > 0
    # Verify targets are sorted by priority score
    scores = [t["priority_score"] for t in targets]
    assert scores == sorted(scores, reverse=True)


def test_evidence_aggregation(client, auth_headers):
    """Test evidence aggregation across sources"""
    response = client.post("/api/v1/evidence/aggregate",
        json={
            "query": "FOXP3 mutations",
            "sources": ["pubmed", "clinvar", "omim", "orphanet"],
            "aggregate_by": "evidence_type"
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    aggregated = response.json()
    assert "genetic_evidence" in aggregated
    assert "clinical_evidence" in aggregated
    assert "literature_evidence" in aggregated


def test_pathway_analysis(client, auth_headers):
    """Test pathway analysis for disease"""
    response = client.post("/api/v1/disease/pathway-analysis",
        json={
            "disease": "IPEX syndrome",
            "genes": ["FOXP3", "IL2", "CD25"],
            "databases": ["kegg", "reactome"]
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    pathways = response.json()["pathways"]
    assert len(pathways) > 0
    assert all("pathway_id" in p for p in pathways)


def test_biomarker_discovery(client, auth_headers):
    """Test biomarker discovery"""
    response = client.post("/api/v1/disease/biomarkers",
        json={
            "disease": "IPEX syndrome",
            "biomarker_types": ["genetic", "protein", "metabolite"]
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    biomarkers = response.json()["biomarkers"]
    assert len(biomarkers) > 0


def test_disease_similarity_analysis(client, auth_headers):
    """Test disease similarity analysis"""
    response = client.post("/api/v1/disease/similarity",
        json={
            "disease": "IPEX syndrome",
            "similarity_metrics": ["genetic", "phenotypic", "pathway"],
            "limit": 10
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    similar_diseases = response.json()["similar_diseases"]
    assert len(similar_diseases) > 0
    assert all(0 <= d["similarity_score"] <= 1 for d in similar_diseases)


def test_workflow_state_management(client, auth_headers):
    """Test workflow state persistence"""
    # Create workflow
    create_response = client.post("/api/v1/workflow/disease-intelligence",
        json={
            "disease": "IPEX syndrome",
            "name": "IPEX Investigation"
        },
        headers=auth_headers
    )
    
    assert create_response.status_code == 201
    workflow_id = create_response.json()["workflow_id"]
    
    # Get workflow status
    status_response = client.get(f"/api/v1/workflow/{workflow_id}", headers=auth_headers)
    assert status_response.status_code == 200
    workflow = status_response.json()
    assert workflow["status"] in ["pending", "running", "completed", "failed"]
    
    # Update workflow
    update_response = client.patch(f"/api/v1/workflow/{workflow_id}",
        json={"status": "completed"},
        headers=auth_headers
    )
    assert update_response.status_code == 200


def test_workflow_error_handling(client, auth_headers):
    """Test workflow error handling"""
    # Invalid disease query
    response = client.post("/api/v1/disease/search",
        json={"query": "", "limit": 10},
        headers=auth_headers
    )
    
    assert response.status_code == 400
    assert "error" in response.json() or "detail" in response.json()


def test_workflow_performance(client, auth_headers):
    """Test workflow performance"""
    import time
    
    start = time.time()
    response = client.post("/api/v1/disease/search",
        json={"query": "IPEX syndrome", "limit": 10},
        headers=auth_headers
    )
    duration = time.time() - start
    
    assert response.status_code == 200
    assert duration < 3.0  # Should complete in under 3 seconds


def test_concurrent_workflows(client, auth_headers):
    """Test concurrent workflow execution"""
    import concurrent.futures
    
    def run_workflow():
        return client.post("/api/v1/disease/search",
            json={"query": "syndrome", "limit": 5},
            headers=auth_headers
        )
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(run_workflow) for _ in range(5)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    assert all(r.status_code == 200 for r in results)
