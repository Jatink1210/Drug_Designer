"""PubMed NCBI E-utilities connector — using enhanced base."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector


class PubMedConnector(BaseConnector):
    name = "PubMed"
    ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    cache_ttl = 21600  # 6h

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        params = {"db": "pubmed", "term": query, "retmax": min(limit, 50), "retmode": "json"}
        data, meta = await self._cached_get(self.ESEARCH, params=params)
        if not data:
            return []
        id_list = data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []
        summary_params = {"db": "pubmed", "id": ",".join(id_list), "retmode": "json"}
        summary, _ = await self._cached_get(self.ESUMMARY, params=summary_params)
        if not summary:
            return []
        results: List[Dict[str, Any]] = []
        for pmid in id_list:
            entry = summary.get("result", {}).get(pmid, {})
            if not entry or "error" in entry:
                continue
            authors = [a.get("name", "") for a in entry.get("authors", [])[:5]]
            results.append({
                "id": "PMID:%s" % pmid,
                "entity_type": "publication",
                "canonical_name": entry.get("title", ""),
                "name": entry.get("title", ""),
                "title": entry.get("title", ""),
                "authors": authors,
                "journal": entry.get("fulljournalname", ""),
                "year": int(entry.get("pubdate", "0000")[:4]) if entry.get("pubdate") else None,
                "pmid": pmid,
                "doi": entry.get("elocationid", ""),
                "url": "https://pubmed.ncbi.nlm.nih.gov/%s/" % pmid,
                "snippet": entry.get("title", ""),
                "provenance": [self._prov(
                    url="https://pubmed.ncbi.nlm.nih.gov/%s/" % pmid,
                    ext_id=pmid, confidence=1.0, reasoning="PubMed indexed"
                ).to_dict()],
            })
        return results

    async def count(self, query: str) -> Optional[int]:
        params = {"db": "pubmed", "term": query, "rettype": "count", "retmode": "json"}
        data, _ = await self._cached_get(self.ESEARCH, params=params, extra_key="count")
        if not data:
            return None
        return int(data.get("esearchresult", {}).get("count", 0))


