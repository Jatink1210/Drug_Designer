"""CTRI (Clinical Trials Registry - India) connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class CTRIConnector(BaseConnector):
    """CTRI connector for Indian clinical trials."""
    
    name = "CTRI"
    SEARCH_URL = "http://ctri.nic.in/Clinicaltrials/advancesearchmain.php"
    cache_ttl = 86400
    http_timeout = 15.0
    rate_limit_rps = 2.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        params = {
            "search_text": query,
            "format": "json"
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        trials = data.get("trials", [])
        
        for trial in trials[:limit]:
            trial_id = trial.get("trial_id", "")
            title = strip_html(trial.get("title", ""))
            
            results.append({
                "id": f"CTRI:{trial_id}",
                "entity_type": "clinical_trial",
                "canonical_name": title,
                "name": title,
                "trial_id": trial_id,
                "title": title,
                "status": trial.get("status", ""),
                "phase": trial.get("phase", ""),
                "url": f"http://ctri.nic.in/Clinicaltrials/showallp.php?trialid={trial_id}",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"http://ctri.nic.in/Clinicaltrials/showallp.php?trialid={trial_id}",
                    ext_id=trial_id,
                    confidence=0.9,
                    reasoning="CTRI clinical trial"
                ).to_dict()],
            })
        
        return results
