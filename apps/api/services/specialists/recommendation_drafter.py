"""G-7: Recommendation Drafter specialist.

Synthesises MAV votes + evidence bundles into a structured dossier narrative
with actionable drug discovery recommendations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)


class RecommendationDrafterSpecialist:
    """Specialist: produces the final recommendation narrative for a dossier.

    Aggregates all specialist verdicts (via MAV consensus) and composes
    a human-readable recommendation with confidence ratings per claim.
    """

    ROLE_ID = "recommendation_drafter"

    def __init__(self, engine: Optional[Any] = None) -> None:
        self.engine = engine
        log.info("recommendation_drafter_initialized")

    async def draft(
        self,
        run_id: str,
        entity_id: str,
        entity_name: str = "",
        specialist_outputs: Optional[Dict[str, Any]] = None,
        mav_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Draft a structured recommendation for *entity_id*.

        Args:
            run_id: Analysis run ID
            entity_id: Target / disease / molecule identifier
            entity_name: Human-readable name
            specialist_outputs: Dict of specialist_role → output dict
            mav_result: MAV consensus result (optional)

        Returns:
            Dict with: headline, sections, confidence, evidence_grade, specialist
        """
        specialist_outputs = specialist_outputs or {}
        sections = self._build_sections(entity_name or entity_id, specialist_outputs, mav_result)
        confidence = self._aggregate_confidence(specialist_outputs, mav_result)
        evidence_grade = self._assign_evidence_grade(confidence, specialist_outputs)
        headline = self._build_headline(entity_name or entity_id, evidence_grade, confidence)

        return {
            "status": "ok",
            "run_id": run_id,
            "entity_id": entity_id,
            "entity_name": entity_name,
            "headline": headline,
            "sections": sections,
            "evidence_grade": evidence_grade,
            "confidence": round(confidence, 4),
            "specialist": self.ROLE_ID,
        }

    def _build_sections(
        self,
        name: str,
        outputs: Dict[str, Any],
        mav: Optional[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        sections: List[Dict[str, str]] = []

        if "target_scoring_expert" in outputs or "target_analyst" in outputs:
            td = outputs.get("target_scoring_expert", outputs.get("target_analyst", {}))
            sections.append(
                {
                    "title": "Target Druggability",
                    "body": (
                        f"Composite druggability score: {td.get('composite_score', 'N/A')}. "
                        f"{td.get('explanation', '')}"
                    ),
                }
            )

        if "contradiction_reviewer" in outputs:
            cd = outputs["contradiction_reviewer"]
            sections.append(
                {
                    "title": "Evidence Contradictions",
                    "body": (
                        f"Total contradictions detected: {cd.get('total_contradictions', 0)}. "
                        f"Directional conflicts: {cd.get('has_directional', False)}."
                    ),
                }
            )

        if "clinical_translator" in outputs:
            ct = outputs["clinical_translator"]
            sections.append(
                {
                    "title": "Clinical Context",
                    "body": ct.get("narrative", ""),
                }
            )

        if "molecule_designer" in outputs:
            md = outputs["molecule_designer"]
            n = md.get("n_generated", 0)
            sections.append(
                {
                    "title": "Candidate Molecules",
                    "body": (
                        f"{n} candidate molecule(s) generated with PPO optimization. "
                        f"Constraints applied: {md.get('constraints_applied', {})}."
                    ),
                }
            )

        if mav:
            sections.append(
                {
                    "title": "Multi-Agent Voting Consensus",
                    "body": (
                        f"Verdict: {mav.get('verdict', 'unknown')}. "
                        f"MAV confidence: {mav.get('confidence', 'N/A')}. "
                        f"Participating agents: {mav.get('agent_count', '?')}."
                    ),
                }
            )

        return sections

    def _aggregate_confidence(
        self, outputs: Dict[str, Any], mav: Optional[Dict[str, Any]]
    ) -> float:
        scores: List[float] = []
        for v in outputs.values():
            if isinstance(v, dict) and "confidence" in v:
                scores.append(float(v["confidence"]))
        if mav and "confidence" in mav:
            scores.append(float(mav["confidence"]))
        return sum(scores) / len(scores) if scores else 0.5

    def _assign_evidence_grade(
        self, confidence: float, outputs: Dict[str, Any]
    ) -> str:
        contradictions = outputs.get("contradiction_reviewer", {}).get("total_contradictions", 0)
        if confidence >= 0.8 and contradictions == 0:
            return "A"
        if confidence >= 0.65 and contradictions <= 2:
            return "B"
        if confidence >= 0.5:
            return "C"
        return "D"

    def _build_headline(self, name: str, grade: str, confidence: float) -> str:
        return (
            f"{name}: Evidence Grade {grade} "
            f"(confidence {confidence:.0%}). "
            "Proceed with further validation."
            if grade in ("A", "B")
            else f"{name}: Evidence Grade {grade} — insufficient data for strong recommendation."
        )
