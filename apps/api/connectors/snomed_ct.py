"""SNOMED CT (Systematized Nomenclature of Medicine - Clinical Terms) connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class SNOMEDCTConnector(BaseConnector):
    """
    SNOMED CT connector for clinical terminology.
    
    SNOMED CT is the most comprehensive, multilingual clinical healthcare
    terminology in the world. It includes:
    - Clinical findings
    - Symptoms
    - Diagnoses
    - Procedures
    - Body structures
    - Organisms
    - Substances
    - Pharmaceutical products
    - Devices
    
    Used in electronic health records worldwide.
    """
    
    name = "SNOMED CT"
    BASE_URL = "https://browser.ihtsdotools.org/snowstorm/snomed-ct/browser/MAIN/concepts"
    SEARCH_URL = "https://browser.ihtsdotools.org/snowstorm/snomed-ct/MAIN/concepts"
    cache_ttl = 86400  # 24h (SNOMED updates biannually)
    http_timeout = 20.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search SNOMED CT for clinical terms.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of SNOMED CT concept dictionaries
        """
        params = {
            "term": query,
            "activeFilter": "true",
            "limit": min(limit, 100),
            "expand": "fsn,pt()"
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        items = data.get("items", []) if isinstance(data, dict) else []
        
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
                
            concept_id = item.get("conceptId", "")
            
            # Get preferred term
            pt = item.get("pt", {})
            term = pt.get("term", "") if isinstance(pt, dict) else ""
            
            # Get fully specified name
            fsn = item.get("fsn", {})
            fsn_term = fsn.get("term", "") if isinstance(fsn, dict) else ""
            
            # Use PT as primary name, FSN as description
            name = term or fsn_term
            description = fsn_term if term else ""
            
            # Get semantic tag (category)
            semantic_tag = ""
            if fsn_term and "(" in fsn_term:
                semantic_tag = fsn_term[fsn_term.rfind("(")+1:fsn_term.rfind(")")]
            
            results.append({
                "id": f"SNOMED:{concept_id}",
                "entity_type": "snomed_concept",
                "canonical_name": name,
                "name": name,
                "concept_id": concept_id,
                "description": description,
                "semantic_tag": semantic_tag,
                "fsn": fsn_term,
                "active": item.get("active", True),
                "url": f"https://browser.ihtsdotools.org/?perspective=full&conceptId1={concept_id}",
                "snippet": description[:300] if description else name,
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://browser.ihtsdotools.org/?perspective=full&conceptId1={concept_id}",
                    ext_id=concept_id,
                    confidence=0.99,
                    reasoning="SNOMED CT international clinical terminology standard"
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
            "term": query,
            "activeFilter": "true",
            "limit": 0
        }
        
        data, _ = await self._cached_get(self.SEARCH_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        return data.get("total", 0)
