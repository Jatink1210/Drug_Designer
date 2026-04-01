"""RCSB PDB connector — using enhanced base."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector


class RCSBConnector(BaseConnector):
    name = "RCSB_PDB"
    SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
    DATA_URL = "https://data.rcsb.org/rest/v1/core/entry"
    cache_ttl = 172800  # 48h

    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        body = {
            "query": {"type": "terminal", "service": "full_text", "parameters": {"value": query}},
            "return_type": "entry",
            "request_options": {"results_content_type": ["experimental"], "paginate": {"start": 0, "rows": min(limit, 25)}},
        }
        data, meta = await self._cached_post(self.SEARCH_URL, json_body=body)
        if not data:
            return []
        results: List[Dict[str, Any]] = []
        for hit in data.get("result_set", []):
            pdb_id = hit.get("identifier", "")
            info = await self._fetch_entry_meta(pdb_id)
            results.append({
                "id": pdb_id,
                "entity_type": "structure",
                "canonical_name": info.get("title", pdb_id),
                "name": info.get("title", pdb_id),
                "title": info.get("title", ""),
                "pdb_id": pdb_id,
                "method": info.get("method", ""),
                "resolution": info.get("resolution"),
                "r_free": info.get("r_free"),
                "deposition_date": info.get("deposition_date", ""),
                "url": "https://www.rcsb.org/structure/%s" % pdb_id,
                "provenance": [self._prov(
                    url="https://www.rcsb.org/structure/%s" % pdb_id,
                    ext_id=pdb_id, confidence=1.0, reasoning="RCSB PDB experimental structure"
                ).to_dict()],
            })
        return results

    async def _fetch_entry_meta(self, pdb_id: str) -> Dict[str, Any]:
        data, _ = await self._cached_get("%s/%s" % (self.DATA_URL, pdb_id))
        if not data:
            return {}
        exptl = data.get("exptl", [{}])[0] if data.get("exptl") else {}
        refine = data.get("refine", [{}])[0] if data.get("refine") else {}
        return {
            "title": data.get("struct", {}).get("title", ""),
            "method": exptl.get("method", ""),
            "resolution": refine.get("ls_d_res_high"),
            "r_free": refine.get("ls_R_factor_R_free"),
            "deposition_date": data.get("rcsb_accession_info", {}).get("deposit_date", ""),
        }

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        results = await self.search(entity_id, limit=1)
        return results[0] if results else None


