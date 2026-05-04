"""IntAct molecular interaction database connector."""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from .base import BaseConnector


class IntActConnector(BaseConnector):
    """Query EMBL-EBI IntAct for molecular interactions."""

    name = "intact"
    BASE_URL = "https://www.ebi.ac.uk/intact/ws/interaction"

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = f"https://www.ebi.ac.uk/intact/ws/interactor/findInteractor/{query}"
        params = {"pageSize": limit, "page": 0}
        body, meta = await self._cached_get(url, params=params)

        if body is None or not isinstance(body, dict):
            return []

        content = body.get("content", [])
        if not isinstance(content, list):
            return []
        results: List[Dict[str, Any]] = []
        for item in content[:limit]:
            if not isinstance(item, dict):
                continue
            mol_a = item.get("moleculeA") or {}
            mol_b = item.get("moleculeB") or {}
            ac = item.get("ac", "")
            results.append({
                "id": f"IntAct:{ac}",
                "entity_type": "interaction",
                "canonical_name": f"{(mol_a.get('identifier') or '?')} - {(mol_b.get('identifier') or '?')}",
                "source_entity": mol_a.get("identifier", "") if isinstance(mol_a, dict) else "",
                "target_entity": mol_b.get("identifier", "") if isinstance(mol_b, dict) else "",
                "interaction_type": item.get("interactionType", ""),
                "confidence_score": item.get("intactMiscore", 0),
                "detection_method": item.get("detectionMethod", ""),
                "source_db": "IntAct",
                "url": f"https://www.ebi.ac.uk/intact/details/interaction/{ac}",
                "provenance": [self._prov(
                    url=f"https://www.ebi.ac.uk/intact/details/interaction/{ac}",
                    ext_id=ac, confidence=1.0, reasoning="IntAct EBI"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE_URL}/{entity_id}"
        body, meta = await self._cached_get(url)
        if body and isinstance(body, dict):
            return {**body, "source": "intact"}
        return None
