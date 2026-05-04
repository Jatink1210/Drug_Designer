"""EMA connector for European Medicines Agency drug approvals."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class EMAConnector(BaseConnector):
    """
    European Medicines Agency (EMA) connector for EU drug approvals.
    
    EMA (https://www.ema.europa.eu) is responsible for the scientific evaluation,
    supervision and safety monitoring of medicines in the European Union.
    
    API: RESTful web services
    No authentication required (free public API).
    """
    
    name = "EMA"
    BASE = "https://www.ema.europa.eu/api"
    cache_ttl = 172800  # 48 hours
    rate_limit_rps = 2.0
    rate_limit_burst = 4
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for EMA-approved medicines."""
        url = f"{self.BASE}/medicines/search"
        params = {"q": query, "limit": min(limit, 50)}
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "medicines" not in data:
            return []
        
        results: List[Dict[str, Any]] = []
        for medicine in data["medicines"][:limit]:
            medicine_id = medicine.get("eu_number", "")
            results.append({
                "id": medicine_id,
                "entity_type": "drug",
                "canonical_name": medicine.get("name", query),
                "name": medicine.get("name", query),
                "description": strip_html(medicine.get("therapeutic_area", "")),
                "eu_number": medicine_id,
                "active_substance": medicine.get("active_substance", ""),
                "authorisation_status": medicine.get("status", ""),
                "approval_date": medicine.get("authorisation_date", ""),
                "source": self.name,
                "url": f"https://www.ema.europa.eu/en/medicines/human/EPAR/{medicine.get('name', '').lower().replace(' ', '-')}",
                "provenance": [self._prov(
                    url=f"https://www.ema.europa.eu/en/medicines/human/EPAR/{medicine.get('name', '').lower().replace(' ', '-')}",
                    ext_id=medicine_id,
                    confidence=0.97,
                    reasoning="EMA official drug approval data"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed medicine data."""
        url = f"{self.BASE}/medicines/{entity_id}"
        data, meta = await self._cached_get(url)
        if not data:
            return None
        
        return {
            "id": entity_id,
            "entity_type": "drug",
            "canonical_name": data.get("name", entity_id),
            "name": data.get("name", entity_id),
            "description": strip_html(data.get("therapeutic_area", "")),
            "eu_number": entity_id,
            "active_substance": data.get("active_substance", ""),
            "authorisation_status": data.get("status", ""),
            "approval_date": data.get("authorisation_date", ""),
            "source": self.name,
            "url": f"https://www.ema.europa.eu/en/medicines/human/EPAR/{data.get('name', '').lower().replace(' ', '-')}",
            "provenance": [self._prov(
                url=f"https://www.ema.europa.eu/en/medicines/human/EPAR/{data.get('name', '').lower().replace(' ', '-')}",
                ext_id=entity_id,
                confidence=0.97,
                reasoning="EMA detailed drug approval data"
            ).to_dict()],
        }

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        """Extract evidence records."""
        drug_data = await self.fetch_by_id(entity_id)
        if not drug_data:
            return []
        
        return [{
            "source": self.name,
            "entity_id": entity_id,
            "evidence_type": "ema_approval",
            "confidence": 0.97,
            "url": drug_data.get("url"),
            "provenance": self._prov(
                url=drug_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.97,
                reasoning="EMA official drug approval data"
            ).to_dict()
        }]
