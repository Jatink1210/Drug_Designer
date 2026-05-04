"""ZINC connector for commercially available compounds for virtual screening."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class ZINCConnector(BaseConnector):
    """
    ZINC connector for commercially available compounds.
    
    ZINC is a free database of commercially-available compounds for
    virtual screening. It contains over 230 million purchasable compounds
    in ready-to-dock, 3D formats.
    
    Provides:
    - Compound structures
    - Vendor information
    - Physicochemical properties
    - Biological annotations
    - 3D conformations
    
    Particularly useful for:
    - Virtual screening
    - Drug discovery
    - Lead optimization
    """
    
    name = "ZINC"
    BASE_URL = "https://zinc.docking.org/api"
    SEARCH_URL = "https://zinc.docking.org/substances/search"
    cache_ttl = 86400  # 24h (compound data changes infrequently)
    http_timeout = 30.0  # ZINC can be slow
    rate_limit_rps = 2.0  # Conservative rate limit
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search ZINC for compounds.
        
        Args:
            query: Search query string (SMILES, name, ZINC ID)
            limit: Maximum number of results
            
        Returns:
            List of compound dictionaries
        """
        params = {
            "q": query,
            "count": min(limit, 100)
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        items = data.get("results", []) if isinstance(data, dict) else []
        
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
                
            zinc_id = item.get("zinc_id", "")
            name = item.get("name", zinc_id)
            smiles = item.get("smiles", "")
            
            # Get physicochemical properties
            properties = item.get("properties", {})
            mw = properties.get("mw", None) if isinstance(properties, dict) else None
            logp = properties.get("logp", None) if isinstance(properties, dict) else None
            
            # Get purchasability
            purchasable = item.get("purchasable", False)
            
            results.append({
                "id": f"ZINC:{zinc_id}",
                "entity_type": "compound",
                "canonical_name": name,
                "name": name,
                "zinc_id": zinc_id,
                "smiles": smiles,
                "description": name,
                "molecular_weight": mw,
                "logp": logp,
                "purchasable": purchasable,
                "url": f"https://zinc.docking.org/substances/{zinc_id}",
                "snippet": f"{name} - {smiles[:50] if smiles else 'No SMILES'}",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://zinc.docking.org/substances/{zinc_id}",
                    ext_id=zinc_id,
                    confidence=0.96,
                    reasoning="ZINC commercially available compound"
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
            "count": 0
        }
        
        data, _ = await self._cached_get(self.SEARCH_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        return data.get("total", 0)
