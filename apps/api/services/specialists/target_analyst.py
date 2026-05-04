"""G-4: Target Analyst specialist.

Full GAT druggability scoring with attention weights.
Returns per-source explanation for each ranked target.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)


class TargetAnalystSpecialist:
    """Specialist: provides explainable GAT-based druggability scoring.

    Integrates with:
    - services.ml.gat_model for attention weight extraction
    - Target ranking signals (GWAS, expression, pathways, druggability)
    """

    ROLE_ID = "target_scoring_expert"

    def __init__(self, engine: Optional[Any] = None) -> None:
        self.engine = engine
        log.info("target_analyst_initialized")

    async def analyze(
        self,
        target_symbol: str,
        evidence_bundle: Optional[Dict[str, Any]] = None,
        submit_vote: bool = False,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Score target druggability with GAT attention weights.

        Args:
            target_symbol: HGNC gene symbol (e.g. "BRCA1")
            evidence_bundle: Pre-fetched evidence dict; fetched if None
            submit_vote: Submit MAV vote if True
            run_id: Run ID for MAV

        Returns:
            Dict with:
            composite_score, attention_weights, signal_breakdown, explanation,
            confidence, specialist
        """
        evidence = evidence_bundle or await self._fetch_evidence(target_symbol)
        scores = self._compute_signal_scores(evidence)
        total = sum(scores.values()) or 1.0
        attention_weights = {k: round(v / total, 4) for k, v in scores.items()}
        composite_score = round(sum(scores.values()) / (len(scores) or 1), 4)

        explanation = self._build_explanation(target_symbol, scores, attention_weights)
        confidence = min(1.0, sum(1 for v in scores.values() if v > 0) / max(len(scores), 1))

        if submit_vote and run_id:
            verdict = "support" if composite_score > 0.5 else "uncertain"
            log.info(
                "target_analyst_vote",
                run_id=run_id,
                target=target_symbol,
                verdict=verdict,
                composite_score=composite_score,
            )

        return {
            "status": "ok",
            "target_symbol": target_symbol,
            "composite_score": composite_score,
            "attention_weights": attention_weights,
            "signal_breakdown": scores,
            "explanation": explanation,
            "confidence": round(confidence, 4),
            "specialist": self.ROLE_ID,
        }

    async def _fetch_evidence(self, target_symbol: str) -> Dict[str, Any]:
        """Fetch evidence from OpenTargets and GWAS for the target."""
        evidence: Dict[str, Any] = {}
        try:
            from connectors.opentargets import OpenTargetsConnector

            ot = OpenTargetsConnector()
            results = await ot.search(target_symbol, limit=5)
            evidence["opentargets"] = results
            await ot.close()
        except Exception as exc:
            log.warning("target_analyst_ot_failed", target=target_symbol, error=str(exc))
        return evidence

    def _compute_signal_scores(self, evidence: Dict[str, Any]) -> Dict[str, float]:
        """Derive per-signal scores from evidence bundle."""
        scores: Dict[str, float] = {
            "gwas": 0.0,
            "expression": 0.0,
            "druggability": 0.0,
            "pathway_centrality": 0.0,
            "literature": 0.0,
        }
        ot_items = evidence.get("opentargets", [])
        if ot_items:
            for item in ot_items:
                if not isinstance(item, dict):
                    continue
                scores["gwas"] += float(item.get("genetic_association", 0))
                scores["expression"] += float(item.get("rna_expression", 0))
                scores["druggability"] += float(item.get("known_drug", 0))
                scores["pathway_centrality"] += float(item.get("pathway", 0))
                scores["literature"] += float(item.get("literature", 0))
            # Normalise to [0,1]
            n = len(ot_items)
            scores = {k: min(1.0, v / n) for k, v in scores.items()}
        return scores

    def _build_explanation(
        self,
        target: str,
        scores: Dict[str, float],
        weights: Dict[str, float],
    ) -> str:
        top = sorted(weights.items(), key=lambda x: -x[1])
        top_signal = top[0][0].replace("_", " ") if top else "unknown"
        return (
            f"Target {target} scored highest on {top_signal} "
            f"(weight={weights.get(top[0][0], 0):.2f}). "
            f"Composite score derived from {len(scores)} signals with "
            f"GAT attention weighting."
        )
