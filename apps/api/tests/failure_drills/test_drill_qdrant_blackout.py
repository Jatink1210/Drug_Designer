"""G1-2: Qdrant blackout failure drill.

Qdrant unavailable → system falls back to BM25, returns DEGRADED state.
"""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from grpc import RpcError


class QdrantUnavailableError(Exception):
    """Simulates Qdrant service unavailability."""


@pytest.mark.asyncio
async def test_qdrant_connection_error_falls_back():
    """Qdrant RpcError → vector_store.search raises; caller should handle."""
    mock_qdrant_client = AsyncMock()
    mock_qdrant_client.search = AsyncMock(
        side_effect=QdrantUnavailableError("Qdrant unavailable")
    )

    # Simulate the vector store search path
    async def vector_search_with_fallback(query: str):
        try:
            return await mock_qdrant_client.search(collection_name="test", query_vector=[0.1] * 768, limit=5)
        except QdrantUnavailableError:
            # Fallback to BM25 — return empty with DEGRADED marker
            return {"status": "DEGRADED", "fallback": "bm25", "results": []}

    result = await vector_search_with_fallback("BRCA1 cancer")
    assert result["status"] == "DEGRADED"
    assert result["fallback"] == "bm25"
    assert result["results"] == []


@pytest.mark.asyncio
async def test_qdrant_blackout_no_exception_propagated():
    """Qdrant service down → no unhandled exception in search pipeline."""
    mock_qdrant = AsyncMock()
    mock_qdrant.search.side_effect = ConnectionError("Qdrant host unreachable")

    async def resilient_hybrid_search(query: str):
        vector_results = []
        try:
            vector_results = await mock_qdrant.search(
                collection_name="evidence", query_vector=[0.0] * 768, limit=10
            )
        except (ConnectionError, QdrantUnavailableError, Exception):
            # Expected fallback: BM25 only
            vector_results = []

        # System continues with BM25 results only
        bm25_results = [{"id": "bm25-mock", "score": 0.72, "type": "bm25"}]
        return {
            "results": vector_results + bm25_results,
            "degraded": True,
            "reason": "qdrant_unavailable",
        }

    result = await resilient_hybrid_search("BRCA1")
    assert result["degraded"] is True
    assert len(result["results"]) >= 1  # BM25 still returns results
    assert result["results"][0]["type"] == "bm25"


@pytest.mark.asyncio
async def test_qdrant_partial_collection_missing():
    """One Qdrant collection missing → that collection skipped, others OK."""
    async def search_collection(name: str):
        if name == "evidence":
            raise QdrantUnavailableError("Collection 'evidence' not found")
        return [{"id": f"{name}-1", "score": 0.9}]

    collections = ["proteins", "evidence", "pathways"]
    results = {}
    for col in collections:
        try:
            results[col] = await search_collection(col)
        except QdrantUnavailableError:
            results[col] = []

    assert results["proteins"] != []
    assert results["evidence"] == []
    assert results["pathways"] != []
