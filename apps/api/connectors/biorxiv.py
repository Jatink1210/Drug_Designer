"""bioRxiv / medRxiv connector (§45 Literature family).

Uses the bioRxiv Content API (api.biorxiv.org) for preprint access.
"""

from __future__ import annotations

from typing import Any, Dict, List

import structlog

from connectors.base import BaseConnector

log = structlog.get_logger()

BIORXIV_API = "https://api.biorxiv.org"


class BioRxivConnector(BaseConnector):
    """Search bioRxiv & medRxiv preprints via the public content API."""

    name = "biorxiv"
    cache_ttl = 86400  # 24h
    rate_limit_rps = 5.0
    http_timeout = 15.0

    async def search(self, query: str, limit: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """Search bioRxiv using the details endpoint with date range."""
        server = kwargs.get("server", "biorxiv")  # biorxiv or medrxiv
        # bioRxiv API uses date-range detail endpoint
        # For keyword search, use the /search endpoint (undocumented but functional)
        url = f"{BIORXIV_API}/details/{server}/2020-01-01/2026-12-31/0/{limit}"
        resp = await self._client.get(url)
        if not resp or "collection" not in resp:
            return []

        results = []
        for item in resp.get("collection", [])[:limit]:
            # Basic keyword filtering since bioRxiv API doesn't support text search natively
            title = item.get("title", "")
            abstract = item.get("abstract", "")
            if query.lower() not in (title + " " + abstract).lower():
                continue
            results.append(self._normalize(item))
        return results[:limit]

    async def fetch_by_id(self, doi: str) -> Dict[str, Any]:
        """Fetch a specific preprint by DOI."""
        url = f"{BIORXIV_API}/details/biorxiv/{doi}"
        resp = await self._client.get(url)
        if not resp or "collection" not in resp:
            return {}
        items = resp.get("collection", [])
        return self._normalize(items[0]) if items else {}

    def _normalize(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": item.get("doi", ""),
            "title": item.get("title", ""),
            "abstract": item.get("abstract", ""),
            "authors": item.get("authors", ""),
            "date": item.get("date", ""),
            "server": item.get("server", "biorxiv"),
            "category": item.get("category", ""),
            "doi": item.get("doi", ""),
            "source": "biorxiv",
            "type": "preprint",
        }
