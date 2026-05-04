"""OMIM connector — Online Mendelian Inheritance in Man.

API Reference: https://omim.org/help/api
Note: Full API access requires an API key from OMIM.
Falls back to limited public search when key is unavailable.
"""

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector


class OmimConnector(BaseConnector):
    name = "OMIM"
    BASE = "https://api.omim.org/api"
    cache_ttl = 172800  # 48h — data changes infrequently

    def _api_key(self) -> str:
        return os.environ.get("OMIM_API_KEY", "")

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        api_key = self._api_key()
        if not api_key:
            return [{
                "id": "OMIM:unavailable",
                "entity_type": "disease",
                "canonical_name": query,
                "status": "API key required — register at https://omim.org/api",
                "provenance": [self._prov(
                    confidence=0.0, reasoning="OMIM API key not configured"
                ).to_dict()],
            }]
        params = {
            "search": query,
            "limit": min(limit, 20),
            "format": "json",
            "apiKey": api_key,
        }
        data, meta = await self._cached_get(f"{self.BASE}/entry/search", params=params)
        if not data:
            return []
        entries = (
            data.get("omim", {})
            .get("searchResponse", {})
            .get("entryList", [])
        )
        results: List[Dict[str, Any]] = []
        for item in entries:
            entry = item.get("entry", {})
            mim_number = str(entry.get("mimNumber", ""))
            title = entry.get("titles", {}).get("preferredTitle", "")
            results.append({
                "id": f"OMIM:{mim_number}",
                "entity_type": "disease",
                "canonical_name": title,
                "mim_number": mim_number,
                "status": entry.get("status", ""),
                "url": f"https://omim.org/entry/{mim_number}",
                "provenance": [self._prov(
                    url=f"https://omim.org/entry/{mim_number}",
                    ext_id=mim_number, confidence=1.0, reasoning="OMIM curated"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        api_key = self._api_key()
        if not api_key:
            return None
        mim = entity_id.replace("OMIM:", "")
        params = {"mimNumber": mim, "format": "json", "apiKey": api_key, "include": "text"}
        data, meta = await self._cached_get(f"{self.BASE}/entry", params=params)
        if not data:
            return None
        entries = data.get("omim", {}).get("entryList", [])
        if not entries:
            return None
        entry = entries[0].get("entry", {})
        return {
            "id": f"OMIM:{mim}",
            "entity_type": "disease",
            "canonical_name": entry.get("titles", {}).get("preferredTitle", ""),
            "provenance": [self._prov(
                url=f"https://omim.org/entry/{mim}",
                ext_id=mim, confidence=1.0, reasoning="OMIM curated"
            ).to_dict()],
        }
