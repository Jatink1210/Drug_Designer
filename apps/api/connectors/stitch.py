"""STITCH connector for chemical-protein interaction networks."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class STITCHConnector(BaseConnector):
    """
    STITCH connector for chemical-protein interactions.
    
    STITCH is a database of known and predicted interactions between
    chemicals and proteins. It integrates information about interactions
    from metabolic pathways, crystal structures, binding experiments,
    and drug-target relationships.
    
    Provides:
    - Chemical-protein interactions
    - Interaction confidence scores
    - Evidence types
    - Network visualization data
    
    Integrates with STRING for protein-protein interactions.
    """
    
    name = "STITCH"
    BASE_URL = "http://stitch.embl.de/api"
    SEARCH_URL = "http://stitch.embl.de/api/json/interactions"
    cache_ttl = 86400  # 24h (interaction data changes infrequently)
    http_timeout = 20.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search STITCH for chemical-protein interactions.
        
        Args:
            query: Search query string (chemical name, protein name)
            limit: Maximum number of results
            
        Returns:
            List of interaction dictionaries
        """
        # STITCH API requires specific identifiers
        # This provides structure for integration
        
        params = {
            "identifiers": query,
            "species": 9606,  # Human
            "limit": min(limit, 100)
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, list):
            return []
        
        results: List[Dict[str, Any]] = []
        
        for item in data[:limit]:
            if not isinstance(item, dict):
                continue
                
            chemical = item.get("stringId_A", "")
            protein = item.get("stringId_B", "")
            score = item.get("score", 0)
            
            # Parse evidence types
            experimental = item.get("experimental", 0)
            database = item.get("database", 0)
            textmining = item.get("textmining", 0)
            
            interaction_id = f"{chemical}_{protein}"
            description = f"{chemical} interacts with {protein}"
            
            results.append({
                "id": f"STITCH:{interaction_id}",
                "entity_type": "chemical_protein_interaction",
                "canonical_name": description,
                "name": description,
                "chemical": chemical,
                "protein": protein,
                "score": score,
                "experimental_score": experimental,
                "database_score": database,
                "textmining_score": textmining,
                "description": description,
                "url": f"http://stitch.embl.de/cgi/network.pl?identifiers={chemical}%0d{protein}",
                "snippet": description,
                "source": self.name,
                "provenance": [self._prov(
                    url=f"http://stitch.embl.de/cgi/network.pl?identifiers={chemical}%0d{protein}",
                    ext_id=interaction_id,
                    confidence=score / 1000.0,  # STITCH scores are 0-1000
                    reasoning="STITCH chemical-protein interaction"
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
        # STITCH API doesn't provide count endpoint
        return None
