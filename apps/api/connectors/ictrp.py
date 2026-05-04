"""ICTRP (International Clinical Trials Registry Platform) connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class ICTRPConnector(BaseConnector):
    """
    ICTRP (International Clinical Trials Registry Platform) connector.
    
    ICTRP is a WHO initiative that provides a single point of access to
    information on clinical trials from registries around the world.
    
    Aggregates data from:
    - ClinicalTrials.gov (USA)
    - EU Clinical Trials Register
    - ISRCTN (UK)
    - ANZCTR (Australia/New Zealand)
    - CTRI (India)
    - And many more national registries
    
    Provides:
    - Trial registration data
    - Study design
    - Recruitment status
    - Outcomes
    - Contact information
    
    Data source: World Health Organization
    """
    
    name = "ICTRP"
    BASE_URL = "https://trialsearch.who.int/api"
    SEARCH_URL = "https://trialsearch.who.int/api/trials"
    cache_ttl = 86400  # 24h (trial data changes infrequently)
    http_timeout = 30.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search ICTRP for clinical trials.
        
        Args:
            query: Search query string (condition, intervention, trial ID)
            limit: Maximum number of results
            
        Returns:
            List of clinical trial dictionaries
        """
        params = {
            "q": query,
            "size": min(limit, 100),
            "from": 0
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        trials = data.get("trials", [])
        
        for trial in trials[:limit]:
            if not isinstance(trial, dict):
                continue
                
            trial_id = trial.get("TrialID", "")
            title = strip_html(trial.get("PublicTitle", ""))
            
            # Get condition
            condition = trial.get("Condition", "")
            
            # Get intervention
            intervention = trial.get("Intervention", "")
            
            # Get recruitment status
            status = trial.get("RecruitmentStatus", "")
            
            # Get phase
            phase = trial.get("Phase", "")
            
            # Get primary registry
            primary_registry = trial.get("PrimaryRegistry", "")
            
            # Get date registered
            date_registered = trial.get("DateRegistered", "")
            
            results.append({
                "id": f"ICTRP:{trial_id}",
                "entity_type": "clinical_trial",
                "canonical_name": title,
                "name": title,
                "trial_id": trial_id,
                "title": title,
                "condition": condition,
                "intervention": intervention,
                "recruitment_status": status,
                "phase": phase,
                "primary_registry": primary_registry,
                "date_registered": date_registered,
                "description": title,
                "url": f"https://trialsearch.who.int/Trial2.aspx?TrialID={trial_id}",
                "snippet": f"{title[:200]} - {status}",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://trialsearch.who.int/Trial2.aspx?TrialID={trial_id}",
                    ext_id=trial_id,
                    confidence=0.97,
                    reasoning="WHO ICTRP registered clinical trial"
                ).to_dict()],
            })
        
        return results
    
    async def count(self, query: str) -> Optional[int]:
        """
        Get count of search results.
        
        Args:
            query: Search query string
            
        Returns:
            Number of results or None
        """
        params = {
            "q": query,
            "size": 0
        }
        
        data, _ = await self._cached_get(self.SEARCH_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        return data.get("total", 0)
