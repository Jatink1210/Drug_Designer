"""Reactome pathway API connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, strip_html


class ReactomeConnector(BaseConnector):
    name = "Reactome"
    BASE = "https://reactome.org/ContentService"
    http_timeout = 30.0  # Reactome API can be slow for complex queries

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = "%s/search/query" % self.BASE
        params = {"query": query, "types": "Pathway", "cluster": "true"}
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return []
        results: List[Dict[str, Any]] = []
        entries = data.get("results", [])
        for group in entries:
            for entry in group.get("entries", [])[:limit]:
                st_id = entry.get("stId", "")
                name = strip_html(entry.get("name", ""))
                species = entry.get("species", ["Homo sapiens"])
                sp = species[0] if species else "Homo sapiens"
                results.append({
                    "id": st_id,
                    "entity_type": "pathway",
                    "canonical_name": name,
                    "name": name,
                    "description": entry.get("summation", [""])[0] if entry.get("summation") else "",
                    "pathway_id": st_id,
                    "source_db": "Reactome",
                    "species": sp,
                    "url": "https://reactome.org/content/detail/%s" % st_id,
                    "provenance": [self._prov(
                        url="https://reactome.org/content/detail/%s" % st_id,
                        ext_id=st_id, confidence=0.95, reasoning="Reactome curated pathway"
                    ).to_dict()],
                })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        # First try to get the pathway name
        detail_url = "%s/data/query/%s" % (self.BASE, entity_id)
        detail_data, _ = await self._cached_get(detail_url)
        name = entity_id
        if detail_data and isinstance(detail_data, dict):
            name = detail_data.get("displayName", entity_id)

        # Get physical entity participants (proteins/genes) — not sub-events
        url = "%s/data/participants/%s" % (self.BASE, entity_id)
        data, meta = await self._cached_get(url)
        genes: List[str] = []
        seen: set = set()
        if isinstance(data, list):
            for participant in data:
                # Extract gene names from refEntities displayName
                # Format: "UniProt:O43543 XRCC2" → gene symbol is last token
                ref = participant.get("refEntities") or []
                if isinstance(ref, list):
                    for r in ref:
                        dn = r.get("displayName", "")
                        parts = dn.split()
                        if len(parts) >= 2:
                            gene = parts[-1]
                            if gene and gene not in seen:
                                seen.add(gene)
                                genes.append(gene)

        # Fallback: if participants returned no gene names, try containedEvents
        if not genes:
            events_url = "%s/data/pathway/%s/containedEvents" % (self.BASE, entity_id)
            events_data, _ = await self._cached_get(events_url)
            if isinstance(events_data, list):
                for ev in events_data:
                    display = ev.get("displayName", "")
                    if display and display not in seen:
                        seen.add(display)
                        genes.append(display)

        return {
            "id": entity_id,
            "entity_type": "pathway",
            "canonical_name": name,
            "pathway_id": entity_id,
            "source_db": "Reactome",
            "genes": genes[:100],
            "gene_count": len(genes),
            "url": "https://reactome.org/content/detail/%s" % entity_id,
        }


