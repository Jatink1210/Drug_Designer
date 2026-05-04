"""MedDRA connector for medical terminology."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class MedDRAConnector(BaseConnector):
    """
    MedDRA (Medical Dictionary for Regulatory Activities) connector.
    
    MedDRA is a clinically validated international medical terminology used by
    regulatory authorities and the biopharmaceutical industry for adverse event reporting.
    
    Note: MedDRA requires subscription for full access. This connector provides
    basic search functionality.
    
    API: MedDRA Browser API
    Authentication may be required for full access.
    """
    
    name = "MedDRA"
    BASE = "https://www.meddra.org/api"
    cache_ttl = 172800
    rate_limit_rps = 2.0
    rate_limit_burst = 4
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = f"{self.BASE}/search"
        params = {"q": query, "limit": min(limit, 50)}
        data, meta = await self._cached_get(url, params=params)
        if not data or "terms" not in data:
            return []
        
        results: List[Dict[str, Any]] = []
        for term in data["terms"][:limit]:
            term_code = term.get("code", "")
            results.append({
                "id": term_code,
                "entity_type": "medical_term",
                "canonical_name": term.get("term", query),
                "name": term.get("term", query),
                "description": f"MedDRA term: {term.get('term', query)}",
                "meddra_code": term_code,
                "level": term.get("level", ""),
                "soc": term.get("soc", ""),
                "source": self.name,
                "url": f"https://www.meddra.org/how-to-use/support-documentation/english/welcome",
                "provenance": [self._prov(
                    url="https://www.meddra.org/how-to-use/support-documentation/english/welcome",
                    ext_id=term_code,
                    confidence=0.95,
                    reasoning="MedDRA standardized medical terminology"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE}/term/{entity_id}"
        data, meta = await self._cached_get(url)
        if not data:
            return None
        
        return {
            "id": entity_id,
            "entity_type": "medical_term",
            "canonical_name": data.get("term", entity_id),
            "name": data.get("term", entity_id),
            "description": f"MedDRA term: {data.get('term', entity_id)}",
            "meddra_code": entity_id,
            "level": data.get("level", ""),
            "soc": data.get("soc", ""),
            "source": self.name,
            "url": "https://www.meddra.org/how-to-use/support-documentation/english/welcome",
            "provenance": [self._prov(
                url="https://www.meddra.org/how-to-use/support-documentation/english/welcome",
                ext_id=entity_id,
                confidence=0.95,
                reasoning="MedDRA detailed medical terminology"
            ).to_dict()],
        }

    async def extract_evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        term_data = await self.fetch_by_id(entity_id)
        if not term_data:
            return []
        
        return [{
            "source": self.name,
            "entity_id": entity_id,
            "evidence_type": "medical_terminology",
            "confidence": 0.95,
            "url": term_data.get("url"),
            "provenance": self._prov(
                url=term_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.95,
                reasoning="MedDRA standardized medical terminology"
            ).to_dict()
        }]
