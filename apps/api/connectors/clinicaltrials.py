"""ClinicalTrials.gov v2 connector — using enhanced base."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector


class ClinicalTrialsConnector(BaseConnector):
    name = "ClinicalTrials.gov"
    BASE = "https://clinicaltrials.gov/api/v2"
    cache_ttl = 43200  # 12h

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = "%s/studies" % self.BASE
        params = {"query.term": query, "pageSize": min(limit, 50), "format": "json"}
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return []
        results: List[Dict[str, Any]] = []
        for study in data.get("studies", []):
            proto = study.get("protocolSection", {})
            ident = proto.get("identificationModule", {})
            status_mod = proto.get("statusModule", {})
            design = proto.get("designModule", {})
            conds = proto.get("conditionsModule", {})
            arms = proto.get("armsInterventionsModule", {})
            nct_id = ident.get("nctId", "")
            interventions = [i.get("name", "") for i in arms.get("interventions", [])[:5]]
            enrollment_info = proto.get("designModule", {}).get("enrollmentInfo", {})
            results.append({
                "id": nct_id,
                "entity_type": "clinical_trial",
                "canonical_name": ident.get("briefTitle", ""),
                "name": ident.get("briefTitle", ""),
                "nct_id": nct_id,
                "phase": ", ".join(design.get("phases", [])),
                "status": status_mod.get("overallStatus", ""),
                "conditions": conds.get("conditions", []),
                "interventions": interventions,
                "enrollment": enrollment_info.get("count"),
                "url": "https://clinicaltrials.gov/study/%s" % nct_id,
                "provenance": [self._prov(
                    url="https://clinicaltrials.gov/study/%s" % nct_id,
                    ext_id=nct_id, confidence=1.0, reasoning="ClinicalTrials.gov registry"
                ).to_dict()],
            })
        return results

    async def count(self, query: str) -> Optional[int]:
        url = "%s/studies" % self.BASE
        params = {"query.term": query, "pageSize": 1, "countTotal": "true", "format": "json"}
        data, _ = await self._cached_get(url, params=params, extra_key="count")
        if not data:
            return None
        return data.get("totalCount", 0)


