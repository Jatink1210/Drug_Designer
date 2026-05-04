"""Drugs@FDA connector for FDA-approved drug information."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class DrugsFDAConnector(BaseConnector):
    """
    Drugs@FDA connector for FDA-approved drug information.
    
    Drugs@FDA (https://www.accessdata.fda.gov/scripts/cder/daf/) provides information
    about FDA-approved brand name and generic drugs.
    
    API: openFDA API
    No authentication required (free public API).
    """
    
    name = "Drugs_FDA"
    BASE = "https://api.fda.gov/drug"
    cache_ttl = 172800  # 48 hours (regulatory data changes slowly)
    rate_limit_rps = 2.0
    rate_limit_burst = 4
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for FDA-approved drugs."""
        url = f"{self.BASE}/drugsfda.json"
        params = {
            "search": f'openfda.brand_name:"{query}" OR openfda.generic_name:"{query}"',
            "limit": min(limit, 100)
        }
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "results" not in data:
            return []
        
        results: List[Dict[str, Any]] = []
        for drug in data["results"][:limit]:
            application_number = drug.get("application_number", "")
            openfda = drug.get("openfda", {})
            brand_name = openfda.get("brand_name", [query])[0] if openfda.get("brand_name") else query
            
            results.append({
                "id": application_number,
                "entity_type": "drug",
                "canonical_name": brand_name,
                "name": brand_name,
                "description": f"FDA-approved drug: {brand_name}",
                "application_number": application_number,
                "generic_name": openfda.get("generic_name", [""])[0] if openfda.get("generic_name") else "",
                "manufacturer": openfda.get("manufacturer_name", [""])[0] if openfda.get("manufacturer_name") else "",
                "approval_date": drug.get("submissions", [{}])[0].get("submission_status_date", "") if drug.get("submissions") else "",
                "source": self.name,
                "url": f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={application_number}",
                "provenance": [self._prov(
                    url=f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={application_number}",
                    ext_id=application_number,
                    confidence=0.98,
                    reasoning="FDA official drug approval data"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed drug data by application number."""
        url = f"{self.BASE}/drugsfda.json"
        params = {"search": f'application_number:"{entity_id}"', "limit": 1}
        
        data, meta = await self._cached_get(url, params=params)
        if not data or "results" not in data or len(data["results"]) == 0:
            return None
        
        drug = data["results"][0]
        openfda = drug.get("openfda", {})
        brand_name = openfda.get("brand_name", [entity_id])[0] if openfda.get("brand_name") else entity_id
        
        return {
            "id": entity_id,
            "entity_type": "drug",
            "canonical_name": brand_name,
            "name": brand_name,
            "description": f"FDA-approved drug: {brand_name}",
            "application_number": entity_id,
            "generic_name": openfda.get("generic_name", [""])[0] if openfda.get("generic_name") else "",
            "manufacturer": openfda.get("manufacturer_name", [""])[0] if openfda.get("manufacturer_name") else "",
            "approval_date": drug.get("submissions", [{}])[0].get("submission_status_date", "") if drug.get("submissions") else "",
            "products": drug.get("products", []),
            "submissions": drug.get("submissions", []),
            "source": self.name,
            "url": f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={entity_id}",
            "provenance": [self._prov(
                url=f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={entity_id}",
                ext_id=entity_id,
                confidence=0.98,
                reasoning="FDA official detailed drug approval data"
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
            "evidence_type": "fda_approval",
            "confidence": 0.98,
            "url": drug_data.get("url"),
            "provenance": self._prov(
                url=drug_data.get("url", ""),
                ext_id=entity_id,
                confidence=0.98,
                reasoning="FDA official drug approval data"
            ).to_dict()
        }]
