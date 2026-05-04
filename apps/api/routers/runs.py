"""Runs & Jobs CRUD — Drug Designer §23, §41, §92.

Every serious action in Drug Designer becomes a tracked Run.
Lifecycle: CREATED → QUEUED → RUNNING → [SUCCESS | PARTIAL_SUCCESS | FAILED | CANCELLED | TIMED_OUT]

§78: All responses use ResponseEnvelope.
§70: List endpoints use cursor-based pagination.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models.envelope import build_envelope as _shared_envelope

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.websocket_manager import get_ws_manager
from models.db_tables import Run, Job, RunEvent
from routers.auth import get_current_user, User

router = APIRouter(prefix="/api/v1/runs", tags=["Runs & Jobs"])
log = structlog.get_logger(__name__)


# ── Request / Response Models ────────────────────────────────

class RunCreateRequest(BaseModel):
    project_id: str
    run_type: str  # disease.intelligence, target.ranking, etc.
    input_snapshot: Dict[str, Any] = Field(default_factory=dict)
    runtime_mode: str = "hosted"  # hosted | local | auto


class RunUpdateRequest(BaseModel):
    state: Optional[str] = None
    output_artifacts: Optional[List[str]] = None
    errors: Optional[List[Dict[str, Any]]] = None


class RunCancelRequest(BaseModel):
    reason: str = ""


# ── Helpers ──────────────────────────────────────────────────

def _build_envelope(req: Request, data: Any, status: str = "ok",
                    warnings: list | None = None, errors: list | None = None) -> Dict[str, Any]:
    return _shared_envelope(req, data, status=status, warnings=warnings, errors=errors)


def _run_to_dict(run: Run) -> Dict[str, Any]:
    return {
        "run_id": run.id,
        "project_id": run.project_id,
        "run_type": run.run_type,
        "state": run.state,
        "input_snapshot": run.input_snapshot or {},
        "runtime_context": run.runtime_context or {},
        "source_footprint": run.source_footprint or [],
        "timing": run.timing or {},
        "output_artifacts": run.output_artifacts or [],
        "errors": run.errors or [],
        "degraded": run.degraded or {},
        "provenance": run.provenance or {},
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


# ── Endpoints (§92 Run Management) ──────────────────────────

@router.post("")
async def create_run(
    req: RunCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """§23.2: Create a tracked run. Returns the run record immediately."""
    run = Run(
        id=str(uuid.uuid4()),
        project_id=req.project_id,
        run_type=req.run_type,
        state="CREATED",
        input_snapshot=req.input_snapshot,
        runtime_context={"mode": req.runtime_mode, "model_id": None, "hardware": None},
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    log.info("run_created", run_id=run.id, run_type=run.run_type, project_id=run.project_id)
    return _build_envelope(request, _run_to_dict(run))


@router.get("")
async def list_runs(
    request: Request,
    project_id: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    run_type: Optional[str] = Query(None),
    limit: int = Query(25, ge=1, le=200),
    cursor: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """§92: List runs with optional filters. Cursor-based pagination (§70)."""
    q = select(Run).order_by(desc(Run.created_at))
    if project_id:
        q = q.where(Run.project_id == project_id)
    if state:
        q = q.where(Run.state == state)
    if run_type:
        q = q.where(Run.run_type == run_type)
    if cursor:
        q = q.where(Run.created_at < cursor)
    q = q.limit(limit + 1)

    result = await db.execute(q)
    rows = result.scalars().all()
    has_more = len(rows) > limit
    runs = [_run_to_dict(r) for r in rows[:limit]]

    return _build_envelope(request, {
        "runs": runs,
        "pagination": {
            "cursor": runs[-1]["created_at"] if runs and has_more else None,
            "has_more": has_more,
            "total_count": None,
            "page_size": limit,
        },
    })


@router.get("/{run_id}")
async def get_run(
    run_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """§92: Get a single run by ID."""
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalars().first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _build_envelope(request, _run_to_dict(run))


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    req: RunCancelRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """§23.3: Cancel a running or queued run."""
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalars().first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.state not in ("CREATED", "QUEUED", "RUNNING"):
        raise HTTPException(status_code=409, detail=f"Cannot cancel run in state {run.state}")

    run.state = "CANCELLED"
    run.completed_at = datetime.now(timezone.utc)
    run.errors = (run.errors or []) + [{"code": "USER_CANCELLED", "message": req.reason or "Cancelled by user"}]
    await db.commit()

    ws = get_ws_manager()
    await ws.emit(run_id, "run.cancelled", {"reason": req.reason})
    log.info("run_cancelled", run_id=run_id)
    return _build_envelope(request, _run_to_dict(run))


@router.post("/{run_id}/retry")
async def retry_run(
    run_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """§23.3: Retry a failed or timed-out run by creating a clone."""
    result = await db.execute(select(Run).where(Run.id == run_id))
    original = result.scalars().first()
    if not original:
        raise HTTPException(status_code=404, detail="Run not found")
    if original.state not in ("FAILED", "TIMED_OUT", "CANCELLED"):
        raise HTTPException(status_code=409, detail=f"Cannot retry run in state {original.state}")

    new_run = Run(
        id=str(uuid.uuid4()),
        project_id=original.project_id,
        run_type=original.run_type,
        state="CREATED",
        input_snapshot=original.input_snapshot,
        runtime_context=original.runtime_context,
    )
    db.add(new_run)
    await db.commit()
    await db.refresh(new_run)
    log.info("run_retried", original_run_id=run_id, new_run_id=new_run.id)
    return _build_envelope(request, {
        "original_run_id": run_id,
        "new_run": _run_to_dict(new_run),
    })


@router.get("/{run_id}/events")
async def get_run_events(
    run_id: str,
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """§57: Get WebSocket events for a run (historical replay)."""
    result = await db.execute(
        select(RunEvent)
        .where(RunEvent.run_id == run_id)
        .order_by(RunEvent.created_at)
        .limit(limit)
    )
    events = result.scalars().all()
    return _build_envelope(request, {
        "run_id": run_id,
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "payload": e.payload or {},
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    })


@router.get("/{run_id}/artifacts")
async def get_run_artifacts(
    run_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """§23.5: List artifacts produced by a run."""
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalars().first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _build_envelope(request, {
        "run_id": run_id,
        "artifacts": run.output_artifacts or [],
    })


@router.get("/{run_id}/jobs")
async def get_run_jobs(
    run_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """§92: List background jobs linked to a run."""
    result = await db.execute(
        select(Job)
        .where(Job.run_id == run_id)
        .order_by(Job.created_at)
    )
    jobs = result.scalars().all()
    return _build_envelope(request, {
        "run_id": run_id,
        "jobs": [
            {
                "id": j.id,
                "queue_name": j.queue_name,
                "status": j.status,
                "retries": j.retries,
                "payload": j.payload or {},
                "result": j.result or {},
                "error": j.error,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            }
            for j in jobs
        ],
    })


# ── Batch Processing Endpoints (§FR-API-010) ────────────────

class BatchRunRequest(BaseModel):
    runs: List[Dict[str, Any]]  # List of {project_id, run_type, input_snapshot}
    runtime_mode: str = "hosted"


@router.post("/batch-execute")
async def batch_execute_runs(
    req: BatchRunRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """§FR-API-010: POST /api/v1/runs/batch-execute — Execute multiple runs at once."""
    try:
        created_runs = []
        failed_runs = []
        
        for idx, run_data in enumerate(req.runs):
            try:
                project_id = run_data.get("project_id")
                run_type = run_data.get("run_type")
                input_snapshot = run_data.get("input_snapshot", {})
                
                if not project_id or not run_type:
                    failed_runs.append({
                        "index": idx,
                        "error": "Missing project_id or run_type",
                        "run_data": run_data
                    })
                    continue
                
                # Create run
                run = Run(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    run_type=run_type,
                    state="QUEUED",
                    input_snapshot=input_snapshot,
                    runtime_context={
                        "mode": req.runtime_mode,
                        "batch": True,
                        "batch_index": idx
                    },
                )
                db.add(run)
                await db.flush()
                
                created_runs.append({
                    "run_id": run.id,
                    "project_id": run.project_id,
                    "run_type": run.run_type,
                    "state": run.state,
                    "batch_index": idx
                })
                
                log.info(
                    "batch_run_created",
                    run_id=run.id,
                    run_type=run.run_type,
                    batch_index=idx
                )
                
            except Exception as e:
                failed_runs.append({
                    "index": idx,
                    "error": str(e),
                    "run_data": run_data
                })
        
        await db.commit()
        
        return _build_envelope(request, {
            "created_count": len(created_runs),
            "failed_count": len(failed_runs),
            "created_runs": created_runs,
            "failed_runs": failed_runs,
            "runtime_mode": req.runtime_mode
        })
        
    except Exception as e:
        log.error("batch_execute_failed", error=str(e))
        return _build_envelope(
            request, None,
            status="error",
            errors=[{"code": "BATCH_EXECUTE_FAILED", "message": str(e)}]
        )
