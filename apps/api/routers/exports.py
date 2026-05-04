"""Export Center — Drug Designer §28, §71.

Multi-format export pipeline: PDF, DOCX, JSON, CSV, SDF, PDB, PNG.
§78: All responses use ResponseEnvelope.
§70: List endpoints use cursor-based pagination.
"""

from __future__ import annotations

import os
import uuid
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog

from models.envelope import build_envelope as _shared_envelope
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.paths import get_data_dir
from models.db_tables import ExportRecord
from routers.auth import get_current_user, User

router = APIRouter(prefix="/api/v1/exports", tags=["Exports"])
log = structlog.get_logger(__name__)


# ── Request Models ───────────────────────────────────────────

class ExportCreateRequest(BaseModel):
    project_id: str
    object_type: str  # evidence | dossier | report | targets | graph | structure
    object_id: str
    export_format: str = "json"  # pdf | docx | json | csv | sdf | pdb | png


# ── Helpers ──────────────────────────────────────────────────

def _build_envelope(req: Request, data: Any, status: str = "ok",
                    warnings: list | None = None) -> Dict[str, Any]:
    return _shared_envelope(req, data, status=status, warnings=warnings)


def _export_to_dict(e: ExportRecord) -> Dict[str, Any]:
    return {
        "id": e.id,
        "project_id": e.project_id,
        "object_type": e.object_type,
        "object_id": e.object_id,
        "export_format": e.export_format,
        "status": e.status,
        "file_ref": e.file_ref,
        "created_by": e.created_by,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def _exports_dir() -> str:
    d = os.path.join(get_data_dir(), "exports")
    os.makedirs(d, exist_ok=True)
    return d


async def _render_export_content(
    db: AsyncSession, object_type: str, object_id: str, fmt: str
) -> Any:
    """Fetch the actual content for an export based on object_type and object_id."""
    if object_type == "dossier":
        from models.db_tables import DossierRecord
        result = await db.execute(select(DossierRecord).where(DossierRecord.id == object_id))
        dossier = result.scalars().first()
        if dossier:
            return {
                "id": dossier.id,
                "project_id": dossier.project_id,
                "title": dossier.title,
                "objective": dossier.objective,
                "status": dossier.status,
                "sections": dossier.sections or [],
                "body_json": dossier.body_json or {},
                "created_at": dossier.created_at.isoformat() if dossier.created_at else None,
            }
    elif object_type == "evidence":
        from models.db_tables import EvidenceItemRecord
        result = await db.execute(
            select(EvidenceItemRecord).where(EvidenceItemRecord.id == object_id)
        )
        item = result.scalars().first()
        if item:
            return {
                "id": item.id,
                "source_name": item.source_name,
                "source_family": item.source_family,
                "title": item.title,
                "snippet": item.snippet,
                "url": item.url,
                "confidence": item.confidence,
                "content": item.content or {},
            }
    elif object_type == "report":
        from models.db_tables import DossierRecord
        result = await db.execute(select(DossierRecord).where(DossierRecord.id == object_id))
        report = result.scalars().first()
        if report:
            return {"id": report.id, "title": report.title, "body_json": report.body_json or {}}

    # Fallback: return a metadata dict
    return {"object_type": object_type, "object_id": object_id, "note": "object not found or unsupported type"}


# ── Endpoints (§71 Export Pipeline) ──────────────────────────

@router.post("")
async def create_export(
    req: ExportCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """§71: Create an export job. Renders the resource in the requested format."""
    allowed_formats = {"pdf", "docx", "json", "csv", "sdf", "pdb", "png"}
    if req.export_format not in allowed_formats:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {req.export_format}. Allowed: {allowed_formats}")

    export = ExportRecord(
        id=str(uuid.uuid4()),
        project_id=req.project_id,
        object_type=req.object_type,
        object_id=req.object_id,
        export_format=req.export_format,
        status="pending",
        created_by=current_user.id,
    )
    db.add(export)
    await db.commit()
    await db.refresh(export)

    # A-8: audit log — data export
    try:
        from core.audit import log_audit
        await log_audit(
            db, user_id=str(current_user.id),
            action="data.export",
            resource_type="exports",
            resource_id=export.id,
            details={
                "object_type": req.object_type,
                "object_id": req.object_id,
                "export_format": req.export_format,
            },
        )
        await db.commit()
    except Exception:
        pass  # audit failure must not block export creation

    # For JSON/CSV, render immediately; PDF/DOCX dispatched to worker
    if req.export_format in ("json", "csv"):
        export.status = "ready"
        file_name = f"{export.id}.{req.export_format}"
        file_path = os.path.join(_exports_dir(), file_name)
        rendered = await _render_export_content(db, req.object_type, req.object_id, req.export_format)
        import json as json_mod
        with open(file_path, "w") as f:
            if req.export_format == "json":
                json_mod.dump(rendered, f, indent=2, default=str)
            else:
                # CSV rendering
                import csv as csv_mod
                import io
                buf = io.StringIO()
                if isinstance(rendered, list) and rendered:
                    writer = csv_mod.DictWriter(buf, fieldnames=rendered[0].keys())
                    writer.writeheader()
                    writer.writerows(rendered)
                elif isinstance(rendered, dict):
                    writer = csv_mod.DictWriter(buf, fieldnames=rendered.keys())
                    writer.writeheader()
                    writer.writerow(rendered)
                f.write(buf.getvalue())
        export.file_ref = file_path
        await db.commit()
    elif req.export_format == "pdf":
        # Render PDF using PDFDossierExporter
        try:
            rendered = await _render_export_content(db, req.object_type, req.object_id, "json")
            file_name = f"{export.id}.pdf"
            file_path = os.path.join(_exports_dir(), file_name)
            
            from services.exports.pdf_exporter import PDFDossierExporter
            
            # Prepare dossier data
            dossier_data = {
                "subtitle": f"{req.object_type.title()} Export",
                "date": datetime.now(timezone.utc).strftime("%B %d, %Y"),
                "sections": [],
                "consensus_traces": [],
                "evidence_records": []
            }
            
            # Extract sections from rendered data
            if isinstance(rendered, dict):
                # Add main content section
                dossier_data["sections"].append({
                    "title": f"{req.object_type.title()} Details",
                    "content": json.dumps(rendered, indent=2, default=str),
                    "level": 1,
                    "tables": []
                })
                
                # Extract MAV consensus traces if present
                if "consensus_traces" in rendered:
                    dossier_data["consensus_traces"] = rendered["consensus_traces"]
                
                # Extract evidence records if present
                if "evidence" in rendered:
                    evidence_list = rendered["evidence"]
                    if isinstance(evidence_list, list):
                        dossier_data["evidence_records"] = evidence_list
            
            # Generate PDF
            pdf_exporter = PDFDossierExporter(
                output_path=file_path,
                title=f"{req.object_type.title()} - {req.object_id}",
                author="Drug Designer System"
            )
            pdf_exporter.export_dossier(dossier_data)
            
            export.file_ref = file_path
            export.status = "ready"
        except Exception as exc:
            log.warning("pdf_render_failed", error=str(exc))
            export.status = "failed"
        await db.commit()
    elif req.export_format == "docx":
        # Render DOCX immediately using DOCXReportExporter
        try:
            rendered = await _render_export_content(db, req.object_type, req.object_id, "json")
            file_name = f"{export.id}.docx"
            file_path = os.path.join(_exports_dir(), file_name)
            
            from services.exports.docx_exporter import DOCXReportExporter
            
            # Prepare report data
            report_data = {
                "subtitle": f"{req.object_type.title()} Report",
                "date": datetime.now(timezone.utc).strftime("%B %d, %Y"),
                "sections": []
            }
            
            # Convert rendered content to sections
            if isinstance(rendered, dict):
                # Handle dossier format
                if "title" in rendered:
                    report_data["subtitle"] = rendered["title"]
                
                if "sections" in rendered and isinstance(rendered["sections"], list):
                    for section in rendered["sections"]:
                        if isinstance(section, dict):
                            report_data["sections"].append({
                                "title": section.get("title", "Section"),
                                "content": section.get("content", ""),
                                "level": 1
                            })
                
                # Handle body_json format
                if "body_json" in rendered and isinstance(rendered["body_json"], dict):
                    body = rendered["body_json"]
                    for key, value in body.items():
                        if isinstance(value, str):
                            report_data["sections"].append({
                                "title": key.replace("_", " ").title(),
                                "content": value,
                                "level": 1
                            })
                        elif isinstance(value, dict):
                            content = "\n\n".join(f"{k}: {v}" for k, v in value.items())
                            report_data["sections"].append({
                                "title": key.replace("_", " ").title(),
                                "content": content,
                                "level": 1
                            })
                
                # If no sections found, create a single section with all data
                if not report_data["sections"]:
                    import json as json_mod
                    report_data["sections"].append({
                        "title": "Data",
                        "content": json_mod.dumps(rendered, indent=2, default=str),
                        "level": 1
                    })
            
            # Generate DOCX
            exporter = DOCXReportExporter(
                output_path=file_path,
                title=report_data.get("subtitle", "Report"),
                author="Drug Designer System"
            )
            exporter.export_report(report_data)
            
            export.file_ref = file_path
            export.status = "ready"
            log.info("docx_render_complete", export_id=export.id)
        except Exception as exc:
            log.warning("docx_render_failed", error=str(exc), export_id=export.id)
            export.status = "failed"
        await db.commit()
    elif req.export_format == "sdf":
        # Render SDF immediately using SDFMoleculeExporter
        try:
            rendered = await _render_export_content(db, req.object_type, req.object_id, "json")
            file_name = f"{export.id}.sdf"
            file_path = os.path.join(_exports_dir(), file_name)
            
            from services.exports.sdf_exporter import SDFMoleculeExporter
            
            # Prepare molecules list
            molecules = []
            
            if isinstance(rendered, dict):
                # Handle single molecule
                if 'smiles' in rendered or 'mol_block' in rendered:
                    molecules.append(rendered)
                # Handle molecule list
                elif 'molecules' in rendered and isinstance(rendered['molecules'], list):
                    molecules = rendered['molecules']
                # Handle dossier with molecules
                elif 'body_json' in rendered and isinstance(rendered['body_json'], dict):
                    body = rendered['body_json']
                    if 'molecules' in body and isinstance(body['molecules'], list):
                        molecules = body['molecules']
            elif isinstance(rendered, list):
                # Handle list of molecules
                molecules = rendered
            
            if not molecules:
                log.warning("no_molecules_found", export_id=export.id)
                export.status = "failed"
            else:
                # Generate SDF
                exporter = SDFMoleculeExporter(output_path=file_path)
                exporter.export_molecules(molecules)
                
                export.file_ref = file_path
                export.status = "ready"
                log.info("sdf_render_complete", export_id=export.id, num_molecules=len(molecules))
        except Exception as exc:
            log.warning("sdf_render_failed", error=str(exc), export_id=export.id)
            export.status = "failed"
        await db.commit()
    else:
        # For PDB/PNG — dispatch to worker queue
        export.status = "rendering"
        await db.commit()
        try:
            from worker import enqueue_job
            await enqueue_job(
                request.app.state,
                "render_export",
                export.id,
                req.object_type,
                req.object_id,
                req.export_format,
                queue_name="exports",
            )
        except Exception as exc:
            log.warning("export_worker_dispatch_failed", error=str(exc))

    from core.audit import log_audit
    await log_audit(db, user_id=current_user.id, action="export.create", resource_type="export", resource_id=export.id, details={"format": req.export_format, "object_type": req.object_type}, ip_address=request.client.host if request.client else None)
    await db.commit()

    log.info("export_created", export_id=export.id, format=req.export_format)
    return _build_envelope(request, _export_to_dict(export))


@router.get("")
async def list_exports(
    request: Request,
    project_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """§71: List exports for a project. Cursor-based pagination (§70)."""
    q = select(ExportRecord).order_by(desc(ExportRecord.created_at))
    if project_id:
        q = q.where(ExportRecord.project_id == project_id)
    if cursor:
        q = q.where(ExportRecord.created_at < cursor)
    q = q.limit(limit + 1)

    result = await db.execute(q)
    rows = result.scalars().all()
    has_more = len(rows) > limit
    exports = [_export_to_dict(e) for e in rows[:limit]]

    return _build_envelope(request, {
        "exports": exports,
        "pagination": {
            "cursor": exports[-1]["created_at"] if exports and has_more else None,
            "has_more": has_more,
            "page_size": limit,
        },
    })


@router.get("/{export_id}")
async def get_export(
    export_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """§71: Get export status and metadata."""
    result = await db.execute(select(ExportRecord).where(ExportRecord.id == export_id))
    export = result.scalars().first()
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")
    return _build_envelope(request, _export_to_dict(export))


@router.get("/{export_id}/download")
async def download_export(
    export_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """§71: Download the rendered export file."""
    result = await db.execute(select(ExportRecord).where(ExportRecord.id == export_id))
    export = result.scalars().first()
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")
    if export.status != "ready":
        raise HTTPException(status_code=409, detail=f"Export not ready (status: {export.status})")
    if not export.file_ref or not os.path.exists(export.file_ref):
        raise HTTPException(status_code=404, detail="Export file not found on disk")

    media_types = {
        "json": "application/json",
        "csv": "text/csv",
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "sdf": "chemical/x-mdl-sdfile",
        "pdb": "chemical/x-pdb",
        "png": "image/png",
        "zip": "application/zip",
    }
    return FileResponse(
        path=export.file_ref,
        media_type=media_types.get(export.export_format, "application/octet-stream"),
        filename=f"export_{export.id}.{export.export_format}",
    )


@router.post("/bulk")
async def create_bulk_export(
    project_id: str,
    request: Request,
    include_raw_data: bool = Query(True),
    include_dossiers: bool = Query(True),
    include_molecules: bool = Query(True),
    include_provenance: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """§71: Create bulk project export as ZIP archive."""
    # Create export record
    export = ExportRecord(
        id=str(uuid.uuid4()),
        project_id=project_id,
        object_type="project",
        object_id=project_id,
        export_format="zip",
        status="pending",
        created_by=current_user.id,
    )
    db.add(export)
    await db.commit()
    await db.refresh(export)
    
    try:
        # Fetch project data
        from models.db_tables import ProjectRecord, DossierRecord, MoleculeCandidateRecord
        
        # Get project
        project_result = await db.execute(
            select(ProjectRecord).where(ProjectRecord.id == project_id)
        )
        project = project_result.scalars().first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Prepare project data
        project_data = {
            "name": project.name,
            "description": project.description,
            "created_at": project.created_at.isoformat() if project.created_at else None,
            "updated_at": project.updated_at.isoformat() if project.updated_at else None,
        }
        
        # Get dossiers
        if include_dossiers:
            dossiers_result = await db.execute(
                select(DossierRecord).where(DossierRecord.project_id == project_id)
            )
            dossiers = dossiers_result.scalars().all()
            project_data["dossiers"] = [
                {
                    "id": d.id,
                    "title": d.title,
                    "metadata": {
                        "objective": d.objective,
                        "status": d.status,
                        "created_at": d.created_at.isoformat() if d.created_at else None,
                    }
                }
                for d in dossiers
            ]
        
        # Get molecules
        if include_molecules:
            molecules_result = await db.execute(
                select(MoleculeCandidateRecord).where(MoleculeCandidateRecord.project_id == project_id)
            )
            molecules = molecules_result.scalars().all()
            project_data["molecules"] = [
                {
                    "id": m.id,
                    "name": m.name,
                    "smiles": m.smiles,
                    "properties": {
                        "molecular_weight": m.molecular_weight,
                        "logp": m.logp,
                        "hbd": m.hbd,
                        "hba": m.hba,
                        "tpsa": m.tpsa,
                    }
                }
                for m in molecules
            ]
        
        # Get raw data
        if include_raw_data:
            project_data["raw_data"] = {
                "project_metadata": {
                    "id": project.id,
                    "name": project.name,
                    "description": project.description,
                }
            }
        
        # Get provenance
        if include_provenance:
            from models.db_tables import ProvenanceRecord
            provenance_result = await db.execute(
                select(ProvenanceRecord).where(ProvenanceRecord.project_id == project_id)
            )
            provenance_records = provenance_result.scalars().all()
            project_data["provenance"] = {
                "evidence_records": [
                    {
                        "id": p.id,
                        "action": p.action,
                        "timestamp": p.timestamp.isoformat() if p.timestamp else None,
                        "details": p.details or {},
                    }
                    for p in provenance_records
                ]
            }
        
        # Generate ZIP
        file_name = f"{export.id}.zip"
        file_path = os.path.join(_exports_dir(), file_name)
        
        from services.exports.bulk_exporter import BulkProjectExporter
        exporter = BulkProjectExporter(
            output_path=file_path,
            project_id=project_id
        )
        exporter.export_project(
            project_data=project_data,
            include_raw_data=include_raw_data,
            include_dossiers=include_dossiers,
            include_molecules=include_molecules,
            include_provenance=include_provenance
        )
        
        export.file_ref = file_path
        export.status = "ready"
        log.info("bulk_export_complete", export_id=export.id, project_id=project_id)
        
    except Exception as exc:
        log.warning("bulk_export_failed", error=str(exc), export_id=export.id)
        export.status = "failed"
    
    await db.commit()
    
    from core.audit import log_audit
    await log_audit(
        db,
        user_id=current_user.id,
        action="export.bulk",
        resource_type="project",
        resource_id=project_id,
        details={"export_id": export.id},
        ip_address=request.client.host if request.client else None
    )
    await db.commit()
    
    return _build_envelope(request, _export_to_dict(export))
