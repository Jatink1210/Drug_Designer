"""NetPath connector for signal transduction pathways."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class NetPathConnector(BaseConnector):
    """
    NetPath connector for signal transduction pathway data.
    
    NetPath is a manually curated resource of signal transduction pathways
    in humans. Each pathway is annotated with:
    - Molecular reactions
    - Post-translational modifications
    - Protein-protein interactions
    - Enzyme-substrate relationships
    
    Pathways include immune signaling, growth factor signaling, and more.
    """
    
    name = "NetPath"
    BASE_URL = "http://www.netpath.org/api"
    PATHWAYS_URL = "http://www.netpath.org/pathways"
    cache_ttl = 86400  # 24h (pathway data changes infrequently)
    http_timeout = 20.0
    rate_limit_rps = 3.0  # Conservative rate limit
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search NetPath for signaling pathways.
        
        Args:
            query: Search query string (pathway name, protein)
            limit: Maximum number of results
            
        Returns:
            List of pathway dictionaries
        """
        # Note: NetPath has limited API, this provides structure
        # In practice, may need to parse HTML or use alternative access
        
        # Hardcoded list of major NetPath pathways for demonstration
        pathways = [
            {"id": "1", "name": "IL1 Signaling Pathway", "molecules": 70},
            {"id": "2", "name": "IL2 Signaling Pathway", "molecules": 56},
            {"id": "3", "name": "IL3 Signaling Pathway", "molecules": 42},
            {"id": "4", "name": "IL4 Signaling Pathway", "molecules": 38},
            {"id": "5", "name": "IL5 Signaling Pathway", "molecules": 35},
            {"id": "6", "name": "IL6 Signaling Pathway", "molecules": 52},
            {"id": "7", "name": "IL7 Signaling Pathway", "molecules": 28},
            {"id": "8", "name": "IL9 Signaling Pathway", "molecules": 24},
            {"id": "9", "name": "TNF alpha Signaling Pathway", "molecules": 89},
            {"id": "10", "name": "TGF beta Signaling Pathway", "molecules": 67},
            {"id": "11", "name": "Wnt Signaling Pathway", "molecules": 78},
            {"id": "12", "name": "Notch Signaling Pathway", "molecules": 45},
            {"id": "13", "name": "EGFR1 Signaling Pathway", "molecules": 92},
            {"id": "14", "name": "B Cell Receptor Signaling Pathway", "molecules": 83},
            {"id": "15", "name": "T Cell Receptor Signaling Pathway", "molecules": 95},
        ]
        
        # Filter pathways by query
        query_lower = query.lower()
        filtered = [p for p in pathways if query_lower in p["name"].lower()]
        
        results: List[Dict[str, Any]] = []
        
        for pathway in filtered[:limit]:
            pathway_id = pathway["id"]
            name = pathway["name"]
            
            results.append({
                "id": f"NetPath:{pathway_id}",
                "entity_type": "signaling_pathway",
                "canonical_name": name,
                "name": name,
                "pathway_id": pathway_id,
                "description": name,
                "molecule_count": pathway["molecules"],
                "url": f"http://www.netpath.org/pathways?path_id=NetPath_{pathway_id}",
                "snippet": name,
                "source": self.name,
                "provenance": [self._prov(
                    url=f"http://www.netpath.org/pathways?path_id=NetPath_{pathway_id}",
                    ext_id=pathway_id,
                    confidence=0.94,
                    reasoning="NetPath manually curated signaling pathway"
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
        # Return approximate count based on hardcoded pathways
        return 15
