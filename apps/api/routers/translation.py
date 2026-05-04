"""Translation Router — Drug Designer §127.

Handles data transformation, result retrieval, and save operations.
§78: All responses use ResponseEnvelope.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from routers.auth import get_current_user
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from models.db_tables import Run, ExportRecord
from models.envelope import build_envelope as _shared_envelope

router = APIRouter(prefix="/api/v1/translation", tags=["Translation"], dependencies=[Depends(get_current_user)])


def _build_envelope(req: Request, data: Any, warnings: list = None) -> Dict[str, Any]:
    return _shared_envelope(req, data, warnings=warnings)


# ── Request / Response Models ───────────────────────────────

class TransformRequest(BaseModel):
    source_format: str = "json"
    target_format: str = "json"
    data: Dict[str, Any] = {}
    options: Dict[str, Any] = {}
    project_id: str = ""


class TranslationSaveRequest(BaseModel):
    result_id: str
    project_id: str = ""
    label: str = ""
    metadata: Dict[str, Any] = {}


# ── Synchronous transform helpers ───────────────────────────

def _json_to_csv(data: Dict[str, Any]) -> str:
    """Convert a dict or list-of-dicts to CSV string."""
    rows: List[Dict[str, Any]] = []
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        # If the dict has a list value, use that; otherwise wrap
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                rows = v
                break
        if not rows:
            rows = [data]

    if not rows:
        return ""

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


_PICO_FIELDS = {"population", "intervention", "comparator", "outcome"}


def _evidence_to_pico(data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract P/I/C/O fields from evidence items."""
    items: List[Dict[str, Any]] = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                items = v
                break
        if not items:
            items = [data]

    pico_results = []
    for item in items:
        pico = {}
        for field in _PICO_FIELDS:
            pico[field] = item.get(field, item.get(field[0].upper(), ""))
        pico["source"] = item.get("source", item.get("title", ""))
        pico_results.append(pico)
    return {"pico_items": pico_results, "count": len(pico_results)}


def _is_simple_transform(source: str, target: str) -> bool:
    return (source, target) in {("json", "csv"), ("evidence", "pico")}


def _do_sync_transform(source: str, target: str, data: Dict[str, Any]) -> Any:
    if source == "json" and target == "csv":
        return _json_to_csv(data)
    if source == "evidence" and target == "pico":
        return _evidence_to_pico(data)
    return data


# ── Endpoints ───────────────────────────────────────────────

@router.post("/transform")
async def transform_data(
    req: TransformRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """§127: POST /api/v1/translation/transform — Transform data between formats."""
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    run = Run(
        id=run_id,
        project_id=req.project_id or "default",
        run_type="translation.transform",
        state="QUEUED",
        input_snapshot={
            "source_format": req.source_format,
            "target_format": req.target_format,
            "data": req.data,
            "options": req.options,
        },
        created_at=now,
    )
    db.add(run)

    warnings: list = []

    if _is_simple_transform(req.source_format, req.target_format):
        # Synchronous transform
        transformed = _do_sync_transform(req.source_format, req.target_format, req.data)
        run.state = "SUCCESS"
        run.output_artifacts = [{"transformed": transformed}]
        run.started_at = now
        run.finished_at = datetime.now(timezone.utc)
        run.elapsed_ms = int((run.finished_at - now).total_seconds() * 1000)
        await db.commit()

        return _build_envelope(request, {
            "result_id": run_id,
            "source_format": req.source_format,
            "target_format": req.target_format,
            "status": "completed",
            "transformed": transformed,
        })
    else:
        # Complex transform — leave QUEUED for ARQ worker pickup
        run.state = "QUEUED"
        await db.commit()
        warnings.append("Complex transform queued for background processing")

        return _build_envelope(request, {
            "result_id": run_id,
            "source_format": req.source_format,
            "target_format": req.target_format,
            "status": "queued",
        }, warnings=warnings)


@router.get("/result/{result_id}")
async def get_translation_result(
    result_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """§127: GET /api/v1/translation/result/{id} — Get translation result."""
    result = await db.execute(select(Run).where(Run.id == result_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {result_id} not found")

    payload: Dict[str, Any] = {
        "result_id": run.id,
        "run_type": run.run_type,
        "status": run.state.lower(),
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }

    if run.state == "SUCCESS":
        payload["data"] = run.output_artifacts or []
        payload["elapsed_ms"] = run.elapsed_ms
        payload["finished_at"] = run.finished_at.isoformat() if run.finished_at else None
    elif run.state in ("QUEUED", "RUNNING"):
        payload["progress"] = run.timing or {}
        payload["started_at"] = run.started_at.isoformat() if run.started_at else None
    elif run.state == "FAILED":
        payload["errors"] = run.errors or []

    return _build_envelope(request, payload)


@router.post("/save")
async def save_translation(
    req: TranslationSaveRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """§127: POST /api/v1/translation/save — Save translation result."""
    # Verify the run exists
    result = await db.execute(select(Run).where(Run.id == req.result_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {req.result_id} not found")

    project_id = req.project_id or run.project_id or "default"

    export = ExportRecord(
        id=str(uuid.uuid4()),
        project_id=project_id,
        object_type="translation_result",
        object_id=run.id,
        export_format="json",
        status="ready",
        file_ref=f"translation/{run.id}",
        created_by=run.user_id or "system",
    )
    db.add(export)

    # Also mark the run summary with save metadata
    run.summary = (run.summary or "") + f" [Saved: {req.label or 'untitled'}]"

    await db.commit()

    return _build_envelope(request, {
        "result_id": req.result_id,
        "export_id": export.id,
        "project_id": project_id,
        "label": req.label,
        "saved": True,
    })
