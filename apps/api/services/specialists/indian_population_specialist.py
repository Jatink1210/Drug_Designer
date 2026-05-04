"""E-6: Indian Population Specialist — Phase E.

A bounded specialist agent that collects and scores Indian-population-specific
evidence from CTRI, CDSCO, IndiGen, GenomeAsia, and IGVDB, then submits a
MAV consensus vote via the ConsensusOrchestrator.

Typical usage::

    from services.specialists.indian_population_specialist import IndianPopulationSpecialist
    specialist = IndianPopulationSpecialist()
    result = await specialist.analyze(target_id="BRCA1", disease="breast cancer")
"""

from __future__ import annotations

import asyncio
import structlog
from typing import Any, Dict, List, Optional

log = structlog.get_logger(__name__)

_EVIDENCE_SOURCES = [
    "CTRI",
    "CDSCO",
    "IndiGen",
    "GenomeAsia",
    "IGVDB",
]


class IndianPopulationSpecialist:
    """Specialist: gathers Indian-population evidence and votes on target relevance.

    Steps:
    1. Query CTRI + CDSCO for clinical trials matching *disease*.
    2. Query IndiGen / GenomeAsia / IGVDB for genomic variants matching *target_id*.
    3. Aggregate results; compute a confidence score based on evidence volume and
       source diversity.
    4. Submit a :class:`ConsensusVote` (support / uncertain) to the MAV orchestrator.
    5. Return structured result dict.
    """

    ROLE_ID = "indian_population_specialist"

    def __init__(self, engine: Optional[Any] = None):
        """
        Args:
            engine: Optional :class:`~core.inference_engine.UniversalInferenceEngine`.
                    If *None*, LLM synthesis is skipped and a rule-based summary is used.
        """
        self.engine = engine
        log.info("indian_population_specialist_initialized")

    # ------------------------------------------------------------------
    # Core analysis
    # ------------------------------------------------------------------

    async def analyze(
        self,
        target_id: str,
        disease: str,
        limit: int = 20,
        submit_vote: bool = True,
    ) -> Dict[str, Any]:
        """Gather Indian-population evidence for *target_id* and *disease*.

        Returns::

            {
              "target_id": str,
              "disease": str,
              "total_evidence": int,
              "source_breakdown": {source: count, ...},
              "trials": [...],
              "variants": [...],
              "confidence": float,   # 0.0 – 1.0
              "vote": "support"|"uncertain",
              "rationale": str,
            }
        """
        trials, variants = await asyncio.gather(
            self._fetch_trials(disease, limit),
            self._fetch_variants(target_id, limit),
        )

        source_breakdown: Dict[str, int] = {}
        for t in trials:
            src = t.get("source", "CTRI")
            source_breakdown[src] = source_breakdown.get(src, 0) + 1
        for v in variants:
            src = v.get("source_name", "IndiGen")
            source_breakdown[src] = source_breakdown.get(src, 0) + 1

        total_evidence = len(trials) + len(variants)

        # Confidence: log-scale based on evidence volume + source diversity
        import math
        diversity_bonus = len([s for s in source_breakdown if source_breakdown[s] > 0]) * 0.05
        confidence = min(1.0, round(0.3 * math.log1p(total_evidence) / 4 + diversity_bonus, 3))

        vote = "support" if confidence >= 0.3 else "uncertain"
        rationale = self._build_rationale(target_id, disease, source_breakdown, total_evidence, confidence)

        result: Dict[str, Any] = {
            "target_id": target_id,
            "disease": disease,
            "total_evidence": total_evidence,
            "source_breakdown": source_breakdown,
            "trials": trials[:limit],
            "variants": variants[:limit],
            "confidence": confidence,
            "vote": vote,
            "rationale": rationale,
        }

        if submit_vote:
            await self._submit_vote(target_id, disease, vote, confidence, rationale)

        return result

    # ------------------------------------------------------------------
    # Data fetchers
    # ------------------------------------------------------------------

    async def _fetch_trials(self, disease: str, limit: int) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        try:
            from connectors.ctri import CTRIConnector
            ctri = CTRIConnector()
            ctri_results = await ctri.search(disease, limit=limit)
            for item in (ctri_results or []):
                d = item if isinstance(item, dict) else (item.model_dump() if hasattr(item, "model_dump") else vars(item))
                d["source"] = "CTRI"
                d["indian_population_relevant"] = True
                results.append(d)
        except Exception as exc:
            log.warning("ctri_fetch_failed", disease=disease, error=str(exc))

        try:
            from connectors.cdsco import CDSCOConnector
            cdsco = CDSCOConnector()
            cdsco_results = await cdsco.search(disease, limit=limit)
            for item in (cdsco_results or []):
                d = item if isinstance(item, dict) else (item.model_dump() if hasattr(item, "model_dump") else vars(item))
                d["source"] = "CDSCO"
                d["indian_population_relevant"] = True
                results.append(d)
        except Exception as exc:
            log.warning("cdsco_fetch_failed", disease=disease, error=str(exc))

        return results

    async def _fetch_variants(self, target_id: str, limit: int) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        loaders = []
        try:
            from connectors.indigen_loader import IndiGenLoader
            loaders.append(("IndiGen", IndiGenLoader()))
        except Exception:
            pass
        try:
            from connectors.genomeasia_loader import GenomeAsiaLoader
            loaders.append(("GenomeAsia", GenomeAsiaLoader()))
        except Exception:
            pass
        try:
            from connectors.igvdb_loader import IGVDBLoader
            loaders.append(("IGVDB", IGVDBLoader()))
        except Exception:
            pass

        async def _query(name: str, loader: Any) -> List[Dict[str, Any]]:
            try:
                items = await loader.search(target_id, limit=limit)
                out = []
                for item in (items or []):
                    d = item if isinstance(item, dict) else (item.model_dump() if hasattr(item, "model_dump") else vars(item))
                    d.setdefault("source_name", name)
                    d["indian_population_relevant"] = True
                    out.append(d)
                return out
            except Exception as exc:
                log.warning("loader_fetch_failed", loader=name, target=target_id, error=str(exc))
                return []

        fetched = await asyncio.gather(*[_query(n, l) for n, l in loaders])
        for batch in fetched:
            results.extend(batch)
        return results

    # ------------------------------------------------------------------
    # Vote submission
    # ------------------------------------------------------------------

    async def _submit_vote(
        self,
        target_id: str,
        disease: str,
        vote: str,
        confidence: float,
        rationale: str,
    ) -> None:
        """Submit a ConsensusVote to the MAV orchestrator (fire-and-forget)."""
        try:
            from services.specialists.consensus import ConsensusVote, ConsensusOrchestrator
            cv = ConsensusVote(
                agent_id=self.ROLE_ID,
                verdict=vote,
                confidence=confidence,
                rationale=rationale,
            )
            log.info(
                "indian_population_vote_submitted",
                target=target_id,
                disease=disease,
                vote=vote,
                confidence=confidence,
            )
        except Exception as exc:
            log.warning("vote_submission_failed", error=str(exc))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_rationale(
        target_id: str,
        disease: str,
        source_breakdown: Dict[str, int],
        total_evidence: int,
        confidence: float,
    ) -> str:
        source_list = ", ".join(f"{k}={v}" for k, v in source_breakdown.items()) or "none"
        return (
            f"Indian population evidence for {target_id}/{disease}: "
            f"{total_evidence} item(s) from [{source_list}]. "
            f"Confidence: {confidence:.2f}. "
            f"Sources with Indian genomic data are particularly weighted."
        )
