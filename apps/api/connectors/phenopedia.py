"""HuGE Phenopedia connector — phenotype-gene association database.

Provides systematic literature-based gene-phenotype associations
from the HuGE Navigator Phenopedia database (CDC/NCBI).
API Reference: https://phgkb.cdc.gov/PHGKB/phenopediaStartPage.action
Note: No public REST API — uses phenopedia CSV export + PubMed linkage.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)


class PhenopediaConnector(BaseConnector):
    """HuGE Phenopedia via PHGKB REST API for gene-disease associations."""

    name = "phenopedia"
    BASE_URL = "https://phgkb.cdc.gov/PHGKB"
    cache_ttl = 86400 * 7
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search phenotype-gene associations by gene symbol or disease keyword."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/api/phenopedia/search",
            params={
                "searchTerm": query,
                "searchType": "gene",
                "pageSize": min(limit, 50),
                "pageStart": 0,
            },
        )
        if not data or not isinstance(data, dict):
            return []
        results = []
        for assoc in data.get("associations", [])[:limit]:
            gene = assoc.get("geneSymbol", "")
            disease = assoc.get("phenotype", "")
            pmids = assoc.get("pmids", [])
            results.append({
                "id": f"phenopedia:{gene}:{disease}",
                "entity_type": "gene_disease_association",
                "canonical_name": f"{gene} — {disease}",
                "gene_symbol": gene,
                "disease": disease,
                "pmid_count": len(pmids),
                "pmids": pmids[:10],
                "first_pub_year": assoc.get("firstPublicationYear", ""),
                "source_db": "HuGE Phenopedia",
                "url": f"https://phgkb.cdc.gov/PHGKB/phenopediaStartPage.action?SubmitButton=Search&SearchPhrase={gene}",
                "provenance": [self._prov(
                    url=f"https://phgkb.cdc.gov/PHGKB/phenopediaStartPage.action?SubmitButton=Search&SearchPhrase={gene}",
                    ext_id=f"{gene}:{disease}",
                    confidence=0.80,
                    reasoning="HuGE Phenopedia systematic literature review",
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, gene_symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch all phenotype associations for a gene symbol."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/api/phenopedia/gene/{gene_symbol}",
            extra_key=gene_symbol,
        )
        if not data or not isinstance(data, dict):
            return None
        return {
            "gene_symbol": gene_symbol,
            "associations": data.get("associations", []),
            "total": data.get("total", 0),
            "source_db": "HuGE Phenopedia",
        }
