"""PeptideAtlas connector for peptide identification and proteomics data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class PeptideAtlasConnector(BaseConnector):
    """
    PeptideAtlas connector for peptide identification and mass spectrometry data.
    
    PeptideAtlas (https://www.peptideatlas.org) is a multi-organism compendium
    of peptides identified in tandem mass spectrometry proteomics experiments.
    
    API: GetProtein CGI script
    No authentication required (free public API).
    """
    
    name = "PeptideAtlas"
    BASE = "https://db.systemsbiology.net/sbeams/cgi/PeptideAtlas"
    cache_ttl = 86400  # 24 hours
    rate_limit_rps = 2.0  # Conservative rate limit
    rate_limit_burst = 5
    http_timeout = 30.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for proteins and their peptides by protein name or accession.
        
        Args:
            query: Protein name, gene symbol, or UniProt accession
            limit: Maximum number of results to return
            
        Returns:
            List of protein records with peptide identification data
        """
        # PeptideAtlas GetProtein API
        url = f"{self.BASE}/GetProtein"
        params = {
            "protein_name": query,
            "atlas_build_id": "490",  # Human PeptideAtlas build
            "apply_action": "QUERY",
            "output_mode": "tsv"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return []
        
        # Parse TSV response
        results: List[Dict[str, Any]] = []
        
        # PeptideAtlas returns TSV data
        if isinstance(data, str):
            lines = data.strip().split('\n')
            if len(lines) < 2:
                return []
            
            headers = lines[0].split('\t')
            for line in lines[1:limit+1]:
                if not line.strip():
                    continue
                    
                values = line.split('\t')
                if len(values) < len(headers):
                    continue
                
                entry = dict(zip(headers, values))
                
                protein_name = entry.get("protein_name", entry.get("biosequence_name", ""))
                protein_acc = entry.get("protein_accession", "")
                gene_symbol = entry.get("gene_symbol", "")
                n_observations = entry.get("n_observations", "0")
                
                results.append({
                    "id": protein_acc or protein_name,
                    "entity_type": "protein",
                    "canonical_name": protein_name,
                    "name": protein_name,
                    "description": f"{protein_name} peptide identifications",
                    "gene_symbol": gene_symbol,
                    "protein_accession": protein_acc,
                    "n_observations": n_observations,
                    "source": self.name,
                    "url": f"{self.BASE}/GetProtein?protein_name={protein_name}&atlas_build_id=490",
                    "provenance": [self._prov(
                        url=f"{self.BASE}/GetProtein?protein_name={protein_name}&atlas_build_id=490",
                        ext_id=protein_acc or protein_name,
                        confidence=0.95,
                        reasoning="PeptideAtlas tandem mass spectrometry peptide identifications"
                    ).to_dict()],
                })
        
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed protein and peptide information by protein accession or name.
        
        Args:
            entity_id: Protein accession or name
            
        Returns:
            Detailed protein record with peptide data
        """
        results = await self.search(entity_id, limit=1)
        return results[0] if results else None

    async def get_peptides(self, protein_name: str) -> Optional[Dict[str, Any]]:
        """
        Get peptide identifications for a specific protein.
        
        Args:
            protein_name: Protein name or accession
            
        Returns:
            Peptide identification data with sequences and observations
        """
        url = f"{self.BASE}/GetProtein"
        params = {
            "protein_name": protein_name,
            "atlas_build_id": "490",
            "apply_action": "QUERY",
            "output_mode": "tsv",
            "display_options": "ShowPeptides"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data or not isinstance(data, str):
            return None
        
        lines = data.strip().split('\n')
        if len(lines) < 2:
            return None
        
        peptides = []
        headers = lines[0].split('\t')
        
        for line in lines[1:]:
            if not line.strip():
                continue
            values = line.split('\t')
            if len(values) < len(headers):
                continue
            
            entry = dict(zip(headers, values))
            peptides.append({
                "peptide_sequence": entry.get("peptide_sequence", ""),
                "n_observations": entry.get("n_observations", "0"),
                "n_samples": entry.get("n_samples", "0"),
                "empirical_proteotypic_score": entry.get("empirical_proteotypic_score", "")
            })
        
        return {
            "protein_name": protein_name,
            "peptides": peptides,
            "total_peptides": len(peptides)
        }

    async def get_protein_coverage(self, protein_name: str) -> Optional[Dict[str, Any]]:
        """
        Get protein sequence coverage from identified peptides.
        
        Args:
            protein_name: Protein name or accession
            
        Returns:
            Protein coverage data with sequence and coverage percentage
        """
        url = f"{self.BASE}/GetProtein"
        params = {
            "protein_name": protein_name,
            "atlas_build_id": "490",
            "apply_action": "QUERY",
            "output_mode": "tsv",
            "display_options": "ShowCoverage"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return None
        
        # Parse coverage data from response
        return {
            "protein_name": protein_name,
            "coverage_data": data
        }

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Extract evidence records for a protein from PeptideAtlas.
        
        Args:
            entity_id: Protein accession or name
            
        Returns:
            List of evidence records with peptide identification data
        """
        protein_data = await self.fetch_by_id(entity_id)
        if not protein_data:
            return []
        
        peptide_data = await self.get_peptides(entity_id)
        
        evidence_items = []
        
        # Protein identification evidence
        evidence_items.append({
            "source": self.name,
            "entity_id": entity_id,
            "evidence_type": "protein_identification",
            "n_observations": protein_data.get("n_observations"),
            "confidence": 0.95,
            "url": protein_data.get("url"),
            "provenance": self._prov(
                url=protein_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.95,
                reasoning="Mass spectrometry-based protein identification"
            ).to_dict()
        })
        
        # Peptide evidence
        if peptide_data and peptide_data.get("peptides"):
            for peptide in peptide_data["peptides"][:10]:  # Limit to top 10 peptides
                evidence_items.append({
                    "source": self.name,
                    "entity_id": entity_id,
                    "evidence_type": "peptide_identification",
                    "peptide_sequence": peptide.get("peptide_sequence"),
                    "n_observations": peptide.get("n_observations"),
                    "confidence": 0.90,
                    "url": protein_data.get("url"),
                    "provenance": self._prov(
                        url=protein_data.get("url", ""),
                        ext_id=entity_id,
                        confidence=0.90,
                        reasoning="Tandem mass spectrometry peptide identification"
                    ).to_dict()
                })
        
        return evidence_items
