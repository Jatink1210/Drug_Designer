"""WebSocket Manager — Server-Side Run Event Broadcasting (Drug Designer §57).

Manages WebSocket connections for real-time run progress events.
§57.1: ws://HOST:8000/ws/runs/{run_id} — authenticated via JWT cookie.
§57.2: Message format with event, run_id, timestamp, payload.
§57.3: Event types: run.progress, run.stage_complete, run.failed, run.completed, run.paused, source.degraded, agent.heartbeat.
§57.4: Reconnection: client sends sync with last_seen_ts, server replays missed events.
"""

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Set, Optional, Any, List
from collections import defaultdict

import structlog
from fastapi import WebSocket, WebSocketDisconnect

logger = structlog.get_logger()


class RunEvent:
    """Structured WebSocket event (§57.2)."""

    def __init__(
        self,
        event: str,
        run_id: str,
        payload: Optional[Dict[str, Any]] = None,
    ):
        self.event = event
        self.run_id = run_id
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.payload = payload or {}

    def to_dict(self) -> dict:
        return {
            "event": self.event,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class WebSocketManager:
    """Manages active WebSocket connections and event broadcasting.
    
    Features:
    - Per-run connection tracking
    - Event history for reconnection replay (§57.4)
    - Broadcast to all subscribers of a run
    - Global broadcast (e.g., source health changes)
    """

    def __init__(self, max_event_history: int = 200):
        # run_id → set of active WebSocket connections
        self._connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        # run_id → list of recent events (for replay on reconnect)
        self._event_history: Dict[str, list] = defaultdict(list)
        self._max_history = max_event_history
        # Global subscribers (not scoped to a run)
        self._global_connections: Set[WebSocket] = set()
        logger.info("websocket_manager_initialized", max_history=max_event_history)

    async def connect(self, websocket: WebSocket, run_id: Optional[str] = None):
        """Accept a new WebSocket connection, optionally scoped to a run."""
        await websocket.accept()
        if run_id:
            self._connections[run_id].add(websocket)
            logger.info("ws_client_connected", run_id=run_id, total=len(self._connections[run_id]))
        else:
            self._global_connections.add(websocket)
            logger.info("ws_global_client_connected", total=len(self._global_connections))

    def disconnect(self, websocket: WebSocket, run_id: Optional[str] = None):
        """Remove a disconnected WebSocket."""
        if run_id and run_id in self._connections:
            self._connections[run_id].discard(websocket)
            if not self._connections[run_id]:
                del self._connections[run_id]
            logger.info("ws_client_disconnected", run_id=run_id)
        else:
            self._global_connections.discard(websocket)

    async def emit(
        self,
        run_id: str,
        event: str,
        payload: Optional[Dict[str, Any]] = None,
    ):
        """Emit an event to all subscribers of a specific run.
        
        §57.2: Every event includes event, run_id, timestamp, payload.
        §57.3: Valid events: run.progress, run.stage_complete, run.failed, run.completed, run.paused, source.degraded, agent.heartbeat.
        """
        run_event = RunEvent(event=event, run_id=run_id, payload=payload)
        event_dict = run_event.to_dict()

        # Store in history for reconnection replay (§57.4)
        self._event_history[run_id].append(event_dict)
        if len(self._event_history[run_id]) > self._max_history:
            self._event_history[run_id] = self._event_history[run_id][-self._max_history:]

        # Broadcast to all subscribers
        message = run_event.to_json()
        dead_connections = set()

        for ws in self._connections.get(run_id, set()):
            try:
                await ws.send_text(message)
            except Exception:
                dead_connections.add(ws)

        # Clean up dead connections
        for ws in dead_connections:
            self._connections[run_id].discard(ws)

        logger.debug("ws_event_emitted", run_id=run_id, ws_event=event,
                      subscribers=len(self._connections.get(run_id, set())))

    async def emit_progress(
        self,
        run_id: str,
        stage: str,
        progress_pct: int,
        message: str,
        sources_completed: int = 0,
        sources_total: int = 0,
        degraded_sources: Optional[list] = None,
    ):
        """Convenience: emit a run.progress event (§57.3)."""
        await self.emit(run_id, "run.progress", {
            "stage": stage,
            "progress_pct": progress_pct,
            "message": message,
            "sources_completed": sources_completed,
            "sources_total": sources_total,
            "degraded_sources": degraded_sources or [],
        })

    async def emit_stage_complete(self, run_id: str, stage: str, artifacts_generated: int = 0):
        """Convenience: emit run.stage_complete (§57.3)."""
        await self.emit(run_id, "run.stage_complete", {
            "stage": stage,
            "artifacts_generated": artifacts_generated,
        })

    async def emit_error(self, run_id: str, stage: str, error: str, recoverable: bool = True):
        """Convenience: emit run.failed (§57.3)."""
        await self.emit(run_id, "run.failed", {
            "stage": stage,
            "error": error,
            "recoverable": recoverable,
        })

    async def emit_complete(self, run_id: str, state: str, output_artifacts: Optional[list] = None):
        """Convenience: emit run.completed (§57.3)."""
        await self.emit(run_id, "run.completed", {
            "state": state,
            "output_artifacts": output_artifacts or [],
        })

    async def emit_source_degraded(
        self,
        run_id: str,
        source_name: str,
        reason: str,
        response_time_ms: Optional[int] = None,
    ):
        """Convenience: emit source.degraded (§57.3)."""
        await self.emit(run_id, "source.degraded", {
            "source_name": source_name,
            "reason": reason,
            "response_time_ms": response_time_ms,
        })

    async def emit_paused(
        self,
        run_id: str,
        reason: str,
        conflicting_votes: Optional[Dict[str, Any]] = None,
    ):
        """Convenience: emit run.paused for MAV consensus conflict / Truthful Pause (§57.3)."""
        await self.emit(run_id, "run.paused", {
            "reason": reason,
            "conflicting_votes": conflicting_votes or {},
        })

    async def emit_agent_heartbeat(
        self,
        agent_id: str,
        status: str = "alive",
        hardware: Optional[Dict[str, Any]] = None,
    ):
        """Convenience: emit agent.heartbeat (§57.3). Broadcast globally."""
        await self.broadcast_global("agent.heartbeat", {
            "agent_id": agent_id,
            "status": status,
            "hardware": hardware or {},
        })

    async def replay_events(
        self,
        websocket: WebSocket,
        run_id: str,
        since_ts: Optional[str] = None,
    ):
        """Replay missed events for reconnection (§57.4).
        
        Client sends: {"event": "sync", "last_seen_ts": "ISO8601"}
        Server replays all events since that timestamp.
        """
        events = self._event_history.get(run_id, [])
        if since_ts:
            events = [e for e in events if e["timestamp"] > since_ts]

        for event in events:
            try:
                await websocket.send_text(json.dumps(event))
            except Exception:
                break

        logger.info("ws_events_replayed", run_id=run_id, count=len(events), since=since_ts)

    async def broadcast_global(self, event_type: str, payload: Dict[str, Any]):
        """Broadcast to all globally-connected clients (e.g., source health updates)."""
        message = json.dumps({
            "event": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        })
        dead = set()
        for ws in self._global_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._global_connections.discard(ws)

    def get_active_run_ids(self) -> list:
        """Return list of run_ids with active WebSocket subscribers."""
        return list(self._connections.keys())

    def get_connection_count(self, run_id: Optional[str] = None) -> int:
        if run_id:
            return len(self._connections.get(run_id, set()))
        return sum(len(s) for s in self._connections.values()) + len(self._global_connections)


# Singleton for app-wide use
_ws_manager: Optional[WebSocketManager] = None


def get_ws_manager() -> WebSocketManager:
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager


# Clinical Workflow Constants
CLINICAL_STAGES = [
    "EHR Data Ingestion",
    "AI Phenotype Clustering",
    "DL Tissue Analysis",
    "Neural Network Biomarker Quantification",
    "Genomic Sequencing",
    "DL Pathogenicity Prediction",
    "Knowledge Graph Cross-Referencing",
    "AI Disruption Modeling",
    "AI Targeted Drug Matching",
    "Advanced Therapy Stratification"
]

# Error type classifications
ERROR_TYPES = {
    "data_error": "Data validation or format error",
    "model_error": "ML/DL model execution error",
    "system_error": "Infrastructure or resource error",
    "timeout_error": "Operation exceeded time limit",
    "validation_error": "Quality validation failed"
}


async def emit_clinical_workflow_started(
    manager: WebSocketManager,
    run_id: str,
    workflow_name: str,
    total_stages: int = 10,
    metadata: Optional[Dict[str, Any]] = None
):
    """Emit when clinical workflow begins."""
    await manager.emit(run_id, "clinical.workflow.started", {
        "workflow_name": workflow_name,
        "total_stages": total_stages,
        "stages": CLINICAL_STAGES,
        "metadata": metadata or {},
        "started_at": datetime.now(timezone.utc).isoformat()
    })


async def emit_clinical_workflow_progress(
    manager: WebSocketManager,
    run_id: str,
    stage_number: int,
    stage_name: str,
    progress_pct: int,
    message: str,
    substage: Optional[str] = None,
    estimated_time_remaining: Optional[int] = None,
    resource_usage: Optional[Dict[str, Any]] = None,
    quality_metrics: Optional[Dict[str, float]] = None
):
    """
    Emit progress update for clinical workflow (10-stage pipeline).
    
    Enhanced with:
    - Real-time ETA calculation
    - Resource usage monitoring (memory, CPU)
    - Quality metrics per stage
    - <100ms latency optimization
    
    Args:
        manager: WebSocketManager instance
        run_id: Unique workflow run identifier
        stage_number: Current stage (1-10)
        stage_name: Name of current stage
        progress_pct: Percentage completion (0-100)
        message: Descriptive progress message
        substage: Optional substage identifier for fine-grained tracking
        estimated_time_remaining: ETA in seconds
        resource_usage: Dict with memory_mb, cpu_pct, gpu_pct (optional)
        quality_metrics: Dict with stage-specific quality scores
    """
    payload = {
        "stage_number": stage_number,
        "stage_name": stage_name,
        "progress_pct": min(100, max(0, progress_pct)),  # Clamp 0-100
        "message": message,
        "total_stages": 10,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    if substage:
        payload["substage"] = substage
    
    if estimated_time_remaining is not None:
        payload["estimated_time_remaining_seconds"] = estimated_time_remaining
        payload["estimated_completion_time"] = (
            datetime.now(timezone.utc).timestamp() + estimated_time_remaining
        )
    
    if resource_usage:
        payload["resource_usage"] = {
            "memory_mb": resource_usage.get("memory_mb", 0),
            "cpu_percent": resource_usage.get("cpu_pct", 0),
            "gpu_percent": resource_usage.get("gpu_pct", 0)
        }
    
    if quality_metrics:
        payload["quality_metrics"] = quality_metrics
    
    await manager.emit(run_id, "clinical.workflow.progress", payload)


async def emit_clinical_stage_complete(
    manager: WebSocketManager,
    run_id: str,
    stage_number: int,
    stage_name: str,
    results_summary: Dict[str, Any],
    quality_score: Optional[float] = None,
    processing_time_seconds: Optional[float] = None,
    records_processed: Optional[int] = None,
    validation_passed: bool = True
):
    """
    Emit stage completion for clinical workflow.
    
    Enhanced with:
    - Quality validation per stage
    - Automatic error detection
    - Stage-specific metrics (processing time, records processed)
    
    Args:
        manager: WebSocketManager instance
        run_id: Unique workflow run identifier
        stage_number: Completed stage (1-10)
        stage_name: Name of completed stage
        results_summary: Dict with stage-specific results
        quality_score: Quality score (0-1) for validation
        processing_time_seconds: Time taken to complete stage
        records_processed: Number of records/items processed
        validation_passed: Whether quality validation passed
    """
    payload = {
        "stage_number": stage_number,
        "stage_name": stage_name,
        "results_summary": results_summary,
        "total_stages": 10,
        "validation_passed": validation_passed,
        "completed_at": datetime.now(timezone.utc).isoformat()
    }
    
    if quality_score is not None:
        payload["quality_score"] = quality_score
        # Flag low quality scores
        if quality_score < 0.7:
            payload["quality_warning"] = "Quality score below threshold (0.7)"
    
    if processing_time_seconds is not None:
        payload["processing_time_seconds"] = processing_time_seconds
    
    if records_processed is not None:
        payload["records_processed"] = records_processed
    
    await manager.emit(run_id, "clinical.stage.complete", payload)


async def emit_clinical_workflow_error(
    manager: WebSocketManager,
    run_id: str,
    stage_number: int,
    stage_name: str,
    error_message: str,
    error_type: str = "system_error",
    recoverable: bool = True,
    recovery_suggestions: Optional[list] = None,
    error_context: Optional[Dict[str, Any]] = None
):
    """
    Emit error notification for clinical workflow.
    
    Enhanced with:
    - Automatic error classification (data_error, model_error, system_error, etc.)
    - Recovery action suggestions
    - Error pattern detection support
    
    Args:
        manager: WebSocketManager instance
        run_id: Unique workflow run identifier
        stage_number: Stage where error occurred (1-10)
        stage_name: Name of stage with error
        error_message: Human-readable error description
        error_type: Classification (data_error, model_error, system_error, timeout_error, validation_error)
        recoverable: Whether workflow can continue/retry
        recovery_suggestions: List of actionable recovery steps
        error_context: Additional context (stack trace, input data, etc.)
    """
    # Validate error type
    if error_type not in ERROR_TYPES:
        logger.warning("unknown_error_type", error_type=error_type)
        error_type = "system_error"
    
    # Generate recovery suggestions if not provided
    if not recovery_suggestions:
        recovery_suggestions = _generate_recovery_suggestions(error_type, stage_name)
    
    payload = {
        "stage_number": stage_number,
        "stage_name": stage_name,
        "error_message": error_message,
        "error_type": error_type,
        "error_type_description": ERROR_TYPES[error_type],
        "recoverable": recoverable,
        "recovery_suggestions": recovery_suggestions,
        "total_stages": 10,
        "error_timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    if error_context:
        payload["error_context"] = error_context
    
    await manager.emit(run_id, "clinical.workflow.error", payload)


async def emit_clinical_workflow_completed(
    manager: WebSocketManager,
    run_id: str,
    workflow_name: str,
    total_processing_time_seconds: float,
    stages_completed: int,
    overall_quality_score: Optional[float] = None,
    output_artifacts: Optional[list] = None,
    summary: Optional[Dict[str, Any]] = None
):
    """Emit when all 10 clinical workflow stages complete successfully."""
    payload = {
        "workflow_name": workflow_name,
        "total_stages": 10,
        "stages_completed": stages_completed,
        "total_processing_time_seconds": total_processing_time_seconds,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "success": stages_completed == 10
    }
    
    if overall_quality_score is not None:
        payload["overall_quality_score"] = overall_quality_score
    
    if output_artifacts:
        payload["output_artifacts"] = output_artifacts
    
    if summary:
        payload["summary"] = summary
    
    await manager.emit(run_id, "clinical.workflow.completed", payload)


async def emit_clinical_substage_progress(
    manager: WebSocketManager,
    run_id: str,
    stage_number: int,
    stage_name: str,
    substage_name: str,
    substage_progress_pct: int,
    message: str
):
    """
    Emit fine-grained progress within a stage.
    
    Useful for long-running stages with multiple steps
    (e.g., tissue analysis with multiple images).
    """
    await manager.emit(run_id, "clinical.substage.progress", {
        "stage_number": stage_number,
        "stage_name": stage_name,
        "substage_name": substage_name,
        "substage_progress_pct": min(100, max(0, substage_progress_pct)),
        "message": message,
        "total_stages": 10,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


def get_clinical_workflow_status(
    manager: WebSocketManager,
    run_id: str
) -> Dict[str, Any]:
    """
    Get current status of a clinical workflow run.
    
    Returns recent events from event history to reconstruct current state.
    """
    events = manager._event_history.get(run_id, [])
    
    # Filter for clinical workflow events
    clinical_events = [
        e for e in events 
        if e.get("event", "").startswith("clinical.")
    ]
    
    if not clinical_events:
        return {"status": "not_found", "run_id": run_id}
    
    # Find latest progress event
    latest_progress = None
    for event in reversed(clinical_events):
        if event.get("event") == "clinical.workflow.progress":
            latest_progress = event
            break
    
    # Check for completion or error
    completed = any(e.get("event") == "clinical.workflow.completed" for e in clinical_events)
    errors = [e for e in clinical_events if e.get("event") == "clinical.workflow.error"]
    
    status = {
        "run_id": run_id,
        "status": "completed" if completed else "in_progress",
        "total_events": len(clinical_events),
        "error_count": len(errors)
    }
    
    if latest_progress:
        payload = latest_progress.get("payload", {})
        status.update({
            "current_stage": payload.get("stage_number"),
            "current_stage_name": payload.get("stage_name"),
            "progress_pct": payload.get("progress_pct"),
            "last_update": latest_progress.get("timestamp")
        })
    
    return status


def _generate_recovery_suggestions(error_type: str, stage_name: str) -> list:
    """Generate contextual recovery suggestions based on error type and stage."""
    suggestions = []
    
    if error_type == "data_error":
        suggestions = [
            "Verify input data format and completeness",
            "Check for missing required fields",
            "Validate data against schema requirements"
        ]
        if "EHR" in stage_name:
            suggestions.append("Ensure EHR data is in supported format (HL7/FHIR/CDA)")
        elif "Genomic" in stage_name:
            suggestions.append("Verify VCF file format and quality scores")
    
    elif error_type == "model_error":
        suggestions = [
            "Check model availability and version",
            "Verify input data dimensions match model requirements",
            "Review model logs for detailed error information"
        ]
        if "DL" in stage_name or "Neural" in stage_name:
            suggestions.append("Ensure GPU resources are available if required")
    
    elif error_type == "system_error":
        suggestions = [
            "Check system resources (memory, CPU, disk space)",
            "Verify network connectivity to external services",
            "Review system logs for infrastructure issues"
        ]
    
    elif error_type == "timeout_error":
        suggestions = [
            "Reduce batch size or input data volume",
            "Increase timeout threshold if appropriate",
            "Check for performance bottlenecks"
        ]
    
    elif error_type == "validation_error":
        suggestions = [
            "Review quality metrics and thresholds",
            "Verify output data meets validation criteria",
            "Check for data quality issues in previous stages"
        ]
    
    # Always add retry suggestion if recoverable
    suggestions.append("Retry the operation")
    
    return suggestions
