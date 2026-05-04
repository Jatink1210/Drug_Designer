"""G-10: Safety Sentinel specialist.

Adverse event signal detection from ClinicalTrials.gov + ClinVar + FDA data.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)

# Severity keywords mapped to score
_SEVERITY_MAP = {
    "death": 1.0,
    "fatal": 1.0,
    "serious adverse": 0.85,
    "severe": 0.75,
    "hospitali": 0.7,
    "adverse event": 0.5,
    "side effect": 0.4,
    "toxicity": 0.6,
    "hepatotoxic": 0.8,
    "cardiotoxic": 0.8,
    "nephrotoxic": 0.75,
}


class SafetySentinelSpecialist:
    """Specialist: aggregates adverse event signals and issues safety alerts.

    Sources:
    - ClinicalTrials.gov adverse events
    - ClinVar pathogenic variants
    - FDA MedWatch / drugcentral toxicology
    """

    ROLE_ID = "safety_sentinel"

    def __init__(self, engine: Optional[Any] = None) -> None:
        self.engine = engine
        log.info("safety_sentinel_initialized")

    async def assess(
        self,
        compound_name: str,
        gene_symbol: Optional[str] = None,
        submit_vote: bool = False,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Assess safety signals for a compound.

        Args:
            compound_name: Drug or compound name / SMILES
            gene_symbol: Optional target gene symbol for ClinVar lookup
            submit_vote: Submit MAV vote if True
            run_id: Run ID for MAV

        Returns:
            Dict with: alerts, severity_score, signal_sources, risk_level, specialist
        """
        alerts: List[Dict[str, Any]] = []
        signal_sources: List[str] = []

        ct_alerts = await self._scan_clinicaltrials(compound_name)
        alerts.extend(ct_alerts)
        if ct_alerts:
            signal_sources.append("clinicaltrials")

        if gene_symbol:
            cv_alerts = await self._scan_clinvar(gene_symbol)
            alerts.extend(cv_alerts)
            if cv_alerts:
                signal_sources.append("clinvar")

        dc_alerts = await self._scan_drugcentral(compound_name)
        alerts.extend(dc_alerts)
        if dc_alerts:
            signal_sources.append("drugcentral")

        severity_score = self._compute_severity(alerts)
        risk_level = self._risk_level(severity_score)

        if submit_vote and run_id:
            verdict = "oppose" if severity_score > 0.7 else ("uncertain" if severity_score > 0.4 else "support")
            log.info(
                "safety_sentinel_vote",
                run_id=run_id,
                compound=compound_name,
                verdict=verdict,
                severity=severity_score,
            )

        return {
            "status": "ok",
            "compound_name": compound_name,
            "alerts": alerts[:20],
            "total_alerts": len(alerts),
            "severity_score": round(severity_score, 4),
            "risk_level": risk_level,
            "signal_sources": signal_sources,
            "specialist": self.ROLE_ID,
        }

    async def _scan_clinicaltrials(self, compound: str) -> List[Dict[str, Any]]:
        alerts: List[Dict[str, Any]] = []
        try:
            from connectors.clinicaltrials import ClinicalTrialsConnector

            conn = ClinicalTrialsConnector()
            results = await conn.search(f"{compound} adverse events", limit=20)
            await conn.close()
            for r in results or []:
                if isinstance(r, dict):
                    text = " ".join(str(v) for v in r.values()).lower()
                    severity = self._text_severity(text)
                    if severity > 0:
                        alerts.append(
                            {"source": "clinicaltrials", "nct_id": r.get("nctId", ""), "severity": severity, "snippet": text[:200]}
                        )
        except Exception as exc:
            log.warning("safety_sentinel_ct_failed", compound=compound, error=str(exc))
        return alerts

    async def _scan_clinvar(self, gene: str) -> List[Dict[str, Any]]:
        alerts: List[Dict[str, Any]] = []
        try:
            from connectors.clinvar import ClinVarConnector

            conn = ClinVarConnector()
            results = await conn.search(gene, limit=20)
            await conn.close()
            for r in results or []:
                if isinstance(r, dict):
                    sig = r.get("clinical_significance", "").lower()
                    if "pathogenic" in sig or "risk factor" in sig:
                        alerts.append(
                            {"source": "clinvar", "variant_id": r.get("id", ""), "significance": sig, "severity": 0.65}
                        )
        except Exception as exc:
            log.warning("safety_sentinel_clinvar_failed", gene=gene, error=str(exc))
        return alerts

    async def _scan_drugcentral(self, compound: str) -> List[Dict[str, Any]]:
        alerts: List[Dict[str, Any]] = []
        try:
            from connectors.drugcentral import DrugCentralConnector

            conn = DrugCentralConnector()
            results = await conn.search(compound, limit=10)
            await conn.close()
            for r in results or []:
                if isinstance(r, dict):
                    text = " ".join(str(v) for v in r.values()).lower()
                    severity = self._text_severity(text)
                    if severity > 0:
                        alerts.append(
                            {"source": "drugcentral", "drug_id": r.get("id", ""), "severity": severity, "snippet": text[:200]}
                        )
        except Exception as exc:
            log.warning("safety_sentinel_dc_failed", compound=compound, error=str(exc))
        return alerts

    def _text_severity(self, text: str) -> float:
        max_sev = 0.0
        for kw, score in _SEVERITY_MAP.items():
            if kw in text:
                max_sev = max(max_sev, score)
        return max_sev

    def _compute_severity(self, alerts: List[Dict[str, Any]]) -> float:
        if not alerts:
            return 0.0
        return min(1.0, sum(a.get("severity", 0.0) for a in alerts) / (len(alerts) + 1))

    def _risk_level(self, score: float) -> str:
        if score >= 0.75:
            return "HIGH"
        if score >= 0.45:
            return "MODERATE"
        if score > 0:
            return "LOW"
        return "NONE"
