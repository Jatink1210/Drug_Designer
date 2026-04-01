"""Router for Decision Dossier export (JSON / HTML / PDF)."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, Any

from services.dossier_builder import DossierBuilder

router = APIRouter(prefix="/api/jobs", tags=["Dossier"])


@router.get("/{job_id}/dossier")
async def get_dossier(
    job_id: str,
    format: str = Query("json", description="Export format: json, html, or pdf"),
) -> Any:
    """Generate and return the Decision Dossier for a job."""
    dossier = DossierBuilder.build(job_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Job not found")

    if format == "html":
        html = DossierBuilder.render_html(dossier)
        return HTMLResponse(content=html, media_type="text/html")

    if format == "pdf":
        # PDF strategy: generate HTML and let the client print-to-pdf.
        # In Docker/Studio mode a headless renderer can be added later.
        html = DossierBuilder.render_html(dossier)
        return HTMLResponse(
            content=html,
            media_type="text/html",
            headers={"X-DSS-PDF-Hint": "Use browser print-to-PDF for now."},
        )

    # Default: JSON
    return JSONResponse(content=dossier)
