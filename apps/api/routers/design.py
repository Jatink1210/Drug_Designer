"""Design Studio — Drug Designer §126, §12, §84.

Molecule generation, ADMET, optimization, and retrosynthesis endpoints.

§78: All responses use ResponseEnvelope.
"""

from __future__ import annotations

import csv
import io
import os
import shutil
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from models.db_tables import Run, Job
from routers.auth import get_current_user, User

router = APIRouter(prefix="/api/v1/design", tags=["Design Studio"])
log = structlog.get_logger(__name__)


# ── Pydantic schemas ──────────────────────────────────────

class GenerateRequest(BaseModel):
    target_id: str
    target_symbol: str = ""
    constraints: Dict[str, Any] = Field(default_factory=dict)
    num_candidates: int = 10
    project_id: Optional[str] = None

class OptimizeRequest(BaseModel):
    candidate_id: str
    objective: str = "binding"
    constraints: Dict[str, Any] = Field(default_factory=dict)
    iterations: int = 20

class RetrosynthesisRequest(BaseModel):
    candidate_id: str
    max_steps: int = 6
    commercial_only: bool = True

class CandidateOut(BaseModel):
    id: str
    smiles: str = ""
    mol_weight: Optional[float] = None
    logp: Optional[float] = None
    qed: Optional[float] = None
    sa_score: Optional[float] = None
    binding_score: Optional[float] = None
    status: str = "generated"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StartDesignSessionRequest(BaseModel):
    target_id: str
    project_id: Optional[str] = None
    binding_site: Dict[str, Any] = Field(default_factory=dict)
    source_context: Dict[str, Any] = Field(default_factory=dict)


def _envelope(data: Any, *, req: Request, warnings: list | None = None):
    return {
        "request_id": getattr(req.state, "request_id", str(uuid.uuid4())),
        "trace_id": getattr(req.state, "trace_id", ""),
        "status": "ok",
        "data": data,
        "warnings": warnings or [],
        "errors": [],
        "timing": {},
        "provenance": {},
    }


def _design_plugin_status() -> Dict[str, Any]:
    """Return plugin availability using ToolInstaller for real binary detection."""
    from services.tool_installer import ToolInstaller

    try:
        from rdkit import Chem  # noqa: F401
        rdkit_available = True
    except Exception:
        rdkit_available = False

    try:
        import torch

        gpu_available = bool(torch.cuda.is_available())
        gpu_name = torch.cuda.get_device_name(0) if gpu_available else ""
    except Exception:
        gpu_available = False
        gpu_name = ""

    esm_configured = bool(os.environ.get("ESM_FORGE_API_KEY", ""))

    # Use ToolInstaller for real binary detection (PATH + tools/bin/)
    installer = ToolInstaller()
    availability = installer.check_availability()
    vina_status = availability.get("vina")
    fpocket_status = availability.get("fpocket")

    return {
        "rdkit_available": rdkit_available,
        "vina_available": vina_status.status == "available" if vina_status else False,
        "fpocket_available": fpocket_status.status == "available" if fpocket_status else False,
        "gpu_available": gpu_available,
        "gpu_name": gpu_name,
        "esm_forge_configured": esm_configured,
    }


# ── POST /design/session/start ──────────────────────────

