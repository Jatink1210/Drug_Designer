"""dbSNP connector — NCBI single-nucleotide polymorphism database.

API Reference: https://www.ncbi.nlm.nih.gov/snp/
Uses NCBI E-utilities (esearch/esummary).
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector


class DbSnpConnector(BaseConnector):
    name = "dbSNP"
    ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    cache_ttl = 86400
    rate_limit_rps = 3.0  # NCBI rate limit: 3 req/s without API key

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        params = {"db": "snp", "term": query, "retmax": min(limit, 50), "retmode": "json"}
        data, meta = await self._cached_get(self.ESEARCH, params=params)
        if not data:
            return []
        id_list = data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []
        summary, _ = await self._cached_get(
            self.ESUMMARY, params={"db": "snp", "id": ",".join(id_list), "retmode": "json"}
        )
        if not summary:
            return [{"id": f"rs{sid}", "entity_type": "variant"} for sid in id_list]
        results: List[Dict[str, Any]] = []
        for snp_id in id_list:
            entry = summary.get("result", {}).get(snp_id, {})
            if not entry or "error" in entry:
                continue
            results.append({
                "id": f"rs{snp_id}",
                "entity_type": "variant",
                "canonical_name": entry.get("snp_id", f"rs{snp_id}"),
                "chromosome": entry.get("chr", ""),
                "gene": entry.get("genes", [{}])[0].get("name", "") if entry.get("genes") else "",
                "clinical_significance": entry.get("clinical_significance", ""),
                "url": f"https://www.ncbi.nlm.nih.gov/snp/rs{snp_id}",
                "provenance": [self._prov(
                    url=f"https://www.ncbi.nlm.nih.gov/snp/rs{snp_id}",
                    ext_id=snp_id, confidence=1.0, reasoning="dbSNP NCBI"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        clean_id = entity_id.lstrip("rs")
        summary, _ = await self._cached_get(
            self.ESUMMARY, params={"db": "snp", "id": clean_id, "retmode": "json"}
        )
        if not summary:
            return None
        entry = summary.get("result", {}).get(clean_id, {})
        if not entry or "error" in entry:
            return None
        return {
            "id": f"rs{clean_id}",
            "entity_type": "variant",
            "canonical_name": entry.get("snp_id", f"rs{clean_id}"),
            "provenance": [self._prov(
                url=f"https://www.ncbi.nlm.nih.gov/snp/rs{clean_id}",
                ext_id=clean_id, confidence=1.0, reasoning="dbSNP NCBI"
            ).to_dict()],
        }
