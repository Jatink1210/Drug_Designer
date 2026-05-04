"""NCBI GEO (Gene Expression Omnibus) connector.

Access gene expression datasets from NCBI GEO via Entrez E-utilities.
API Reference: https://www.ncbi.nlm.nih.gov/books/NBK25499/
Rate Limits: 3 req/s without API key, 10 req/s with key.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)


class GEONCBIConnector(BaseConnector):
    """Query NCBI GEO for gene expression datasets and series."""

    name = "geo_ncbi"
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    cache_ttl = 86400 * 2
    http_timeout = 25.0
    rate_limit_rps = 3.0  # Conservative without API key

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search GEO datasets by keyword or gene symbol."""
        # Step 1: esearch to get IDs
        search_data, _meta = await self._cached_get(
            f"{self.BASE_URL}/esearch.fcgi",
            params={
                "db": "gds",
                "term": f"{query}[Gene Symbol] OR {query}[All Fields]",
                "retmax": min(limit, 200),
                "retmode": "json",
                "usehistory": "n",
            },
        )
        if not search_data or not isinstance(search_data, dict):
            return []
        id_list = search_data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []

        # Step 2: esummary to get metadata
        summary_data, _meta2 = await self._cached_get(
            f"{self.BASE_URL}/esummary.fcgi",
            params={
                "db": "gds",
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
            acc = doc.get("accession", f"GEO{uid}")
            title = doc.get("title", "")
            results.append({
                "id": acc,
                "entity_type": "expression_dataset",
                "canonical_name": acc,
                "description": title,
                "organism": doc.get("taxon", ""),
                "type": doc.get("gdstype", ""),
                "n_samples": doc.get("n_samples", 0),
                "platform": doc.get("platform", ""),
                "pub_date": doc.get("pdat", ""),
                "pmids": doc.get("pubmedids", []),
                "source_db": "NCBI GEO",
                "url": f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={acc}",
                "provenance": [self._prov(
                    url=f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={acc}",
                    ext_id=acc,
                    confidence=0.85,
                    reasoning="NCBI GEO expression dataset",
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, geo_accession: str) -> Optional[Dict[str, Any]]:
        """Fetch GEO series/dataset by accession (GSE*, GDS*, GPL*)."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/esearch.fcgi",
            params={
                "db": "gds",
                "term": geo_accession,
                "retmode": "json",
            },
            extra_key=geo_accession,
        )
        if not data or not isinstance(data, dict):
            return None
        ids = data.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return None
        summ, _ = await self._cached_get(
            f"{self.BASE_URL}/esummary.fcgi",
            params={"db": "gds", "id": ids[0], "retmode": "json"},
            extra_key=ids[0],
        )
        if not summ or not isinstance(summ, dict):
            return None
        uid_map = summ.get("result", {})
        doc = uid_map.get(ids[0], {})
        return {
            "accession": geo_accession,
            "title": doc.get("title", ""),
            "organism": doc.get("taxon", ""),
            "type": doc.get("gdstype", ""),
            "n_samples": doc.get("n_samples", 0),
            "summary": doc.get("summary", ""),
            "source_db": "NCBI GEO",
        }