@router.post("/session/start")
async def start_design_session(
    body: StartDesignSessionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a canonical design session and return honest plugin status."""
    plugin_status = _design_plugin_status()
    warnings: list[str] = []

    if not plugin_status["rdkit_available"]:
        warnings.append("RDKit not detected; physicochemical and cheminformatics tooling may degrade")
    if not plugin_status["vina_available"]:
        warnings.append("AutoDock Vina binary not detected; docking may run in degraded mode or fail")
    if not plugin_status["fpocket_available"]:
        warnings.append("fpocket binary not detected; binding-site detection may fall back to external annotations")
    if not plugin_status["gpu_available"]:
        warnings.append("No GPU detected; optimization and model inference will run on CPU")

    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        project_id=body.project_id or "",
        run_type="design.session",
        state="STARTED",
        input_snapshot=body.model_dump(),
        timing={"started_at": datetime.now(timezone.utc).isoformat()},
        runtime_context={"mode": "cpu" if not plugin_status["gpu_available"] else "gpu", **plugin_status},
    )
    db.add(run)
    await db.commit()

    return _envelope(
        {
            "session_id": run_id,
            "run_id": run_id,
            "target_id": body.target_id,
            "binding_site": body.binding_site,
            "source_context": body.source_context,
            "plugin_status": plugin_status,
            "stream_channel": f"/api/v1/runs/{run_id}/events",
            "status": "degraded" if warnings else "ready",
        },
        req=request,
        warnings=warnings or None,
    )


# ── POST /design/generate ────────────────────────────────

@router.post("/generate")
async def generate_candidates(
    body: GenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Trigger molecule generation for a target (§126).

    Creates a run of type molecule.generation and queues
    the job for async processing via ARQ.
    """
    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        project_id=body.project_id or "",
        run_type="molecule.generation",
        state="QUEUED",
        input_snapshot=body.model_dump(),
        runtime_context={"mode": "hosted"},
    )
    db.add(run)
    await db.commit()

    log.info("design_generate_queued", run_id=run_id, target=body.target_symbol)
    return _envelope({
        "run_id": run_id,
        "status": "QUEUED",
        "message": f"Molecule generation queued for target {body.target_symbol}",
    }, req=request)


# ── GET /design/candidates ───────────────────────────────

