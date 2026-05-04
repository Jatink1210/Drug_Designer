"""TTD (Therapeutic Target Database) connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class TTDConnector(BaseConnector):
    """
    TTD (Therapeutic Target Database) connector.
    
    TTD provides information about known and explored therapeutic protein
    and nucleic acid targets, targeted disease, pathway information, and
    corresponding drugs directed at each of these targets.
    
    Provides:
    - Therapeutic targets
    - Target-disease associations
    - Target-drug associations
    - Clinical development status
    - Pathway information
    """
    
    name = "TTD"
    BASE_URL = "http://db.idrblab.net/ttd/api"
    SEARCH_URL = "http://db.idrblab.net/ttd/search"
    cache_ttl = 86400  # 24h (target data changes infrequently)
    http_timeout = 20.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search TTD for therapeutic targets and drugs.
        
        Args:
            query: Search query string (target name, drug name)
            limit: Maximum number of results
            
        Returns:
            List of target/drug dictionaries
        """
        params = {
            "query": query,
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
                
            ttd_id = item.get("ttd_id", "")
            name = item.get("name", "")
            target_type = item.get("type", "")
            
            # Get associated diseases
            diseases = item.get("diseases", [])
            if isinstance(diseases, str):
                diseases = [diseases]
            
            # Get associated drugs
            drugs = item.get("drugs", [])
            if isinstance(drugs, str):
                drugs = [drugs]
            
            results.append({
                "id": f"TTD:{ttd_id}",
                "entity_type": "therapeutic_target",
                "canonical_name": name,
                "name": name,
                "ttd_id": ttd_id,
                "target_type": target_type,
                "description": name,
                "diseases": diseases[:5] if isinstance(diseases, list) else [],
                "drugs": drugs[:5] if isinstance(drugs, list) else [],
                "url": f"http://db.idrblab.net/ttd/data/target/details/{ttd_id}",
                "snippet": f"{name} - {target_type}",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"http://db.idrblab.net/ttd/data/target/details/{ttd_id}",
                    ext_id=ttd_id,
                    confidence=0.95,
                    reasoning="TTD curated therapeutic target"
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
            "query": query,
            "limit": 0
        }
        
        data, _ = await self._cached_get(self.SEARCH_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        return data.get("total", 0)
