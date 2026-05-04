from fastapi import APIRouter, Depends, HTTPException, Query, Request
from routers.auth import get_current_user
from fastapi.responses import FileResponse
from typing import List, Dict, Any, Optional
import logging
import os
import uuid
from datetime import datetime, timezone

from services.job_logger import JobLogger

router = APIRouter(prefix="/api/v1/media", tags=["Media"], dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)


def _media_envelope(req: Request, data, warnings=None):
    return {
        "request_id": req.headers.get("X-Request-ID", str(uuid.uuid4())),
        "status": "ok",
        "data": data,
        "warnings": warnings or [],
        "errors": [],
        "timing": {"started_at": datetime.now(timezone.utc).isoformat(), "elapsed_ms": 0},
        "provenance": {"runtime_mode": "hosted"},
    }


@router.get("/jobs/{job_id}")
async def get_job_media(job_id: str) -> List[Dict[str, Any]]:
    """Return all artifacts generated for a specific job."""
    return JobLogger.get_job_artifacts(job_id)

@router.get("/{artifact_id}/download")
async def download_artifact(artifact_id: str, format: str = Query("png", description="Format: svg, png, or json")):
    """Download the raw file for a given artifact."""
    artifact = JobLogger.get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
        
    path_key = f"{format}_path"
    if path_key not in artifact or not artifact[path_key]:
        raise HTTPException(status_code=400, detail=f"Format {format} not available for this artifact.")
        
    file_path = artifact[path_key]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File missing on disk.")
        
    media_types = {"png": "image/png", "svg": "image/svg+xml", "json": "application/json"}
    return FileResponse(file_path, media_type=media_types.get(format, "application/octet-stream"), filename=f"{artifact_id}.{format}")


# ── §129 Spec-Aligned Media Endpoints ────────────────────

@router.get("")
async def list_media(
    request: Request,
    project_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    """§129: GET /api/v1/media?project_id=... — List media artifacts."""
    from core.db import AsyncSessionLocal
    from models.db_tables import MediaArtifactRecord
    from sqlalchemy import select
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(MediaArtifactRecord).limit(limit)
            if project_id:
                stmt = stmt.where(MediaArtifactRecord.project_id == project_id)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            artifacts = [{"id": r.id, "name": r.name, "mime_type": r.mime_type,
                          "project_id": r.project_id, "created_at": str(r.created_at)} for r in rows]
            return _media_envelope(request, {"artifacts": artifacts, "total": len(artifacts)})
    except Exception:
        return _media_envelope(request, {"artifacts": [], "total": 0})


@router.get("/{artifact_id}")
async def get_media_artifact(artifact_id: str, request: Request) -> Dict[str, Any]:
    """§129: GET /api/v1/media/{artifactId} — Get media artifact metadata."""
    artifact = JobLogger.get_artifact(artifact_id)
    if not artifact:
        return _media_envelope(request, {"artifact_id": artifact_id, "found": False},
                              warnings=["Artifact not found"])
    return _media_envelope(request, artifact)


@router.post("/export")
async def export_media(request: Request) -> Dict[str, Any]:
    """§129: POST /api/v1/media/export — Export media artifacts."""
    from core.db import AsyncSessionLocal
    from models.db_tables import ExportRecord
    export_id = str(uuid.uuid4())
    try:
        async with AsyncSessionLocal() as session:
            record = ExportRecord(id=export_id, format="zip", status="rendering")
            session.add(record)
            await session.commit()
    except Exception:
        pass
    return _media_envelope(request, {
        "export_id": export_id,
        "status": "rendering",
    })
