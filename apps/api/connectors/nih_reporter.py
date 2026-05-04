"""NIH RePORTER grant data connector (F-10).

NIH RePORTER provides programmatic access to NIH-funded research projects,
publications, and patents.

API: https://api.reporter.nih.gov/v2/
Rate Limits: 50 req/min
Auth: None required
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

from connectors.base import BaseConnector, strip_html

log = structlog.get_logger(__name__)

NIH_BASE = "https://api.reporter.nih.gov/v2"


class NIHReporterConnector(BaseConnector):
    """NIH RePORTER grant data connector.

    Provides:
    - Funded research projects by keyword / PI / institution
    - Publication linkages to grants
    - Budget and funding details
    """

    name = "nih_reporter"
    cache_ttl = 86400 * 2  # 2 days
    rate_limit_rps = 0.8   # ~50/min
    rate_limit_burst = 5
    http_timeout = 20.0
    max_retries = 3
    degradation_mode = "degrade"

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search NIH-funded projects matching the query."""
        return await self.search_projects(query, limit=limit)

    async def search_projects(
        self,
        query: str,
        fiscal_years: Optional[List[int]] = None,
        activity_codes: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search NIH-funded research projects.

        Args:
            query: Free-text search (project title, abstract, keywords)
            fiscal_years: List of fiscal years to filter by
            activity_codes: Activity code filter e.g. ["R01", "R21", "U01"]
            limit: Max results

        Returns:
            List of project dicts
        """
        payload: Dict[str, Any] = {
            "criteria": {
                "advanced_text_search": {
                    "operator": "and",
                    "search_field": "all",
                    "search_text": query,
                },
            },
            "offset": 0,
            "limit": min(limit, 100),
            "sort_field": "project_start_date",
            "sort_order": "desc",
        }
        if fiscal_years:
            payload["criteria"]["fiscal_years"] = fiscal_years
        if activity_codes:
            payload["criteria"]["activity_codes"] = activity_codes

        url = f"{NIH_BASE}/projects/search"
        body, meta = await self._post_cached(url, payload, extra_key=f"proj_{query}")
        if not body:
            log.warning("nih_reporter_empty", query=query, meta=meta)
            return []

        items = body.get("results", []) if isinstance(body, dict) else []
        return [self._normalize(r) for r in items[:limit] if isinstance(r, dict)]

    async def _post_cached(
        self, url: str, payload: Dict[str, Any], extra_key: str = ""
    ) -> tuple:
        from core.cache import cache_key, async_two_tier_get, async_two_tier_put
        import time
        key = cache_key(self.name, url, extra_key)
        cached = await async_two_tier_get(key)
        if cached is not None:
            return cached, {"cache_hit": True}
        try:
            import httpx
            t0 = time.time()
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                body = resp.json()
            await async_two_tier_put(key, self.name, url, body, ttl=self.cache_ttl, payload_hash="")
            return body, {"elapsed_ms": round((time.time() - t0) * 1000, 1)}
        except Exception as exc:
            log.warning("nih_reporter_post_failed", url=url, error=str(exc))
            return None, {"error": str(exc)}

    def _normalize(self, item: Dict[str, Any]) -> Dict[str, Any]:
        pi_names = [
            f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
            for p in item.get("principal_investigators", [])
        ]
        return {
            "project_id": item.get("project_num", ""),
            "title": strip_html(item.get("project_title", "")),
            "abstract": strip_html(item.get("abstract_text", ""))[:400],
            "fiscal_year": item.get("fiscal_year"),
            "total_cost": item.get("award_amount"),
            "activity_code": item.get("activity_code", ""),
            "organization": item.get("organization", {}).get("org_name", ""),
            "pi_names": pi_names,
            "start_date": item.get("project_start_date", ""),
            "end_date": item.get("project_end_date", ""),
            "study_section": item.get("full_study_section", {}).get("name", "") if isinstance(item.get("full_study_section"), dict) else "",
            "source_db": "nih_reporter",
        }

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single grant by project number."""
        url = f"{NIH_BASE}/projects/{entity_id}"
        body, meta = await self._cached_get(url, extra_key=entity_id)
        if not body:
            return None
        return self._normalize(body) if isinstance(body, dict) else None
