"""STRING protein interaction database connector (optional, behind toggle)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector


class STRINGConnector(BaseConnector):
    name = "STRING"
    BASE = "https://string-db.org/api/json"
    cache_ttl = 259200  # 72h — interaction data is stable
    SPECIES_HUMAN = 9606

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = "%s/network" % self.BASE
        params = {
            "identifiers": query,
            "species": self.SPECIES_HUMAN,
            "limit": min(limit, 50),
            "caller_identity": "drugsynth_workbench",
        }
        data, meta = await self._cached_get(url, params=params)
        if not data or not isinstance(data, list):
            return []
        results: List[Dict[str, Any]] = []
        seen = set()
        for interaction in data:
            pref_a = interaction.get("preferredName_A", "")
            pref_b = interaction.get("preferredName_B", "")
            score = interaction.get("score", 0)
            pair_key = tuple(sorted([pref_a, pref_b]))
            if pair_key in seen:
                continue
            seen.add(pair_key)
            results.append({
                "id": "STRING:%s-%s" % (pref_a, pref_b),
                "entity_type": "interaction",
                "canonical_name": "%s ↔ %s" % (pref_a, pref_b),
                "name": "%s ↔ %s" % (pref_a, pref_b),
                "source_entity": pref_a,
                "target_entity": pref_b,
                "interaction_type": "protein-protein",
                "score": score,
                "string_id_a": interaction.get("stringId_A", ""),
                "string_id_b": interaction.get("stringId_B", ""),
                "provenance": [self._prov(
                    url="https://string-db.org/network/%s" % interaction.get("stringId_A", ""),
                    confidence=min(score, 1.0),
                    reasoning="STRING combined score %.3f" % score,
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        protein = entity_id.replace("STRING:", "").split("-")[0]
        results = await self.search(protein, limit=10)
        return results[0] if results else None


