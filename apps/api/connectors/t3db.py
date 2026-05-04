"""T3DB (Toxin and Toxin-Target Database) connector.

Provides toxin structures, targets, mechanisms, and toxicity data.
API Reference: http://www.t3db.ca/
Note: T3DB does not have a formal JSON API; connector uses scrape-safe endpoints.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)


class T3DBConnector(BaseConnector):
    """Query T3DB for toxin records, targets, and mechanistic data."""

    name = "t3db"
    BASE_URL = "https://www.t3db.ca"
    cache_ttl = 86400 * 7
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search T3DB toxins by name, CAS, or target."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/toxins",
            params={"name": query, "format": "json", "limit": min(limit, 100)},
        )
        if not data or not isinstance(data, list):
            return []
        results = []
        for toxin in data[:limit]:
            t3db_id = toxin.get("t3db_id", toxin.get("id", ""))
            results.append({
                "id": t3db_id,
                "entity_type": "toxin",
                "canonical_name": toxin.get("common_name", toxin.get("name", "")),
                "description": toxin.get("description", ""),
                "t3db_id": t3db_id,
                "cas_number": toxin.get("cas_registry_number", ""),
                "molecular_formula": toxin.get("chemical_formula", ""),
                "smiles": toxin.get("smiles", ""),
                "exposure_routes": toxin.get("exposure_routes", []),
                "toxicity_summary": toxin.get("toxicity", ""),
                "mechanism_summary": toxin.get("mechanism_of_toxicity", ""),
                "lethality_ld50": toxin.get("lethal_dose", ""),
                "target_count": toxin.get("target_count", 0),
                "source_db": "T3DB",
                "url": f"https://www.t3db.ca/toxins/{t3db_id}",
                "provenance": [self._prov(
                    url=f"https://www.t3db.ca/toxins/{t3db_id}",
                    ext_id=t3db_id,
                    confidence=0.85,
                    reasoning="T3DB curated toxin record",
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, t3db_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full toxin record by T3DB ID."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/toxins/{t3db_id}",
            params={"format": "json"},
            extra_key=t3db_id,
        )
        if not data or not isinstance(data, dict):
            return None
        return {
            "id": t3db_id,
            "name": data.get("common_name", ""),
            "synonyms": data.get("synonyms", []),
            "cas_number": data.get("cas_registry_number", ""),
            "molecular_formula": data.get("chemical_formula", ""),
            "smiles": data.get("smiles", ""),
            "inchikey": data.get("inchikey", ""),
            "mechanism_of_toxicity": data.get("mechanism_of_toxicity", ""),
            "toxicity": data.get("toxicity", ""),
            "targets": data.get("targets", []),
            "source_db": "T3DB",
        }

    async def get_targets(self, t3db_id: str) -> List[Dict[str, Any]]:
        """Get molecular targets for a T3DB toxin."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/toxins/{t3db_id}/targets",
            params={"format": "json"},
            extra_key=f"targets_{t3db_id}",
        )
        if not data or not isinstance(data, list):
            return []
        return [
            {
                "uniprot_id": t.get("uniprot_id", ""),
                "gene_symbol": t.get("gene_name", ""),
                "protein_name": t.get("name", ""),
                "organism": t.get("organism", ""),
                "mechanism": t.get("mechanism", ""),
            }
            for t in data[:50]
        ]
