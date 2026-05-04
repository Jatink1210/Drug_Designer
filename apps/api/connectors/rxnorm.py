"""RxNorm connector for standardized drug nomenclature."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class RxNormConnector(BaseConnector):
    """
    RxNorm connector for standardized drug nomenclature.
    
    RxNorm (https://www.nlm.nih.gov/research/umls/rxnorm) provides normalized names
    for clinical drugs and links to many drug vocabularies.
    
    API: RxNorm REST API
    No authentication required (free public API).
    """
    
    name = "RxNorm"
    BASE = "https://rxnav.nlm.nih.gov/REST"
    cache_ttl = 172800
    rate_limit_rps = 3.0
    rate_limit_burst = 6
    http_timeout = 15.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = f"{self.BASE}/drugs.json"
        params = {"name": query}
        data, meta = await self._cached_get(url, params=params)
        if not data or "drugGroup" not in data or "conceptGroup" not in data["drugGroup"]:
            return []
        
        results: List[Dict[str, Any]] = []
        for group in data["drugGroup"]["conceptGroup"]:
            if "conceptProperties" in group:
                concepts = group["conceptProperties"] if isinstance(group["conceptProperties"], list) else [group["conceptProperties"]]
                for concept in concepts[:limit]:
                    rxcui = concept.get("rxcui", "")
                    results.append({
                        "id": rxcui,
                        "entity_type": "drug",
                        "canonical_name": concept.get("name", query),
                        "name": concept.get("name", query),
                        "description": f"RxNorm concept: {concept.get('name', query)}",
                        "rxcui": rxcui,
                        "tty": concept.get("tty", ""),
                        "source": self.name,
                        "url": f"https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm={rxcui}",
                        "provenance": [self._prov(
                            url=f"https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm={rxcui}",
                            ext_id=rxcui,
                            confidence=0.96,
                            reasoning="RxNorm standardized drug nomenclature"
                        ).to_dict()],
                    })
        return results[:limit]

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE}/rxcui/{entity_id}/properties.json"
        data, meta = await self._cached_get(url)
        if not data or "properties" not in data:
            return None
        
        props = data["properties"]
        return {
            "id": entity_id,
            "entity_type": "drug",
            "canonical_name": props.get("name", entity_id),
            "name": props.get("name", entity_id),
            "description": f"RxNorm concept: {props.get('name', entity_id)}",
            "rxcui": entity_id,
            "tty": props.get("tty", ""),
            "source": self.name,
            "url": f"https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm={entity_id}",
            "provenance": [self._prov(
                url=f"https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm={entity_id}",
                ext_id=entity_id,
                confidence=0.96,
                reasoning="RxNorm detailed drug concept"
            ).to_dict()],
        }

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        drug_data = await self.fetch_by_id(entity_id)
        if not drug_data:
            return []
        
        return [{
            "source": self.name,
            "entity_id": entity_id,
            "evidence_type": "drug_nomenclature",
            "confidence": 0.96,
            "url": drug_data.get("url"),
            "provenance": self._prov(
                url=drug_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.96,
                reasoning="RxNorm standardized drug nomenclature"
            ).to_dict()
        }]
