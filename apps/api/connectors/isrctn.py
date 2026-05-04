"""ISRCTN Registry connector for clinical trial data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class ISRCTNConnector(BaseConnector):
    """
    ISRCTN Registry connector for international clinical trial data.
    
    ISRCTN (https://www.isrctn.com) is a primary clinical trial registry recognized
    by WHO and ICMJE, providing trial registration and results reporting.
    
    API: RESTful web services
    No authentication required (free public API).
    """
    
    name = "ISRCTN"
    BASE = "https://www.isrctn.com/api"
    cache_ttl = 86400  # 24 hours
    rate_limit_rps = 2.0
    rate_limit_burst = 4
    http_timeout = 30.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for clinical trials."""
        url = f"{self.BASE}/search"
        params = {"q": query, "limit": min(limit, 50)}
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "trials" not in data:
            return []
        
        results: List[Dict[str, Any]] = []
        for trial in data["trials"][:limit]:
            trial_id = trial.get("isrctn_id", "")
            results.append({
                "id": trial_id,
                "entity_type": "clinical_trial",
                "canonical_name": trial.get("title", query),
                "name": trial.get("title", query),
                "description": strip_html(trial.get("condition", "")),
                "isrctn_id": trial_id,
                "status": trial.get("status", ""),
                "phase": trial.get("phase", ""),
                "source": self.name,
                "url": f"https://www.isrctn.com/{trial_id}",
                "provenance": [self._prov(
                    url=f"https://www.isrctn.com/{trial_id}",
                    ext_id=trial_id,
                    confidence=0.93,
                    reasoning="ISRCTN WHO-recognized trial registry"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed trial data by ISRCTN ID."""
        url = f"{self.BASE}/trial/{entity_id}"
        data, meta = await self._cached_get(url)
        if not data:
            return None
        
        return {
            "id": entity_id,
            "entity_type": "clinical_trial",
            "canonical_name": data.get("title", entity_id),
            "name": data.get("title", entity_id),
            "description": strip_html(data.get("condition", "")),
            "isrctn_id": entity_id,
            "status": data.get("status", ""),
            "phase": data.get("phase", ""),
            "interventions": data.get("interventions", []),
            "source": self.name,
            "url": f"https://www.isrctn.com/{entity_id}",
            "provenance": [self._prov(
                url=f"https://www.isrctn.com/{entity_id}",
                ext_id=entity_id,
                confidence=0.93,
                reasoning="ISRCTN detailed trial data"
            ).to_dict()],
        }

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        """Extract evidence records."""
        trial_data = await self.fetch_by_id(entity_id)
        if not trial_data:
            return []
        
        return [{
            "source": self.name,
            "entity_id": entity_id,
            "evidence_type": "clinical_trial",
            "confidence": 0.93,
            "url": trial_data.get("url"),
            "provenance": self._prov(
                url=trial_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.93,
                reasoning="ISRCTN WHO-recognized trial data"
            ).to_dict()
        }]
