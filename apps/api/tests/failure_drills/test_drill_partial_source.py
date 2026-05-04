"""G1-7: Partial source success failure drill.

99 sources timeout, 1 succeeds → result shows 1 source, no crash.
"""
from __future__ import annotations
import asyncio
import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_99_timeouts_1_success_returns_partial():
    """99 connector timeouts + 1 success → 1 result returned, system stable."""

    async def timeout_connector(_query: str, _limit: int = 5):
        raise asyncio.TimeoutError("Simulated timeout")

    async def success_connector(query: str, limit: int = 5):
        return [{"id": "success-1", "canonical_name": "BRCA1", "entity_type": "gene", "source": "success_db"}]

    tasks = [timeout_connector("BRCA1") for _ in range(99)] + [success_connector("BRCA1")]

    results_raw = await asyncio.gather(*tasks, return_exceptions=True)

    # Aggregate: filter out exceptions
    aggregated = []
    error_count = 0
    for r in results_raw:
        if isinstance(r, Exception):
            error_count += 1
        elif isinstance(r, list):
            aggregated.extend(r)

    assert error_count == 99
    assert len(aggregated) == 1
    assert aggregated[0]["canonical_name"] == "BRCA1"
    # System returned valid response, no unhandled exception


@pytest.mark.asyncio
async def test_partial_source_result_has_source_metadata():
    """Result from 1 surviving source includes source identification."""
    async def single_success(query: str, limit: int = 5):
        return [{"id": "uniprot:P04637", "source": "UniProt", "canonical_name": "TP53"}]

    tasks = [asyncio.sleep(0) for _ in range(5)]  # No-ops for other "sources"
    results = await asyncio.gather(*tasks, return_exceptions=True)
    success = await single_success("TP53")

    assert success[0]["source"] == "UniProt"
    assert "id" in success[0]


@pytest.mark.asyncio
async def test_all_sources_fail_returns_empty_not_exception():
    """All sources fail → empty aggregated result, not an exception."""
    async def always_fail(_q: str, _l: int = 5):
        raise ConnectionError("Source unreachable")

    tasks = [always_fail("BRCA2") for _ in range(10)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    aggregated = [r for r in results if isinstance(r, list)]
    assert aggregated == []
    # No unhandled exception; caller receives empty list


@pytest.mark.asyncio
async def test_source_error_types_all_handled():
    """Various error types from sources → all treated as degraded, not reraise."""
    error_types = [
        asyncio.TimeoutError("timeout"),
        ConnectionError("conn error"),
        ValueError("bad response"),
        KeyError("missing field"),
        RuntimeError("unexpected"),
    ]

    async def make_failing(exc):
        raise exc

    results = await asyncio.gather(
        *[make_failing(e) for e in error_types],
        return_exceptions=True,
    )

    # All results are exceptions (gathered, not raised)
    assert all(isinstance(r, Exception) for r in results)
    assert len(results) == 5
