"""DrugCentral connector for drug information and pharmacology."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class DrugCentralConnector(BaseConnector):
    """
    DrugCentral connector for comprehensive drug information.
    
    DrugCentral provides information on active ingredients, chemical
    entities, pharmaceutical products, drug mode of action, indications,
    and pharmacologic action.
    
    Provides:
    - Drug structures
    - Pharmacological actions
    - Indications
    - Contraindications
    - Drug-drug interactions
    - Adverse effects
    - Dosing information
    - FDA approval information
    
    Data source: University of New Mexico
    """
    
    name = "DrugCentral"
    BASE_URL = "https://drugcentral.org/api/v1"
    SEARCH_URL = "https://drugcentral.org/api/v1/search"
    cache_ttl = 86400  # 24h (drug data changes infrequently)
    http_timeout = 20.0
    rate_limit_rps = 10.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search DrugCentral for drugs.
        
        Args:
            query: Search query string (drug name, indication)
            limit: Maximum number of results
            
        Returns:
            List of drug dictionaries
        """
        params = {
            "q": query,
            "limit": min(limit, 100)
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        items = data.get("results", []) if isinstance(data, dict) else []
        
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
                
            struct_id = item.get("struct_id", "")
            name = item.get("name", "")
            
            # Get indications
            indications = item.get("indications", [])
            if isinstance(indications, str):
                indications = [indications]
            
            # Get pharmacological actions
            actions = item.get("pharmacological_actions", [])
            if isinstance(actions, str):
                actions = [actions]
            
            # Get approval status
            approval = item.get("approval", {})
            fda_approved = approval.get("fda", False) if isinstance(approval, dict) else False
            
            results.append({
                "id": f"DrugCentral:{struct_id}",
                "entity_type": "drug",
                "canonical_name": name,
                "name": name,
                "struct_id": struct_id,
                "description": name,
                "indications": indications[:5] if isinstance(indications, list) else [],
                "pharmacological_actions": actions[:5] if isinstance(actions, list) else [],
                "fda_approved": fda_approved,
                "url": f"https://drugcentral.org/drugcard/{struct_id}",
                "snippet": f"{name} - {', '.join(indications[:2]) if indications else 'No indications'}",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://drugcentral.org/drugcard/{struct_id}",
                    ext_id=str(struct_id),
                    confidence=0.96,
                    reasoning="DrugCentral curated drug information"
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
            "limit": 0
        }
        
        data, _ = await self._cached_get(self.SEARCH_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        return data.get("total", 0)
