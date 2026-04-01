"""PubChem PUG REST connector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector


class PubChemConnector(BaseConnector):
    name = "PubChem"
    BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
    cache_ttl = 172800  # 48h — compound data is stable

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = "%s/compound/name/%s/property/MolecularFormula,MolecularWeight,CanonicalSMILES,InChIKey,XLogP,TPSA,IUPACName/JSON" % (
            self.BASE, query
        )
        data, meta = await self._cached_get(url)
        if not data:
            return await self._text_search(query, limit)
        props_list = data.get("PropertyTable", {}).get("Properties", [])
        results: List[Dict[str, Any]] = []
        for props in props_list[:limit]:
            cid = props.get("CID", "")
            results.append(self._normalize_compound(cid, props, query))
        return results

    async def _text_search(self, query: str, limit: int) -> List[Dict[str, Any]]:
        url = "https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound/%s/json" % query
        data, meta = await self._cached_get(url)
        if not data:
            return []
        suggestions = data.get("dictionary_terms", {}).get("compound", [])[:limit]
        results: List[Dict[str, Any]] = []
        for name in suggestions:
            results.append({
                "id": "PUBCHEM:%s" % name,
                "entity_type": "molecule",
                "canonical_name": name,
                "name": name,
                "provenance": [self._prov(
                    url="https://pubchem.ncbi.nlm.nih.gov/#query=%s" % name,
                    confidence=0.7, reasoning="PubChem autocomplete match"
                ).to_dict()],
            })
        return results

    def _normalize_compound(self, cid: Any, props: Dict, query: str) -> Dict[str, Any]:
        cid_str = str(cid)
        return {
            "id": "CID:%s" % cid_str,
            "entity_type": "molecule",
            "canonical_name": props.get("IUPACName", query),
            "name": props.get("IUPACName", query),
            "smiles": props.get("CanonicalSMILES", ""),
            "inchi_key": props.get("InChIKey", ""),
            "formula": props.get("MolecularFormula", ""),
            "molecular_weight": props.get("MolecularWeight"),
            "logp": props.get("XLogP"),
            "tpsa": props.get("TPSA"),
            "pubchem_url": "https://pubchem.ncbi.nlm.nih.gov/compound/%s" % cid_str,
            "provenance": [self._prov(
                url="https://pubchem.ncbi.nlm.nih.gov/compound/%s" % cid_str,
                ext_id=cid_str, confidence=1.0, reasoning="PubChem direct lookup"
            ).to_dict()],
        }

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        cid = entity_id.replace("CID:", "")
        url = "%s/compound/cid/%s/property/MolecularFormula,MolecularWeight,CanonicalSMILES,InChIKey,XLogP,TPSA,IUPACName/JSON" % (
            self.BASE, cid
        )
        data, meta = await self._cached_get(url)
        if not data:
            return None
        props = data.get("PropertyTable", {}).get("Properties", [{}])[0]
        return self._normalize_compound(cid, props, cid)


