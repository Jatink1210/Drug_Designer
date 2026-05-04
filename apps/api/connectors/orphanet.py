"""Orphanet (Orphadata) connector — rare disease database.

API Reference: https://www.orphadata.com/
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector


class OrphanetConnector(BaseConnector):
    name = "Orphanet"
    BASE = "https://api.orphadata.com"
    cache_ttl = 172800  # 48h — rare disease data is stable

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = f"{self.BASE}/rd-cross-referencing/orphacodes"
        params = {"lang": "en"}
        data, meta = await self._cached_get(url, params=params)
        if not data:
            # Fallback: return a placeholder indicating the API was unreachable
            return [{
                "id": f"Orphanet:search:{query}",
                "entity_type": "disease",
                "canonical_name": query,
                "status": "Orphadata API query attempted",
                "provenance": [self._prov(
                    confidence=0.3, reasoning="Orphanet search — limited public API"
                ).to_dict()],
            }]
        # Orphadata returns a large dataset; filter client-side
        if isinstance(data, str):
            return []
        items = data if isinstance(data, list) else data.get("data", []) if isinstance(data, dict) else []
        q_lower = query.lower()
        results: List[Dict[str, Any]] = []
        for entry in items:
            if not isinstance(entry, dict):
                continue
            name = entry.get("Preferred term", entry.get("name", ""))
            if q_lower in name.lower():
                orpha_code = str(entry.get("ORPHAcode", entry.get("orphacode", "")))
                results.append({
                    "id": f"ORPHA:{orpha_code}",
                    "entity_type": "disease",
                    "canonical_name": name,
                    "orpha_code": orpha_code,
                    "url": f"https://www.orpha.net/en/disease/detail/{orpha_code}",
                    "provenance": [self._prov(
                        url=f"https://www.orpha.net/en/disease/detail/{orpha_code}",
                        ext_id=orpha_code, confidence=0.9, reasoning="Orphanet curated"
                    ).to_dict()],
                })
                if len(results) >= limit:
                    break
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        orpha_code = entity_id.replace("ORPHA:", "")
        url = f"{self.BASE}/rd-cross-referencing/orphacodes/{orpha_code}"
        data, meta = await self._cached_get(url)
        if not data or not isinstance(data, dict):
            return None
        name = data.get("Preferred term", data.get("name", ""))
        return {
            "id": f"ORPHA:{orpha_code}",
            "entity_type": "disease",
            "canonical_name": name,
            "url": f"https://www.orpha.net/en/disease/detail/{orpha_code}",
            "provenance": [self._prov(
                url=f"https://www.orpha.net/en/disease/detail/{orpha_code}",
                ext_id=orpha_code, confidence=0.9, reasoning="Orphanet curated"
            ).to_dict()],
        }
