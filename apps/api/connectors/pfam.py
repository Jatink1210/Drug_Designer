"""Pfam (Protein families database) connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class PfamConnector(BaseConnector):
    """
    Pfam connector for protein family classifications.
    
    Pfam is a comprehensive collection of protein families represented by
    multiple sequence alignments and hidden Markov models (HMMs).
    
    Provides:
    - Protein domain families
    - Functional annotations
    - Sequence alignments
    - 3D structures
    - Species distribution
    """
    
    name = "Pfam"
    BASE_URL = "https://www.ebi.ac.uk/interpro/api/entry/pfam"
    SEARCH_URL = "https://www.ebi.ac.uk/interpro/api/entry/pfam"
    cache_ttl = 86400  # 24h (Pfam updates infrequently)
    http_timeout = 20.0
    rate_limit_rps = 10.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search Pfam for protein families.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of Pfam family dictionaries
        """
        params = {
            "search": query,
            "page_size": min(limit, 100)
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
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
            
            # Get type (Family, Domain, Repeat, Motif)
            entry_type = metadata.get("type", "")
            
            results.append({
                "id": f"Pfam:{accession}",
                "entity_type": "protein_family",
                "canonical_name": name,
                "name": name,
                "accession": accession,
                "description": description,
                "type": entry_type,
                "member_databases": metadata.get("member_databases", {}),
                "url": f"https://www.ebi.ac.uk/interpro/entry/pfam/{accession}",
                "snippet": description[:300] if description else name,
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://www.ebi.ac.uk/interpro/entry/pfam/{accession}",
                    ext_id=accession,
                    confidence=0.98,
                    reasoning="Pfam curated protein family"
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
            "search": query,
            "page_size": 0
        }
        
        data, _ = await self._cached_get(self.SEARCH_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        return data.get("count", 0)
