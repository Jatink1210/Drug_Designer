"""CATH (Class, Architecture, Topology, Homology) protein structure classification connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class CATHConnector(BaseConnector):
    """CATH connector for protein structure classification."""
    
    name = "CATH"
    SEARCH_URL = "https://www.cathdb.info/search/by_name"
    cache_ttl = 86400  # 24h
    http_timeout = 15.0
    rate_limit_rps = 3.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        params = {
            "name": query,
            "limit": min(limit, 50)
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        domains = data.get("data", [])
        
        for domain in domains[:limit]:
            domain_id = domain.get("domain_id", "")
            name = domain.get("name", "")
            
            results.append({
                "id": f"CATH:{domain_id}",
                "entity_type": "protein_domain",
                "canonical_name": name,
                "name": name,
                "domain_id": domain_id,
                "cath_code": domain.get("cath_code", ""),
                "description": domain.get("description", ""),
                "url": f"https://www.cathdb.info/version/latest/domain/{domain_id}",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://www.cathdb.info/version/latest/domain/{domain_id}",
                    ext_id=domain_id,
                    confidence=1.0,
                    reasoning="CATH domain classification"
                ).to_dict()],
            })
        
        return results
