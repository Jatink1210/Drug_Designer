from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from typing import List, Dict, Any
import logging
import os

from services.job_logger import JobLogger

router = APIRouter(prefix="/api", tags=["Media"])
logger = logging.getLogger(__name__)

@router.get("/jobs/{job_id}/media")
async def get_job_media(job_id: str) -> List[Dict[str, Any]]:
    """Return all artifacts generated for a specific job."""
    return JobLogger.get_job_artifacts(job_id)

@router.get("/media/{artifact_id}/download")
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
