"""AACT (Aggregate Analysis of ClinicalTrials.gov) connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class AACTConnector(BaseConnector):
    """AACT connector for clinical trials data."""
    
    name = "AACT"
    SEARCH_URL = "https://aact.ctti-clinicaltrials.org/api/studies"
    cache_ttl = 86400
    http_timeout = 15.0
    rate_limit_rps = 3.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        params = {
            "query.term": query,
            "max_rnk": min(limit, 50)
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        studies = data.get("studies", [])
        
        for study in studies[:limit]:
            nct_id = study.get("nct_id", "")
            title = strip_html(study.get("brief_title", ""))
            
            results.append({
                "id": f"AACT:{nct_id}",
                "entity_type": "clinical_trial",
                "canonical_name": title,
                "name": title,
                "nct_id": nct_id,
                "title": title,
                "status": study.get("overall_status", ""),
                "phase": study.get("phase", ""),
                "conditions": study.get("conditions", []),
                "url": f"https://clinicaltrials.gov/ct2/show/{nct_id}",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://clinicaltrials.gov/ct2/show/{nct_id}",
                    ext_id=nct_id,
                    confidence=1.0,
                    reasoning="AACT clinical trial"
                ).to_dict()],
            })
        
        return results
