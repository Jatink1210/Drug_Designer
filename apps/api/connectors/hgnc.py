"""HGNC (HUGO Gene Nomenclature Committee) connector.

Provides official gene symbols, names, locus groups, and cross-references.
API Reference: https://www.genenames.org/help/rest/
Rate Limits: ~10 req/s, no API key required.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)


class HGNCConnector(BaseConnector):
    """Query HGNC REST API for official gene nomenclature."""

    name = "hgnc"
    BASE_URL = "https://rest.genenames.org"
    cache_ttl = 86400 * 7  # 7-day cache — gene names change rarely

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/search/symbol/{query}",
            params={},
            extra_key=query,
        )
        if not data or not isinstance(data, dict):
            return []
        docs = data.get("response", {}).get("docs", [])
        results = []
        for doc in docs[:limit]:
            hgnc_id = doc.get("hgnc_id", "")
            symbol = doc.get("symbol", "")
            results.append({
                "id": hgnc_id,
                "entity_type": "gene",
                "canonical_name": symbol,
                "name": doc.get("name", symbol),
                "description": doc.get("name", ""),
                "locus_group": doc.get("locus_group", ""),
                "locus_type": doc.get("locus_type", ""),
                "location": doc.get("location", ""),
                "entrez_id": doc.get("entrez_id", ""),
                "ensembl_gene_id": doc.get("ensembl_gene_id", ""),
                "uniprot_ids": doc.get("uniprot_ids", []),
                "synonyms": doc.get("alias_symbol", []),
                "source_db": "HGNC",
                "url": f"https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/{hgnc_id}",
                "provenance": [self._prov(
                    url=f"https://rest.genenames.org/fetch/hgnc_id/{hgnc_id}",
                    ext_id=hgnc_id,
                    confidence=1.0,
                    reasoning="HGNC official gene nomenclature",
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, hgnc_id: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed gene record by HGNC ID."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/fetch/hgnc_id/{hgnc_id}"
        )
        if not data or not isinstance(data, dict):
            return None
        docs = data.get("response", {}).get("docs", [])
        if not docs:
            return None
        doc = docs[0]
        return {
            "id": doc.get("hgnc_id", hgnc_id),
            "symbol": doc.get("symbol", ""),
            "name": doc.get("name", ""),
            "locus_group": doc.get("locus_group", ""),
            "locus_type": doc.get("locus_type", ""),
            "status": doc.get("status", ""),
            "location": doc.get("location", ""),
            "location_sortable": doc.get("location_sortable", ""),
            "entrez_id": doc.get("entrez_id", ""),
            "ensembl_gene_id": doc.get("ensembl_gene_id", ""),
            "ucsc_id": doc.get("ucsc_id", ""),
            "uniprot_ids": doc.get("uniprot_ids", []),
            "ccds_id": doc.get("ccds_id", []),
            "refseq_accession": doc.get("refseq_accession", []),
            "gene_group": doc.get("gene_group", []),
            "gene_group_id": doc.get("gene_group_id", []),
            "date_approved_reserved": doc.get("date_approved_reserved", ""),
            "date_modified": doc.get("date_modified", ""),
            "source_db": "HGNC",
        }
