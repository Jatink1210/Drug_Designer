"""CDSCO connector for Indian drug approvals."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class CDSCOConnector(BaseConnector):
    """
    Central Drugs Standard Control Organization (CDSCO) connector for Indian drug approvals.
    
    CDSCO (https://cdsco.gov.in) is India's national regulatory authority for pharmaceuticals
    and medical devices.
    """
    
    name = "CDSCO"
    BASE = "https://cdsco.gov.in/opencms/opencms/en/api"
    cache_ttl = 172800
    rate_limit_rps = 2.0
    rate_limit_burst = 4
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = f"{self.BASE}/drugs/search"
        params = {"q": query, "limit": min(limit, 50)}
        data, meta = await self._cached_get(url, params=params)
        if not data or "drugs" not in data:
            return []
        
        results: List[Dict[str, Any]] = []
        for drug in data["drugs"][:limit]:
            drug_id = drug.get("approval_number", "")
            results.append({
                "id": drug_id,
                "entity_type": "drug",
                "canonical_name": drug.get("name", query),
                "name": drug.get("name", query),
                "description": strip_html(drug.get("indication", "")),
                "approval_number": drug_id,
                "approval_date": drug.get("approval_date", ""),
                "source": self.name,
                "url": f"https://cdsco.gov.in/opencms/opencms/en/Drugs/Approved-Drugs/",
                "provenance": [self._prov(
                    url="https://cdsco.gov.in/opencms/opencms/en/Drugs/Approved-Drugs/",
                    ext_id=drug_id,
                    confidence=0.94,
                    reasoning="CDSCO official drug approval data"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE}/drugs/{entity_id}"
        data, meta = await self._cached_get(url)
        if not data:
            return None
        
        return {
            "id": entity_id,
            "entity_type": "drug",
            "canonical_name": data.get("name", entity_id),
            "name": data.get("name", entity_id),
            "description": strip_html(data.get("indication", "")),
            "approval_number": entity_id,
            "approval_date": data.get("approval_date", ""),
            "source": self.name,
            "url": "https://cdsco.gov.in/opencms/opencms/en/Drugs/Approved-Drugs/",
            "provenance": [self._prov(
                url="https://cdsco.gov.in/opencms/opencms/en/Drugs/Approved-Drugs/",
                ext_id=entity_id,
                confidence=0.94,
                reasoning="CDSCO detailed drug approval data"
            ).to_dict()],
        }

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        drug_data = await self.fetch_by_id(entity_id)
        if not drug_data:
            return []
        
        return [{
            "source": self.name,
            "entity_id": entity_id,
            "evidence_type": "cdsco_approval",
            "confidence": 0.94,
            "url": drug_data.get("url"),
            "provenance": self._prov(
                url=drug_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.94,
                reasoning="CDSCO official drug approval data"
            ).to_dict()
        }]
