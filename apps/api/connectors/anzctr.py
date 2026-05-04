"""ANZCTR (Australian New Zealand Clinical Trials Registry) connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class ANZCTRConnector(BaseConnector):
    """ANZCTR connector for Australian/NZ clinical trials."""
    
    name = "ANZCTR"
    SEARCH_URL = "https://www.anzctr.org.au/TrialSearch.aspx"
    cache_ttl = 86400
    http_timeout = 15.0
    rate_limit_rps = 2.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        params = {
            "searchTxt": query,
            "format": "json"
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        trials = data.get("trials", [])
        
        for trial in trials[:limit]:
            trial_id = trial.get("trialid", "")
            title = strip_html(trial.get("title", ""))
            
            results.append({
                "id": f"ANZCTR:{trial_id}",
                "entity_type": "clinical_trial",
                "canonical_name": title,
                "name": title,
                "trial_id": trial_id,
                "title": title,
                "status": trial.get("recruitmentstatus", ""),
                "phase": trial.get("phase", ""),
                "url": f"https://www.anzctr.org.au/Trial/Registration/TrialReview.aspx?id={trial_id}",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://www.anzctr.org.au/Trial/Registration/TrialReview.aspx?id={trial_id}",
                    ext_id=trial_id,
                    confidence=0.9,
                    reasoning="ANZCTR clinical trial"
                ).to_dict()],
            })
        
        return results
