"""ClinVar connector — free, NCBI E-utilities.

Genomic variants and their relationship to human health.
API Reference: https://www.ncbi.nlm.nih.gov/clinvar/
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector


class ClinVarConnector(BaseConnector):
    name = "ClinVar"
    ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    cache_ttl = 86400

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        params = {"db": "clinvar", "term": query, "retmax": min(limit, 50), "retmode": "json"}
        data, meta = await self._cached_get(self.ESEARCH, params=params)
        if not data:
            return []
        id_list = data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []
        summary, _ = await self._cached_get(
            self.ESUMMARY, params={"db": "clinvar", "id": ",".join(id_list), "retmode": "json"}
        )
        if not summary:
            return []
        results = []
        for cv_id in id_list:
            entry = summary.get("result", {}).get(cv_id, {})
            if not entry or "error" in entry:
                continue
            results.append({
                "id": f"ClinVar:{cv_id}",
                "entity_type": "variant",
                "canonical_name": entry.get("title", ""),
                "clinical_significance": entry.get("clinical_significance", {}).get("description", ""),
                "gene": entry.get("genes", [{}])[0].get("symbol", "") if entry.get("genes") else "",
                "url": f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{cv_id}/",
                "provenance": [self._prov(
                    url=f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{cv_id}/",
                    ext_id=cv_id, confidence=1.0, reasoning="ClinVar NCBI"
                ).to_dict()],
            })
        return results
