"""NCBI Entrez Utilities connector — gene summaries, taxonomy, etc.

General-purpose access to NCBI databases: Gene, Taxonomy, RefSeq, Protein.
API Reference: https://www.ncbi.nlm.nih.gov/books/NBK25499/
Rate Limits: 3 req/s without API key, 10 req/s with key.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)


class EUtilsNCBIConnector(BaseConnector):
    """NCBI Entrez E-utilities for gene summaries, taxonomy, and cross-references."""

    name = "eutils_ncbi"
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    cache_ttl = 86400 * 3
    http_timeout = 25.0
    rate_limit_rps = 3.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search NCBI Gene database by gene symbol or name."""
        search_data, _meta = await self._cached_get(
            f"{self.BASE_URL}/esearch.fcgi",
            params={
                "db": "gene",
                "term": f"{query}[Gene Symbol] AND (Homo sapiens[Organism])",
                "retmax": min(limit, 100),
                "retmode": "json",
                "sort": "relevance",
            },
        )
        if not search_data or not isinstance(search_data, dict):
            return []
        id_list = search_data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []
        summary_data, _meta2 = await self._cached_get(
            f"{self.BASE_URL}/esummary.fcgi",
            params={
                "db": "gene",
                "id": ",".join(id_list[:limit]),
                "retmode": "json",
            },
            extra_key=",".join(id_list[:limit]),
        )
        if not summary_data or not isinstance(summary_data, dict):
            return []
        results = []
        uid_map = summary_data.get("result", {})
        for uid in uid_map.get("uids", []):
            doc = uid_map.get(uid, {})
            symbol = doc.get("name", "")
            results.append({
                "id": uid,
                "entity_type": "gene",
                "canonical_name": symbol,
                "name": doc.get("description", symbol),
                "description": doc.get("summary", ""),
                "chromosome": doc.get("chromosome", ""),
                "location": doc.get("maplocation", ""),
                "organism": doc.get("organism", {}).get("scientificname", ""),
                "taxid": str(doc.get("organism", {}).get("taxid", "")),
                "other_aliases": doc.get("otheraliases", ""),
                "source_db": "NCBI Gene",
                "url": f"https://www.ncbi.nlm.nih.gov/gene/{uid}",
                "provenance": [self._prov(
                    url=f"https://www.ncbi.nlm.nih.gov/gene/{uid}",
                    ext_id=uid,
                    confidence=0.95,
                    reasoning="NCBI Gene official record",
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entrez_gene_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full gene record from NCBI Gene by Entrez Gene ID."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/efetch.fcgi",
            params={
                "db": "gene",
                "id": entrez_gene_id,
                "rettype": "gene_table",
                "retmode": "json",
            },
            extra_key=entrez_gene_id,
        )
        if not data:
            return None
        # efetch returns raw text for gene_table, fallback to esummary
        summ, _ = await self._cached_get(
            f"{self.BASE_URL}/esummary.fcgi",
            params={"db": "gene", "id": entrez_gene_id, "retmode": "json"},
            extra_key=f"summ_{entrez_gene_id}",
        )
        if not summ or not isinstance(summ, dict):
            return None
        uid_map = summ.get("result", {})
        doc = uid_map.get(entrez_gene_id, {})
        return {
            "id": entrez_gene_id,
            "symbol": doc.get("name", ""),
            "name": doc.get("description", ""),
            "summary": doc.get("summary", ""),
            "chromosome": doc.get("chromosome", ""),
            "map_location": doc.get("maplocation", ""),
            "organism": doc.get("organism", {}).get("scientificname", ""),
            "source_db": "NCBI Gene",
        }
