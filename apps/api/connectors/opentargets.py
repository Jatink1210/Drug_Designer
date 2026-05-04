"""OpenTargets GraphQL connector — using enhanced base."""

from __future__ import annotations

from typing import Any, Dict, List

from config import settings
from connectors.base import BaseConnector


class OpenTargetsConnector(BaseConnector):
    name = "OpenTargets"

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        gql = {
            "query": """
                query SearchQuery($q: String!, $size: Int!) {
                    search(queryString: $q, entityNames: ["target", "disease", "drug"], page: {index: 0, size: $size}) {
                        total
                        hits { id entity name description score }
                    }
                }
            """,
            "variables": {"q": query, "size": min(limit, 40)},
        }
        data, meta = await self._cached_post(settings.opentargets_api_url, json_body=gql)
        if not data:
            return []
        hits = data.get("data", {}).get("search", {}).get("hits", [])
        results: List[Dict[str, Any]] = []
        for h in hits:
            etype = h.get("entity", "target")
            mapped = {"target": "gene", "disease": "disease", "drug": "drug"}.get(etype, "gene")
            eid = h.get("id", "")
            results.append({
                "id": eid,
                "entity_type": mapped,
                "canonical_name": h.get("name", ""),
                "name": h.get("name", ""),
                "description": (h.get("description") or "")[:300],
                "association_score": h.get("score"),
                "url": "https://platform.opentargets.org/%s/%s" % (etype, eid),
                "provenance": [self._prov(
                    url="https://platform.opentargets.org/%s/%s" % (etype, eid),
                    ext_id=eid, confidence=0.95, reasoning="OpenTargets platform"
                ).to_dict()],
            })
        return results


