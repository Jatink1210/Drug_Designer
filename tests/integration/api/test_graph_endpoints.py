"""
Integration tests for knowledge graph endpoints
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
        "email": "graph@example.com",
        "password": "SecurePassword123!",
        "full_name": "Graph User"
    })
    
    login_response = client.post("/api/v1/auth/login", json={
        "email": "graph@example.com",
        "password": "SecurePassword123!"
    })
    
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_build_knowledge_graph(client, auth_headers):
    """Test building knowledge graph"""
    response = client.post("/api/v1/graph/build", json={
        "disease_id": "disease_001",
        "target_ids": ["target_001", "target_002"],
        "evidence_ids": ["evidence_001", "evidence_002", "evidence_003"]
    }, headers=auth_headers)
    
    assert response.status_code == 200
    graph = response.json()
    assert "nodes" in graph
    assert "edges" in graph
    assert len(graph["nodes"]) > 0


def test_community_detection(client, auth_headers):
    """Test community detection in graph"""
    response = client.post("/api/v1/graph/community-detection", json={
        "graph_id": "graph_001",
        "algorithm": "louvain"
    }, headers=auth_headers)
    
    assert response.status_code == 200
    communities = response.json()
    assert "communities" in communities
    assert len(communities["communities"]) > 0


def test_centrality_analysis(client, auth_headers):
    """Test centrality analysis"""
    response = client.post("/api/v1/graph/centrality", json={
        "graph_id": "graph_001",
        "centrality_type": "betweenness"
    }, headers=auth_headers)
    
    assert response.status_code == 200
    centrality = response.json()
    assert "node_centrality" in centrality


def test_shortest_path(client, auth_headers):
    """Test shortest path finding"""
    response = client.post("/api/v1/graph/shortest-path", json={
        "graph_id": "graph_001",
        "source_node": "node_001",
        "target_node": "node_010"
    }, headers=auth_headers)
    
    assert response.status_code == 200
    path = response.json()
    assert "path" in path
    assert "length" in path


def test_subgraph_extraction(client, auth_headers):
    """Test subgraph extraction"""
    response = client.post("/api/v1/graph/subgraph-extract", json={
        "graph_id": "graph_001",
        "node_ids": ["node_001", "node_002", "node_003"],
        "include_neighbors": True
    }, headers=auth_headers)
    
    assert response.status_code == 200
    subgraph = response.json()
    assert "nodes" in subgraph
    assert "edges" in subgraph


def test_graph_query(client, auth_headers):
    """Test graph query"""
    response = client.post("/api/v1/graph/query", json={
        "graph_id": "graph_001",
        "query": {
            "node_type": "target",
            "properties": {"druggability_score": {">": 0.7}}
        }
    }, headers=auth_headers)
    
    assert response.status_code == 200
    results = response.json()
    assert "nodes" in results


def test_graph_export(client, auth_headers):
    """Test graph export"""
    response = client.post("/api/v1/graph/export", json={
        "graph_id": "graph_001",
        "format": "graphml"
    }, headers=auth_headers)
    
    assert response.status_code == 200


def test_graph_visualization(client, auth_headers):
    """Test graph visualization data"""
    response = client.get("/api/v1/graph/graph_001/visualization", 
        headers=auth_headers)
    
    assert response.status_code == 200
    viz_data = response.json()
    assert "nodes" in viz_data
    assert "edges" in viz_data
    assert "layout" in viz_data
