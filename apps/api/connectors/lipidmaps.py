"""LIPID MAPS connector — lipid molecular species database.

Comprehensive lipid structure, classification, and ontology.
API Reference: https://www.lipidmaps.org/databases/lmsd/programmatic-access
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog
from .base import BaseConnector

log = structlog.get_logger(__name__)


class LipidMapsConnector(BaseConnector):
    """Query LIPID MAPS Structure Database (LMSD) for lipid entities."""

    name = "lipidmaps"
    BASE_URL = "https://www.lipidmaps.org/rest"
    cache_ttl = 86400 * 7
    http_timeout = 20.0

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search lipids by common name or systematic name."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/compound/name/{query}/all/json"
        )
        if not data:
            return []
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            return []
        results = []
        for lipid in data[:limit]:
            lm_id = lipid.get("lm_id", "")
            results.append({
                "id": lm_id,
                "entity_type": "lipid",
                "canonical_name": lipid.get("common_name", lipid.get("name", lm_id)),
                "description": lipid.get("systematic_name", ""),
                "lm_id": lm_id,
                "systematic_name": lipid.get("systematic_name", ""),
                "category": lipid.get("category", ""),
                "main_class": lipid.get("main_class", ""),
                "sub_class": lipid.get("sub_class", ""),
                "formula": lipid.get("formula", ""),
                "exact_mass": lipid.get("exact_mass", ""),
                "inchi": lipid.get("inchi", ""),
                "inchi_key": lipid.get("inchi_key", ""),
                "smiles": lipid.get("smiles", ""),
                "pubchem_cid": lipid.get("pubchem_cid", ""),
                "hmdb_id": lipid.get("hmdbid", ""),
                "chebi_id": lipid.get("chebi_id", ""),
                "source_db": "LIPID MAPS",
                "url": f"https://www.lipidmaps.org/databases/lmsd/{lm_id}",
                "provenance": [self._prov(
                    url=f"https://www.lipidmaps.org/rest/compound/lm_id/{lm_id}/all/json",
                    ext_id=lm_id,
                    confidence=0.90,
                    reasoning="LIPID MAPS curated lipid structure",
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, lm_id: str) -> Optional[Dict[str, Any]]:
        """Fetch lipid by LIPID MAPS ID (e.g., LMSP02010012)."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/compound/lm_id/{lm_id}/all/json"
        )
        if not data or not isinstance(data, dict):
            return None
        return {
            "lm_id": lm_id,
            "common_name": data.get("common_name", ""),
            "systematic_name": data.get("systematic_name", ""),
            "category": data.get("category", ""),
            "main_class": data.get("main_class", ""),
            "sub_class": data.get("sub_class", ""),
            "formula": data.get("formula", ""),
            "exact_mass": data.get("exact_mass", ""),
            "smiles": data.get("smiles", ""),
            "inchi": data.get("inchi", ""),
            "inchi_key": data.get("inchi_key", ""),
            "pubchem_cid": data.get("pubchem_cid", ""),
            "chebi_id": data.get("chebi_id", ""),
            "kegg_id": data.get("kegg_id", ""),
            "source_db": "LIPID MAPS",
        }

    async def get_lipid_by_category(self, category: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Browse lipids by LIPID MAPS category (e.g., 'Fatty Acyls')."""
        data, _meta = await self._cached_get(
            f"{self.BASE_URL}/compound/category/{category}/all/json",
            extra_key=category,
        )
        if not data or not isinstance(data, list):
            return []
        return data[:limit]
