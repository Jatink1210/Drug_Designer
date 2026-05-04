"""Run Manager — lifecycle management (§41.1).

Centralises run creation, state transitions, event emission, and
artifact tracking. All other subsystems use this to track work.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import structlog

from models.run import RunRecord, RunState, RunEvent, JobRecord, RunType

log = structlog.get_logger()

# In-memory run store (fallback when PostgreSQL is unavailable)
_RUN_STORE: Dict[str, RunRecord] = {}


class RunManager:
    """Manages the complete lifecycle of scientific runs (§41.1)."""

    def __init__(self, db=None, event_bus=None):
        self._db = db
        self._event_bus = event_bus

    async def create_run(
        self,
        run_type: str,
        project_id: str,
        input_snapshot: Dict[str, Any] = None,
        runtime_context: Dict[str, Any] = None,
    ) -> RunRecord:
        """Create a new run and persist."""
        run = RunRecord(
            run_type=run_type,
            project_id=project_id,
            state=RunState.CREATED,
            input_snapshot=input_snapshot or {},
            runtime_context=runtime_context or {"mode": "hosted"},
        )
        log.info("run.created", run_id=run.run_id, run_type=run_type, project_id=project_id)

        # Persist to PostgreSQL if available
        if self._db is not None:
            try:
                from sqlalchemy import text
                await self._db.execute(
                    text(
                        "INSERT INTO runs (id, run_type, project_id, state, input_snapshot, runtime_context) "
                        "VALUES (:id, :run_type, :project_id, :state, :input_snapshot, :runtime_context)"
                    ),
                    {
                        "id": run.run_id,
                        "run_type": run_type,
                        "project_id": project_id,
                        "state": RunState.CREATED.value,
                        "input_snapshot": str(input_snapshot or {}),
                        "runtime_context": str(runtime_context or {}),
                    },
                )
                await self._db.commit()
            except Exception as exc:
                log.warning("run.db_create_failed", error=str(exc))

        # Always store in memory
        _RUN_STORE[run.run_id] = run
        return run

    async def transition(self, run_id: str, new_state: RunState) -> None:
        """Transition a run to a new state and emit WebSocket event."""
        log.info("run.transition", run_id=run_id, new_state=new_state.value)

        # Update in-memory
        if run_id in _RUN_STORE:
            _RUN_STORE[run_id].state = new_state

        # Update in PostgreSQL
        if self._db is not None:
            try:
                from sqlalchemy import text
                await self._db.execute(
                    text("UPDATE runs SET state = :state, updated_at = NOW() WHERE id = :id"),
                    {"state": new_state.value, "id": run_id},
                )
                await self._db.commit()
            except Exception as exc:
                log.debug("run.db_transition_failed", error=str(exc))

        # Emit WebSocket event
        if self._event_bus:
            event_name = "run.stage_complete" if new_state == RunState.RUNNING else "run.complete"
            event = RunEvent(
                event=event_name,
                run_id=run_id,
                payload={"state": new_state.value},
            )
            try:
                await self._event_bus.broadcast(run_id, event.model_dump())
            except Exception as exc:
                log.debug("run.ws_emit_failed", error=str(exc))

    async def emit_progress(
        self,
        run_id: str,
        stage: str,
        progress_pct: int,
        message: str = "",
        sources_completed: int = 0,
    ) -> None:
        """Emit granular progress update via WebSocket (§51)."""
        event = RunEvent(
            event="run.progress",
            run_id=run_id,
            payload={
                "stage": stage,
                "progress_pct": progress_pct,
                "message": message,
                "sources_completed": sources_completed,
            },
        )
        log.info("run.progress", run_id=run_id, stage=stage, progress_pct=progress_pct)
        if self._event_bus:
            try:
                await self._event_bus.broadcast(run_id, event.model_dump())
            except Exception:
                pass

    async def complete(
        self,
        run_id: str,
        artifacts: List[str] = None,
        degraded_sources: List[str] = None,
    ) -> None:
        """Mark a run as complete with results."""
        state = RunState.PARTIAL_SUCCESS if degraded_sources else RunState.SUCCESS
        log.info(
            "run.complete",
            run_id=run_id,
            state=state.value,
            artifact_count=len(artifacts or []),
            degraded_count=len(degraded_sources or []),
        )

        # Store artifacts
        if run_id in _RUN_STORE:
            _RUN_STORE[run_id].artifacts = artifacts or []
            _RUN_STORE[run_id].degraded_sources = degraded_sources or []

        await self.transition(run_id, state)

    async def fail(self, run_id: str, error: Dict[str, Any]) -> None:
        """Mark a run as failed with structured error."""
        log.error("run.failed", run_id=run_id, error=error)
        if run_id in _RUN_STORE:
            _RUN_STORE[run_id].error = error
        await self.transition(run_id, RunState.FAILED)

    async def get_run(self, run_id: str) -> Optional[RunRecord]:
        """Retrieve a run by ID."""
        if run_id in _RUN_STORE:
            return _RUN_STORE[run_id]

        if self._db is not None:
            try:
                from sqlalchemy import text
                result = await self._db.execute(
                    text("SELECT * FROM runs WHERE id = :id"), {"id": run_id}
                )
                row = result.fetchone()
                if row:
                    return RunRecord(
                        run_id=row.id,
                        run_type=row.run_type,
                        project_id=row.project_id,
                        state=RunState(row.state),
                    )
            except Exception:
                pass
        return None

    async def list_runs(
        self, project_id: str, limit: int = 50, offset: int = 0
    ) -> List[RunRecord]:
        """List runs for a project."""
        runs = [
            r for r in _RUN_STORE.values()
            if r.project_id == project_id
        ]
        runs.sort(key=lambda r: getattr(r, 'created_at', 0), reverse=True)
        return runs[offset: offset + limit]
