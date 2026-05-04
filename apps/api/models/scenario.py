"""Scenario Simulation & DAG Planner models (Drug Designer §25, §43, §58).

SynthArena: Compares competing scientific/translational scenarios under
uncertainty. The DAG Planner translates natural language into a directed
acyclic graph of modules to execute.
"""

from __future__ import annotations

import uuid
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _uuid() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ── §25.3 — Scenario Object ───────────────────────────────
class Scenario(BaseModel):
    """A single scenario in a SynthArena comparison.

    Scenario types (§25.2): Target-First vs Pathway-First,
    Compound A vs B vs C, Indian vs Global population, etc.
    """

    scenario_id: str = Field(default_factory=_uuid)
    title: str = Field(..., description="e.g. 'EGFR-targeted vs PI3K-targeted for NSCLC'")
    assumptions: List[str] = Field(default_factory=list)
    seed_entities: Dict[str, List[str]] = Field(
        default_factory=lambda: {"targets": [], "pathways": [], "compounds": []},
    )
    supporting_evidence: List[str] = Field(
        default_factory=list, description="Evidence bundle IDs"
    )
    scoring_function: Dict[str, Any] = Field(
        default_factory=lambda: {
            "weights": {"genetic_support": 0.3, "druggability": 0.25,
                        "safety": 0.2, "novelty": 0.15, "literature": 0.1}
        },
    )
    graph_context: Optional[str] = Field(
        None, description="Subgraph snapshot ID"
    )
    population_context: str = Field("global", description="global | indian | custom")
    simulation_result: Optional[Dict[str, Any]] = Field(
        None,
        description="trajectory, final_score, risk_factors, contradictions",
    )


# ── SynthArena Session ─────────────────────────────────────
class SynthArenaSession(BaseModel):
    """A SynthArena comparison session with 2+ scenarios."""

    session_id: str = Field(default_factory=_uuid)
    project_id: str
    title: str
    scenarios: List[Scenario] = Field(default_factory=list)
    status: str = Field("created", description="created | running | complete | failed")
    comparison_result: Optional[Dict[str, Any]] = None
    created_at: str = Field(default_factory=_now_iso)


# ── §58 — DAG Planner Models ──────────────────────────────
class DAGNode(BaseModel):
    """A single node in the Agentic DAG execution plan.

    Available modules (§58.2): disease.intelligence, target.ranking,
    evidence.search, graph.enrichment, molecule.generation, admet.batch,
    retrosynthesis.plan, scenario.simulation, dossier.generation,
    pico.extraction
    """

    node_id: str
    module: str = Field(
        ...,
        description="One of the available modules",
    )
    input: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    status: str = Field("pending", description="pending | running | complete | failed")


class DAGPlan(BaseModel):
    """A Directed Acyclic Graph execution plan generated from a user prompt.

    §58.3: If the LLM returns clarification_needed, the Cockpit displays
    an inline dialog. If 0 nodes, system responds with guidance.
    """

    dag_id: str = Field(default_factory=_uuid)
    created_from_prompt: str = Field("", description="Original user prompt")
    nodes: List[DAGNode] = Field(default_factory=list)
    execution_order: List[str] = Field(default_factory=list)
    estimated_duration_seconds: int = 0
    clarification_needed: Optional[str] = Field(
        None, description="If set, ask user before proceeding"
    )
    error: Optional[str] = None
