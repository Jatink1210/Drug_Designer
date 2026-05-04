"""Target Prioritization models (Drug Designer §94.3, §11, §83).

Target_Score = Σ(weight_i × score_i) across 7 signals:
GWAS, Druggability, Pathway Centrality, Expression, Safety, Novelty, Literature.

Every score shown to a user must have an explainability path (§107.7).
Every rank should be connected to evidence, not just a black-box number.
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


# ── §94.3 — Target Ranking Item ────────────────────────────
class TargetScoreBreakdown(BaseModel):
    """Per-signal score breakdown for explainability."""

    gwas: float = Field(0.0, description="Genetic validation score")
    druggability: float = Field(0.0, description="Pocket/surface analysis score")
    pathway_centrality: float = Field(0.0, description="Network importance")
    expression: float = Field(0.0, description="Tissue-specific expression score")
    safety: float = Field(0.0, description="Off-target homology penalty")
    novelty: float = Field(0.0, description="Existing drug count penalty")
    literature: float = Field(0.0, description="Publication co-occurrence score")


class TargetRankingItem(BaseModel):
    """A ranked target with full evidence breakdown.

    §83: Composite scoring with UCB exploration bonus.
    """

    target_id: str = Field(default_factory=_uuid)
    target_symbol: str = Field(..., description="Gene symbol, e.g. PPARG")
    uniprot_id: str = Field("", description="UniProt accession, e.g. P37231")
    rank: int = Field(0)
    composite_score: float = Field(0.0, ge=0.0, le=1.0)
    score_breakdown: TargetScoreBreakdown = Field(default_factory=TargetScoreBreakdown)
    ucb_score: Optional[float] = Field(
        None, description="UCB exploration bonus (§11.4)"
    )
    contradiction_flag: bool = Field(
        False, description="True if conflicting evidence exists"
    )
    explanation: str = Field(
        "", description="Human-readable explanation of ranking rationale"
    )
    explanation_md: str = Field(
        "", description="Spec §3.4 markdown explanation alias"
    )
    evidence_item_ids: List[str] = Field(
        default_factory=list, description="Evidence items supporting this ranking"
    )
    evidence_count: int = Field(
        0, description="Spec §3.4 — number of supporting evidence items"
    )
    run_id: Optional[str] = None


# ── Target Ranking Result ─────────────────────────────────
class TargetRankingResult(BaseModel):
    """Complete output of a target prioritization run."""

    run_id: str
    project_id: str
    targets: List[TargetRankingItem] = Field(default_factory=list)
    total_candidates: int = 0
    scoring_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "gwas": 0.20, "druggability": 0.15, "pathway_centrality": 0.15,
            "expression": 0.15, "safety": 0.15, "novelty": 0.10, "literature": 0.10,
        }
    )
    graph_snapshot_id: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)
