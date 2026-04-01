"""IntAct molecular interaction database connector."""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from .base import BaseConnector


class IntActConnector(BaseConnector):
    """Query EMBL-EBI IntAct for molecular interactions."""

    name = "intact"
    BASE_URL = "https://www.ebi.ac.uk/intact/ws/interaction"

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = f"{self.BASE_URL}/findInteractions/{query}"
        params = {"pageSize": limit, "page": 0}
        body, meta = await self._cached_get(url, params=params)

        if body is None:
            return []

        content = body.get("content", []) if isinstance(body, dict) else []
        return [
            {
                "ac": item.get("ac", ""),
                "interaction_type": item.get("interactionType", ""),
                "host_organism": item.get("hostOrganism", ""),
                "interactor_a": item.get("moleculeA", {}).get("identifier", ""),
                "interactor_b": item.get("moleculeB", {}).get("identifier", ""),
                "confidence_score": item.get("intactMiscore", 0),
                "detection_method": item.get("detectionMethod", ""),
                "source": "intact",
                "url": f"https://www.ebi.ac.uk/intact/details/interaction/{item.get('ac', '')}",
            }
            for item in content[:limit]
        ]

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE_URL}/{entity_id}"
        body, meta = await self._cached_get(url)
        if body and isinstance(body, dict):
            return {**body, "source": "intact"}
        return None
