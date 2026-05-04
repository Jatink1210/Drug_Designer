"""Lens.org patent and scholarly search connector (F-9).

Lens.org aggregates patents and scholarly articles with open APIs.

API: https://api.lens.org/
Auth: Bearer token (LENS_API_KEY env var)
Rate Limits: 50 req/min on free tier
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import structlog

from connectors.base import BaseConnector, strip_html

log = structlog.get_logger(__name__)

LENS_BASE = "https://api.lens.org"


class LensOrgConnector(BaseConnector):
    """Lens.org patent + scholarly literature connector.

    Provides:
    - Patent search and metadata
    - Scholarly article search with citation counts
    - Cross-reference between patents and literature
    """

    name = "lens_org"
    cache_ttl = 86400 * 2  # 2 days
    rate_limit_rps = 0.8   # ~50/min
    rate_limit_burst = 5
    http_timeout = 20.0
    max_retries = 3
    degradation_mode = "degrade"

    def __init__(self) -> None:
        super().__init__()
        self._api_key: str = os.environ.get("LENS_API_KEY", "")

    def _auth_headers(self) -> Dict[str, str]:
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        return {}

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search both patents and scholarly articles."""
        scholarly = await self.search_scholarly(query, limit=limit // 2 + 1)
        patents = await self.search_patents(query, limit=limit // 2 + 1)
        return (scholarly + patents)[:limit]

    async def search_scholarly(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search Lens.org scholarly articles."""
        payload = {
            "query": {
                "match": {"title": query}
            },
            "size": min(limit, 50),
            "sort": [{"year_published": "desc"}],
            "include": ["title", "authors", "year_published", "doi", "abstract",
                        "citation_count", "source"],
        }
        url = f"{LENS_BASE}/scholarly/search"
        body, meta = await self._post_cached(url, payload, extra_key=f"scholarly_{query}")
        if not body:
            log.warning("lens_scholarly_empty", query=query, meta=meta)
            return []
        items = body.get("data", []) if isinstance(body, dict) else []
        return [self._normalize_scholarly(r) for r in items[:limit] if isinstance(r, dict)]

    async def search_patents(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search Lens.org patents."""
        payload = {
            "query": {"match": {"title": query}},
            "size": min(limit, 50),
            "include": ["lens_id", "title", "date_published", "inventors",
                        "applicants", "abstract"],
        }
        url = f"{LENS_BASE}/patent/search"
        body, meta = await self._post_cached(url, payload, extra_key=f"patent_{query}")
        if not body:
            return []
        items = body.get("data", []) if isinstance(body, dict) else []
        return [self._normalize_patent(r) for r in items[:limit] if isinstance(r, dict)]

    async def _post_cached(
        self, url: str, payload: Dict[str, Any], extra_key: str = ""
    ) -> tuple:
        """POST with caching — fall back to GET-cache key pattern."""
        from core.cache import cache_key, async_two_tier_get, async_two_tier_put
        import json, time
        key = cache_key(self.name, url, extra_key)
        cached = await async_two_tier_get(key)
        if cached is not None:
            return cached, {"cache_hit": True}

        limiter_registry = getattr(self, "_rl_registry", None)
        try:
            import httpx
            headers = {"Content-Type": "application/json", **self._auth_headers()}
            t0 = time.time()
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                body = resp.json()
            await async_two_tier_put(key, self.name, url, body, ttl=self.cache_ttl, payload_hash="")
            return body, {"elapsed_ms": round((time.time() - t0) * 1000, 1)}
        except Exception as exc:
            log.warning("lens_post_failed", url=url, error=str(exc))
            return None, {"error": str(exc)}

    def _normalize_scholarly(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": item.get("lens_id", ""),
            "type": "scholarly",
            "title": strip_html(item.get("title", "")),
            "year": item.get("year_published"),
            "doi": item.get("doi", ""),
            "abstract": strip_html(item.get("abstract", ""))[:500],
            "citation_count": item.get("citation_count", 0),
            "authors": [a.get("display_name", "") for a in item.get("authors", [])],
            "journal": item.get("source", {}).get("title", "") if isinstance(item.get("source"), dict) else "",
            "source_db": "lens_org",
        }

    def _normalize_patent(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": item.get("lens_id", ""),
            "type": "patent",
            "title": strip_html(item.get("title", "")),
            "date_published": item.get("date_published", ""),
            "abstract": strip_html(item.get("abstract", ""))[:500],
            "inventors": [i.get("name", "") for i in item.get("inventors", [])],
            "applicants": [a.get("name", "") for a in item.get("applicants", [])],
            "source_db": "lens_org",
        }

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        results = await self.search(entity_id, limit=5)
        return results[0] if results else None
