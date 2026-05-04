"""CrossRef connector — free, no API key needed.

Covers: 130M+ DOI-registered works, citation metadata.
API Reference: https://api.crossref.org/swagger-ui/index.html
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector, strip_html


class CrossRefConnector(BaseConnector):
    name = "CrossRef"
    BASE_URL = "https://api.crossref.org"
    cache_ttl = 21600

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        params = {"query": query, "rows": min(limit, 50)}
        data, meta = await self._cached_get(f"{self.BASE_URL}/works", params=params)
        if not data or "message" not in data:
            return []
        results = []
        for item in data["message"].get("items", []):
            authors = [
                f"{a.get('given', '')} {a.get('family', '')}".strip()
                for a in (item.get("author") or [])[:5]
            ]
            year = None
            date_parts = (item.get("published-print") or item.get("published-online") or {}).get("date-parts", [[]])
            if date_parts and date_parts[0]:
                year = date_parts[0][0]
            title = strip_html((item.get("title") or [""])[0])
            results.append({
                "id": item.get("DOI", ""),
                "entity_type": "publication",
                "canonical_name": title,
                "title": title,
                "authors": authors,
                "journal": (item.get("container-title") or [""])[0],
                "year": year,
                "doi": item.get("DOI", ""),
                "url": item.get("URL", ""),
                "citation_count": item.get("is-referenced-by-count", 0),
                "provenance": [self._prov(
                    url=item.get("URL", ""), ext_id=item.get("DOI", ""),
                    confidence=1.0, reasoning="CrossRef DOI registry"
                ).to_dict()],
            })
        return results

    async def count(self, query: str) -> Optional[int]:
        data, _ = await self._cached_get(
            f"{self.BASE_URL}/works", params={"query": query, "rows": 0}, extra_key="count"
        )
        if not data:
            return None
        return data.get("message", {}).get("total-results", 0)
