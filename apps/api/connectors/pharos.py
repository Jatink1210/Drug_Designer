"""Pharos (TCRD/IDG) connector — GraphQL target knowledge base.

API Reference: https://pharos.ncats.nih.gov/
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector


class PharosConnector(BaseConnector):
    name = "Pharos"
    BASE = "https://pharos-api.ncats.io/graphql"
    cache_ttl = 86400

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        gql = {
            "query": (
                "query($term:String!,$top:Int)"
                "{targets(filter:{term:$term}){count targets(top:$top)"
                "{name sym uniprot tdl fam description}}}"
            ),
            "variables": {"term": query, "top": min(limit, 50)},
        }
        data, meta = await self._cached_post(self.BASE, json_body=gql, extra_key=query)
        if not data:
            return []
        targets = (
            data.get("data", {})
            .get("targets", {})
            .get("targets", [])
        )
        results: List[Dict[str, Any]] = []
        for t in targets:
            uniprot = t.get("uniprot", "")
            gene_sym = t.get("sym", "")
            results.append({
                "id": f"Pharos:{uniprot}" if uniprot else t.get("name", ""),
                "entity_type": "target",
                "canonical_name": t.get("name", ""),
                "symbol": gene_sym,
                "gene_symbol": gene_sym,
                "uniprot": uniprot,
                "tdl": t.get("tdl", ""),
                "idg_family": t.get("fam", ""),
                "description": (t.get("description") or "")[:500],
                "url": f"https://pharos.ncats.nih.gov/targets/{uniprot}" if uniprot else "",
                "provenance": [self._prov(
                    url=f"https://pharos.ncats.nih.gov/targets/{uniprot}",
                    ext_id=uniprot, confidence=0.95, reasoning="Pharos IDG GraphQL"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        gql = {
            "query": (
                "query($acc:String!){target(q:{uniprot:$acc}){"
                "name uniprot tdl fam description novelty}}"
            ),
            "variables": {"acc": entity_id},
        }
        data, meta = await self._cached_post(self.BASE, json_body=gql, extra_key=entity_id)
        if not data:
            return None
        t = data.get("data", {}).get("target", {})
        if not t:
            return None
        return {
            "id": f"Pharos:{t.get('uniprot', entity_id)}",
            "entity_type": "target",
            "canonical_name": t.get("name", ""),
            "uniprot": t.get("uniprot", ""),
            "tdl": t.get("tdl", ""),
            "novelty": t.get("novelty"),
            "provenance": [self._prov(
                url=f"https://pharos.ncats.nih.gov/targets/{entity_id}",
                ext_id=entity_id, confidence=0.95, reasoning="Pharos IDG GraphQL"
            ).to_dict()],
        }
