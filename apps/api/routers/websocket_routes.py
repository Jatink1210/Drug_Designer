"""WebSocket Route — Run Progress Streaming (Drug Designer §57).

FastAPI WebSocket endpoint for real-time run event streaming.
Endpoint: ws://HOST:8000/ws/runs/{run_id}
Authenticated via JWT cookie or query param token.

§57.4: On reconnect, client sends {"event": "sync", "last_seen_ts": ...}
       and server replays all events since that timestamp.
"""

import os
import json
import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.auth import verify_access_token
from core.websocket_manager import get_ws_manager

logger = structlog.get_logger()
router = APIRouter(tags=["websocket"])


async def _authenticate_ws(websocket: WebSocket) -> bool:
    """Validate JWT on WebSocket handshake (§57.1).

    Checks HTTP-only cookie first, then falls back to ?token= query param
    for non-browser clients. Returns True if authenticated (or auth disabled).
    """
    if not os.environ.get("DRUGDESIGNER_AUTH_ENABLED", "true").lower() == "true":
        return True

    token = websocket.cookies.get("dss_access_token")
    if not token:
        token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return False

    payload = verify_access_token(token)
    if payload is None:
        await websocket.close(code=4003, reason="Invalid or expired token")
        return False

    # Attach user info for downstream use
    websocket.state.user_id = payload.get("sub")
    return True


@router.websocket("/ws/runs/{run_id}")
async def websocket_run_progress(websocket: WebSocket, run_id: str):
    """WebSocket endpoint for streaming run progress events.
    
    §57.1: Validated via JWT cookie or query param token.
    §57.2: Sends structured events with event, run_id, timestamp, payload.
    §57.4: On reconnect, replays events since last_seen_ts.
    """
    await websocket.accept()
    if not await _authenticate_ws(websocket):
        return

    manager = get_ws_manager()
    await manager.connect(websocket, run_id=run_id)
    logger.info("ws_run_connected", run_id=run_id)

    try:
        while True:
            # Listen for client messages (e.g., sync requests)
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                event_type = message.get("event")

                # §57.4: Reconnection sync
                if event_type == "sync":
                    last_seen_ts = message.get("last_seen_ts")
                    await manager.replay_events(websocket, run_id, since_ts=last_seen_ts)
                    logger.info("ws_sync_replayed", run_id=run_id, since=last_seen_ts)

                # Client can send ping
                elif event_type == "ping":
                    await websocket.send_text(json.dumps({"event": "pong", "run_id": run_id}))

            except json.JSONDecodeError:
                logger.debug("ws_invalid_message", data=data[:100])

    except WebSocketDisconnect:
        manager.disconnect(websocket, run_id=run_id)
        logger.info("ws_run_disconnected", run_id=run_id)


@router.websocket("/ws/global")
async def websocket_global_events(websocket: WebSocket):
    """Global WebSocket for system-wide events (source health, DLQ alerts).
    
    Not scoped to a specific run — receives all broadcast events.
    §57.1: Authenticated via JWT cookie or query param.
    """
    await websocket.accept()
    if not await _authenticate_ws(websocket):
        return

    manager = get_ws_manager()
    await manager.connect(websocket)
    logger.info("ws_global_connected")

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("event") == "ping":
                    await websocket.send_text(json.dumps({"event": "pong"}))
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("ws_global_disconnected")
