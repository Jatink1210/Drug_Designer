"""wwPDB (Worldwide Protein Data Bank) connector for global protein structure data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class wwPDBConnector(BaseConnector):
    """
    wwPDB (Worldwide Protein Data Bank) connector.
    
    wwPDB is the global archive for 3D structural data of biological
    macromolecules. It is a collaboration between:
    - RCSB PDB (USA)
    - PDBe (Europe)
    - PDBj (Japan)
    - BMRB (NMR data)
    
    Provides unified access to all deposited protein structures worldwide.
    """
    
    name = "wwPDB"
    BASE_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
    cache_ttl = 86400  # 24h (structures change infrequently)
    http_timeout = 20.0
    rate_limit_rps = 10.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search wwPDB for protein structures.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of protein structure dictionaries
        """
        # wwPDB uses JSON query format
        query_json = {
            "query": {
                "type": "terminal",
                "service": "text",
                "parameters": {
                    "value": query
                }
            },
            "return_type": "entry",
            "request_options": {
                "pager": {
                    "start": 0,
                    "rows": min(limit, 100)
                },
                "results_content_type": ["experimental"],
                "sort": [{"sort_by": "score", "direction": "desc"}]
            }
        }
        
        data, meta = await self._cached_post(
            self.BASE_URL,
            json_data=query_json
        )
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        result_set = data.get("result_set", [])
        
        for item in result_set[:limit]:
            if not isinstance(item, dict):
                continue
                
            pdb_id = item.get("identifier", "")
            
            # Get additional details from summary endpoint
            # For now, use basic information
            
            results.append({
                "id": f"wwPDB:{pdb_id}",
                "entity_type": "protein_structure",
                "canonical_name": pdb_id,
                "name": pdb_id,
                "pdb_id": pdb_id,
                "score": item.get("score", 0),
                "url": f"https://www.rcsb.org/structure/{pdb_id}",
                "snippet": f"PDB structure {pdb_id}",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://www.rcsb.org/structure/{pdb_id}",
                    ext_id=pdb_id,
                    confidence=0.99,
                    reasoning="wwPDB global protein structure archive"
                ).to_dict()],
            })
        
        return results
    
    async def get_structure_details(self, pdb_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a PDB structure.
        
        Args:
            pdb_id: PDB identifier
            
        Returns:
            Detailed structure information or None
        """
        url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
        
        data, meta = await self._cached_get(url)
        
        if not data or not isinstance(data, dict):
            return None
        
        return {
            "pdb_id": pdb_id,
            "title": data.get("struct", {}).get("title", ""),
            "experimental_method": data.get("exptl", [{}])[0].get("method", ""),
            "resolution": data.get("rcsb_entry_info", {}).get("resolution_combined", [None])[0],
            "deposition_date": data.get("rcsb_accession_info", {}).get("deposit_date", ""),
            "release_date": data.get("rcsb_accession_info", {}).get("initial_release_date", "")
        }
    
    async def count(self, query: str) -> Optional[int]:
        """
        Get count of search results.
        
        Args:
            query: Search query string
            
        Returns:
            Number of results or None
        """
        query_json = {
            "query": {
                "type": "terminal",
                "service": "text",
                "parameters": {
                    "value": query
                }
            },
            "return_type": "entry",
            "request_options": {
                "pager": {
                    "start": 0,
                    "rows": 0
                }
            }
        }
        
        data, _ = await self._cached_post(
            self.BASE_URL,
            json_data=query_json,
            extra_key="count"
        )
        
        if not data or not isinstance(data, dict):
            return None
        
        return data.get("total_count", 0)
