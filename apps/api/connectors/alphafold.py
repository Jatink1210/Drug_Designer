"""AlphaFold Database connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector


class AlphaFoldConnector(BaseConnector):
    name = "AlphaFold"
    BASE = "https://alphafold.ebi.ac.uk/api"

    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search by UniProt accession."""
        url = "%s/prediction/%s" % (self.BASE, query.strip())
        data, meta = await self._cached_get(url)
        if not data:
            return []
        entries = data if isinstance(data, list) else [data]
        results: List[Dict[str, Any]] = []
        for entry in entries[:limit]:
            uid = entry.get("uniprotAccession", query)
            model_url = entry.get("pdbUrl", "")
            results.append({
                "id": "AF-%s" % uid,
                "entity_type": "structure",
                "canonical_name": "AlphaFold prediction: %s" % uid,
                "name": "AlphaFold: %s" % uid,
                "title": "AlphaFold prediction for %s" % uid,
                "pdb_id": "AF-%s" % uid,
                "method": "AlphaFold prediction",
                "resolution": None,
                "pdb_url": model_url,
                "pae_url": entry.get("paeImageUrl", ""),
                "confidence_url": entry.get("cifUrl", ""),
                "model_version": entry.get("latestVersion", 0),
                "url": "https://alphafold.ebi.ac.uk/entry/%s" % uid,
                "provenance": [self._prov(
                    url="https://alphafold.ebi.ac.uk/entry/%s" % uid,
                    ext_id=uid,
                    confidence=0.85,
                    reasoning="AlphaFold predicted structure (not experimentally determined)",
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        uid = entity_id.replace("AF-", "")
        results = await self.search(uid, limit=1)
        return results[0] if results else None


