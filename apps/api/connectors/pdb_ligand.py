"""PDB Ligand Expo connector for small molecule ligands in PDB structures."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class PDBLigandConnector(BaseConnector):
    """
    PDB Ligand Expo connector for small molecule ligands.
    
    The Ligand Expo is a data resource for finding information about
    small molecules bound to proteins and nucleic acids in the Protein
    Data Bank (PDB).
    
    Provides:
    - Ligand chemical structures
    - Ligand descriptors
    - Ideal coordinates
    - Chemical component dictionary
    - 2D and 3D representations
    
    Useful for:
    - Drug design
    - Molecular docking
    - Structure-based screening
    """
    
    name = "PDB Ligand"
    BASE_URL = "http://ligand-expo.rcsb.org/ld-search.html"
    API_URL = "https://data.rcsb.org/rest/v1/core/chemcomp"
    cache_ttl = 86400  # 24h (ligand data changes infrequently)
    http_timeout = 20.0
    rate_limit_rps = 10.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search PDB Ligand Expo for ligands.
        
        Args:
            query: Search query string (ligand ID, name)
            limit: Maximum number of results
            
        Returns:
            List of ligand dictionaries
        """
        # Note: Ligand Expo doesn't have a direct search API
        # This implementation uses RCSB PDB chemical component API
        
        # For a proper implementation, would need to:
        # 1. Query RCSB PDB search API for chemical components
        # 2. Filter by query string
        # 3. Fetch details for each component
        
        results: List[Dict[str, Any]] = []
        
        # Example: If query is a 3-letter ligand code, fetch directly
        if len(query) == 3 and query.isalnum():
            ligand_id = query.upper()
            url = f"{self.API_URL}/{ligand_id}"
            
            data, meta = await self._cached_get(url)
            
            if data and isinstance(data, dict):
                chem_comp = data.get("chem_comp", {})
                name = chem_comp.get("name", "") if isinstance(chem_comp, dict) else ""
                formula = chem_comp.get("formula", "") if isinstance(chem_comp, dict) else ""
                
                results.append({
                    "id": f"PDBLigand:{ligand_id}",
                    "entity_type": "ligand",
                    "canonical_name": name,
                    "name": name,
                    "ligand_id": ligand_id,
                    "formula": formula,
                    "description": name,
                    "url": f"http://ligand-expo.rcsb.org/reports/{ligand_id[0]}/{ligand_id}/index.html",
                    "snippet": f"{name} ({formula})",
                    "source": self.name,
                    "provenance": [self._prov(
                        url=f"http://ligand-expo.rcsb.org/reports/{ligand_id[0]}/{ligand_id}/index.html",
                        ext_id=ligand_id,
                        confidence=0.99,
                        reasoning="PDB Ligand Expo chemical component"
                    ).to_dict()],
                })
        
        return results
    
    async def get_ligand_details(self, ligand_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific ligand.
        
        Args:
            ligand_id: 3-letter ligand code
            
        Returns:
            Detailed ligand information or None
        """
        url = f"{self.API_URL}/{ligand_id.upper()}"
        
        data, meta = await self._cached_get(url)
        
        if not data or not isinstance(data, dict):
            return None
        
        chem_comp = data.get("chem_comp", {})
        
        return {
            "ligand_id": ligand_id.upper(),
            "name": chem_comp.get("name", "") if isinstance(chem_comp, dict) else "",
            "formula": chem_comp.get("formula", "") if isinstance(chem_comp, dict) else "",
            "type": chem_comp.get("type", "") if isinstance(chem_comp, dict) else "",
            "weight": chem_comp.get("formula_weight", None) if isinstance(chem_comp, dict) else None
        }
    
    async def count(self, query: str) -> Optional[int]:
        """
        Get count of search results.
        
        Args:
            query: Search query string
            
        Returns:
            Number of results or None
        """
        # Ligand Expo doesn't provide count API
        return None