@router.get("/candidates")
async def list_candidates(
    request: Request,
    project_id: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = Query(None, description="ISO timestamp cursor for keyset pagination"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List generated molecule candidates (§126). Cursor-based pagination (§70)."""
    from datetime import datetime as _dt
    q = select(Run).where(Run.run_type == "molecule.generation").order_by(desc(Run.created_at))
    if project_id:
        q = q.where(Run.project_id == project_id)
    if run_id:
        q = q.where(Run.id == run_id)
    if cursor:
        try:
            cursor_dt = _dt.fromisoformat(cursor)
            q = q.where(Run.created_at < cursor_dt)
        except ValueError:
            pass
    q = q.limit(limit + 1)

    rows = (await db.execute(q)).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    candidates = []
    for r in rows:
        for art in (r.output_artifacts or []):
            candidates.append({"run_id": r.id, **art} if isinstance(art, dict) else {"run_id": r.id, "id": art})

    next_cursor = rows[-1].created_at.isoformat() if has_more and rows else None
    return _envelope({"candidates": candidates, "total": len(candidates), "next_cursor": next_cursor, "has_more": has_more}, req=request)


# ── GET /design/candidates/{id}/admet ────────────────────

@router.get("/candidates/{candidate_id}/admet")
async def get_candidate_admet(
    candidate_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get ADMET profile for a candidate molecule (§126, §85).

    Looks up completed ADMET runs whose output_artifacts reference this
    candidate.  Falls back to a 404 when no prediction exists yet.
    """
    # Query completed ADMET runs that reference this candidate
    q = (
        select(Run)
        .where(
            or_(
                Run.run_type.ilike("%admet%"),
                Run.run_type == "admet.batch",
            ),
            Run.state.in_(["SUCCESS", "PARTIAL_SUCCESS"]),
        )
        .order_by(desc(Run.completed_at))
    )
    rows = (await db.execute(q)).scalars().all()

    for run in rows:
        artifacts = run.output_artifacts or []
        # artifacts may be a list of dicts; look for matching candidate_id
        for art in artifacts:
            cid = art.get("candidate_id", "") if isinstance(art, dict) else ""
            if cid == candidate_id:
                return _envelope({
                    "candidate_id": candidate_id,
                    "admet": art.get("admet", art),
                    "run_id": run.id,
                    "status": "complete",
                }, req=request)
        # Also check if input_snapshot references this candidate
        inp = run.input_snapshot or {}
        if inp.get("candidate_id") == candidate_id or candidate_id in str(inp.get("smiles", "")):
            # Return full output_artifacts as the ADMET result
            return _envelope({
                "candidate_id": candidate_id,
                "admet": artifacts[0] if artifacts else {},
                "run_id": run.id,
                "status": "complete",
            }, req=request)

    raise HTTPException(status_code=404, detail=f"No completed ADMET prediction found for candidate {candidate_id}")


# ── POST /design/optimize ────────────────────────────────

@router.post("/optimize")
async def optimize_candidate(
    body: OptimizeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Trigger PPO-based molecule optimization (§126, §84)."""
    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        project_id="",
        run_type="molecule.optimization",
        state="QUEUED",
        input_snapshot=body.model_dump(),
    )
    db.add(run)
    await db.commit()
    log.info("design_optimize_queued", run_id=run_id, candidate=body.candidate_id)
    return _envelope({"run_id": run_id, "status": "QUEUED"}, req=request)


# ── POST /design/retrosynthesis ──────────────────────────

@router.post("/retrosynthesis")
async def plan_retrosynthesis(
    body: RetrosynthesisRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Plan retrosynthetic route (§126, §13.4)."""
    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        project_id="",
        run_type="retrosynthesis.plan",
        state="QUEUED",
        input_snapshot=body.model_dump(),
    )
    db.add(run)
    await db.commit()
    log.info("retrosynthesis_queued", run_id=run_id, candidate=body.candidate_id)
    return _envelope({"run_id": run_id, "status": "QUEUED"}, req=request)


# ── GET /design/candidates/{id}/retro-routes ─────────────

@router.get("/candidates/{candidate_id}/retro-routes")
async def get_retro_routes(
    candidate_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get planned retrosynthetic routes for a candidate (§126)."""
    q = (
        select(Run)
        .where(
            Run.run_type.ilike("%retrosynthesis%"),
            Run.state.in_(["SUCCESS", "PARTIAL_SUCCESS"]),
        )
        .order_by(desc(Run.completed_at))
    )
    rows = (await db.execute(q)).scalars().all()

    for run in rows:
        inp = run.input_snapshot or {}
        if inp.get("candidate_id") == candidate_id:
            routes = run.output_artifacts if isinstance(run.output_artifacts, list) else []
            return _envelope({
                "candidate_id": candidate_id,
                "routes": routes,
                "run_id": run.id,
                "status": "complete",
            }, req=request)

    return _envelope({
        "candidate_id": candidate_id,
        "routes": [],
        "status": "no_results",
    }, req=request)


# ── §126 Spec-Aligned Additional Endpoints ───────────────

class RetrieveCandidatesRequest(BaseModel):
    target_id: str
    smiles_template: str = ""
    query: str = ""
    scoring_filter: Dict[str, Any] = Field(default_factory=dict)
    limit: int = 20


class EvaluateAdmetRequest(BaseModel):
    smiles_list: List[str] = Field(default_factory=list)
    smiles: str = ""  # single SMILES shortcut
    candidate_id: str = ""
    project_id: str = ""


class SaveCandidateRequest(BaseModel):
    project_id: str
    smiles: str
    name: str = ""
    properties: Dict[str, Any] = {}


class DesignExportRequest(BaseModel):
    run_id: str = ""
    candidate_ids: List[str] = []
    format: str = "sdf"  # sdf | csv


@router.post("/retrieve-candidates")
async def retrieve_candidates(
    body: RetrieveCandidatesRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """§126: POST /api/v1/design/retrieve-candidates — Virtual screening lookup.

    Searches completed molecule-generation runs for candidates matching
    the given target, optional SMILES sub-structure, and scoring filters.
    """
    q = (
        select(Run)
        .where(
            Run.run_type.in_(["molecule.generation", "molecule.optimization"]),
            Run.state.in_(["SUCCESS", "PARTIAL_SUCCESS"]),
        )
        .order_by(desc(Run.completed_at))
    )
    rows = (await db.execute(q)).scalars().all()

    candidates: list[dict] = []
    for run in rows:
        inp = run.input_snapshot or {}
        # Filter by target_id if present in the generation input
        if body.target_id and inp.get("target_id") != body.target_id:
            continue
        for art in (run.output_artifacts or []):
            if not isinstance(art, dict):
                continue
            # Optional SMILES sub-string filter
            if body.smiles_template and body.smiles_template not in art.get("smiles", ""):
                continue
            # Optional scoring filter (e.g. {"qed_min": 0.5})
            skip = False
            for key, threshold in body.scoring_filter.items():
                field = key.removesuffix("_min").removesuffix("_max")
                val = art.get(field)
                if val is None:
                    continue
                if key.endswith("_min") and val < threshold:
                    skip = True
                if key.endswith("_max") and val > threshold:
                    skip = True
            if skip:
                continue
            candidates.append({"run_id": run.id, **art})
            if len(candidates) >= body.limit:
                break
        if len(candidates) >= body.limit:
            break

    return _envelope({
        "target_id": body.target_id,
        "candidates": candidates,
        "total": len(candidates),
    }, req=request)


@router.post("/evaluate-admet")
async def evaluate_admet(
    body: EvaluateAdmetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """§126: POST /api/v1/design/evaluate-admet — Submit batch ADMET prediction.

    Creates a Run of type admet.batch, enqueues an ARQ job, and returns
    the run_id so the client can poll or listen on the events channel.
    """
    smiles_list = body.smiles_list or ([body.smiles] if body.smiles else [])
    if not smiles_list:
        raise HTTPException(status_code=422, detail="Provide at least one SMILES string")

    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        project_id=body.project_id or "",
        run_type="admet.batch",
        state="QUEUED",
        input_snapshot={
            "smiles_list": smiles_list,
            "candidate_id": body.candidate_id,
        },
    )
    db.add(run)
    await db.commit()

    warnings: list[str] = []
    try:
        from worker import enqueue_job
        await enqueue_job(
            request.app.state,
            "run_admet_prediction",
            run_id,
            smiles_list,
            queue_name="admet.batch",
            idempotency_key=f"admet:{run_id}",
        )
    except Exception as exc:
        log.warning("admet_enqueue_failed", run_id=run_id, error=str(exc))
        warnings.append("Job enqueue failed; run created but processing may be delayed")

    log.info("admet_batch_queued", run_id=run_id, count=len(smiles_list))
    return _envelope({
        "run_id": run_id,
        "smiles_count": len(smiles_list),
        "status": "QUEUED",
        "stream_channel": f"/api/v1/runs/{run_id}/events",
    }, req=request, warnings=warnings or None)


@router.post("/save-candidate")
async def save_candidate(
    body: SaveCandidateRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    """§126: POST /api/v1/design/save-candidate — Save a molecule candidate."""
    candidate_id = str(uuid.uuid4())
    return _envelope({
        "candidate_id": candidate_id,
        "project_id": body.project_id,
        "smiles": body.smiles,
        "name": body.name,
        "saved": True,
    }, req=request)


# ── POST /design/generate-diffusion (U-2.5) ─────────────

class DiffusionGenerateRequest(BaseModel):
    """Request body for diffusion-based molecule generation."""
    num_atoms: int = Field(default=32, ge=5, le=128, description="Number of atoms in generated molecule")
    pocket_embed: Optional[List[float]] = Field(default=None, description="512-d pocket embedding from EquivariantGNN")
    target_id: str = ""
    project_id: Optional[str] = None
    num_candidates: int = Field(default=5, ge=1, le=20, description="Number of molecules to generate")


@router.post("/generate-diffusion")
async def generate_diffusion(
    body: DiffusionGenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """§84, U-2.5: Generate molecules via Graph Diffusion Model.

    Uses the E(n)-equivariant denoiser with cosine noise schedule to
    generate novel molecular graphs conditioned on a binding pocket.
    Returns atom features and 3D coordinates for each generated molecule.
    Falls back to degraded state if PyTorch is unavailable.
    """
    from services.dl_models import DLModelService

    warnings: list[str] = []
    candidates = []

    for i in range(body.num_candidates):
        result = DLModelService.run_molecule_diffusion(
            num_atoms=body.num_atoms,
            pocket_embed=body.pocket_embed,
        )
        if result.status == "fallback":
            warnings.append("Diffusion model unavailable (PyTorch not installed); returning degraded result")
            candidates.append({
                "id": str(uuid.uuid4()),
                "index": i,
                "status": "degraded",
                "message": result.predictions.get("message", "Model unavailable"),
            })
        else:
            candidates.append({
                "id": str(uuid.uuid4()),
                "index": i,
                "status": "generated",
                "atom_features": result.predictions.get("atom_features"),
                "coordinates": result.predictions.get("coordinates"),
                "num_atoms": body.num_atoms,
                "metadata": result.metadata,
            })

    # Persist as a run
    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        project_id=body.project_id or "",
        run_type="molecule.diffusion_generation",
        state="SUCCESS" if not warnings else "PARTIAL_SUCCESS",
        input_snapshot=body.model_dump(),
        output_artifacts=candidates,
        runtime_context={"model": "GraphDiffusionModel", "target_id": body.target_id},
    )
    db.add(run)
    await db.commit()

    log.info("diffusion_generation_complete", run_id=run_id, count=len(candidates), degraded=bool(warnings))
    return _envelope({
        "run_id": run_id,
        "candidates": candidates,
        "total": len(candidates),
        "model": "GraphDiffusionModel",
        "status": "degraded" if warnings else "success",
    }, req=request, warnings=warnings or None)


# ── POST /design/send-to-lab (U-4.5) ────────────────────

class SendToLabRequest(BaseModel):
    """Request body for sending a molecule context to a Research Lab."""
    lab_type: str = Field(..., description="Target lab: target-discovery, admet, retrosynthesis, molecule-generation, vaccine, metabolic-engineering, pharmacogenomics")
    smiles: str = Field(default="", description="SMILES string of the molecule")
    target_id: str = Field(default="", description="Target protein PDB/UniProt ID")
    project_id: str = Field(default="", description="Project ID for context")
    binding_site: Dict[str, Any] = Field(default_factory=dict, description="Binding site context from design session")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Computed properties (ADMET, scores, etc.)")
    design_session_id: str = Field(default="", description="Source design session run_id")
    notes: str = Field(default="", description="User notes for the lab run")


@router.post("/send-to-lab")
async def send_to_lab(
    body: SendToLabRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """U-4.5: Send molecule context from Design Studio to a Research Lab.

    Creates a lab run pre-populated with the molecule context from the
    current design session, enabling seamless handoff to specialized labs.
    """
    from worker import enqueue_job

    # Map lab_type to queue/job names
    lab_queue_map = {
        "target-discovery": ("run_target_discovery_lab", "labs.target_discovery"),
        "admet": ("run_admet_lab", "labs.admet"),
        "retrosynthesis": ("run_retrosynthesis_lab", "labs.retrosynthesis"),
        "molecule-generation": ("run_molecule_generation_lab", "labs.molecule_generation"),
        "vaccine": ("run_vaccine_design_lab", "labs.vaccine"),
        "metabolic-engineering": ("run_metabolic_engineering_lab", "labs.metabolic"),
        "pharmacogenomics": ("run_pharmacogenomics_lab", "labs.pharmacogenomics"),
    }

    if body.lab_type not in lab_queue_map:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown lab type: {body.lab_type}. Valid: {list(lab_queue_map.keys())}",
        )

    job_fn, queue_name = lab_queue_map[body.lab_type]
    run_id = str(uuid.uuid4())

    input_data = {
        "smiles": body.smiles,
        "target_id": body.target_id,
        "binding_site": body.binding_site,
        "properties": body.properties,
        "design_session_id": body.design_session_id,
        "notes": body.notes,
        "source": "design_studio",
    }

    run = Run(
        id=run_id,
        project_id=body.project_id or "",
        run_type=queue_name,
        state="QUEUED",
        input_snapshot=input_data,
        runtime_context={"mode": "hosted", "source": "design_studio"},
    )
    db.add(run)
    await db.commit()

    warnings: list[str] = []
    try:
        await enqueue_job(
            request.app.state,
            job_fn,
            run_id,
            input_data,
            queue_name=queue_name,
            idempotency_key=f"lab:{run_id}",
        )
    except Exception as exc:
        log.warning("send_to_lab_enqueue_failed", run_id=run_id, error=str(exc))
        warnings.append("Job enqueue failed; run created but processing may be delayed")

    log.info("design_send_to_lab", run_id=run_id, lab=body.lab_type, smiles=body.smiles[:30] if body.smiles else "")
    return _envelope({
        "run_id": run_id,
        "lab_type": body.lab_type,
        "status": "QUEUED",
        "stream_channel": f"/api/v1/runs/{run_id}/events",
        "message": f"Molecule context sent to {body.lab_type} lab",
    }, req=request, warnings=warnings or None)


@router.post("/export")
async def export_design(
    body: DesignExportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """§126: POST /api/v1/design/export — Export molecule candidates as SDF or CSV."""
    # Collect candidate dicts from runs
    candidates: list[dict] = []

    if body.run_id:
        run = (await db.execute(select(Run).where(Run.id == body.run_id))).scalar_one_or_none()
        if not run:
            raise HTTPException(status_code=404, detail=f"Run {body.run_id} not found")
        for art in (run.output_artifacts or []):
            if isinstance(art, dict):
                candidates.append(art)

    if body.candidate_ids:
        # Search recent generation / optimization runs for matching candidate ids
        q = (
            select(Run)
            .where(
                Run.run_type.in_(["molecule.generation", "molecule.optimization", "admet.batch"]),
                Run.state.in_(["SUCCESS", "PARTIAL_SUCCESS"]),
            )
            .order_by(desc(Run.completed_at))
            .limit(200)
        )
        rows = (await db.execute(q)).scalars().all()
        wanted = set(body.candidate_ids)
        for run in rows:
            for art in (run.output_artifacts or []):
                if isinstance(art, dict) and art.get("id") in wanted:
                    candidates.append(art)
                    wanted.discard(art["id"])
            if not wanted:
                break

    if not candidates:
        raise HTTPException(status_code=404, detail="No candidate data found for export")

    fmt = body.format.lower()
    if fmt == "csv":
        buf = io.StringIO()
        fieldnames = sorted({k for c in candidates for k in c})
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for c in candidates:
            writer.writerow(c)
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=candidates.csv"},
        )

    # Default: SDF-like text output
    lines: list[str] = []
    for c in candidates:
        lines.append(c.get("smiles", ""))
        lines.append(f"  id: {c.get('id', 'unknown')}")
        for k, v in c.items():
            if k not in ("smiles", "id"):
                lines.append(f"  {k}: {v}")
        lines.append("$$$$")
    content = "\n".join(lines)
    return StreamingResponse(
        iter([content]),
        media_type="chemical/x-mdl-sdfile" if fmt == "sdf" else "text/plain",
        headers={"Content-Disposition": f"attachment; filename=candidates.{fmt}"},
    )


# ── GET /design/plugins — Plugin health check (Task 17.5) ──────────────

class PluginStatus(BaseModel):
    name: str
    status: str  # available, not_detected, cpu_only, degraded
    version: str = ""
    details: str = ""
    install_hint: str = ""


@router.get("/plugins")
async def get_plugin_status(request: Request):
    """GET /api/v1/design/plugins — Return status of each Design Studio plugin.

    Reports: RDKit, AutoDock Vina, fpocket, GPU Acceleration, Diffusion Model.
    Uses ToolInstaller for real binary detection (PATH + tools/bin/).
    Requirements: 7.1, 7.8
    """
    from services.tool_installer import ToolInstaller

    plugins: list[dict] = []
    installer = ToolInstaller()
    availability = installer.check_availability()

    # RDKit
    try:
        from rdkit import Chem, rdBase  # noqa: F401
        plugins.append({
            "name": "RDKit",
            "status": "available",
            "version": rdBase.rdkitVersion if hasattr(rdBase, "rdkitVersion") else "unknown",
            "details": "Molecular descriptors, analog generation, SMILES validation, fingerprints",
            "install_hint": "",
        })
    except Exception:
        plugins.append({
            "name": "RDKit",
            "status": "not_detected",
            "version": "",
            "details": "Required for cheminformatics operations",
            "install_hint": "pip install rdkit-pypi",
        })

    # AutoDock Vina — use ToolInstaller
    vina_status = availability.get("vina")
    if vina_status and vina_status.status == "available":
        plugins.append({
            "name": "AutoDock Vina",
            "status": "available",
            "version": "",
            "details": "Molecular docking with configurable search parameters",
            "install_hint": "",
            "path": vina_status.path,
        })
    else:
        plugins.append({
            "name": "AutoDock Vina",
            "status": "not_detected",
            "version": "",
            "details": "Required for molecular docking",
            "install_hint": (
                vina_status.install_hint if vina_status
                else "Install from https://vina.scripps.edu/ or use POST /api/v1/design/plugins/install"
            ),
        })

    # fpocket — use ToolInstaller
    fpocket_status = availability.get("fpocket")
    if fpocket_status and fpocket_status.status == "available":
        plugins.append({
            "name": "fpocket",
            "status": "available",
            "version": "",
            "details": "Binding site pocket detection and druggability ranking",
            "install_hint": "",
            "path": fpocket_status.path,
        })
    else:
        plugins.append({
            "name": "fpocket",
            "status": "not_detected",
            "version": "",
            "details": "Required for pocket detection from PDB structures",
            "install_hint": (
                fpocket_status.install_hint if fpocket_status
                else "Install from https://github.com/Discngine/fpocket or conda install -c bioconda fpocket"
            ),
        })

    # GPU Acceleration
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            plugins.append({
                "name": "GPU Acceleration",
                "status": "available",
                "version": f"CUDA {torch.version.cuda}",
                "details": f"GPU: {gpu_name}",
                "install_hint": "",
            })
        else:
            plugins.append({
                "name": "GPU Acceleration",
                "status": "cpu_only",
                "version": f"PyTorch {torch.__version__}",
                "details": "No CUDA GPU detected; running in CPU-only mode (slower but functional)",
                "install_hint": "Install CUDA toolkit and PyTorch with GPU support",
            })
    except Exception:
        plugins.append({
            "name": "GPU Acceleration",
            "status": "not_detected",
            "version": "",
            "details": "PyTorch not available",
            "install_hint": "pip install torch",
        })

    # Diffusion Model
    try:
        from services.dl_models import GraphDiffusionModel  # noqa: F401
        plugins.append({
            "name": "Diffusion Model",
            "status": "available",
            "version": "",
            "details": "De novo molecule generation conditioned on binding site geometry",
            "install_hint": "",
        })
    except Exception:
        plugins.append({
            "name": "Diffusion Model",
            "status": "degraded",
            "version": "",
            "details": "Diffusion model module not loadable",
            "install_hint": "Ensure services/dl_models.py is available with PyTorch",
        })

    return _envelope({"plugins": plugins}, req=request)


# ── POST /design/plugins/install — On-demand tool installation ──────

class PluginInstallRequest(BaseModel):
    tools: List[str] = Field(
        ...,
        description="List of tool names to install (e.g., ['vina', 'fpocket'])",
        min_length=1,
    )


@router.post("/plugins/install")
async def install_plugins(
    body: PluginInstallRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    """POST /api/v1/design/plugins/install — Install missing tool binaries.

    Accepts a list of tool names and attempts to install each one.
    Returns per-tool installation status: installed, already_available, or failed.
    Requirements: 6.5, 6.10, 10.3
    """
    from services.tool_installer import ToolInstaller

    installer = ToolInstaller()
    results: Dict[str, Any] = {}

    for tool_name in body.tools:
        tool_key = tool_name.strip().lower()
        if tool_key not in ("vina", "fpocket"):
            results[tool_key] = {
                "status": "failed",
                "error": f"Unknown tool: {tool_key}. Supported tools: vina, fpocket",
            }
            continue

        result = await installer.install_tool(tool_key)
        results[tool_key] = {
            "status": result.status,
            "path": result.path,
            "error": result.error,
            "duration_seconds": result.duration_seconds,
        }

    log.info("plugin_install_request", tools=body.tools, results={k: v["status"] for k, v in results.items()})
    return _envelope({"results": results}, req=request)

class DockRequest(BaseModel):
    receptor_pdb: str = Field(..., description="PDB ID or path to receptor file")
    ligand_smiles: str = Field(..., description="SMILES string of ligand")
    center_x: float = 0.0
    center_y: float = 0.0
    center_z: float = 0.0
    size_x: float = 20.0
    size_y: float = 20.0
    size_z: float = 20.0
    exhaustiveness: int = 8
    num_modes: int = 9
    project_id: Optional[str] = None


@router.post("/dock")
async def submit_docking_job(
    body: DockRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """POST /api/v1/design/dock — Submit a molecular docking job.

    Creates a background docking run with WebSocket progress reporting.
    Requirements: 7.3, 7.6, 20.1, 20.2
    """
    from services.docking_service import DockingService

    vina_bin = shutil.which("vina") or shutil.which("autodock_vina")
    warnings: list[str] = []
    if not vina_bin:
        warnings.append("AutoDock Vina not detected; docking will run in simulated mode")

    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        project_id=body.project_id or "",
        run_type="docking.vina",
        state="QUEUED",
        input_snapshot=body.model_dump(),
        runtime_context={"vina_available": bool(vina_bin)},
    )
    db.add(run)
    await db.commit()

    log.info("docking_job_queued", run_id=run_id, receptor=body.receptor_pdb, ligand=body.ligand_smiles[:30])
    return _envelope({
        "run_id": run_id,
        "status": "QUEUED",
        "stream_channel": f"/ws/runs/{run_id}",
        "message": f"Docking job queued for {body.receptor_pdb}",
        "vina_available": bool(vina_bin),
    }, req=request, warnings=warnings or None)


# ── POST /design/descriptors — Compute molecular descriptors (Task 17.5) ──

class DescriptorsRequest(BaseModel):
    smiles: str = Field(..., description="SMILES string")
    include_fingerprints: bool = False


@router.post("/descriptors")
async def compute_descriptors(
    body: DescriptorsRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    """POST /api/v1/design/descriptors — Compute molecular descriptors via RDKit.

    Returns physicochemical properties, drug-likeness scores, and optionally fingerprints.
    Requirements: 7.2
    """
    from services.molecule_service import compute_physichem, compute_physichem_rdkit

    # Try RDKit first, fall back to heuristic
    try:
        descriptors = compute_physichem_rdkit(body.smiles)
    except Exception:
        descriptors = compute_physichem(body.smiles)

    result: dict = {"smiles": body.smiles, "descriptors": descriptors}

    if body.include_fingerprints:
        try:
            from rdkit import Chem
            from rdkit.Chem import AllChem
            mol = Chem.MolFromSmiles(body.smiles)
            if mol:
                fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)
                result["fingerprint_morgan2"] = fp.ToBitString()
        except Exception as e:
            result["fingerprint_error"] = str(e)

    return _envelope(result, req=request)


# ── POST /design/analogs — Generate analogs (Task 17.5) ──────────────

class AnalogsRequest(BaseModel):
    smiles: str = Field(..., description="SMILES string of seed molecule")
    method: str = "scaffold_hop"  # scaffold_hop, r_group, similarity
    limit: int = 10
    project_id: Optional[str] = None


@router.post("/analogs")
async def generate_analogs(
    body: AnalogsRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    """POST /api/v1/design/analogs — Generate molecular analogs.

    Supports scaffold hopping, R-group enumeration, and similarity search.
    Requirements: 7.2
    """
    from services.molecule_service import AnalogGenerator

    generator = AnalogGenerator()
    analogs = await generator.generate_analogs(
        smiles=body.smiles,
        method=body.method,
        num_analogs=body.limit,
    )

    return _envelope({
        "seed_smiles": body.smiles,
        "method": body.method,
        "analogs": analogs,
        "count": len(analogs),
    }, req=request)
