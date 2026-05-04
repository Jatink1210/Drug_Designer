"""Human Protein Atlas connector for protein expression and localization data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class HumanProteinAtlasConnector(BaseConnector):
    """
    Human Protein Atlas connector for protein expression, localization, and tissue data.
    
    The Human Protein Atlas (https://www.proteinatlas.org) provides comprehensive
    protein expression data across human tissues, cells, and pathology samples.
    
    API: Search-based with JSON/XML/TSV export
    No authentication required (free public API).
    """
    
    name = "HumanProteinAtlas"
    BASE = "https://www.proteinatlas.org"
    cache_ttl = 86400  # 24 hours
    rate_limit_rps = 3.0  # Conservative rate limit
    rate_limit_burst = 5
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for proteins by gene symbol, Ensembl ID, or protein name.
        
        Args:
            query: Gene symbol (e.g., "FOXP3"), Ensembl ID, or protein name
            limit: Maximum number of results to return
            
        Returns:
            List of protein records with expression and localization data
        """
        # Human Protein Atlas search API
        url = f"{self.BASE}/api/search_download.php"
        params = {
            "search": query,
            "format": "json",
            "columns": "g,eg,up,pe,rnats,rnatd,scl,relih",
            "compress": "no"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return []
        
        results: List[Dict[str, Any]] = []
        entries = data if isinstance(data, list) else [data]
        
        for entry in entries[:limit]:
            gene_name = entry.get("Gene", entry.get("g", ""))
            ensembl_id = entry.get("Ensembl", entry.get("eg", ""))
            uniprot_id = entry.get("Uniprot", entry.get("up", ""))
            protein_evidence = entry.get("Protein evidence", entry.get("pe", ""))
            
            # RNA tissue specificity
            rna_tissue_spec = entry.get("RNA tissue specificity", entry.get("rnats", ""))
            rna_tissue_dist = entry.get("RNA tissue distribution", entry.get("rnatd", ""))
            
            # Subcellular location
            subcell_location = entry.get("Subcellular location", entry.get("scl", ""))
            
            # Reliability
            reliability = entry.get("Reliability (IH)", entry.get("relih", ""))
            
            results.append({
                "id": ensembl_id or gene_name,
                "entity_type": "protein",
                "canonical_name": gene_name,
                "name": gene_name,
                "description": f"{gene_name} protein expression and localization",
                "gene_symbol": gene_name,
                "ensembl_id": ensembl_id,
                "uniprot_id": uniprot_id,
                "protein_evidence": protein_evidence,
                "rna_tissue_specificity": rna_tissue_spec,
                "rna_tissue_distribution": rna_tissue_dist,
                "subcellular_location": subcell_location,
                "reliability": reliability,
                "source": self.name,
                "url": f"{self.BASE}/{ensembl_id}" if ensembl_id else f"{self.BASE}/search/{gene_name}",
                "provenance": [self._prov(
                    url=f"{self.BASE}/{ensembl_id}" if ensembl_id else f"{self.BASE}/search/{gene_name}",
                    ext_id=ensembl_id or gene_name,
                    confidence=0.95,
                    reasoning="Human Protein Atlas immunohistochemistry and RNA-seq data"
                ).to_dict()],
            })
        
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed protein information by Ensembl ID or gene symbol.
        
        Args:
            entity_id: Ensembl ID or gene symbol
            
        Returns:
            Detailed protein record with expression and localization data
        """
        results = await self.search(entity_id, limit=1)
        return results[0] if results else None

    async def get_tissue_expression(self, gene_symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get tissue-specific expression data for a gene.
        
        Args:
            gene_symbol: Gene symbol (e.g., "FOXP3")
            
        Returns:
            Tissue expression data with RNA and protein levels
        """
        # Search with tissue-specific columns
        url = f"{self.BASE}/api/search_download.php"
        params = {
            "search": gene_symbol,
            "format": "json",
            "columns": "g,rnats,rnatd,rnatss,rnatsm",
            "compress": "no"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return None
        
        entry = data[0] if isinstance(data, list) and data else data
        if not entry:
            return None
        
        return {
            "gene_symbol": entry.get("Gene", entry.get("g", "")),
            "rna_tissue_specificity": entry.get("RNA tissue specificity", entry.get("rnats", "")),
            "rna_tissue_distribution": entry.get("RNA tissue distribution", entry.get("rnatd", "")),
            "rna_tissue_specificity_score": entry.get("RNA tissue specificity score", entry.get("rnatss", "")),
            "rna_tissue_specific_ntpm": entry.get("RNA tissue specific nTPM", entry.get("rnatsm", ""))
        }

    async def get_subcellular_location(self, gene_symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get subcellular localization data for a protein.
        
        Args:
            gene_symbol: Gene symbol (e.g., "FOXP3")
            
        Returns:
            Subcellular localization data with reliability scores
        """
        url = f"{self.BASE}/api/search_download.php"
        params = {
            "search": gene_symbol,
            "format": "json",
            "columns": "g,scl,scml,scal,relih,relce",
            "compress": "no"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return None
        
        entry = data[0] if isinstance(data, list) and data else data
        if not entry:
            return None
        
        return {
            "gene_symbol": entry.get("Gene", entry.get("g", "")),
            "subcellular_location": entry.get("Subcellular location", entry.get("scl", "")),
            "subcellular_main_location": entry.get("Subcellular main location", entry.get("scml", "")),
            "subcellular_additional_location": entry.get("Subcellular additional location", entry.get("scal", "")),
            "reliability_ih": entry.get("Reliability (IH)", entry.get("relih", "")),
            "reliability_if": entry.get("Reliability (IF)", entry.get("relce", ""))
        }

    async def get_pathology_data(self, gene_symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get cancer pathology data for a protein.
        
        Args:
            gene_symbol: Gene symbol (e.g., "FOXP3")
            
        Returns:
            Cancer pathology data with prognostic information
        """
        url = f"{self.BASE}/api/search_download.php"
        params = {
            "search": gene_symbol,
            "format": "json",
            "columns": "g,rnacas,rnacad,rnacass",
            "compress": "no"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return None
        
        entry = data[0] if isinstance(data, list) and data else data
        if not entry:
            return None
        
        return {
            "gene_symbol": entry.get("Gene", entry.get("g", "")),
            "rna_cancer_specificity": entry.get("RNA cancer specificity", entry.get("rnacas", "")),
            "rna_cancer_distribution": entry.get("RNA cancer distribution", entry.get("rnacad", "")),
            "rna_cancer_specificity_score": entry.get("RNA cancer specificity score", entry.get("rnacass", ""))
        }

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Extract evidence records for a protein from Human Protein Atlas.
        
        Args:
            entity_id: Ensembl ID or gene symbol
            
        Returns:
            List of evidence records with expression and localization data
        """
        protein_data = await self.fetch_by_id(entity_id)
        if not protein_data:
            return []
        
        evidence_items = []
        
        # Expression evidence
        if protein_data.get("rna_tissue_specificity"):
            evidence_items.append({
                "source": self.name,
                "entity_id": entity_id,
                "evidence_type": "rna_expression",
                "tissue_specificity": protein_data.get("rna_tissue_specificity"),
                "tissue_distribution": protein_data.get("rna_tissue_distribution"),
                "confidence": 0.95,
                "url": protein_data.get("url"),
                "provenance": self._prov(
                    url=protein_data.get("url", ""),
                    ext_id=entity_id,
                    confidence=0.95,
                    reasoning="RNA-seq tissue expression data"
                ).to_dict()
            })
        
        # Localization evidence
        if protein_data.get("subcellular_location"):
            evidence_items.append({
                "source": self.name,
                "entity_id": entity_id,
                "evidence_type": "subcellular_localization",
                "location": protein_data.get("subcellular_location"),
                "reliability": protein_data.get("reliability"),
                "confidence": 0.90,
                "url": protein_data.get("url"),
                "provenance": self._prov(
                    url=protein_data.get("url", ""),
                    ext_id=entity_id,
                    confidence=0.90,
                    reasoning="Immunohistochemistry localization data"
                ).to_dict()
            })
        
        return evidence_items
