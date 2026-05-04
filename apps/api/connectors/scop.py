"""SCOP (Structural Classification of Proteins) connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class SCOPConnector(BaseConnector):
    """
    SCOP (Structural Classification of Proteins) connector.
    
    SCOP provides a detailed and comprehensive description of the structural
    and evolutionary relationships of proteins with known structure.
    
    Hierarchy:
    - Class: Overall shape (all-alpha, all-beta, alpha/beta, etc.)
    - Fold: Major structural similarity
    - Superfamily: Probable common evolutionary origin
    - Family: Clear evolutionary relationship
    - Protein: Different proteins in same family
    - Species: Same protein from different species
    """
    
    name = "SCOP"
    BASE_URL = "https://scop.mrc-lmb.cam.ac.uk/api"
    SEARCH_URL = "https://scop.mrc-lmb.cam.ac.uk/api/search"
    cache_ttl = 86400  # 24h (SCOP updates infrequently)
    http_timeout = 20.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search SCOP for protein classifications.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of SCOP classification dictionaries
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
                
            scop_id = item.get("sunid", "")
            description = strip_html(item.get("description", ""))
            sccs = item.get("sccs", "")  # SCOP concise classification string
            
            # Parse hierarchy level
            level = item.get("type", "")
            
            results.append({
                "id": f"SCOP:{scop_id}",
                "entity_type": "protein_classification",
                "canonical_name": description,
                "name": description,
                "scop_id": scop_id,
                "sccs": sccs,
                "description": description,
                "level": level,
                "url": f"https://scop.mrc-lmb.cam.ac.uk/term/{scop_id}",
                "snippet": description[:300],
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://scop.mrc-lmb.cam.ac.uk/term/{scop_id}",
                    ext_id=str(scop_id),
                    confidence=0.98,
                    reasoning="SCOP curated protein structure classification"
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
