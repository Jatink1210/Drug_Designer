"""HPO (Human Phenotype Ontology) connector — free, no API key.

Links diseases to phenotypes. ~17K phenotype terms.
API Reference: https://hpo.jax.org/
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector


class HPOConnector(BaseConnector):
    name = "HPO"
    BASE_URL = "https://ontology.jax.org/api/hp"
    cache_ttl = 86400

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        data, meta = await self._cached_get(
            f"{self.BASE_URL}/search", params={"q": query, "max": min(limit, 50)}
        )
        if not data or not isinstance(data, dict) or "terms" not in data:
            return []
        results = []
        for term in data["terms"]:
            hp_id = term.get("id", "")
            results.append({
                "id": hp_id,
                "entity_type": "phenotype",
                "canonical_name": term.get("name", ""),
                "description": term.get("definition", ""),
                "synonyms": term.get("synonyms", []),
                "source_db": "HPO",
                "url": f"https://hpo.jax.org/browse/term/{hp_id}",
                "provenance": [self._prov(
                    url=f"https://hpo.jax.org/browse/term/{hp_id}",
                    confidence=1.0, reasoning="HPO indexed"
                ).to_dict()],
            })
        return results[:limit]
