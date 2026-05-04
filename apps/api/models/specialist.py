"""Specialist & Consensus models (Drug Designer §22, §40).

The Specialist Workflow Engine provides bounded expert behaviors.
Each specialist is defined by a role specification with allowed tools,
expected I/O schemas, and failure behavior.

For high-stakes claims, the MAV (Multi-Agent Voting) protocol spawns
3 independent specialist instances for blind evaluation (§22.5).
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


# ── §22.3 — Specialist Role Definition ─────────────────────
class SpecialistRole(BaseModel):
    """A bounded expert role specification.

    12 specialist profiles exist (§22.3): Disease Normalization Expert,
    Source Aggregation Expert, Mapping Expert, Target Scoring Expert,
    Contradiction Reviewer, Evidence Summarizer, Recommendation Drafter,
    Provenance Auditor, Runtime Diagnostician, PICO Extractor,
    Graph Reasoner, ADMET Analyst.
    """

    role_id: str = Field(
        ..., description="e.g. contradiction_reviewer, disease_normalizer"
    )
    system_prompt: str = Field(
        ..., description="Full system prompt for this specialist"
    )
    allowed_tools: List[str] = Field(
        default_factory=list,
        description="e.g. evidence_search, source_lookup, graph_query",
    )
    input_schema: Dict[str, Any] = Field(
        default_factory=dict, description="Expected input structure"
    )
    output_schema: Dict[str, Any] = Field(
        default_factory=dict, description="Expected output structure"
    )
    max_context_tokens: int = Field(8192)
    failure_mode: str = Field(
        "degrade", description="degrade | abort"
    )
    review_threshold: str = Field(
        "always_show_provenance",
        description="When and how to surface results for review",
    )


# ── §22.5 — MAV Consensus Vote ─────────────────────────────
class ConsensusVote(BaseModel):
    """A single agent's vote in a MAV jury evaluation."""

    agent_id: str
    verdict: str = Field(
        ..., description="support | refute | uncertain"
    )
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    rationale: str = ""


class ConsensusResult(BaseModel):
    """Result of a MAV (Multi-Agent Voting) evaluation.

    Majority Rule: ≥2/3 for 'verified'.
    Unanimous: 3/3 for 'canonical'.
    Conflict: triggers Truthful Pause Rule for human arbitration.
    """

    claim_id: str = Field(default_factory=_uuid)
    claim_text: str = ""
    status: str = Field(
        ..., description="verified | canonical | conflict"
    )
    votes: List[ConsensusVote] = Field(default_factory=list)
    consensus_met: bool = False
    requires_human_arbitration: bool = Field(
        False,
        description="True if MAV conflict triggers Truthful Pause (§22.5)",
    )
    created_at: str = Field(default_factory=_now_iso)
