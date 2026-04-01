"""Europe PMC connector (optional, behind toggle)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector


class EuropePMCConnector(BaseConnector):
    name = "EuropePMC"
    BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
    cache_ttl = 43200  # 12h

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = "%s/search" % self.BASE
        params = {
            "query": query,
            "format": "json",
            "pageSize": min(limit, 25),
            "resultType": "core",
        }
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return []
        results: List[Dict[str, Any]] = []
        for article in data.get("resultList", {}).get("result", []):
            pmid = article.get("pmid", "")
            eid = "PMID:%s" % pmid if pmid else article.get("id", "")
            results.append({
                "id": eid,
                "entity_type": "publication",
                "canonical_name": article.get("title", ""),
                "name": article.get("title", ""),
                "title": article.get("title", ""),
                "authors": [
                    a.get("fullName", "") for a in article.get("authorList", {}).get("author", [])[:5]
                ],
                "journal": article.get("journalTitle", ""),
                "year": int(article.get("pubYear", 0)) if article.get("pubYear") else None,
                "pmid": pmid,
                "doi": article.get("doi", ""),
                "abstract": article.get("abstractText", "")[:500],
                "citation_count": article.get("citedByCount"),
                "is_open_access": article.get("isOpenAccess", "N") == "Y",
                "url": "https://europepmc.org/article/MED/%s" % pmid if pmid else "",
                "provenance": [self._prov(
                    url="https://europepmc.org/article/MED/%s" % pmid,
                    ext_id=pmid, confidence=0.95, reasoning="Europe PMC full-text search"
                ).to_dict()],
            })
        return results

    async def count(self, query: str) -> Optional[int]:
        url = "%s/search" % self.BASE
        params = {"query": query, "format": "json", "pageSize": 1}
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return None
        return data.get("hitCount", 0)


