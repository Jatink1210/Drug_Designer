"""Harmonizome connector — multi-omics gene-attribute associations.

Aggregates data from 100+ genomics datasets in a unified API.
API Reference: https://maayanlab.cloud/Harmonizome/api/1.0
Rate Limits: ~5 req/s, no API key required.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)


class HarmonizomeConnector(BaseConnector):
    """Query Harmonizome for gene-attribute associations across multiple datasets."""

    name = "harmonizome"
    BASE_URL = "https://maayanlab.cloud/Harmonizome/api/1.0"
    cache_ttl = 86400 * 3
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search genes, attributes, or datasets."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/search",
            params={"q": query, "limit": min(limit, 100)},
        )
        if not data or not isinstance(data, dict):
            return []
        results = []
        # Harmonizome returns gene results
        for gene in data.get("gene", {}).get("results", [])[:limit]:
            gene_symbol = gene.get("symbol", "")
            results.append({
                "id": gene.get("href", "").split("/")[-1] or gene_symbol,
                "entity_type": "gene",
                "canonical_name": gene_symbol,
                "name": gene.get("name", gene_symbol),
                "description": gene.get("description", ""),
                "ncbi_entrez_gene_id": gene.get("ncbiEntrezGeneId", ""),
                "source_db": "Harmonizome",
                "url": f"https://maayanlab.cloud/Harmonizome{gene.get('href', '')}",
                "provenance": [self._prov(
                    url=f"https://maayanlab.cloud/Harmonizome/gene/{gene_symbol}",
                    ext_id=gene_symbol,
                    confidence=0.85,
                    reasoning="Harmonizome multi-omics gene entry",
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, gene_symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch gene details + associations from Harmonizome."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/gene/{gene_symbol}"
        )
        if not data or not isinstance(data, dict):
            return None
        return {
            "id": gene_symbol,
            "symbol": data.get("symbol", gene_symbol),
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "ncbi_entrez_gene_id": data.get("ncbiEntrezGeneId", ""),
            "gene_synonyms": [g.get("name", "") for g in data.get("synonyms", [])],
            "gene_sets": data.get("geneSets", []),
            "source_db": "Harmonizome",
        }

    async def get_gene_associations(self, gene_symbol: str, dataset: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        """Get gene-attribute associations (optionally filtered by dataset)."""
        url = f"{self.BASE_URL}/gene/{gene_symbol}/associations"
        if dataset:
            url = f"{self.BASE_URL}/gene/{gene_symbol}/associations?dataset={dataset}"
        data, _meta = await self._cached_get(url, extra_key=gene_symbol + dataset)
        if not data or not isinstance(data, dict):
            return []
        associations = []
        for assoc in data.get("associations", [])[:limit]:
            associations.append({
                "attribute": assoc.get("attribute", {}).get("name", ""),
                "attribute_id": assoc.get("attribute", {}).get("href", "").split("/")[-1],
                "dataset": assoc.get("dataset", {}).get("name", ""),
                "standardized_value": assoc.get("standardizedValue", 0.0),
                "threshold_value": assoc.get("thresholdValue", 0.0),
                "direction": "+" if assoc.get("thresholdValue", 0) > 0 else "-",
                "source_db": "Harmonizome",
            })
        return associations
