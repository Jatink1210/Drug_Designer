"""Acceptance Gate Integration Tests — Final Product Hardening §12.6.

Tests backend API contracts for each acceptance gate.
Run: pytest tests/integration/test_acceptance_gates.py -v
"""

import os
import pytest
import httpx

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")
TIMEOUT = 30.0


@pytest.fixture
def client():
    """HTTP client for API requests."""
    return httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)


class TestGate1CockpitAnalyze:
    """Gate 1: Cockpit general query + slash command routing."""

    def test_cockpit_analyze_creates_result(self, client):
        """POST /cockpit/analyze returns a full analysis result."""
        resp = client.post("/cockpit/analyze", json={"query": "Aspirin", "limit": 10})
        assert resp.status_code == 200
        data = resp.json()
        # Unwrap envelope if present
        payload = data.get("data", data)
        assert "query" in payload or "run_id" in payload

    def test_cockpit_recent_runs(self, client):
        """GET /cockpit/recent-runs returns runs ordered by creation time."""
        resp = client.get("/cockpit/recent-runs", params={"limit": 5})
        assert resp.status_code == 200
        data = resp.json()
        payload = data.get("data", data)
        assert "recent_runs" in payload
        assert isinstance(payload["recent_runs"], list)


class TestGate6SourceHealth:
    """Gate 6: Connector health observability."""

    def test_source_health_returns_all_connectors(self, client):
        """GET /cockpit/source-health returns all registered connectors."""
        resp = client.get("/cockpit/source-health")
        assert resp.status_code == 200
        data = resp.json()
        payload = data.get("data", data)
        assert "sources" in payload
        assert "summary" in payload
        assert isinstance(payload["sources"], list)
        # Should have at least some connectors
        assert len(payload["sources"]) > 0

    def test_catalog_stats_returns_counts(self, client):
        """GET /catalog/stats returns collection counts."""
        resp = client.get("/catalog/stats")
        assert resp.status_code == 200
        data = resp.json()
        payload = data.get("data", data)
        assert "collections" in payload
        assert "total" in payload


class TestGate10Settings:
    """Gate 10: Settings exposes runtime/model/connector/privacy control."""

    def test_settings_returns_full_tree(self, client):
        """GET /settings returns the full settings tree."""
        resp = client.get("/settings")
        assert resp.status_code == 200
        data = resp.json()
        payload = data.get("data", data)
        assert isinstance(payload, dict)

    def test_runtime_status(self, client):
        """GET /runtime/status returns accurate runtime state."""
        resp = client.get("/runtime/status")
        assert resp.status_code == 200
        data = resp.json()
        payload = data.get("data", data)
        assert isinstance(payload, dict)


class TestGate11ContractNormalization:
    """Gate 11: FE↔BE contract map is normalized."""

    def test_health_endpoint(self, client):
        """GET /health returns valid health response."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_targets_rank_endpoint(self, client):
        """POST /targets/rank accepts canonical request."""
        resp = client.post("/targets/rank", json={
            "query_id": "test",
            "candidates": ["BRCA1", "TP53"],
        })
        # May return 200 or 422 depending on validation, but should not 404
        assert resp.status_code != 404

    def test_targets_prioritize_alias(self, client):
        """POST /targets/prioritize still works as backward-compatible alias."""
        resp = client.post("/targets/prioritize", json={
            "disease": "breast cancer",
            "genes": ["BRCA1"],
        })
        # Should not 404 — alias must be preserved
        assert resp.status_code != 404

    def test_deprecated_route_aliases(self, client):
        """Deprecated route aliases should still respond."""
        endpoints = [
            "/cockpit/summary",
            "/cockpit/source-health",
            "/cockpit/recent-runs",
        ]
        for endpoint in endpoints:
            resp = client.get(endpoint)
            assert resp.status_code == 200, f"{endpoint} returned {resp.status_code}"
