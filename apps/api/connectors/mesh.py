"""MeSH (Medical Subject Headings) connector for biomedical vocabulary."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class MeSHConnector(BaseConnector):
    """
    MeSH (Medical Subject Headings) connector.
    
    MeSH is the National Library of Medicine's controlled vocabulary thesaurus
    used for indexing articles in PubMed. It includes:
    - Diseases
    - Chemicals and drugs
    - Analytical techniques
    - Anatomical terms
    - Organisms
    - Biological phenomena
    """
    
    name = "MeSH"
    BASE_URL = "https://id.nlm.nih.gov/mesh/sparql"
    SEARCH_URL = "https://meshb.nlm.nih.gov/api/search"
    cache_ttl = 86400  # 24h (MeSH updates annually)
    http_timeout = 20.0
    rate_limit_rps = 10.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search MeSH for biomedical terms.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of MeSH term dictionaries
        """
        params = {
            "q": query,
            "limit": min(limit, 100),
            "format": "json"
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        items = data.get("results", []) if isinstance(data, dict) else []
        
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
                
            mesh_id = item.get("ui", "")
            heading = item.get("heading", "")
            scope_note = strip_html(item.get("scopeNote", ""))
            
            # Parse tree numbers (hierarchical classification)
            tree_numbers = item.get("treeNumbers", [])
            if isinstance(tree_numbers, str):
                tree_numbers = [tree_numbers]
            
            # Parse terms (synonyms)
            terms = item.get("terms", [])
            synonyms = []
            if isinstance(terms, list):
                for term in terms:
                    if isinstance(term, dict):
                        term_name = term.get("term", "")
                        if term_name and term_name != heading:
                            synonyms.append(term_name)
            
            results.append({
                "id": f"MeSH:{mesh_id}",
                "entity_type": "mesh_term",
                "canonical_name": heading,
                "name": heading,
                "mesh_id": mesh_id,
                "description": scope_note,
                "synonyms": synonyms[:10],
                "tree_numbers": tree_numbers[:5] if isinstance(tree_numbers, list) else [],
                "url": f"https://meshb.nlm.nih.gov/record/ui?ui={mesh_id}",
                "snippet": scope_note[:300] if scope_note else heading,
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://meshb.nlm.nih.gov/record/ui?ui={mesh_id}",
                    ext_id=mesh_id,
                    confidence=0.99,
                    reasoning="NLM MeSH controlled vocabulary term"
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
            "limit": 0,
            "format": "json"
        }
        
        data, _ = await self._cached_get(self.SEARCH_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        return data.get("total", 0)
