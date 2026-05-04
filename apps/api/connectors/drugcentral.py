"""DrugCentral connector — falls back to PubChem compound search.

Original DrugCentral API (drugcentral.org/api) has no public REST endpoint.
This connector uses PubChem's free autocomplete + compound API as a
free alternative for drug compound lookups.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector

log = logging.getLogger(__name__)


class DrugCentralConnector(BaseConnector):
    name = "DrugCentral"
    BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
    cache_ttl = 86400

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        # Use PubChem autocomplete for drug name search
        ac_url = "https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound/{}/json".format(query)
        ac_data, _ = await self._cached_get(ac_url, params={"limit": min(limit, 25)})
        names: List[str] = []
        if ac_data and isinstance(ac_data, dict):
            names = (ac_data.get("dictionary_terms", {}).get("compound", []) or [])[:limit]

        if not names:
            names = [query]

        results: List[Dict[str, Any]] = []
        for drug_name in names[:limit]:
            # Get CID for this compound
            cid_url = f"{self.BASE}/compound/name/{drug_name}/cids/JSON"
            cid_data, _ = await self._cached_get(cid_url, extra_key=drug_name)
            cid = ""
            if cid_data and isinstance(cid_data, dict):
                cids = cid_data.get("IdentifierList", {}).get("CID", [])
                if cids:
                    cid = str(cids[0])
            results.append({
                "id": f"DrugCentral:PubChem:{cid}" if cid else f"DrugCentral:{drug_name}",
                "entity_type": "drug",
                "canonical_name": drug_name,
                "cid": cid,
                "url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}" if cid else "",
                "source_db": "DrugCentral (via PubChem)",
                "provenance": [self._prov(
                    url=f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}" if cid else "",
                    ext_id=cid, confidence=0.8,
                    reasoning="PubChem compound (DrugCentral alternative)"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        # Try as PubChem CID
        url = f"{self.BASE}/compound/cid/{entity_id}/JSON"
        data, meta = await self._cached_get(url)
        if data and isinstance(data, dict):
            compounds = data.get("PC_Compounds", [])
            if compounds:
                cpd = compounds[0]
                props = {p.get("urn", {}).get("label", ""): p.get("value", {}) for p in cpd.get("props", [])}
                name = props.get("IUPAC Name", {}).get("sval", entity_id)
                return {
                    "id": f"DrugCentral:PubChem:{entity_id}",
                    "entity_type": "drug",
                    "canonical_name": name if isinstance(name, str) else entity_id,
                    "source_db": "DrugCentral (via PubChem)",
                    "url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{entity_id}",
                }
        return None
