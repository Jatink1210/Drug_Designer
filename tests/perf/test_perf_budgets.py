"""
Performance Budget Verification Tests

These tests verify that the Drug Designer system meets its performance budgets.
All tests FAIL if the budget is exceeded (not just warn).

Performance Budgets:
- Cockpit load time < 1500ms
- Evidence first partial < 3000ms
- Disease normalization < 2500ms
- Graph expansion (2-hop) < 2000ms
- Local agent heartbeat < 100ms
- Health endpoint < 50ms
"""

import pytest
import time
import asyncio
from typing import Dict, Any
import httpx
from apps.api.main import app
from apps.api.core.db import get_db
from apps.api.services.disease_service import DiseaseService
from apps.api.services.graph_store import GraphStore
from fastapi.testclient import TestClient


# Performance budget constants (in milliseconds)
COCKPIT_LOAD_BUDGET = 1500
EVIDENCE_FIRST_PARTIAL_BUDGET = 3000
DISEASE_NORMALIZATION_BUDGET = 2500
GRAPH_EXPANSION_BUDGET = 2000
LOCAL_AGENT_HEARTBEAT_BUDGET = 100
HEALTH_ENDPOINT_BUDGET = 50


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Get authentication headers for test user"""
    # Register test user
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "perf_test@example.com",
            "password": "test_password_123",
            "full_name": "Performance Test User"
        }
    )
    
    # Login
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "perf_test@example.com",
            "password": "test_password_123"
        }
    )
    
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def measure_time_ms(func):
    """Decorator to measure function execution time in milliseconds"""
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        elapsed_ms = (end - start) * 1000
        return result, elapsed_ms
    return wrapper


@pytest.mark.performance
def test_cockpit_load_time(client, auth_headers):
    """
    Test: Cockpit load time < 1500ms
    
    Measures the time to load the cockpit summary endpoint,
    which includes job counts, health checks, and last-run data.
    """
    @measure_time_ms
    def load_cockpit():
        response = client.get("/api/v1/cockpit/summary", headers=auth_headers)
        assert response.status_code == 200
        return response.json()
    
    result, elapsed_ms = load_cockpit()
    
    print(f"\nCockpit load time: {elapsed_ms:.2f}ms (budget: {COCKPIT_LOAD_BUDGET}ms)")
    
    assert elapsed_ms < COCKPIT_LOAD_BUDGET, (
        f"Cockpit load time ({elapsed_ms:.2f}ms) exceeds budget ({COCKPIT_LOAD_BUDGET}ms)"
    )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_evidence_first_partial(client, auth_headers):
    """
    Test: Evidence first partial < 3000ms
    
    Measures the time from job enqueue to first WebSocket event
    for evidence aggregation workflow.
    """
    import websockets
    import json
    
    # Create a project
    response = client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={
            "name": "Performance Test Project",
            "description": "Testing evidence first partial"
        }
    )
    project_id = response.json()["data"]["id"]
    
    # Start evidence aggregation job
    start_time = time.perf_counter()
    
    response = client.post(
        f"/api/v1/projects/{project_id}/runs",
        headers=auth_headers,
        json={
            "run_type": "evidence",
            "config": {
                "query": "Alzheimer's disease",
                "sources": ["pubmed", "clinicaltrials"]
            }
        }
    )
    run_id = response.json()["data"]["id"]
    
    # Connect to WebSocket and wait for first event
    token = auth_headers["Authorization"].split(" ")[1]
    ws_url = f"ws://localhost:8000/api/v1/ws/{run_id}?token={token}"
    
    first_event_time = None
    
    async with websockets.connect(ws_url) as websocket:
        # Wait for first event
        message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        first_event_time = time.perf_counter()
        
        event = json.loads(message)
        assert event["type"] in ["progress", "partial_result"]
    
    elapsed_ms = (first_event_time - start_time) * 1000
    
    print(f"\nEvidence first partial: {elapsed_ms:.2f}ms (budget: {EVIDENCE_FIRST_PARTIAL_BUDGET}ms)")
    
    assert elapsed_ms < EVIDENCE_FIRST_PARTIAL_BUDGET, (
        f"Evidence first partial ({elapsed_ms:.2f}ms) exceeds budget ({EVIDENCE_FIRST_PARTIAL_BUDGET}ms)"
    )


@pytest.mark.performance
def test_disease_normalization(client, auth_headers):
    """
    Test: Disease normalization < 2500ms
    
    Measures the time to normalize a disease name to standard ontology terms.
    """
    @measure_time_ms
    def normalize_disease():
        response = client.post(
            "/api/v1/diseases/normalize",
            headers=auth_headers,
            json={
                "disease_name": "Alzheimer's disease"
            }
        )
        assert response.status_code == 200
        return response.json()
    
    result, elapsed_ms = normalize_disease()
    
    print(f"\nDisease normalization: {elapsed_ms:.2f}ms (budget: {DISEASE_NORMALIZATION_BUDGET}ms)")
    
    assert elapsed_ms < DISEASE_NORMALIZATION_BUDGET, (
        f"Disease normalization ({elapsed_ms:.2f}ms) exceeds budget ({DISEASE_NORMALIZATION_BUDGET}ms)"
    )


@pytest.mark.performance
def test_graph_expansion_2hop(client, auth_headers):
    """
    Test: Graph expansion (2-hop) < 2000ms
    
    Measures the time to expand a 2-hop neighborhood in the knowledge graph.
    """
    # First, get a gene ID to expand from
    response = client.get(
        "/api/v1/graph/search",
        headers=auth_headers,
        params={"query": "APOE", "node_type": "Gene"}
    )
    assert response.status_code == 200
    gene_id = response.json()["data"][0]["id"]
    
    @measure_time_ms
    def expand_graph():
        response = client.post(
            "/api/v1/graph/expand",
            headers=auth_headers,
            json={
                "node_id": gene_id,
                "hops": 2,
                "max_nodes": 100
            }
        )
        assert response.status_code == 200
        return response.json()
    
    result, elapsed_ms = expand_graph()
    
    print(f"\nGraph expansion (2-hop): {elapsed_ms:.2f}ms (budget: {GRAPH_EXPANSION_BUDGET}ms)")
    
    assert elapsed_ms < GRAPH_EXPANSION_BUDGET, (
        f"Graph expansion ({elapsed_ms:.2f}ms) exceeds budget ({GRAPH_EXPANSION_BUDGET}ms)"
    )


@pytest.mark.performance
def test_local_agent_heartbeat(client, auth_headers):
    """
    Test: Local agent heartbeat < 100ms
    
    Measures the time for a local agent heartbeat check.
    """
    @measure_time_ms
    def check_heartbeat():
        response = client.get(
            "/api/v1/runtime/heartbeat",
            headers=auth_headers
        )
        assert response.status_code == 200
        return response.json()
    
    result, elapsed_ms = check_heartbeat()
    
    print(f"\nLocal agent heartbeat: {elapsed_ms:.2f}ms (budget: {LOCAL_AGENT_HEARTBEAT_BUDGET}ms)")
    
    assert elapsed_ms < LOCAL_AGENT_HEARTBEAT_BUDGET, (
        f"Local agent heartbeat ({elapsed_ms:.2f}ms) exceeds budget ({LOCAL_AGENT_HEARTBEAT_BUDGET}ms)"
    )


@pytest.mark.performance
def test_health_endpoint(client):
    """
    Test: Health endpoint < 50ms
    
    Measures the time for the health check endpoint.
    This is the most critical performance metric as it's used for load balancer health checks.
    """
    # Warm up (first request may be slower due to cold start)
    client.get("/api/v1/health")
    
    # Measure 10 requests and take the average
    times = []
    for _ in range(10):
        @measure_time_ms
        def check_health():
            response = client.get("/api/v1/health")
            assert response.status_code == 200
            return response.json()
        
        result, elapsed_ms = check_health()
        times.append(elapsed_ms)
    
    avg_time = sum(times) / len(times)
    max_time = max(times)
    min_time = min(times)
    
    print(f"\nHealth endpoint:")
    print(f"  Average: {avg_time:.2f}ms")
    print(f"  Min: {min_time:.2f}ms")
    print(f"  Max: {max_time:.2f}ms")
    print(f"  Budget: {HEALTH_ENDPOINT_BUDGET}ms")
    
    assert avg_time < HEALTH_ENDPOINT_BUDGET, (
        f"Health endpoint average time ({avg_time:.2f}ms) exceeds budget ({HEALTH_ENDPOINT_BUDGET}ms)"
    )
    
    assert max_time < HEALTH_ENDPOINT_BUDGET * 2, (
        f"Health endpoint max time ({max_time:.2f}ms) exceeds 2x budget ({HEALTH_ENDPOINT_BUDGET * 2}ms)"
    )


@pytest.mark.performance
def test_performance_summary(client, auth_headers):
    """
    Generate a performance summary report
    """
    print("\n" + "="*80)
    print("PERFORMANCE BUDGET SUMMARY")
    print("="*80)
    
    budgets = [
        ("Cockpit load time", COCKPIT_LOAD_BUDGET),
        ("Evidence first partial", EVIDENCE_FIRST_PARTIAL_BUDGET),
        ("Disease normalization", DISEASE_NORMALIZATION_BUDGET),
        ("Graph expansion (2-hop)", GRAPH_EXPANSION_BUDGET),
        ("Local agent heartbeat", LOCAL_AGENT_HEARTBEAT_BUDGET),
        ("Health endpoint", HEALTH_ENDPOINT_BUDGET),
    ]
    
    print(f"\n{'Metric':<30} {'Budget':<15} {'Status':<10}")
    print("-"*80)
    
    for metric, budget in budgets:
        print(f"{metric:<30} {budget}ms{'':<10} {'✅ Defined':<10}")
    
    print("\n" + "="*80)
    print("Run individual tests to verify actual performance against budgets")
    print("="*80)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "performance"])
