"""UMLS (Unified Medical Language System) connector for integrated biomedical terminology."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class UMLSConnector(BaseConnector):
    """
    UMLS (Unified Medical Language System) connector.
    
    UMLS integrates and distributes key terminology, classification and coding
    standards, and associated resources to promote creation of more effective
    and interoperable biomedical information systems and services.
    
    UMLS includes:
    - Metathesaurus: concepts from 200+ source vocabularies
    - Semantic Network: categories and relationships
    - SPECIALIST Lexicon: biomedical terms
    
    Integrates: MeSH, SNOMED CT, ICD-10, RxNorm, LOINC, and many others.
    
    Note: Requires UMLS API key (free registration at UTS).
    """
    
    name = "UMLS"
    BASE_URL = "https://uts-ws.nlm.nih.gov/rest"
    SEARCH_URL = "https://uts-ws.nlm.nih.gov/rest/search/current"
    cache_ttl = 86400  # 24h (UMLS updates quarterly)
    http_timeout = 20.0
    rate_limit_rps = 20.0  # UMLS allows 20 requests/second with API key
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search UMLS for biomedical concepts.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of UMLS concept dictionaries
        """
        # Note: UMLS requires API key authentication
        # This implementation provides structure for integration
        
        params = {
            "string": query,
            "pageSize": min(limit, 100),
            "returnIdType": "concept",
            # "apiKey": os.getenv("UMLS_API_KEY", "")
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        result_data = data.get("result", {})
        items = result_data.get("results", []) if isinstance(result_data, dict) else []
        
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
                
            cui = item.get("ui", "")  # Concept Unique Identifier
            name = item.get("name", "")
            
            # Get source vocabularies
            root_source = item.get("rootSource", "")
            
            # Get semantic types
            uri = item.get("uri", "")
            
            results.append({
                "id": f"UMLS:{cui}",
                "entity_type": "umls_concept",
                "canonical_name": name,
                "name": name,
                "cui": cui,
                "description": name,
                "root_source": root_source,
                "uri": uri,
                "url": f"https://uts.nlm.nih.gov/uts/umls/concept/{cui}",
                "snippet": name,
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://uts.nlm.nih.gov/uts/umls/concept/{cui}",
                    ext_id=cui,
                    confidence=0.98,
                    reasoning="UMLS integrated biomedical terminology concept"
                ).to_dict()],
            })
        
        return results
    
    async def get_concept_details(self, cui: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a UMLS concept.
        
        Args:
            cui: Concept Unique Identifier
            
        Returns:
            Detailed concept information or None
        """
        url = f"{self.BASE_URL}/content/current/CUI/{cui}"
        
        params = {
            # "apiKey": os.getenv("UMLS_API_KEY", "")
        }
        
        data, meta = await self._cached_get(url, params=params)
        
        if not data or not isinstance(data, dict):
            return None
        
        result = data.get("result", {})
        
        return {
            "cui": cui,
            "name": result.get("name", ""),
            "semantic_types": result.get("semanticTypes", []),
            "definitions": result.get("definitions", []),
            "atoms": result.get("atoms", []),
            "relations": result.get("relations", [])
        }
    
    async def count(self, query: str) -> Optional[int]:
        """
        Get count of search results.
        
        Args:
            query: Search query string
            
        Returns:
            Number of results or None
        """
        params = {
            "string": query,
            "pageSize": 0
        }
        
        data, _ = await self._cached_get(self.SEARCH_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        result_data = data.get("result", {})
        return result_data.get("recCount", 0) if isinstance(result_data, dict) else None
