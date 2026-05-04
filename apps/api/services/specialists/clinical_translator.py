"""G-6: Clinical Translator specialist.

Converts PICO evidence into clinical context narratives, integrating
India-specific trial data and population genetics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)


class ClinicalTranslatorSpecialist:
    """Specialist: translates evidence bundles into clinical context narratives.

    - Parses PICO extractions
    - Queries India clinical trials connector
    - Weights evidence by Indian population genetics where relevant
    """

    ROLE_ID = "clinical_translator"

    def __init__(self, engine: Optional[Any] = None) -> None:
        self.engine = engine
        log.info("clinical_translator_initialized")

    async def translate(
        self,
        disease_name: str,
        pico: Optional[Dict[str, Any]] = None,
        evidence_items: Optional[List[Dict[str, Any]]] = None,
        include_india_trials: bool = True,
        submit_vote: bool = False,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Translate evidence into clinical context.

        Args:
            disease_name: Disease name (e.g. "Type 2 diabetes")
            pico: Optional PICO dict (from PICOExtractorSpecialist)
            evidence_items: Evidence list to contextualise
            include_india_trials: Query India clinical trials connector
            submit_vote: Submit MAV vote if True
            run_id: Run ID for MAV

        Returns:
            Dict with: narrative, india_trials, population_relevance, confidence, specialist
        """
        evidence_items = evidence_items or []
        india_trials: List[Dict[str, Any]] = []

        if include_india_trials:
            india_trials = await self._fetch_india_trials(disease_name)

        narrative = self._build_narrative(disease_name, pico, evidence_items, india_trials)
        population_relevance = self._score_population_relevance(india_trials)
        confidence = 0.6 + 0.2 * population_relevance

        if submit_vote and run_id:
            verdict = "support" if confidence > 0.7 else "uncertain"
            log.info(
                "clinical_translator_vote",
                run_id=run_id,
                disease=disease_name,
                verdict=verdict,
                confidence=confidence,
            )

        return {
            "status": "ok",
            "disease_name": disease_name,
            "narrative": narrative,
            "india_trials": india_trials[:10],
            "population_relevance": round(population_relevance, 4),
            "pico_applied": bool(pico),
            "evidence_count": len(evidence_items),
            "confidence": round(confidence, 4),
            "specialist": self.ROLE_ID,
        }

    async def _fetch_india_trials(self, disease_name: str) -> List[Dict[str, Any]]:
        """Fetch India-specific clinical trials."""
        trials: List[Dict[str, Any]] = []
        try:
            from connectors.clinicaltrials import ClinicalTrialsConnector

            conn = ClinicalTrialsConnector()
            results = await conn.search(
                f"{disease_name} India", limit=15
            )
            await conn.close()
            trials = results if isinstance(results, list) else []
        except Exception as exc:
            log.warning("clinical_translator_trials_failed", disease=disease_name, error=str(exc))
        return trials

    def _score_population_relevance(self, india_trials: List[Dict[str, Any]]) -> float:
        """Score how relevant Indian population data is (0.0–1.0)."""
        if not india_trials:
            return 0.0
        return min(1.0, len(india_trials) / 10.0)

    def _build_narrative(
        self,
        disease: str,
        pico: Optional[Dict[str, Any]],
        evidence: List[Dict[str, Any]],
        india_trials: List[Dict[str, Any]],
    ) -> str:
        parts: List[str] = [f"Clinical context for: {disease}."]
        if pico:
            pop = pico.get("population", "")
            inter = pico.get("intervention", "")
            out = pico.get("outcome", "")
            if pop:
                parts.append(f"Population: {pop}.")
            if inter:
                parts.append(f"Intervention: {inter}.")
            if out:
                parts.append(f"Outcome: {out}.")
        if evidence:
            parts.append(f"{len(evidence)} evidence item(s) retrieved from curated sources.")
        if india_trials:
            parts.append(
                f"{len(india_trials)} India-specific clinical trial(s) identified; "
                "Indian population pharmacogenomics data may modify dosing recommendations."
            )
        return " ".join(parts)
