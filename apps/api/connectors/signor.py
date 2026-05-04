"""SIGNOR (SIGnaling Network Open Resource) connector for signaling pathways."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class SIGNORConnector(BaseConnector):
    """
    SIGNOR connector for signaling pathway data.
    
    SIGNOR is a comprehensive resource of causal relationships between
    biological entities with a focus on signaling pathways.
    
    Provides:
    - Protein-protein interactions
    - Post-translational modifications
    - Transcriptional regulation
    - Signaling cascades
    - Pathway diagrams
    
    Manually curated from literature.
    """
    
    name = "SIGNOR"
    BASE_URL = "https://signor.uniroma2.it/api"
    SEARCH_URL = "https://signor.uniroma2.it/api/search"
    cache_ttl = 86400  # 24h (signaling data changes infrequently)
    http_timeout = 20.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search SIGNOR for signaling interactions.
        
        Args:
            query: Search query string (protein name, gene symbol)
            limit: Maximum number of results
            
        Returns:
            List of signaling interaction dictionaries
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
                
            interaction_id = item.get("signor_id", "")
            entity_a = item.get("entityA", "")
            entity_b = item.get("entityB", "")
            mechanism = item.get("mechanism", "")
            effect = item.get("effect", "")
            
            # Build interaction description
            description = f"{entity_a} {mechanism} {entity_b} ({effect})"
            
            results.append({
                "id": f"SIGNOR:{interaction_id}",
                "entity_type": "signaling_interaction",
                "canonical_name": description,
                "name": description,
                "signor_id": interaction_id,
                "entity_a": entity_a,
                "entity_b": entity_b,
                "mechanism": mechanism,
                "effect": effect,
                "description": description,
                "url": f"https://signor.uniroma2.it/relation_result.php?id={interaction_id}",
                "snippet": description,
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://signor.uniroma2.it/relation_result.php?id={interaction_id}",
                    ext_id=interaction_id,
                    confidence=0.95,
                    reasoning="SIGNOR manually curated signaling interaction"
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
