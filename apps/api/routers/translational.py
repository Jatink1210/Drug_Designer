"""Translational Workflow & PICO Verification API Routes."""
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from routers.auth import get_current_user
from pydantic import BaseModel

from services.workflow_engine import WorkflowEngine, TranslationalProject
from models.envelope import build_envelope as _shared_envelope
from services.pico_extractor import extract_pico_data, verify_claim

router = APIRouter(prefix="/api/v1/translational", tags=["Translational Workflow"], dependencies=[Depends(get_current_user)])


@router.get("/projects", response_model=Dict[str, Any])
async def list_projects(request: Request):
    """Returns all active research projects."""
    projects = WorkflowEngine.list_projects()
    return _build_envelope(request, [p.model_dump() for p in projects])


class ProjectCreateRequest(BaseModel):
    name: str
    description: str = ""

@router.post("/projects", response_model=Dict[str, Any])
async def create_project(req: ProjectCreateRequest, request: Request):
    """Initializes a new translational research workflow."""
    project = WorkflowEngine.create_project(name=req.name, description=req.description)
    return _build_envelope(request, project.model_dump())


@router.get("/projects/{project_id}", response_model=Dict[str, Any])
async def get_project(project_id: str, request: Request):
    project = WorkflowEngine.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _build_envelope(request, project.model_dump())


@router.post("/projects/{project_id}/advance", response_model=Dict[str, Any])
async def advance_project_stage(project_id: str, request: Request):
    """Moves the project one stage forward down the pipeline."""
    project = WorkflowEngine.advance_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _build_envelope(request, project.model_dump())


class ArtifactCreateRequest(BaseModel):
    artifact_type: str
    content: Dict[str, Any]

@router.post("/projects/{project_id}/artifacts", response_model=Dict[str, Any])
async def add_project_artifact(project_id: str, req: ArtifactCreateRequest, request: Request):
    """Saves distinct research items (PICO extractions, targets) directly to the local workflow container."""
    project = WorkflowEngine.add_artifact(project_id, req.artifact_type, req.content)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _build_envelope(request, project.model_dump())


@router.get("/projects/{project_id}/export")
async def export_project_report(project_id: str, request: Request):
    """Generates a Markdown executive report summarizing aggregated project findings."""
    project = WorkflowEngine.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    lines = [
        f"# Translational Research Report: {project.name}",
        f"**Description:** {project.description}",
        f"**Current Path:** `{project.current_stage}`",
        f"**Last Updated:** `{project.updated_at}`\n",
        "## Aggregated Evidence Artifacts\n"
    ]
    
    for art in project.artifacts:
        lines.append(f"### Artifact: {art.artifact_type.upper()}")
        lines.append("```json")
        lines.append(repr(art.content))
        lines.append("```\n")
        
    return _build_envelope(request, {"markdown_report": "\n".join(lines)})


class ExtractPicoRequest(BaseModel):
    text: str

@router.post("/pico/extract")
async def extract_pico_endpoint(req: ExtractPicoRequest, request: Request):
    data = await extract_pico_data(req.text)
    return _build_envelope(request, data)

class VerifyClaimRequest(BaseModel):
    claim: str
    evidence_text: str

@router.post("/pico/verify")
async def verify_claim_endpoint(req: VerifyClaimRequest, request: Request):
    """Utilizes local LLM inference models (BioBERT/llama3.1) evaluating raw abstract text against stated researcher logic."""
    data = await verify_claim(req.claim, req.evidence_text)
    return _build_envelope(request, data)
    
def _build_envelope(req: Request, data: Any, warnings: list = None) -> Dict[str, Any]:
    return _shared_envelope(req, data, warnings=warnings)


# ── §127 Spec-Aligned Translational Endpoints ────────────

class TranslationalAnalyzeRequest(BaseModel):
    evidence_text: str = ""
    run_id: str = ""


class TranslationalExportRequest(BaseModel):
    run_id: str = ""
    format: str = "json"


@router.post("/analyze")
async def analyze_translational(req: TranslationalAnalyzeRequest, request: Request):
    """§127: POST /api/v1/translational/analyze — Runs PICO extraction against evidence."""
    import uuid as _uuid
    run_id = req.run_id or str(_uuid.uuid4())
    pico_data = await extract_pico_data(req.evidence_text) if req.evidence_text else {}
    return _build_envelope(request, {"run_id": run_id, "pico": pico_data, "status": "completed"})


@router.get("/run/{run_id}")
async def get_translational_run(run_id: str, request: Request):
    """§127: GET /api/v1/translational/run/{runId} — Get translational run status."""
    from core.db import AsyncSessionLocal
    from models.db_tables import Run
    from sqlalchemy import select
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Run).where(Run.id == run_id))
            run = result.scalar_one_or_none()
            if run:
                return _build_envelope(request, {
                    "run_id": run_id,
                    "status": run.state,
                    "run_type": run.run_type,
                    "elapsed_ms": run.elapsed_ms,
                })
    except Exception:
        pass
    return _build_envelope(request, {"run_id": run_id, "status": "not_found"})


@router.post("/export")
async def export_translational(req: TranslationalExportRequest, request: Request):
    """§127: POST /api/v1/translational/export — Export translational results."""
    import uuid as _uuid
    from core.db import AsyncSessionLocal
    from models.db_tables import ExportRecord
    export_id = str(_uuid.uuid4())
    try:
        async with AsyncSessionLocal() as session:
            record = ExportRecord(id=export_id, run_id=req.run_id, format=req.format, status="rendering")
            session.add(record)
            await session.commit()
    except Exception:
        pass
    return _build_envelope(request, {
        "export_id": export_id,
        "run_id": req.run_id,
        "format": req.format,
        "status": "rendering",
    })
