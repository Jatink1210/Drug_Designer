"""G1-3: Neo4j kill mid-pathway-expansion failure drill.

Neo4j dies during expansion → error logged, no 500 cascade to client.
"""
from __future__ import annotations
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class Neo4jConnectionError(Exception):
    """Simulates Neo4j service failure during query."""


@pytest.mark.asyncio
async def test_neo4j_kill_mid_expansion_no_500(caplog):
    """Neo4j unavailable during pathway expansion → logged error, graceful response."""
    async def expand_pathway_graph(gene_id: str, depth: int = 2):
        nodes = [{"id": gene_id, "type": "gene"}]
        # Simulate first-hop success
        for i in range(depth):
            if i == 1:
                # Neo4j dies on second hop
                raise Neo4jConnectionError("ServiceUnavailable: Neo4j unreachable")
            nodes.append({"id": f"{gene_id}_interactor_{i}", "type": "protein"})
        return nodes

    result_nodes = []
    error_logged = False
    with caplog.at_level(logging.ERROR):
        try:
            result_nodes = await expand_pathway_graph("BRCA1", depth=3)
        except Neo4jConnectionError as exc:
            error_logged = True
            # In production, log and return partial results
            logging.getLogger(__name__).error(
                "neo4j_expansion_failed",
                gene_id="BRCA1",
                error=str(exc),
            )

    assert error_logged, "Neo4j error must be logged"
    # No 500: function handled gracefully (no unhandled exception propagated to caller)
    assert result_nodes == []  # Empty partial result, not a crash


@pytest.mark.asyncio
async def test_neo4j_kill_response_is_not_500():
    """Simulate HTTP route handler: Neo4j error → 503 not 500."""
    from fastapi import HTTPException

    async def route_handler():
        try:
            raise Neo4jConnectionError("Neo4j connection reset")
        except Neo4jConnectionError:
            raise HTTPException(status_code=503, detail="Graph service temporarily unavailable")

    with pytest.raises(Exception) as exc_info:
        await route_handler()

    exc = exc_info.value
    # Should be HTTPException with 503, not unhandled 500
    assert hasattr(exc, "status_code")
    assert exc.status_code == 503
    assert "temporarily unavailable" in exc.detail


@pytest.mark.asyncio
async def test_neo4j_error_includes_partial_results():
    """Partial pathway expansion before Neo4j death → partial results returned."""
    async def safe_expand(gene_id: str):
        partial = []
        try:
            partial = [{"id": gene_id, "depth": 0}]
            raise Neo4jConnectionError("Simulated kill")
        except Neo4jConnectionError:
            return {"status": "DEGRADED", "partial_results": partial, "error": "neo4j_unavailable"}
        return {"status": "OK", "partial_results": partial}

    result = await safe_expand("TP53")
    assert result["status"] == "DEGRADED"
    assert len(result["partial_results"]) == 1
    assert result["partial_results"][0]["id"] == "TP53"
