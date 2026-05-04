"""PID (Pathway Interaction Database) connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class PIDConnector(BaseConnector):
    """
    PID (Pathway Interaction Database) connector.
    
    PID was a highly-structured, curated collection of information about
    known biomolecular interactions and key cellular processes.
    
    Note: PID was retired by NCI in 2012, but data is archived and
    integrated into other resources like:
    - Reactome
    - WikiPathways
    - Pathway Commons
    
    This connector provides access to archived PID data via Pathway Commons.
    """
    
    name = "PID"
    BASE_URL = "https://www.pathwaycommons.org/pc2"
    SEARCH_URL = "https://www.pathwaycommons.org/pc2/search.json"
    cache_ttl = 86400  # 24h (archived data doesn't change)
    http_timeout = 20.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search PID pathways via Pathway Commons.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of pathway dictionaries
        """
        params = {
            "q": query,
            "type": "pathway",
            "datasource": "pid",
            "page": 0,
            "pageSize": min(limit, 100)
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        search_hit = data.get("searchHit", [])
        
        for hit in search_hit[:limit]:
            if not isinstance(hit, dict):
                continue
                
            uri = hit.get("uri", "")
            name = hit.get("name", "")
            organism = hit.get("organism", "")
            datasource = hit.get("dataSource", [])
            
            # Extract pathway ID from URI
            pathway_id = uri.split("/")[-1] if uri else ""
            
            results.append({
                "id": f"PID:{pathway_id}",
                "entity_type": "pathway",
                "canonical_name": name,
                "name": name,
                "pathway_id": pathway_id,
                "uri": uri,
                "description": name,
                "organism": organism,
                "datasource": datasource,
                "url": f"https://www.pathwaycommons.org/pc2/get?uri={uri}",
                "snippet": name,
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://www.pathwaycommons.org/pc2/get?uri={uri}",
                    ext_id=pathway_id,
                    confidence=0.93,
                    reasoning="PID archived pathway data via Pathway Commons"
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
            "type": "pathway",
            "datasource": "pid",
            "page": 0,
            "pageSize": 0
        }
        
        data, _ = await self._cached_get(self.SEARCH_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        return data.get("numHits", 0)
