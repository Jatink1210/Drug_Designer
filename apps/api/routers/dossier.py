"""Decision Dossier Router — Drug Designer §A10, §20.6.

§A10: The Dossier is the canonical final output of every Drug Designer workflow.
It is NOT a report. It is a structured Decision Support Artifact with:
  1. Evidence-backed summaries
  2. Conflict/contradiction sections  
  3. MAV consensus verification (§22.5)
  4. Full provenance chain
  5. Export as PDF, DOCX, JSON, ZIP

§23.2: Dossier generation is a tracked Run (type: dossier.generation)
§78: All responses use ResponseEnvelope
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from routers.auth import get_current_user
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import structlog

from services.dossier_builder import DossierBuilder
from core.websocket_manager import get_ws_manager
from core.db import AsyncSessionLocal
from models.db_tables import DossierRecord, EvidenceItemRecord
from models.envelope import build_envelope as _canonical_envelope

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/dossiers", tags=["Decision Dossier"], dependencies=[Depends(get_current_user)])


# ── Request / Response Models ────────────────────────────────

class DossierGenerateRequest(BaseModel):
    project_id: str
    title: Optional[str] = None
    include_sections: List[str] = [
        "objective", "constraints", "evidence_summary", "ranked_options",
        "contradictions", "assumptions", "recommendations", "provenance",
        "export_metadata",
    ]
    evidence_bundle_ids: List[str] = []
    target_ranking_id: Optional[str] = None
    disease_run_id: Optional[str] = None


class DossierResponse(BaseModel):
    """§78 ResponseEnvelope-compatible."""
    request_id: str
    status: str
    data: Optional[Dict[str, Any]] = None
    warnings: List[str] = []
    errors: List[Dict[str, Any]] = []
    timing: Dict[str, Any] = {}
    provenance: Dict[str, Any] = {}


# ── Endpoints ────────────────────────────────────────────────

@router.post("/generate", response_model=DossierResponse)
async def generate_dossier(payload: DossierGenerateRequest, request: Request):
    """Generate a Decision Dossier (§A10).
    
    Creates a tracked run (type: dossier.generation).
    Invokes Context Fabric to pull ALL L2 artifacts, then routes through:
      Evidence Summarizer → Recommendation Drafter → Provenance Auditor
    """
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    ws = get_ws_manager()
    warnings = []

    try:
        await ws.emit_progress(run_id, "context_assembly", 10, "Assembling context from project memory...")

        # Build dossier from project data (async, queries DB for runs/evidence)
        dossier = await DossierBuilder.build_from_project(
            project_id=payload.project_id,
            evidence_bundle_ids=payload.evidence_bundle_ids,
            target_ranking_id=payload.target_ranking_id,
            disease_run_id=payload.disease_run_id,
        )

        # Fallback to legacy job-based build if project-based returns nothing
        if not dossier:
            dossier = DossierBuilder.build(payload.project_id)

        if not dossier:
            return DossierResponse(
                request_id=request_id,
                status="error",
                errors=[{"code": "NO_DATA", "message": "No project data found for dossier generation", "recoverable": True}],
                timing={"total_ms": _elapsed_ms(started_at)},
            )

        await ws.emit_stage_complete(run_id, "context_assembly")
        await ws.emit_progress(run_id, "drafting", 50, "Drafting dossier sections...")

        # Determine completeness
        missing_sections = []
        for section in payload.include_sections:
            if section not in dossier:
                missing_sections.append(section)
        if missing_sections:
            warnings.append(f"Missing dossier sections: {', '.join(missing_sections)}")

        await ws.emit_stage_complete(run_id, "drafting")
        await ws.emit_complete(run_id, "ok" if not warnings else "partial")

        # B-5/B-6: MAV trace — populated during DB persist block below
        mav_trace: dict = {}

        # Persist dossier to database
        dossier_id = str(uuid.uuid4())
        try:
            # Derive section names from dossier content
            section_names = []
            if dossier.get("ranked_options"):
                section_names.append("target_rankings")
            if dossier.get("evidence_summary"):
                section_names.append("evidence_summary")
            if dossier.get("disease_summary"):
                section_names.append("disease_intelligence")
            if dossier.get("source_footprint"):
                section_names.append("source_footprint")
            if dossier.get("recommendations"):
                section_names.append("recommendations")
            if dossier.get("objective"):
                section_names.append("objective")

            async with AsyncSessionLocal() as session:
                # B-5: collect MAV consensus trace for this dossier
                try:
                    from services.consensus.mav_service import aggregate_votes
                    if payload.disease_run_id:
                        mav_trace = await aggregate_votes(session, run_id=payload.disease_run_id)
                except Exception:
                    pass

                record = DossierRecord(
                    id=dossier_id,
                    project_id=payload.project_id,
                    title=payload.title or dossier.get("title", "Untitled Dossier"),
                    objective=dossier.get("objective", ""),
                    status="finalized",
                    sections=section_names,
                    body_json=dossier,
                    provenance_appendix=dossier.get("provenance", {}),
                    mav_consensus_trace=mav_trace,  # B-5
                )
                session.add(record)
                await session.commit()
                # A-8: audit log — dossier create
                try:
                    from core.audit import log_audit
                    user_id = getattr(request.state, "user_id", "system")
                    await log_audit(
                        session, user_id=user_id,
                        action="dossier.create",
                        resource_type="dossiers",
                        resource_id=dossier_id,
                        details={"project_id": payload.project_id, "title": payload.title},
                    )
                    await session.commit()
                except Exception:
                    pass  # audit failure must never break dossier generation
        except Exception as db_err:
            log.warning("dossier_db_persist_failed", error=str(db_err), dossier_id=dossier_id)
            warnings.append("Dossier generated but DB persistence failed")

        return DossierResponse(
            request_id=request_id,
            status="ok" if not warnings else "partial",
            data={
                "run_id": run_id,
                "dossier_id": dossier_id,
                "project_id": payload.project_id,
                "title": payload.title or dossier.get("title", "Untitled Dossier"),
                "sections": dossier,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            warnings=warnings,
            timing={"total_ms": _elapsed_ms(started_at)},
            provenance={
                "run_id": run_id,
                "runtime_mode": "hosted",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "sources": list(dossier.get("source_footprint", [])),
                "runtime_context": {
                    "consensus": mav_trace,  # B-6
                },
            },
        )

    except Exception as e:
        log.error("dossier_generation_failed", error=str(e), run_id=run_id)
        await ws.emit_error(run_id, "dossier", str(e), recoverable=False)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{dossier_id}")
async def get_dossier(
    dossier_id: str,
    format: str = Query("json", description="Export format: json, html, or pdf"),
) -> Any:
    """Retrieve a previously generated dossier in various formats."""
    # Try DB first
    dossier = None
    try:
        async with AsyncSessionLocal() as session:
            record = await session.get(DossierRecord, dossier_id)
            if record:
                dossier = record.body_json or {
                    "title": record.title,
                    "objective": record.objective,
                    "sections": record.sections,
                    "provenance": record.provenance_appendix,
                    "job_id": dossier_id,
                    "generated_at": record.created_at.isoformat() if record.created_at else "",
                    "question": record.objective or record.title,
                    "constraints": {"applied": False, "summary": "N/A", "step": None},
                    "evidence": [],
                    "ranking_table": [],
                    "contradictions": [],
                    "assumptions_and_overrides": [],
                    "recommended_next_experiments": [],
                    "media_artifacts": [],
                    "run_recipe": {},
                    "trace_summary": {"status": record.status},
                }
    except Exception as db_err:
        log.warning("dossier_db_read_failed", error=str(db_err), dossier_id=dossier_id)

    # Fallback to legacy job-based build
    if not dossier:
        dossier = DossierBuilder.build(dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier not found")

    if format == "html":
        html = DossierBuilder.render_html(dossier)
        return HTMLResponse(content=html, media_type="text/html")

    if format == "pdf":
        html = DossierBuilder.render_html(dossier)
        return HTMLResponse(
            content=html,
            media_type="text/html",
            headers={"X-DSS-PDF-Hint": "Use browser print-to-PDF for now."},
        )

    return JSONResponse(content=dossier)


# ── Legacy compatibility (§23.4) ─────────────────────────────

@router.get("/jobs/{job_id}/dossier")
async def get_dossier_by_job(
    job_id: str,
    format: str = Query("json", description="Export format: json, html, or pdf"),
) -> Any:
    """Legacy endpoint — get dossier by job_id (preserved for backward compat)."""
    return await get_dossier(job_id, format)


def _elapsed_ms(started_at: datetime) -> int:
    return int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)


def _build_dossier_envelope(req: Request, data, status: str = "ok", warnings: list = None) -> Dict[str, Any]:
    return _canonical_envelope(req, data, status=status, warnings=warnings)


@router.get("")
async def list_dossiers(
    request: Request,
    project_id: str = Query(None),
    limit: int = Query(10, ge=1, le=200),
) -> Dict[str, Any]:
    """§A10: List all dossiers, optionally filtered by project."""
    from sqlalchemy import select

    dossiers_list: List[Dict[str, Any]] = []
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(DossierRecord).order_by(DossierRecord.created_at.desc()).limit(limit)
            if project_id:
                stmt = stmt.where(DossierRecord.project_id == project_id)
            result = await session.execute(stmt)
            records = result.scalars().all()
            for rec in records:
                sections = rec.sections if isinstance(rec.sections, list) else []
                dossiers_list.append({
                    "dossier_id": rec.id,
                    "project_id": rec.project_id,
                    "title": rec.title,
                    "status": rec.status,
                    "section_count": len(sections),
                    "sections": sections,
                    "created_at": rec.created_at.isoformat() if rec.created_at else None,
                    "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
                })
    except Exception as db_err:
        log.warning("dossier_list_db_failed", error=str(db_err))

    return _build_dossier_envelope(request, {"dossiers": dossiers_list, "total": len(dossiers_list)})


@router.post("/{dossier_id}/export")
async def export_dossier(
    dossier_id: str,
    request: Request,
    format: str = Query("json", description="Export format: json, html, pdf, docx, zip"),
) -> Any:
    """§A10: Export a dossier in the specified format."""
    dossier = DossierBuilder.build(dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier not found")

    if format == "html":
        html = DossierBuilder.render_html(dossier)
        return HTMLResponse(content=html, media_type="text/html")

    if format == "pdf":
        html = DossierBuilder.render_html(dossier)
        return HTMLResponse(
            content=html,
            media_type="text/html",
            headers={"X-DSS-PDF-Hint": "Use browser print-to-PDF or wkhtmltopdf."},
        )

    return JSONResponse(content=dossier)


# ── §129 Spec-Aligned Additional Dossier Endpoints ───────

@router.post("")
async def create_dossier(payload: DossierGenerateRequest, request: Request):
    """§129: POST /api/v1/dossiers — Create a new dossier (alias for /generate)."""
    return await generate_dossier(payload, request)


class DossierUpdateRequest(BaseModel):
    title: Optional[str] = None
    objective: Optional[str] = None
    status: Optional[str] = None
    include_sections: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    body_updates: Optional[Dict[str, Any]] = None


@router.patch("/{dossier_id}")
async def update_dossier(dossier_id: str, req: DossierUpdateRequest, request: Request) -> Dict[str, Any]:
    """§129: PATCH /api/v1/dossiers/{dossierId} — Update dossier metadata and content."""
    try:
        async with AsyncSessionLocal() as session:
            record = await session.get(DossierRecord, dossier_id)
            if not record:
                raise HTTPException(status_code=404, detail="Dossier not found")

            if req.title is not None:
                record.title = req.title
            if req.objective is not None:
                record.objective = req.objective
            if req.status is not None:
                record.status = req.status
            if req.include_sections is not None:
                record.sections = req.include_sections

            # Merge updates into body_json
            if req.body_updates or req.metadata:
                body = dict(record.body_json) if record.body_json else {}
                if req.body_updates:
                    body.update(req.body_updates)
                if req.metadata:
                    body.setdefault("metadata", {})
                    body["metadata"].update(req.metadata)
                record.body_json = body

            await session.commit()
            await session.refresh(record)

            return _build_dossier_envelope(request, {
                "dossier_id": record.id,
                "project_id": record.project_id,
                "title": record.title,
                "objective": record.objective,
                "status": record.status,
                "sections": record.sections,
                "updated_at": record.updated_at.isoformat() if record.updated_at else None,
            })
    except HTTPException:
        raise
    except Exception as e:
        log.error("dossier_update_failed", error=str(e), dossier_id=dossier_id)
        raise HTTPException(status_code=500, detail=str(e))


class InsertEvidenceRequest(BaseModel):
    evidence_item_ids: List[str] = []
    section: str = "evidence_summary"


@router.post("/{dossier_id}/insert-evidence")
async def insert_evidence_to_dossier(
    dossier_id: str, req: InsertEvidenceRequest, request: Request,
) -> Dict[str, Any]:
    """§129: POST /api/v1/dossiers/{dossierId}/insert-evidence — Add evidence items to dossier."""
    from sqlalchemy import select

    if not req.evidence_item_ids:
        return _build_dossier_envelope(request, {
            "dossier_id": dossier_id,
            "inserted_count": 0,
            "section": req.section,
        })

    try:
        async with AsyncSessionLocal() as session:
            # Load dossier
            record = await session.get(DossierRecord, dossier_id)
            if not record:
                raise HTTPException(status_code=404, detail="Dossier not found")

            # Fetch requested evidence items
            stmt = select(EvidenceItemRecord).where(
                EvidenceItemRecord.id.in_(req.evidence_item_ids)
            )
            result = await session.execute(stmt)
            evidence_rows = result.scalars().all()

            if not evidence_rows:
                raise HTTPException(status_code=404, detail="No matching evidence items found")

            # Serialize evidence items
            items_to_insert = []
            for ev in evidence_rows:
                items_to_insert.append({
                    "id": ev.id,
                    "source_name": ev.source_name,
                    "source_type": ev.source_type,
                    "title": ev.title,
                    "snippet": ev.snippet,
                    "url": ev.url,
                    "confidence": ev.confidence,
                    "entity_type": ev.entity_type,
                    "retrieved_at": ev.retrieved_at.isoformat() if ev.retrieved_at else None,
                })

            # Append to dossier body_json
            body = dict(record.body_json) if record.body_json else {}
            section_key = req.section
            existing = body.get(section_key, [])
            if not isinstance(existing, list):
                existing = []
            existing.extend(items_to_insert)
            body[section_key] = existing
            record.body_json = body

            await session.commit()

            return _build_dossier_envelope(request, {
                "dossier_id": dossier_id,
                "inserted_count": len(items_to_insert),
                "section": section_key,
                "evidence_ids": [e["id"] for e in items_to_insert],
            })
    except HTTPException:
        raise
    except Exception as e:
        log.error("dossier_insert_evidence_failed", error=str(e), dossier_id=dossier_id)
        raise HTTPException(status_code=500, detail=str(e))
