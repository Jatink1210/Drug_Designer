"""WHO ICTRP connector for international clinical trial data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class WHOICTRPConnector(BaseConnector):
    """
    WHO International Clinical Trials Registry Platform (ICTRP) connector.
    
    WHO ICTRP (https://trialsearch.who.int) provides a single point of access to
    clinical trial information from registries worldwide.
    
    API: RESTful web services
    No authentication required (free public API).
    """
    
    name = "WHO_ICTRP"
    BASE = "https://trialsearch.who.int/api"
    cache_ttl = 86400  # 24 hours
    rate_limit_rps = 2.0
    rate_limit_burst = 4
    http_timeout = 30.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for clinical trials across WHO registries."""
        url = f"{self.BASE}/search"
        params = {"q": query, "limit": min(limit, 50)}
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "trials" not in data:
            return []
        
        results: List[Dict[str, Any]] = []
        for trial in data["trials"][:limit]:
            trial_id = trial.get("trial_id", "")
            results.append({
                "id": trial_id,
                "entity_type": "clinical_trial",
                "canonical_name": trial.get("title", query),
                "name": trial.get("title", query),
                "description": strip_html(trial.get("condition", "")),
                "trial_id": trial_id,
                "registry": trial.get("registry", ""),
                "status": trial.get("status", ""),
                "phase": trial.get("phase", ""),
                "source": self.name,
                "url": f"https://trialsearch.who.int/Trial2.aspx?TrialID={trial_id}",
                "provenance": [self._prov(
                    url=f"https://trialsearch.who.int/Trial2.aspx?TrialID={trial_id}",
                    ext_id=trial_id,
                    confidence=0.95,
                    reasoning="WHO ICTRP international trial registry"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed trial data."""
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
            "trial_id": entity_id,
            "registry": data.get("registry", ""),
            "status": data.get("status", ""),
            "phase": data.get("phase", ""),
            "interventions": data.get("interventions", []),
            "source": self.name,
            "url": f"https://trialsearch.who.int/Trial2.aspx?TrialID={entity_id}",
            "provenance": [self._prov(
                url=f"https://trialsearch.who.int/Trial2.aspx?TrialID={entity_id}",
                ext_id=entity_id,
                confidence=0.95,
                reasoning="WHO ICTRP detailed trial data"
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
            "confidence": 0.95,
            "url": trial_data.get("url"),
            "provenance": self._prov(
                url=trial_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.95,
                reasoning="WHO ICTRP international trial data"
            ).to_dict()
        }]
