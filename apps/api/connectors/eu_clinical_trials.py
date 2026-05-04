"""EU Clinical Trials Register connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class EUClinicalTrialsConnector(BaseConnector):
    """
    EU Clinical Trials Register connector for European clinical trial data.
    
    The EU Clinical Trials Register (https://www.clinicaltrialsregister.eu) provides
    information on clinical trials conducted in the European Union (EU), European Economic
    Area (EEA), and other countries.
    
    API: RESTful web services
    No authentication required (free public API).
    """
    
    name = "EU_Clinical_Trials"
    BASE = "https://www.clinicaltrialsregister.eu/ctr-search/rest"
    cache_ttl = 86400  # 24 hours
    rate_limit_rps = 2.0  # Conservative rate limit
    rate_limit_burst = 4
    http_timeout = 30.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for clinical trials by condition, intervention, or sponsor.
        
        Args:
            query: Search term (disease, drug name, sponsor)
            limit: Maximum number of results to return
            
        Returns:
            List of clinical trial records
        """
        url = f"{self.BASE}/search"
        params = {
            "query": query,
            "page": 1,
            "pageSize": min(limit, 50)
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "results" not in data:
            return []
        
        results: List[Dict[str, Any]] = []
        
        for trial in data["results"][:limit]:
            trial_id = trial.get("eudract_number", "")
            trial_title = trial.get("title", query)
            
            results.append({
                "id": trial_id,
                "entity_type": "clinical_trial",
                "canonical_name": trial_title,
                "name": trial_title,
                "description": strip_html(trial.get("medical_condition", "")),
                "eudract_number": trial_id,
                "sponsor": trial.get("sponsor_name", ""),
                "status": trial.get("trial_status", ""),
                "phase": trial.get("phase", ""),
                "start_date": trial.get("start_date", ""),
                "source": self.name,
                "url": f"https://www.clinicaltrialsregister.eu/ctr-search/trial/{trial_id}",
                "provenance": [self._prov(
                    url=f"https://www.clinicaltrialsregister.eu/ctr-search/trial/{trial_id}",
                    ext_id=trial_id,
                    confidence=0.95,
                    reasoning="EU Clinical Trials Register official data"
                ).to_dict()],
            })
        
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed trial data by EudraCT number.
        
        Args:
            entity_id: EudraCT number (e.g., 2020-001234-12)
            
        Returns:
            Detailed clinical trial record
        """
        url = f"{self.BASE}/trial/{entity_id}"
        
        data, meta = await self._cached_get(url)
        if not data:
            return None
        
        trial_title = data.get("title", entity_id)
        
        return {
            "id": entity_id,
            "entity_type": "clinical_trial",
            "canonical_name": trial_title,
            "name": trial_title,
            "description": strip_html(data.get("medical_condition", "")),
            "eudract_number": entity_id,
            "sponsor": data.get("sponsor_name", ""),
            "status": data.get("trial_status", ""),
            "phase": data.get("phase", ""),
            "start_date": data.get("start_date", ""),
            "end_date": data.get("end_date", ""),
            "countries": data.get("countries", []),
            "interventions": data.get("interventions", []),
            "primary_endpoints": data.get("primary_endpoints", []),
            "secondary_endpoints": data.get("secondary_endpoints", []),
            "source": self.name,
            "url": f"https://www.clinicaltrialsregister.eu/ctr-search/trial/{entity_id}",
            "provenance": [self._prov(
                url=f"https://www.clinicaltrialsregister.eu/ctr-search/trial/{entity_id}",
                ext_id=entity_id,
                confidence=0.95,
                reasoning="EU Clinical Trials Register detailed trial data"
            ).to_dict()],
        }

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Extract evidence records for clinical trial data.
        
        Args:
            entity_id: EudraCT number
            
        Returns:
            List of evidence records
        """
        trial_data = await self.fetch_by_id(entity_id)
        if not trial_data:
            return []
        
        return [{
            "source": self.name,
            "entity_id": entity_id,
            "evidence_type": "clinical_trial",
            "confidence": 0.95,
            "phase": trial_data.get("phase"),
            "status": trial_data.get("status"),
            "url": trial_data.get("url"),
            "provenance": self._prov(
                url=trial_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.95,
                reasoning="EU Clinical Trials Register official trial data"
            ).to_dict()
        }]
