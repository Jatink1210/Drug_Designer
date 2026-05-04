"""G-1: Contradiction Reviewer specialist.

Integrates with Phase C contradiction detector to produce structured
conflict reports (directional / temporal / population types).
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)


class ContradictionReviewerSpecialist:
    """Specialist: runs all Phase-C detectors and synthesises a conflict report.

    Invocation pattern::

        specialist = ContradictionReviewerSpecialist()
        result = await specialist.analyze(evidence_items=[...])
    """

    ROLE_ID = "contradiction_reviewer"

    def __init__(self, engine: Optional[Any] = None) -> None:
        self.engine = engine
        log.info("contradiction_reviewer_initialized")

    async def analyze(
        self,
        evidence_items: List[Dict[str, Any]],
        submit_vote: bool = False,
        run_id: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run all contradiction detectors and return a structured conflict report.

        Args:
            evidence_items: List of evidence dicts (must include id, score,
                entity_id, source, year, population, study_type keys).
            submit_vote: If True, submit MAV vote after analysis.
            run_id: Optional run ID for MAV voting.
            entity_id: Optional entity ID for MAV voting.

        Returns:
            Dict with keys:
            - contradictions: list of ContradictionResult dicts
            - type_breakdown: {type: count}
            - total_contradictions: int
            - has_directional: bool
            - confidence: float
            - status: "ok" | "no_contradictions"
        """
        from services.contradiction.detector import run_all

        contradictions = run_all(evidence_items)
        type_breakdown: Dict[str, int] = {}
        for c in contradictions:
            ctype = getattr(c, "contradiction_type", "unknown")
            type_breakdown[ctype] = type_breakdown.get(ctype, 0) + 1

        confidence = min(1.0, len(contradictions) / max(len(evidence_items), 1))
        verdict = "support" if len(contradictions) == 0 else "uncertain"

        if submit_vote and run_id and entity_id:
            await self._submit_vote(run_id, entity_id, verdict, confidence, len(contradictions))

        return {
            "status": "ok" if contradictions else "no_contradictions",
            "total_contradictions": len(contradictions),
            "type_breakdown": type_breakdown,
            "contradictions": [
                {
                    "id": getattr(c, "id", ""),
                    "contradiction_type": getattr(c, "contradiction_type", ""),
                    "item_a_id": getattr(c, "item_a_id", ""),
                    "item_b_id": getattr(c, "item_b_id", ""),
                    "details": getattr(c, "details", {}),
                }
                for c in contradictions
            ],
            "has_directional": type_breakdown.get("directional", 0) > 0,
            "has_population": type_breakdown.get("population", 0) > 0,
            "confidence": round(confidence, 4),
            "specialist": self.ROLE_ID,
        }

    async def _submit_vote(
        self,
        run_id: str,
        entity_id: str,
        verdict: str,
        confidence: float,
        n_contradictions: int,
    ) -> None:
        try:
            from services.specialists.consensus import ConsensusVote

            vote = ConsensusVote(
                agent_id=self.ROLE_ID,
                verdict=verdict,
                confidence=confidence,
                rationale=f"Contradiction Reviewer found {n_contradictions} contradiction(s).",
            )
            log.info("contradiction_reviewer_vote_submitted", verdict=verdict, run_id=run_id)
        except Exception as exc:
            log.warning("contradiction_reviewer_vote_failed", error=str(exc))
