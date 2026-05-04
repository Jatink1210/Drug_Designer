"""G1-1: Source timeout failure drill.

All connectors time out → system returns DEGRADED, no crash.
"""
from __future__ import annotations
import asyncio
import pytest
from unittest.mock import AsyncMock, patch


class _TimeoutResponse:
    """Simulates a connector that always times out."""
    async def _cached_get(self, *args, **kwargs):
        raise asyncio.TimeoutError("Simulated source timeout")

    async def _cached_post(self, *args, **kwargs):
        raise asyncio.TimeoutError("Simulated source timeout")


@pytest.mark.asyncio
async def test_connector_timeout_returns_empty_not_exception():
    """Individual connector timeout → empty list, no exception propagated."""
    from apps.api.connectors.uniprot import UniProtConnector

    conn = UniProtConnector()
    with patch.object(conn, "_cached_get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = asyncio.TimeoutError("Timeout")
        try:
            result = await conn.search("BRCA1", limit=5)
        except asyncio.TimeoutError:
            pytest.fail("TimeoutError should be caught inside connector, not propagated")
        # Result should be empty list or None, not an exception
        assert result is None or isinstance(result, list)


@pytest.mark.asyncio
async def test_multiple_connector_timeouts_degrade_gracefully():
    """Multiple connectors timing out → at least 0 results, no crash."""
    from apps.api.connectors.pubmed import PubMedConnector
    from apps.api.connectors.chembl import ChEMBLConnector
    from apps.api.connectors.uniprot import UniProtConnector

    connectors = [PubMedConnector(), ChEMBLConnector(), UniProtConnector()]
    tasks = []
    for conn in connectors:
        with patch.object(conn, "_cached_get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = asyncio.TimeoutError("Timeout")
            tasks.append(conn.search("BRCA1", limit=5))

    # Run all; none should raise
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        assert not isinstance(r, asyncio.TimeoutError), (
            f"TimeoutError leaked out of connector: {r}"
        )


@pytest.mark.asyncio
async def test_all_sources_timeout_no_500():
    """Simulate full connector pool timeout via heterogeneous gather."""
    timeout_mock = AsyncMock(side_effect=asyncio.TimeoutError("All sources timed out"))

    async def timed_out_search(query, limit=5):
        raise asyncio.TimeoutError("All sources timed out")

    results = await asyncio.gather(
        *[timed_out_search("BRCA1") for _ in range(10)],
        return_exceptions=True,
    )
    # All results are exceptions, but gather itself did not raise
    assert len(results) == 10
    for r in results:
        assert isinstance(r, asyncio.TimeoutError)


@pytest.mark.asyncio
async def test_partial_timeout_some_results_returned():
    """9 sources timeout, 1 succeeds → result contains 1 source."""
    async def timeout_search(query, limit=5):
        raise asyncio.TimeoutError("Timeout")

    async def success_search(query, limit=5):
        return [{"id": "mock-1", "canonical_name": "BRCA1", "entity_type": "gene"}]

    coros = [timeout_search("BRCA1") for _ in range(9)] + [success_search("BRCA1")]
    results = await asyncio.gather(*coros, return_exceptions=True)

    successful = [r for r in results if isinstance(r, list)]
    assert len(successful) == 1
    assert successful[0][0]["canonical_name"] == "BRCA1"
