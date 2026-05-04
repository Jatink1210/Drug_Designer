"""BindingDB connector for protein-ligand binding affinity data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class BindingDBConnector(BaseConnector):
    """
    BindingDB connector for experimentally measured protein-ligand binding affinities.
    
    BindingDB (https://www.bindingdb.org) is a public database of measured
    binding affinities (Ki, Kd, IC50, EC50) between small molecules and proteins.
    
    API: RESTful web services at bindingdb.org
    No authentication required (free public API).
    """
    
    name = "BindingDB"
    BASE = "https://bindingdb.org/axis2/services/BDBService"
    cache_ttl = 86400  # 24 hours
    rate_limit_rps = 2.0  # Conservative rate limit
    rate_limit_burst = 5
    http_timeout = 30.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for binding data by target name or UniProt ID.
        
        Args:
            query: Target name, gene symbol, or UniProt accession
            limit: Maximum number of results to return
            
        Returns:
            List of binding records with affinity data
        """
        # BindingDB RESTful API endpoint
        url = f"{self.BASE}/getTargetByUniprot"
        params = {
            "uniprot": query,
            "response": "application/json"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return []
        
        results: List[Dict[str, Any]] = []
        
        # Parse BindingDB response
        entries = data if isinstance(data, list) else [data]
        
        for entry in entries[:limit]:
            target_name = entry.get("target_name", entry.get("Target Name", ""))
            uniprot_id = entry.get("uniprot", entry.get("UniProt (SwissProt) Primary ID of Target Chain", query))
            gene_name = entry.get("gene_name", entry.get("Target Source Organism According to Curator or DataSource", ""))
            
            results.append({
                "id": uniprot_id or query,
                "entity_type": "protein_target",
                "canonical_name": target_name or query,
                "name": target_name or query,
                "description": f"{target_name or query} binding affinity data",
                "gene_symbol": gene_name,
                "uniprot_id": uniprot_id,
                "source": self.name,
                "url": f"https://www.bindingdb.org/bind/chemsearch/marvin/MolStructure.jsp?monomerid={uniprot_id}",
                "provenance": [self._prov(
                    url=f"https://www.bindingdb.org/bind/chemsearch/marvin/MolStructure.jsp?monomerid={uniprot_id}",
                    ext_id=uniprot_id or query,
                    confidence=0.95,
                    reasoning="BindingDB experimentally measured binding affinities"
                ).to_dict()],
            })
        
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed binding data by UniProt ID.
        
        Args:
            entity_id: UniProt accession
            
        Returns:
            Detailed binding record with affinity measurements
        """
        results = await self.search(entity_id, limit=1)
        return results[0] if results else None

    async def get_binding_data(
        self, 
        uniprot_id: str, 
        affinity_cutoff: Optional[float] = None,
        affinity_type: str = "IC50"
    ) -> Optional[Dict[str, Any]]:
        """
        Get binding affinity data for a target protein.
        
        Args:
            uniprot_id: UniProt accession
            affinity_cutoff: Optional affinity cutoff in nM (e.g., 1000 for 1 µM)
            affinity_type: Type of affinity measurement (Ki, Kd, IC50, EC50)
            
        Returns:
            Binding data with compounds and affinity values
        """
        url = f"{self.BASE}/getTargetByUniprot"
        params = {
            "uniprot": uniprot_id,
            "response": "application/json"
        }
        
        if affinity_cutoff:
            params["cutoff"] = str(affinity_cutoff)
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return None
        
        return {
            "uniprot_id": uniprot_id,
            "affinity_type": affinity_type,
            "affinity_cutoff": affinity_cutoff,
            "binding_data": data,
            "url": f"https://www.bindingdb.org/bind/chemsearch/marvin/MolStructure.jsp?monomerid={uniprot_id}"
        }

    async def get_ligands_for_target(
        self, 
        uniprot_id: str,
        fda_approved_only: bool = False,
        commercially_available_only: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get ligands that bind to a target protein.
        
        Args:
            uniprot_id: UniProt accession
            fda_approved_only: Return only FDA-approved drugs
            commercially_available_only: Return only commercially available compounds
            
        Returns:
            List of ligands with binding data
        """
        url = f"{self.BASE}/getTargetByUniprot"
        params = {
            "uniprot": uniprot_id,
            "response": "application/json"
        }
        
        if fda_approved_only:
            params["fda"] = "true"
        if commercially_available_only:
            params["commercial"] = "true"
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return None
        
        return {
            "uniprot_id": uniprot_id,
            "fda_approved_only": fda_approved_only,
            "commercially_available_only": commercially_available_only,
            "ligands": data,
            "url": f"https://www.bindingdb.org/bind/chemsearch/marvin/MolStructure.jsp?monomerid={uniprot_id}"
        }

    async def search_by_compound(self, smiles: str, similarity_cutoff: float = 0.9) -> List[Dict[str, Any]]:
        """
        Search for binding data by compound structure similarity.
        
        Args:
            smiles: SMILES string of query compound
            similarity_cutoff: Tanimoto similarity cutoff (0.0-1.0)
            
        Returns:
            List of similar compounds with binding data
        """
        url = f"{self.BASE}/getLigandByCompound"
        params = {
            "smiles": smiles,
            "cutoff": str(similarity_cutoff),
            "response": "application/json"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return []
        
        results: List[Dict[str, Any]] = []
        entries = data if isinstance(data, list) else [data]
        
        for entry in entries:
            results.append({
                "id": entry.get("monomerid", ""),
                "entity_type": "compound",
                "smiles": entry.get("smiles", ""),
                "similarity": entry.get("similarity", 0.0),
                "binding_data": entry,
                "source": self.name,
                "provenance": [self._prov(
                    url="https://www.bindingdb.org",
                    confidence=0.90,
                    reasoning="BindingDB compound similarity search"
                ).to_dict()],
            })
        
        return results

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Extract evidence records for binding data from BindingDB.
        
        Args:
            entity_id: UniProt accession
            
        Returns:
            List of evidence records with binding affinity data
        """
        protein_data = await self.fetch_by_id(entity_id)
        if not protein_data:
            return []
        
        binding_data = await self.get_binding_data(entity_id)
        
        evidence_items = [{
            "source": self.name,
            "entity_id": entity_id,
            "evidence_type": "protein_ligand_binding",
            "confidence": 0.95,
            "url": protein_data.get("url"),
            "provenance": self._prov(
                url=protein_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.95,
                reasoning="Experimentally measured protein-ligand binding affinities"
            ).to_dict()
        }]
        
        return evidence_items
