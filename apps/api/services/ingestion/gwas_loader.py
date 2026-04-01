"""GWAS Catalog loader for Variant-Trait-Gene associations."""

import json
import asyncio
from typing import Any, Dict, List, Optional
from pathlib import Path
import structlog

from connectors.base import BaseConnector
from models.entities import VariantEntity, DiseaseEntity, GeneEntity

log = structlog.get_logger()


class GWASConnector(BaseConnector):
    """Fetches from EBI GWAS Catalog REST API."""
    name = "GWASCatalog"
    BASE_URL = "https://www.ebi.ac.uk/gwas/rest/api"

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        # Map query to generic GWAS trait search
        url = f"{self.BASE_URL}/studies/search/findByDiseaseTrait"
        params = {"diseaseTrait": query}
        try:
            data, meta = await self._cached_get(url, params=params)
        except Exception as e:
            log.warning(f"GWAS API unavailable for {query}: {e}")
            return []
            
        if not data:
            return []
        
        results = []
        docs = data.get("_embedded", {}).get("studies", [])
        for doc in docs[:limit]:
            norm = self.normalize(doc)
            if norm:
                results.append(norm.model_dump())
        return results

    def normalize(self, raw_data: Dict[str, Any]) -> Optional[Any]:
        # Minimal normalization
        res_type = raw_data.get("resourcename", "")
        if res_type == "variant":
            rsid = raw_data.get("rsId", "")
            return VariantEntity(
                canonical_name=rsid,
                rs_id=rsid,
                gene=raw_data.get("mappedGenes", [""])[0] if raw_data.get("mappedGenes") else "",
                consequence=raw_data.get("consequence", ""),
                description=f"GWAS Variant {rsid}",
                provenance=[self._prov(
                    url=f"https://www.ebi.ac.uk/gwas/variants/{rsid}",
                    ext_id=rsid,
                    confidence=0.9,
                    reasoning="GWAS Catalog API"
                ).model_dump()]
            )
        elif res_type == "trait":
            trait = raw_data.get("trait", "")
            return DiseaseEntity(
                canonical_name=trait,
                description=f"GWAS Trait {trait}",
                provenance=[self._prov(
                    url=f"https://www.ebi.ac.uk/gwas/efotraits/{raw_data.get('shortForm', '')}",
                    ext_id=trait,
                    confidence=0.9,
                    reasoning="GWAS Catalog API"
                ).model_dump()]
            )
        return None
