"""GTEx (Genotype-Tissue Expression) connector for gene expression data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class GTExConnector(BaseConnector):
    """
    GTEx (Genotype-Tissue Expression) connector.
    
    GTEx is a comprehensive public resource to study tissue-specific gene
    expression and regulation. Samples were collected from 54 non-diseased
    tissue sites across nearly 1000 individuals.
    
    Provides:
    - Gene expression levels across tissues
    - Expression quantitative trait loci (eQTLs)
    - Splicing QTLs (sQTLs)
    - Allele-specific expression
    - Tissue-specific gene regulation
    
    Data source: NIH Common Fund
    """
    
    name = "GTEx"
    BASE_URL = "https://gtexportal.org/api/v2"
    SEARCH_URL = "https://gtexportal.org/api/v2/expression/geneExpression"
    cache_ttl = 86400  # 24h (expression data changes infrequently)
    http_timeout = 30.0
    rate_limit_rps = 5.0
    
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search GTEx for gene expression data.
        
        Args:
            query: Search query string (gene symbol, Ensembl ID)
            limit: Maximum number of results
            
        Returns:
            List of gene expression dictionaries
        """
        params = {
            "geneId": query,
            "datasetId": "gtex_v8"
        }
        
        data, meta = await self._cached_get(self.SEARCH_URL, params=params)
        
        if not data or not isinstance(data, dict):
            return []
        
        results: List[Dict[str, Any]] = []
        
        # GTEx returns expression data by tissue
        gene_expression = data.get("geneExpression", [])
        
        for tissue_expr in gene_expression[:limit]:
            if not isinstance(tissue_expr, dict):
                continue
                
            tissue = tissue_expr.get("tissueSiteDetailId", "")
            tissue_name = tissue_expr.get("tissueSiteDetail", "")
            median_tpm = tissue_expr.get("median", 0)
            gene_symbol = tissue_expr.get("geneSymbol", query)
            
            expr_id = f"{gene_symbol}_{tissue}"
            description = f"{gene_symbol} expression in {tissue_name}"
            
            results.append({
                "id": f"GTEx:{expr_id}",
                "entity_type": "gene_expression",
                "canonical_name": description,
                "name": description,
                "gene_symbol": gene_symbol,
                "tissue": tissue,
                "tissue_name": tissue_name,
                "median_tpm": median_tpm,
                "description": description,
                "url": f"https://gtexportal.org/home/gene/{gene_symbol}",
                "snippet": f"{description} - Median TPM: {median_tpm:.2f}",
                "source": self.name,
                "provenance": [self._prov(
                    url=f"https://gtexportal.org/home/gene/{gene_symbol}",
                    ext_id=expr_id,
                    confidence=0.98,
                    reasoning="GTEx tissue-specific gene expression"
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
            "geneId": query,
            "datasetId": "gtex_v8"
        }
        
        data, _ = await self._cached_get(self.SEARCH_URL, params=params, extra_key="count")
        
        if not data or not isinstance(data, dict):
            return None
        
        gene_expression = data.get("geneExpression", [])
        return len(gene_expression) if isinstance(gene_expression, list) else None
