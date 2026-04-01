"""Translational Workflow & PICO Verification API Routes."""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from services.workflow_engine import WorkflowEngine, TranslationalProject
from services.pico_extractor import extract_pico_data, verify_claim

router = APIRouter(prefix="/api/translational", tags=["Translational Workflow"])


@router.get("/projects", response_model=List[TranslationalProject])
async def list_projects():
    """Returns all active research projects."""
    return WorkflowEngine.list_projects()


class ProjectCreateRequest(BaseModel):
    name: str
    description: str = ""

@router.post("/projects", response_model=TranslationalProject)
async def create_project(req: ProjectCreateRequest):
    """Initializes a new translational research workflow."""
    return WorkflowEngine.create_project(name=req.name, description=req.description)


@router.get("/projects/{project_id}", response_model=TranslationalProject)
async def get_project(project_id: str):
    project = WorkflowEngine.load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/projects/{project_id}/advance", response_model=TranslationalProject)
async def advance_project_stage(project_id: str):
    """Moves the project one stage forward down the pipeline."""
    project = WorkflowEngine.advance_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


class ArtifactCreateRequest(BaseModel):
    artifact_type: str
    content: Dict[str, Any]

@router.post("/projects/{project_id}/artifacts", response_model=TranslationalProject)
async def add_project_artifact(project_id: str, req: ArtifactCreateRequest):
    """Saves distinct research items (PICO extractions, targets) directly to the local workflow container."""
    project = WorkflowEngine.add_artifact(project_id, req.artifact_type, req.content)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/projects/{project_id}/export")
async def export_project_report(project_id: str):
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
        
    return {"markdown_report": "\n".join(lines)}


class ExtractPicoRequest(BaseModel):
    text: str

@router.post("/pico/extract")
async def extract_pico_endpoint(req: ExtractPicoRequest):
    data = await extract_pico_data(req.text)
    return data

class VerifyClaimRequest(BaseModel):
    claim: str
    evidence_text: str

@router.post("/pico/verify")
async def verify_claim_endpoint(req: VerifyClaimRequest):
    """Utilizes local LLM inference models (BioBERT/llama3.1) evaluating raw abstract text against stated researcher logic."""
    data = await verify_claim(req.claim, req.evidence_text)
    return data
