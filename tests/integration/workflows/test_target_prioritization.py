"""
Integration tests for Target Prioritization Workflow
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


def test_target_prioritization_workflow_complete(client, auth_headers):
    """Test complete target prioritization workflow"""
    # Step 1: Discover targets
    discover_response = client.post("/api/v1/target/discover",
        json={"disease": "IPEX syndrome", "limit": 20},
        headers=auth_headers
    )
    
    assert discover_response.status_code == 200
    targets = discover_response.json()["targets"]
    assert len(targets) > 0
    
    # Step 2: Score targets
    target_ids = [t["id"] for t in targets[:10]]
    score_response = client.post("/api/v1/targets/bulk-score",
        json={
            "target_ids": target_ids,
            "scoring_criteria": {
                "druggability": 0.3,
                "genetic_evidence": 0.3,
                "expression": 0.2,
                "safety": 0.2
            }
        },
        headers=auth_headers
    )
    
    assert score_response.status_code == 200
    scored_targets = score_response.json()["targets"]
    assert len(scored_targets) == len(target_ids)
    
    # Step 3: Get target details
    target_id = scored_targets[0]["id"]
    detail_response = client.get(f"/api/v1/target/{target_id}", headers=auth_headers)
    assert detail_response.status_code == 200
    target_details = detail_response.json()
    assert "gene_symbol" in target_details
    assert "protein_name" in target_details
    
    # Step 4: Get protein structure
    structure_response = client.get(f"/api/v1/target/{target_id}/structure", headers=auth_headers)
    assert structure_response.status_code == 200
    structure = structure_response.json()
    assert "pdb_id" in structure or "predicted_structure" in structure
    
    # Step 5: Predict druggability
    druggability_response = client.post(f"/api/v1/target/{target_id}/druggability",
        json={},
        headers=auth_headers
    )
    
    assert druggability_response.status_code == 200
    druggability = druggability_response.json()
    assert "druggability_score" in druggability
    assert 0 <= druggability["druggability_score"] <= 1


def test_target_discovery_with_filters(client, auth_headers):
    """Test target discovery with filters"""
    response = client.post("/api/v1/target/discover",
        json={
            "disease": "IPEX syndrome",
            "filters": {
                "target_class": ["kinase", "gpcr", "ion_channel"],
                "expression_tissue": ["immune_system"],
                "druggability_min": 0.5
            },
            "limit": 20
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    targets = response.json()["targets"]
    assert len(targets) > 0


def test_target_validation(client, auth_headers):
    """Test target validation"""
    response = client.post("/api/v1/target/validate",
        json={
            "target_gene": "FOXP3",
            "disease": "IPEX syndrome",
            "validation_criteria": ["genetic_evidence", "expression_data", "pathway_analysis"]
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    validation = response.json()
    assert "validation_score" in validation
    assert "evidence_summary" in validation


def test_target_expression_analysis(client, auth_headers):
    """Test target expression analysis"""
    response = client.post("/api/v1/target/expression",
        json={
            "gene_symbol": "FOXP3",
            "tissues": ["blood", "spleen", "thymus"],
            "databases": ["gtex", "hpa"]
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    expression = response.json()
    assert "tissue_expression" in expression
    assert len(expression["tissue_expression"]) > 0


def test_target_safety_assessment(client, auth_headers):
    """Test target safety assessment"""
    response = client.post("/api/v1/target/safety",
        json={
            "target_gene": "FOXP3",
            "assessment_types": ["knockout_phenotype", "tissue_specificity", "pathway_essentiality"]
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    safety = response.json()
    assert "safety_score" in safety
    assert "risk_factors" in safety


def test_target_tractability_analysis(client, auth_headers):
    """Test target tractability analysis"""
    response = client.post("/api/v1/target/tractability",
        json={
            "target_gene": "FOXP3",
            "modality": ["small_molecule", "antibody", "protein"]
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    tractability = response.json()
    assert "tractability_scores" in tractability
    assert all(m in tractability["tractability_scores"] for m in ["small_molecule", "antibody", "protein"])


def test_target_pathway_enrichment(client, auth_headers):
    """Test pathway enrichment for targets"""
    response = client.post("/api/v1/target/pathway-enrichment",
        json={
            "target_genes": ["FOXP3", "IL2", "CD25", "CTLA4"],
            "databases": ["kegg", "reactome", "go"]
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    enrichment = response.json()
    assert "enriched_pathways" in enrichment
    assert len(enrichment["enriched_pathways"]) > 0


def test_target_protein_interactions(client, auth_headers):
    """Test protein-protein interaction analysis"""
    response = client.post("/api/v1/target/interactions",
        json={
            "target_gene": "FOXP3",
            "interaction_types": ["physical", "genetic", "pathway"],
            "databases": ["string", "biogrid"]
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    interactions = response.json()
    assert "interactions" in interactions
    assert len(interactions["interactions"]) > 0


def test_target_ligand_prediction(client, auth_headers):
    """Test ligand prediction for target"""
    response = client.post("/api/v1/target/predict-ligands",
        json={
            "target_gene": "FOXP3",
            "ligand_types": ["small_molecule", "peptide"],
            "num_predictions": 10
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    ligands = response.json()
    assert "predicted_ligands" in ligands
    assert len(ligands["predicted_ligands"]) > 0


def test_target_comparison(client, auth_headers):
    """Test target comparison"""
    response = client.post("/api/v1/target/compare",
        json={
            "target_genes": ["FOXP3", "IL2RA", "CTLA4"],
            "comparison_criteria": ["druggability", "safety", "expression"]
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    comparison = response.json()
    assert "comparison_matrix" in comparison
    assert len(comparison["comparison_matrix"]) == 3


def test_target_ranking(client, auth_headers):
    """Test target ranking"""
    response = client.post("/api/v1/target/rank",
        json={
            "disease": "IPEX syndrome",
            "ranking_method": "weighted_score",
            "weights": {
                "genetic_evidence": 0.4,
                "druggability": 0.3,
                "safety": 0.3
            },
            "limit": 10
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    ranked_targets = response.json()["targets"]
    assert len(ranked_targets) > 0
    # Verify ranking order
    ranks = [t["rank"] for t in ranked_targets]
    assert ranks == list(range(1, len(ranks) + 1))


def test_workflow_state_persistence(client, auth_headers):
    """Test workflow state persistence"""
    # Create workflow
    create_response = client.post("/api/v1/workflow/target-prioritization",
        json={
            "disease": "IPEX syndrome",
            "name": "IPEX Target Discovery"
        },
        headers=auth_headers
    )
    
    assert create_response.status_code == 201
    workflow_id = create_response.json()["workflow_id"]
    
    # Get workflow status
    status_response = client.get(f"/api/v1/workflow/{workflow_id}", headers=auth_headers)
    assert status_response.status_code == 200


def test_workflow_error_handling(client, auth_headers):
    """Test workflow error handling"""
    # Invalid target gene
    response = client.post("/api/v1/target/validate",
        json={"target_gene": "INVALID_GENE", "disease": "IPEX syndrome"},
        headers=auth_headers
    )
    
    assert response.status_code in [400, 404]


def test_workflow_performance(client, auth_headers):
    """Test workflow performance"""
    import time
    
    start = time.time()
    response = client.post("/api/v1/target/discover",
        json={"disease": "IPEX syndrome", "limit": 10},
        headers=auth_headers
    )
    duration = time.time() - start
    
    assert response.status_code == 200
    assert duration < 5.0  # Should complete in under 5 seconds
