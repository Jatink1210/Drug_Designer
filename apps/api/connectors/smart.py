"""SMART (Simple Modular Architecture Research Tool) connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class SMARTConnector(BaseConnector):
    """
    SMART (Simple Modular Architecture Research Tool) connector.
    
    SMART allows the identification and annotation of genetically mobile
    domains and the analysis of domain architectures.
    
    Provides:
    - Protein domain identification
    - Domain architectures
    - Phylogenetic distributions
    - Functional annotations
    
    Focuses on:
    - Signaling domains
    - Extracellular domains
    - Chromatin-associated domains
    """
    
    name = "SMART"
    BASE_URL = "http://smart.embl-heidelberg.de"
    SEARCH_URL = "http://smart.embl-heidelberg.de/smart/search.pl"
    cache_ttl = 86400  # 24h (SMART updates infrequently)
    http_timeout = 20.0
    rate_limit_rps = 3.0  # Conservative rate limit
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search SMART for protein domains.
        
        Args:
            query: Search query string (domain name or accession)
            limit: Maximum number of results
            
        Returns:
            List of SMART domain dictionaries
        """
        # Note: SMART has limited API, this provides structure for integration
        # In practice, may need to use InterPro API which includes SMART data
        
        interpro_url = "https://www.ebi.ac.uk/interpro/api/entry/smart"
        params = {
            "search": query,
            "page_size": min(limit, 100)
        }
        
        data, meta = await self._cached_get(interpro_url, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        items = data.get("results", []) if isinstance(data, dict) else []
        
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
                
            metadata = item.get("metadata", {})
            accession = metadata.get("accession", "")
            name = metadata.get("name", "")
            description = strip_html(metadata.get("description", ""))
            
            # Get type
            entry_type = metadata.get("type", "")
            
            results.append({
                "id": f"SMART:{accession}",
                "entity_type": "protein_domain",
                "canonical_name": name,
                "name": name,
                "accession": accession,
                "description": description,
                "type": entry_type,
                "url": f"http://smart.embl-heidelberg.de/smart/do_annotation.pl?DOMAIN={accession}",
                "interpro_url": f"https://www.ebi.ac.uk/interpro/entry/smart/{accession}",
                "snippet": description[:300] if description else name,
                "source": self.name,
                "provenance": [self._prov(
                    url=f"http://smart.embl-heidelberg.de/smart/do_annotation.pl?DOMAIN={accession}",
                    ext_id=accession,
                    confidence=0.97,
                    reasoning="SMART curated protein domain"
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
        interpro_url = "https://www.ebi.ac.uk/interpro/api/entry/smart"
        params = {
            "search": query,
            "page_size": 0
        }
        
        data, _ = await self._cached_get(interpro_url, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        return data.get("count", 0)
