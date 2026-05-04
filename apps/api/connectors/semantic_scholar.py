"""Semantic Scholar connector — free, optional API key for higher rate limits.

Covers: 200M+ papers, citation graphs, TLDR summaries.
API Reference: https://api.semanticscholar.org/
Set S2_API_KEY env var for higher rate limits (free at https://www.semanticscholar.org/product/api#api-key-form).
"""

from __future__ import annotations
import logging
import os
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector, strip_html

log = logging.getLogger(__name__)


class SemanticScholarConnector(BaseConnector):
    name = "SemanticScholar"
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    cache_ttl = 21600  # 6h

    def _headers(self) -> dict:
        headers = {"User-Agent": "DrugDesigner/1.0"}
        api_key = os.environ.get("S2_API_KEY", "")
        if api_key:
            headers["x-api-key"] = api_key
        return headers

    def __init__(self) -> None:
        super().__init__()
        import httpx
        from core.http_client import ResilientClient
        self._client = ResilientClient(timeout=self.http_timeout)
        self._client._client = httpx.AsyncClient(
            timeout=self.http_timeout,
            follow_redirects=True,
            headers=self._headers(),
        )

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        params = {
            "query": query,
            "limit": min(limit, 100),
            "fields": "title,authors,year,abstract,citationCount,journal,externalIds,url,tldr",
        }
        data, meta = await self._cached_get(f"{self.BASE_URL}/paper/search", params=params)
        if not data or "data" not in data:
            return []
        results = []
        for paper in data["data"]:
            if not paper:
                continue
            ext_ids = paper.get("externalIds") or {}
            pmid = ext_ids.get("PubMed", "")
            doi = ext_ids.get("DOI", "")
            authors = [a.get("name", "") for a in (paper.get("authors") or [])[:5]]
            title = strip_html(paper.get("title") or "")
            results.append({
                "id": paper.get("paperId", ""),
                "entity_type": "publication",
                "canonical_name": title,
                "title": title,
                "authors": authors,
                "journal": (paper.get("journal") or {}).get("name", ""),
                "year": paper.get("year"),
                "pmid": pmid,
                "doi": doi,
                "url": paper.get("url", ""),
                "abstract": strip_html(paper.get("abstract") or "")[:1000],
                "snippet": strip_html((paper.get("tldr") or {}).get("text") or paper.get("abstract") or "")[:300],
                "citation_count": paper.get("citationCount", 0),
                "provenance": [self._prov(
                    url=paper.get("url", ""), ext_id=paper.get("paperId", ""),
                    confidence=1.0, reasoning="Semantic Scholar indexed"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        data, _ = await self._cached_get(
            f"{self.BASE_URL}/paper/{entity_id}",
            params={"fields": "title,authors,year,abstract,citationCount,references,citations,journal,externalIds,url,tldr"},
        )
        return data

    async def count(self, query: str) -> Optional[int]:
        params = {"query": query, "limit": 1, "fields": "title"}
        data, _ = await self._cached_get(f"{self.BASE_URL}/paper/search", params=params, extra_key="count")
        if not data:
            return None
        return data.get("total", 0)
