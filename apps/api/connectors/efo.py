"""EFO (Experimental Factor Ontology) connector for disease and phenotype ontology."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class EFOConnector(BaseConnector):
    """
    EFO (Experimental Factor Ontology) connector.
    
    EFO provides a systematic description of experimental variables in studies,
    particularly in functional genomics experiments. It includes:
    - Disease terms
    - Anatomical parts
    - Cell types
    - Developmental stages
    - Experimental factors
    
    Data source: EMBL-EBI Ontology Lookup Service (OLS)
    """
    
    name = "EFO"
    BASE_URL = "https://www.ebi.ac.uk/ols/api/search"
    cache_ttl = 86400  # 24h (ontology data changes infrequently)
    http_timeout = 20.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search EFO for disease and phenotype terms.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of ontology term dictionaries
        """
        params = {
            "q": query,
            "ontology": "efo",
            "rows": min(limit, 100),
            "format": "json"
        }
        
        data, meta = await self._cached_get(self.BASE_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        response = data.get("response", {})
        docs = response.get("docs", []) if isinstance(response, dict) else []
        
        for doc in docs[:limit]:
            if not isinstance(doc, dict):
                continue
                
            term_id = doc.get("obo_id", doc.get("iri", ""))
            label = doc.get("label", "")
            description = strip_html(doc.get("description", [""])[0] if isinstance(doc.get("description"), list) else doc.get("description", ""))
            
            # Parse synonyms
            synonyms = doc.get("synonym", [])
            if isinstance(synonyms, str):
                synonyms = [synonyms]
            
            results.append({
                "id": f"EFO:{term_id}",
                "entity_type": "ontology_term",
                "canonical_name": label,
                "name": label,
                "term_id": term_id,
                "description": description,
                "synonyms": synonyms[:10] if isinstance(synonyms, list) else [],
                "ontology": "EFO",
                "url": doc.get("iri", ""),
                "snippet": description[:300] if description else label,
                "source": self.name,
                "provenance": [self._prov(
                    url=doc.get("iri", ""),
                    ext_id=term_id,
                    confidence=0.98,
                    reasoning="EFO curated ontology term from EMBL-EBI"
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
            "ontology": "efo",
            "rows": 0,
            "format": "json"
        }
        
        data, _ = await self._cached_get(self.BASE_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        response = data.get("response", {})
        return response.get("numFound", 0) if isinstance(response, dict) else None
