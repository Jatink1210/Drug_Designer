"""Router for job execution logs, traces, and run-recipe export."""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any

from services.job_logger import JobLogger

router = APIRouter(prefix="/api/logs", tags=["Logs"])


@router.get("/jobs")
async def list_log_jobs() -> List[Dict[str, Any]]:
    """List all jobs that have execution traces."""
    return JobLogger.get_all_jobs()


@router.get("/job/{job_id}")
async def get_job_trace(job_id: str) -> Dict[str, Any]:
    """Get the full minute-by-minute execution trace for a specific job."""
    trace = JobLogger.get_job_trace(job_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace


@router.get("/job/{job_id}/logs")
async def get_job_logs(
    job_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    search: str = Query("", description="Case-insensitive text search across log entries"),
    tool: str = Query("", description="Filter by tool_name (e.g. opentargets_connector)"),
) -> Dict[str, Any]:
    """Return paged, searchable JSONL log entries for a job."""
    result = JobLogger.get_job_logs(
        job_id, offset=offset, limit=limit, search=search, tool_filter=tool
    )
    if result["total"] == 0 and not _job_exists(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return result


@router.get("/job/{job_id}/recipe")
async def get_job_recipe(job_id: str) -> Dict[str, Any]:
    """Return the reproducibility run-recipe JSON for a job."""
    recipe = JobLogger.get_job_recipe(job_id)
    if not recipe:
        # Fall back to building a minimal recipe from trace data
        trace = JobLogger.get_job_trace(job_id)
        if not trace:
            raise HTTPException(status_code=404, detail="Job not found")
        return {
            "schema_version": "1.0",
            "job_id": job_id,
            "name": trace.get("name", ""),
            "status": trace.get("status", "unknown"),
            "started_at": trace.get("started_at", ""),
            "duration_ms": trace.get("duration_ms", 0),
            "steps_total": len(trace.get("steps", [])),
            "note": "Recipe was not recorded at run time; this is a reconstruction from trace data.",
        }
    return recipe


def _job_exists(job_id: str) -> bool:
    """Quick check if a job exists in the DB at all."""
    trace = JobLogger.get_job_trace(job_id)
    return trace is not None

