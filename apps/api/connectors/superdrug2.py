"""SuperDrug2 connector for 3D drug structures and conformations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class SuperDrug2Connector(BaseConnector):
    """
    SuperDrug2 connector for 3D drug structures.
    
    SuperDrug2 is a database of approved and experimental drugs with
    3D structures and conformations. It includes:
    - 3D drug structures
    - Multiple conformations
    - Binding site information
    - Physicochemical properties
    - Target information
    
    Particularly useful for:
    - Structure-based drug design
    - Molecular docking
    - Virtual screening
    - Drug repurposing
    """
    
    name = "SuperDrug2"
    BASE_URL = "http://cheminfo.charite.de/superdrug2/api"
    SEARCH_URL = "http://cheminfo.charite.de/superdrug2/search"
    cache_ttl = 86400  # 24h (drug structures change infrequently)
    http_timeout = 20.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search SuperDrug2 for drug structures.
        
        Args:
            query: Search query string (drug name, target)
            limit: Maximum number of results
            
        Returns:
            List of drug structure dictionaries
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
                
            drug_id = item.get("superdrug_id", "")
            name = item.get("name", "")
            
            # Get approval status
            status = item.get("status", "")
            
            # Get targets
            targets = item.get("targets", [])
            if isinstance(targets, str):
                targets = [targets]
            
            # Get physicochemical properties
            properties = item.get("properties", {})
            mol_weight = properties.get("molecular_weight", None) if isinstance(properties, dict) else None
            logp = properties.get("logp", None) if isinstance(properties, dict) else None
            
            results.append({
                "id": f"SuperDrug2:{drug_id}",
                "entity_type": "drug_structure",
                "canonical_name": name,
                "name": name,
                "superdrug_id": drug_id,
                "description": name,
                "status": status,
                "targets": targets[:5] if isinstance(targets, list) else [],
                "molecular_weight": mol_weight,
                "logp": logp,
                "url": f"http://cheminfo.charite.de/superdrug2/drugs/{drug_id}",
                "snippet": f"{name} - {status}",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"http://cheminfo.charite.de/superdrug2/drugs/{drug_id}",
                    ext_id=drug_id,
                    confidence=0.94,
                    reasoning="SuperDrug2 3D drug structure"
                ).to_dict()],
            })
        
        return results
    
    async def get_3d_structure(self, drug_id: str, format: str = "sdf") -> Optional[str]:
        """
        Get 3D structure file for a drug.
        
        Args:
            drug_id: SuperDrug2 drug ID
            format: Structure format (sdf, mol2, pdb)
            
        Returns:
            Structure file content or None
        """
        url = f"{self.BASE_URL}/structure/{drug_id}"
        params = {"format": format}
        
        data, meta = await self._cached_get(url, params=params)
        
        if isinstance(data, str):
            return data
        
        return None
    
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
