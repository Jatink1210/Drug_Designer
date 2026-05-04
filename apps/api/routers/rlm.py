"""Router for RLM (Recursive Language Model) engine execution jobs."""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from starlette.responses import StreamingResponse
from models.envelope import build_envelope
from routers.auth import get_current_user

from services.job_logger import JobLogger
from services.rlm_engine import RLMEngine

router = APIRouter(prefix="/api/v1/jobs", tags=["rlm_jobs"], dependencies=[Depends(get_current_user)])
log = logging.getLogger(__name__)


@router.get("/history")
async def list_job_history(request: Request) -> Dict[str, Any]:
    """List all past job runs (most recent first)."""
    try:
        history = JobLogger.get_all_jobs()
        return build_envelope(request, history)
    except Exception as e:
        log.warning("Could not list job history: %s", e)
        return build_envelope(request, [])


class RunJobRequest(BaseModel):
    query: str
    constraints: Dict[str, Any] = {}
    project_id: Optional[str] = None


# In-memory active job store: {job_id: {"status": ..., "queue": Queue, ...}}
_ACTIVE_JOBS: Dict[str, Dict[str, Any]] = {}


async def _run_rlm_task(
    job_logger: JobLogger,
    engine: RLMEngine,
    step_queue: asyncio.Queue,
):
    """Background task runner for the RLM loop."""
    try:
        with job_logger:
            result = await engine.run(job_logger=job_logger, step_queue=step_queue)
            _ACTIVE_JOBS[job_logger.job_id]["result"] = result
            _ACTIVE_JOBS[job_logger.job_id]["status"] = "completed"
    except Exception as e:
        _ACTIVE_JOBS[job_logger.job_id]["status"] = "failed"
        try:
            step_queue.put_nowait({"type": "done", "error": str(e)})
        except Exception:
            log.debug("Failed to push done event to step queue")
        with job_logger:
            job_logger.log_step(
                "Execution Error", "failed",
                details={"error": str(e)}, duration_ms=0,
            )


@router.post("/run")
async def start_rlm_job(
    req: RunJobRequest, request: Request, background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """Start an RLM async reasoning job."""
    engine = RLMEngine(
        query=req.query,
        constraints=req.constraints,
        project_id=req.project_id,
    )
    job_logger = JobLogger(job_name=req.query[:40])
    step_queue: asyncio.Queue = asyncio.Queue()

    _ACTIVE_JOBS[job_logger.job_id] = {
        "status": "active",
        "query": req.query,
        "queue": step_queue,
    }
    background_tasks.add_task(_run_rlm_task, job_logger, engine, step_queue)

    return build_envelope(request, {
        "job_id": job_logger.job_id,
        "status": "started",
        "message": "RLM reasoning loop initialized.",
    })


@router.get("/{job_id}")
async def get_job_status(job_id: str, request: Request) -> Dict[str, Any]:
    """Get the result or current status of an RLM job."""

    # 1. Check in-memory result first
    job = _ACTIVE_JOBS.get(job_id, {})
    if job.get("status") == "completed" and "result" in job:
        return build_envelope(request, job["result"])

    # 2. Check the SQLite JobLogger
    trace = JobLogger.get_job_trace(job_id)
    if trace:
        return build_envelope(request, {
            "job_id": job_id,
            "name": trace.get("name"),
            "status": trace.get("status"),
        })

    raise HTTPException(status_code=404, detail="Job not found")


@router.get("/{job_id}/trace")
async def get_job_trace(job_id: str, request: Request) -> Dict[str, Any]:
    """Get the full minute-by-minute execution trace for reproducible science."""
    trace = JobLogger.get_job_trace(job_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return build_envelope(request, {"trace": trace})


@router.get("/{job_id}/stream")
async def stream_job_progress(job_id: str):
    """SSE endpoint for real-time step-by-step progress streaming."""
    if job_id not in _ACTIVE_JOBS:
        raise HTTPException(status_code=404, detail="Job not found")

    queue = _ACTIVE_JOBS[job_id].get("queue")
    if queue is None:
        raise HTTPException(
            status_code=404, detail="Stream not available for this job",
        )

    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                payload = json.dumps(event, default=str)
                if event.get("type") == "done":
                    yield f"event: done\ndata: {payload}\n\n"
                    break
                yield f"data: {payload}\n\n"
            except asyncio.TimeoutError:
                # Keep-alive comment to prevent proxy timeouts
                yield ": keepalive\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
