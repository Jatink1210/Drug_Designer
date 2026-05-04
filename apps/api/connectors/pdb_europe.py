"""Protein Data Bank Europe (PDBe) connector for protein structure data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class PDBEuropeConnector(BaseConnector):
    """
    Protein Data Bank Europe (PDBe) connector.
    
    PDBe is the European resource for the collection, organization and
    dissemination of data on biological macromolecular structures.
    
    Provides:
    - 3D protein structures
    - Experimental data
    - Validation reports
    - Annotations
    - Ligand information
    """
    
    name = "PDB Europe"
    BASE_URL = "https://www.ebi.ac.uk/pdbe/api"
    SEARCH_URL = "https://www.ebi.ac.uk/pdbe/search/pdb/select"
    cache_ttl = 86400  # 24h (structures change infrequently)
    http_timeout = 20.0
    rate_limit_rps = 10.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search PDBe for protein structures.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of protein structure dictionaries
        """
        params = {
            "q": query,
            "rows": min(limit, 100),
            "wt": "json",
            "fl": "pdb_id,title,experimental_method,resolution,organism_scientific_name,molecule_name"
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        response = data.get("response", {})
        docs = response.get("docs", []) if isinstance(response, dict) else []
        
        for doc in docs[:limit]:
            if not isinstance(doc, dict):
                continue
                
            pdb_id = doc.get("pdb_id", "")
            title = strip_html(doc.get("title", ""))
            
            # Parse experimental method
            exp_method = doc.get("experimental_method", [])
            if isinstance(exp_method, str):
                exp_method = [exp_method]
            
            # Parse organism
            organism = doc.get("organism_scientific_name", [])
            if isinstance(organism, str):
                organism = [organism]
            
            # Parse molecule name
            molecule = doc.get("molecule_name", [])
            if isinstance(molecule, str):
                molecule = [molecule]
            
            results.append({
                "id": f"PDBe:{pdb_id}",
                "entity_type": "protein_structure",
                "canonical_name": title,
                "name": title,
                "pdb_id": pdb_id,
                "title": title,
                "experimental_method": exp_method[0] if exp_method else "",
                "resolution": doc.get("resolution", None),
                "organism": organism[0] if organism else "",
                "molecule_name": molecule[0] if molecule else "",
                "url": f"https://www.ebi.ac.uk/pdbe/entry/pdb/{pdb_id}",
                "snippet": title[:300],
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://www.ebi.ac.uk/pdbe/entry/pdb/{pdb_id}",
                    ext_id=pdb_id,
                    confidence=0.99,
                    reasoning="PDBe curated protein structure"
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
            "rows": 0,
            "wt": "json"
        }
        
        data, _ = await self._cached_get(self.SEARCH_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        response = data.get("response", {})
        return response.get("numFound", 0) if isinstance(response, dict) else None
