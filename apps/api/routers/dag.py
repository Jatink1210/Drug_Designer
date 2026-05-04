"""DAG Planner Router (§50, §58) — Translate natural language into execution DAGs
and dispatch Ghost Execution via the Autonomous Run Orchestrator.

§50.1: Natural language entry point (CommandPalette)
§50.2: Autonomous DAG Planner (Specialist Engine → LLM → DAGPlan)
§50.3: Ghost Execution (DAGPlan → ARQ worker → sequential node dispatch)
§50.4: Truthful Pause (halt on API failure, emit dag.paused)
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core.db import get_db
from core.inference_engine import UniversalInferenceEngine
from core.llm_security import DAG_PLANNER_PROMPT
from models.db_tables import Run
from models.envelope import build_envelope
from models.scenario import DAGPlan, DAGNode
from routers.auth import get_current_user, User
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/dag", tags=["DAG Planner"], dependencies=[Depends(get_current_user)])
log = structlog.get_logger()

_engine = UniversalInferenceEngine()


class DAGRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=2000, description="Natural language request")
    project_id: str = Field("", description="Optional project context")
    auto_execute: bool = Field(True, description="§50.3: Immediately begin Ghost Execution after planning")


def _parse_llm_json(raw: str) -> dict:
    """Extract JSON from LLM output (may be wrapped in markdown fences)."""
    json_str = raw.strip()
    if json_str.startswith("```"):
        json_str = json_str.split("```")[1]
        if json_str.startswith("json"):
            json_str = json_str[4:]
    return json.loads(json_str.strip())


# ── Keyword-based fallback planner (no LLM required) ─────────
_MODULE_KEYWORDS: dict[str, list[str]] = {
    "disease.intelligence": [
        "disease", "indication", "illness", "disorder", "syndrome", "condition",
        "alzheimer", "cancer", "diabetes", "asthma", "nsclc", "parkinson",
        "covid", "malaria", "tuberculosis", "hiv", "lupus", "arthritis",
        "huntington", "leukemia", "melanoma", "glioblastoma", "fibrosis",
    ],
    "evidence.search": [
        "evidence", "search", "find", "literature", "papers", "publications",
        "pubmed", "research", "study", "studies", "review", "articles", "cite",
    ],
    "target.ranking": [
        "target", "rank", "prioriti", "gene", "protein", "bind", "brca",
        "egfr", "tp53", "kras", "braf", "her2", "jak", "candidate",
        "druggab", "score", "ppi", "interact",
    ],
    "graph.enrichment": [
        "graph", "network", "pathway", "kegg", "reactome", "string",
        "interaction", "relationship", "connect", "neighbor", "node", "edge",
    ],
    "molecule.generation": [
        "molecule", "compound", "drug", "design", "generate", "scaffold",
        "smiles", "chemical", "ligand", "inhibitor", "agonist", "antagonist",
        "novel", "lead", "hit",
    ],
    "admet.batch": [
        "admet", "absorption", "distribution", "metabolism", "excretion",
        "toxicity", "safety", "herg", "caco", "clearance", "bioavail",
    ],
    "retrosynthesis.plan": [
        "synthes", "retro", "route", "reaction", "precursor", "reagent",
    ],
    "dossier.generation": [
        "dossier", "report", "summary", "compile", "export", "document",
    ],
    "pico.extraction": [
        "pico", "clinical trial", "population", "intervention", "outcome",
        "comparison", "rct", "trial",
    ],
    "export.render": [
        "export", "render", "pdf", "html", "csv", "sdf", "download",
        "zip", "format", "bundle",
    ],
    "runtime.local_dispatch": [
        "runtime", "local", "dispatch", "agent", "hardware",
        "gpu", "cpu", "vram", "airllm", "ollama",
    ],
}


def _keyword_fallback_plan(prompt: str) -> dict:
    """Build a DAG from keyword matching when no LLM is available.

    Scans the prompt for module-related keywords and constructs a
    reasonable linear pipeline. This ensures Auto-Pilot works even
    without Ollama or an OpenAI key (§50.2 degraded mode).
    """
    prompt_lower = prompt.lower()
    # Score each module by keyword hits
    scores: dict[str, int] = {}
    for module, keywords in _MODULE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in prompt_lower)
        if score > 0:
            scores[module] = score

    if not scores:
        # Default: evidence search is always useful
        scores = {"evidence.search": 1}

    # Sort by score descending, build nodes
    ordered = sorted(scores.keys(), key=lambda m: scores[m], reverse=True)
    nodes = []
    for i, module in enumerate(ordered):
        node_id = f"n{i+1}"
        node = {
            "node_id": node_id,
            "module": module,
            "input": {"query": prompt},
            "depends_on": [f"n{i}"] if i > 0 else [],
        }
        nodes.append(node)

    return {
        "nodes": nodes,
        "execution_order": [n["node_id"] for n in nodes],
        "estimated_duration_seconds": len(nodes) * 15,
    }


@router.post("", summary="Generate & execute DAG from prompt (§50, §58)")
async def create_dag(
    body: DAGRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """§50/§58: Parse a natural language prompt into a DAGPlan via the LLM,
    then immediately dispatch Ghost Execution as a background worker job.

    Returns the DAGPlan with a run_id. The frontend subscribes to
    ws://HOST/ws/runs/{run_id} for live node-by-node progress.
    """
    # ── §50.2: Generate DAG plan via LLM ──────────────────────
    parsed = None
    try:
        result = await _engine.generate(
            prompt=body.prompt,
            system_prompt=DAG_PLANNER_PROMPT,
            max_tokens=1024,
            temperature=0.2,
        )
        raw_text = result.get("text", "").strip()
        if raw_text:
            parsed = _parse_llm_json(raw_text)
    except json.JSONDecodeError:
        log.info("dag_plan_json_parse_failed_falling_back_to_keywords", prompt=body.prompt[:100])
    except Exception as exc:
        log.warning("dag_plan_llm_failed_falling_back_to_keywords", error=str(exc))

    # Keyword-based fallback when LLM is unavailable or returns garbage
    if parsed is None:
        log.info("dag_plan_using_keyword_fallback", prompt=body.prompt[:100])
        parsed = _keyword_fallback_plan(body.prompt)

    nodes = [DAGNode(**n) for n in parsed.get("nodes", [])]
    plan = DAGPlan(
        created_from_prompt=body.prompt,
        nodes=nodes,
        execution_order=parsed.get("execution_order", [n.node_id for n in nodes]),
        estimated_duration_seconds=parsed.get("estimated_duration_seconds", 0),
        clarification_needed=parsed.get("clarification_needed"),
        error=parsed.get("error"),
    )
    log.info("dag_plan_created", node_count=len(nodes), prompt_len=len(body.prompt))

    # §58.3: If clarification needed or zero nodes, return plan without executing
    if plan.clarification_needed or plan.error or not plan.nodes:
        return build_envelope(request, plan.model_dump())

    # ── §50.3: Ghost Execution — persist Run, enqueue worker ──
    run_id = str(uuid.uuid4())
    project_id = body.project_id or "default"

    if body.auto_execute:
        run = Run(
            id=run_id,
            project_id=project_id,
            user_id=current_user.id,
            run_type="dag.ghost_execution",
            module_name="dag_planner",
            trigger_type="agentic",
            state="QUEUED",
            query_text=body.prompt,
            input_snapshot=plan.model_dump(),
            runtime_mode="hosted",
        )
        db.add(run)
        await db.commit()

        # Enqueue the Ghost Execution worker
        from worker import enqueue_job
        await enqueue_job(
            request.app.state,
            "execute_dag_plan",
            run_id,
            plan.model_dump(),
            project_id,
            queue_name="dag.ghost_execution",
            idempotency_key=f"dag:{run_id}",
        )
        log.info("dag_ghost_execution_enqueued", run_id=run_id, dag_id=plan.dag_id, nodes=len(nodes))

    response = plan.model_dump()
    response["run_id"] = run_id
    response["execution_status"] = "queued" if body.auto_execute else "plan_only"
    return build_envelope(request, response)


@router.get("/{run_id}", summary="Get DAG execution status (§50.3)")
async def get_dag_status(
    run_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """§50.3: Retrieve the current state of a Ghost Execution run."""
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="DAG run not found")
    return build_envelope(request, {
        "run_id": run.id,
        "state": run.state,
        "dag_plan": run.input_snapshot,
        "output_artifacts": run.output_artifacts,
        "errors": run.errors,
        "elapsed_ms": run.elapsed_ms,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    })
