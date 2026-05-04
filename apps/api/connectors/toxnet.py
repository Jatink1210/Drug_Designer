"""TOXNET connector — HSDB and IRIS toxicology data.

Provides hazardous substance data (HSDB) and EPA IRIS toxicology values.
Note: TOXNET was retired Nov 2019. Data migrated to NLM/PubChem/EPA.
This connector wraps the PubChem BioAssay and EPA CompTox endpoints as replacement.
API Reference: https://comptox.epa.gov/dashboard/api
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)


class TOXNETConnector(BaseConnector):
    """Toxicology data from EPA CompTox (TOXNET successor) and NLM toxicology APIs."""

    name = "toxnet"
    BASE_URL = "https://comptox.epa.gov/dashboard/api"
    cache_ttl = 86400 * 7
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search chemicals by name or CAS number in CompTox."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/chemical/search/equal/{query}",
            params={"limit": min(limit, 50)},
        )
        if not data or not isinstance(data, list):
            return []
        results = []
        for chem in data[:limit]:
            dtxsid = chem.get("dtxsid", "")
            results.append({
                "id": dtxsid,
                "entity_type": "chemical",
                "canonical_name": chem.get("preferredName", chem.get("name", "")),
                "description": chem.get("toxicityCategories", ""),
                "dtxsid": dtxsid,
                "cas_rn": chem.get("casrn", ""),
                "molecular_formula": chem.get("molecularFormula", ""),
                "molecular_weight": chem.get("molecularMass", 0.0),
                "qsar_ready_smiles": chem.get("qsarReadySmiles", ""),
                "hazard_summary": chem.get("hazardSummary", ""),
                "source_db": "EPA CompTox (TOXNET successor)",
                "url": f"https://comptox.epa.gov/dashboard/chemical/details/{dtxsid}",
                "provenance": [self._prov(
                    url=f"https://comptox.epa.gov/dashboard/api/chemical/detail/{dtxsid}",
                    ext_id=dtxsid,
                    confidence=0.85,
                    reasoning="EPA CompTox hazard + toxicology data",
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, dtxsid: str) -> Optional[Dict[str, Any]]:
        """Fetch chemical hazard details by DTXSID."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/chemical/detail/{dtxsid}"
        )
        if not data or not isinstance(data, dict):
            return None
        return {
            "id": dtxsid,
            "preferred_name": data.get("preferredName", ""),
            "cas_rn": data.get("casrn", ""),
            "molecular_formula": data.get("molecularFormula", ""),
            "molecular_weight": data.get("molecularMass", 0.0),
            "smiles": data.get("smiles", ""),
            "inchi": data.get("inchi", ""),
            "inchikey": data.get("inchikey", ""),
            "hazard_summary": data.get("hazardSummary", ""),
            "source_db": "EPA CompTox",
        }

    async def get_toxicity_values(self, dtxsid: str) -> List[Dict[str, Any]]:
        """Get toxicity reference values (TRVs) for a chemical."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/toxicity/search/by-dtxsid/{dtxsid}",
            extra_key=f"tox_{dtxsid}",
        )
        if not data or not isinstance(data, list):
            return []
        return [
            {
                "value": entry.get("toxvalNumeric", ""),
                "unit": entry.get("toxvalUnits", ""),
                "study_type": entry.get("studyType", ""),
                "toxval_type": entry.get("toxvalType", ""),
                "source": entry.get("source", ""),
                "risk_assessment_class": entry.get("riskAssessmentClass", ""),
            }
            for entry in data[:50]
        ]
