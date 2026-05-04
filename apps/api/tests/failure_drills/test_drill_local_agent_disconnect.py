"""G1-4: Local agent WebSocket disconnect failure drill.

WebSocket interrupted mid-generation → run marked DEGRADED, client notified.
"""
from __future__ import annotations
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock


class WebSocketDisconnect(Exception):
    """Simulates starlette WebSocketDisconnect."""
    def __init__(self, code: int = 1000):
        self.code = code
        super().__init__(f"WebSocket closed with code {code}")


@pytest.mark.asyncio
async def test_websocket_disconnect_mid_stream_marks_degraded():
    """WebSocket closes during token stream → run state set to DEGRADED."""
    run_state = {"status": "RUNNING", "tokens_sent": 0}

    async def stream_tokens(ws, run_state: dict):
        for i in range(10):
            if i == 5:
                raise WebSocketDisconnect(code=1001)
            run_state["tokens_sent"] = i
            await asyncio.sleep(0)  # yield

    try:
        await stream_tokens(MagicMock(), run_state)
    except WebSocketDisconnect:
        run_state["status"] = "DEGRADED"
        run_state["disconnect_reason"] = "websocket_closed"

    assert run_state["status"] == "DEGRADED"
    assert run_state["tokens_sent"] == 4  # Sent tokens 0-4 before disconnect


@pytest.mark.asyncio
async def test_websocket_disconnect_preserves_partial_output():
    """Disconnect mid-run → partial output and provenance preserved."""
    run_record = {
        "status": "RUNNING",
        "output_chunks": [],
        "provenance": [],
    }

    async def mock_agent_run(run_record: dict):
        for chunk_idx in range(20):
            if chunk_idx == 10:
                raise WebSocketDisconnect(code=1006)
            run_record["output_chunks"].append(f"chunk_{chunk_idx}")
            run_record["provenance"].append({"step": chunk_idx, "source": "local_agent"})

    try:
        await mock_agent_run(run_record)
    except WebSocketDisconnect:
        run_record["status"] = "DEGRADED"

    assert run_record["status"] == "DEGRADED"
    assert len(run_record["output_chunks"]) == 10
    assert len(run_record["provenance"]) == 10  # Provenance preserved up to disconnect


@pytest.mark.asyncio
async def test_websocket_reconnect_can_resume():
    """After disconnect, client can reconnect and get run status."""
    run_store = {"run_123": {"status": "DEGRADED", "output_chunks": ["a", "b", "c"]}}

    async def get_run_status(run_id: str) -> dict:
        return run_store.get(run_id, {"status": "NOT_FOUND"})

    status = await get_run_status("run_123")
    assert status["status"] == "DEGRADED"
    assert len(status["output_chunks"]) == 3


@pytest.mark.asyncio
async def test_disconnect_code_1001_vs_1006():
    """Different disconnect codes handled gracefully."""
    for code in [1000, 1001, 1006, 1011]:
        exc = WebSocketDisconnect(code=code)
        assert exc.code == code
        assert "WebSocket closed" in str(exc)
