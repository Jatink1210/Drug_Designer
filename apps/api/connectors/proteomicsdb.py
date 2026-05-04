"""ProteomicsDB connector for protein expression and quantification data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class ProteomicsDBConnector(BaseConnector):
    """
    ProteomicsDB connector for mass spectrometry-based protein quantification.
    
    ProteomicsDB (https://www.proteomicsdb.org) provides comprehensive protein
    expression data across human tissues, cell lines, and body fluids.
    
    API Documentation: https://www.proteomicsdb.org/proteomicsdb/#api
    No authentication required (free public API).
    """
    
    name = "ProteomicsDB"
    BASE = "https://www.proteomicsdb.org/proteomicsdb/logic/api"
    cache_ttl = 86400  # 24 hours
    rate_limit_rps = 3.0  # Conservative rate limit
    rate_limit_burst = 5
    http_timeout = 30.0  # Longer timeout for large datasets

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for proteins by gene symbol, UniProt ID, or protein name.
        
        Args:
            query: Gene symbol (e.g., "FOXP3"), UniProt ID, or protein name
            limit: Maximum number of results to return
            
        Returns:
            List of protein records with expression data
        """
        # ProteomicsDB uses protein filter parameter
        url = f"{self.BASE}/proteinpeptideresult.xsodata/InputParams(PROTEINFILTER='{query}')/Results"
        params = {
            "$select": "UNIQUE_IDENTIFIER,PROTEIN_NAME,GENE_NAME,ORGANISM",
            "$format": "json",
            "$top": min(limit, 100)
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return []
        
        results: List[Dict[str, Any]] = []
        entries = data.get("d", {}).get("results", [])
        
        for entry in entries[:limit]:
            protein_id = entry.get("UNIQUE_IDENTIFIER", "")
            protein_name = strip_html(entry.get("PROTEIN_NAME", ""))
            gene_name = entry.get("GENE_NAME", "")
            organism = entry.get("ORGANISM", "Homo sapiens")
            
            results.append({
                "id": protein_id,
                "entity_type": "protein",
                "canonical_name": protein_name or protein_id,
                "name": protein_name or protein_id,
                "description": f"{protein_name} ({gene_name})" if gene_name else protein_name,
                "gene_symbol": gene_name,
                "uniprot_id": protein_id if protein_id.startswith(("P", "Q", "O")) else None,
                "organism": organism,
                "source": self.name,
                "url": f"https://www.proteomicsdb.org/proteomicsdb/#protein/proteinDetails/{protein_id}",
                "provenance": [self._prov(
                    url=f"https://www.proteomicsdb.org/proteomicsdb/#protein/proteinDetails/{protein_id}",
                    ext_id=protein_id,
                    confidence=0.95,
                    reasoning="ProteomicsDB mass spectrometry-based protein quantification"
                ).to_dict()],
            })
        
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed protein information by UniProt ID or ProteomicsDB ID.
        
        Args:
            entity_id: UniProt accession or ProteomicsDB protein identifier
            
        Returns:
            Detailed protein record with expression data
        """
        results = await self.search(entity_id, limit=1)
        return results[0] if results else None

    async def get_protein_expression(
        self, 
        protein_id: str, 
        tissue_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get protein expression data across tissues or for a specific tissue.
        
        Args:
            protein_id: UniProt accession or protein identifier
            tissue_id: Optional tissue ID to filter results
            
        Returns:
            Expression data with normalized and unnormalized values
        """
        if tissue_id:
            # Get expression for specific tissue
            url = f"{self.BASE}/proteinspertissue.xsodata/InputParams(TISSUE_ID='{tissue_id}',CALCULATION_METHOD=0,SWISSPROT_ONLY=1,NO_ISOFORM=1)/Results"
            params = {
                "$select": "ENTRY_NAME,UNIQUE_IDENTIFIER,PROTEIN_DESCRIPTION,PEPTIDES,SAMPLE_NAME,NORMALIZED_EXPRESSION,UNNORMALIZED_EXPRESSION",
                "$filter": f"UNIQUE_IDENTIFIER eq '{protein_id}'",
                "$format": "json"
            }
        else:
            # Get expression across all tissues
            url = f"{self.BASE}/proteinexpression.xsodata/InputParams(PROTEINFILTER='{protein_id}')/Results"
            params = {
                "$select": "UNIQUE_IDENTIFIER,TISSUE_NAME,TISSUE_ID,NORMALIZED_EXPRESSION,SAMPLE_NAME",
                "$format": "json"
            }
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return None
        
        entries = data.get("d", {}).get("results", [])
        if not entries:
            return None
        
        # Aggregate expression data
        expression_data = {
            "protein_id": protein_id,
            "tissues": [],
            "samples": []
        }
        
        for entry in entries:
            tissue_name = entry.get("TISSUE_NAME", entry.get("SAMPLE_NAME", "Unknown"))
            normalized_expr = entry.get("NORMALIZED_EXPRESSION", 0)
            
            expression_data["samples"].append({
                "tissue": tissue_name,
                "tissue_id": entry.get("TISSUE_ID"),
                "sample_name": entry.get("SAMPLE_NAME"),
                "normalized_expression": normalized_expr,
                "unnormalized_expression": entry.get("UNNORMALIZED_EXPRESSION"),
                "peptides": entry.get("PEPTIDES")
            })
        
        return expression_data

    async def get_tissues(self) -> List[Dict[str, Any]]:
        """
        Get list of all available tissues with expression data.
        
        Returns:
            List of tissue records with metadata
        """
        url = f"{self.BASE}/tissuelist.xsodata/CA_AVAILABLEBIOLOGICALSOURCES_API"
        params = {
            "$select": "TISSUE_ID,TISSUE_NAME,TISSUE_GROUP_NAME,TISSUE_CATEGORY,SCOPE_NAME,QUANTIFICATION_METHOD_NAME,MS_LEVEL",
            "$format": "json"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return []
        
        entries = data.get("d", {}).get("results", [])
        
        tissues = []
        for entry in entries:
            tissues.append({
                "tissue_id": entry.get("TISSUE_ID"),
                "tissue_name": entry.get("TISSUE_NAME"),
                "tissue_group": entry.get("TISSUE_GROUP_NAME"),
                "category": entry.get("TISSUE_CATEGORY"),
                "scope": entry.get("SCOPE_NAME"),
                "quantification_method": entry.get("QUANTIFICATION_METHOD_NAME"),
                "ms_level": entry.get("MS_LEVEL")
            })
        
        return tissues

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Extract evidence records for a protein from ProteomicsDB.
        
        Args:
            entity_id: UniProt accession or protein identifier
            
        Returns:
            List of evidence records with expression data
        """
        expression_data = await self.get_protein_expression(entity_id)
        if not expression_data:
            return []
        
        evidence_items = []
        for sample in expression_data.get("samples", []):
            evidence_items.append({
                "source": self.name,
                "entity_id": entity_id,
                "evidence_type": "protein_expression",
                "tissue": sample.get("tissue"),
                "normalized_expression": sample.get("normalized_expression"),
                "sample_name": sample.get("sample_name"),
                "confidence": 0.95,
                "url": f"https://www.proteomicsdb.org/proteomicsdb/#protein/proteinDetails/{entity_id}",
                "provenance": self._prov(
                    url=f"https://www.proteomicsdb.org/proteomicsdb/#protein/proteinDetails/{entity_id}",
                    ext_id=entity_id,
                    confidence=0.95,
                    reasoning="Mass spectrometry-based protein quantification"
                ).to_dict()
            })
        
        return evidence_items
