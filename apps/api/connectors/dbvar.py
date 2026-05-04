"""dbVar connector for NCBI Database of Genomic Structural Variation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector


class dbVarConnector(BaseConnector):
    """
    dbVar connector for NCBI Database of Genomic Structural Variation.
    
    dbVar (https://www.ncbi.nlm.nih.gov/dbvar) is NCBI's database of genomic
    structural variation including insertions, deletions, duplications, inversions,
    and copy number variants.
    
    API: NCBI E-utilities
    No authentication required (free public API).
    """
    
    name = "dbVar"
    BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    cache_ttl = 86400
    rate_limit_rps = 3.0  # NCBI allows 3 requests per second without API key
    rate_limit_burst = 6
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = f"{self.BASE}/esearch.fcgi"
        params = {
            "db": "dbvar",
            "term": query,
            "retmax": min(limit, 100),
            "retmode": "json"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "esearchresult" not in data or "idlist" not in data["esearchresult"]:
            return []
        
        results: List[Dict[str, Any]] = []
        for variant_id in data["esearchresult"]["idlist"][:limit]:
            results.append({
                "id": variant_id,
                "entity_type": "structural_variant",
                "canonical_name": f"dbVar:{variant_id}",
                "name": f"dbVar:{variant_id}",
                "description": f"dbVar structural variant: {variant_id}",
                "dbvar_id": variant_id,
                "source": self.name,
                "url": f"https://www.ncbi.nlm.nih.gov/dbvar/variants/{variant_id}/",
                "provenance": [self._prov(
                    url=f"https://www.ncbi.nlm.nih.gov/dbvar/variants/{variant_id}/",
                    ext_id=variant_id,
                    confidence=0.96,
                    reasoning="NCBI dbVar structural variation data"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE}/esummary.fcgi"
        params = {
            "db": "dbvar",
            "id": entity_id,
            "retmode": "json"
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "result" not in data or entity_id not in data["result"]:
            return None
        
        variant_data = data["result"][entity_id]
        
        return {
            "id": entity_id,
            "entity_type": "structural_variant",
            "canonical_name": f"dbVar:{entity_id}",
            "name": f"dbVar:{entity_id}",
            "description": variant_data.get("title", f"dbVar structural variant: {entity_id}"),
            "dbvar_id": entity_id,
            "variant_type": variant_data.get("variant_type", ""),
            "chromosome": variant_data.get("chr", ""),
            "start": variant_data.get("start"),
            "stop": variant_data.get("stop"),
            "source": self.name,
            "url": f"https://www.ncbi.nlm.nih.gov/dbvar/variants/{entity_id}/",
            "provenance": [self._prov(
                url=f"https://www.ncbi.nlm.nih.gov/dbvar/variants/{entity_id}/",
                ext_id=entity_id,
                confidence=0.96,
                reasoning="NCBI dbVar detailed structural variation data"
            ).to_dict()],
        }

    async def search_by_region(
        self, 
        chromosome: str,
        start: int,
        end: int,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search for structural variants in a genomic region."""
        query = f"{chromosome}[Chromosome] AND {start}:{end}[Base Position]"
        return await self.search(query, limit=limit)

    async def search_by_gene(
        self, 
        gene_symbol: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search for structural variants affecting a gene."""
        query = f"{gene_symbol}[Gene Name]"
        return await self.search(query, limit=limit)

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        """Extract evidence records for structural variant data."""
        variant_data = await self.fetch_by_id(entity_id)
        if not variant_data:
            return []
        
        return [{
            "source": self.name,
            "entity_id": entity_id,
            "evidence_type": "structural_variant",
            "confidence": 0.96,
            "variant_type": variant_data.get("variant_type"),
            "chromosome": variant_data.get("chromosome"),
            "url": variant_data.get("url"),
            "provenance": self._prov(
                url=variant_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.96,
                reasoning="NCBI dbVar structural variation data"
            ).to_dict()
        }]
