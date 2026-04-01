"""ChEMBL REST API connector — using enhanced base."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector


class ChEMBLConnector(BaseConnector):
    name = "ChEMBL"
    BASE = "https://www.ebi.ac.uk/chembl/api/data"
    cache_ttl = 172800  # 48h

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = "%s/molecule/search.json" % self.BASE
        params = {"q": query, "limit": min(limit, 40)}
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return []
        results: List[Dict[str, Any]] = []
        for mol in data.get("molecules", []):
            chembl_id = mol.get("molecule_chembl_id", "")
            props = mol.get("molecule_properties") or {}
            name = mol.get("pref_name") or chembl_id
            results.append({
                "id": chembl_id,
                "entity_type": "molecule",
                "canonical_name": name,
                "name": name,
                "smiles": (mol.get("molecule_structures") or {}).get("canonical_smiles", ""),
                "formula": props.get("full_molformula", ""),
                "molecular_weight": float(props["full_mwt"]) if props.get("full_mwt") else None,
                "logp": float(props["alogp"]) if props.get("alogp") else None,
                "clinical_phase": str(mol.get("max_phase", "")),
                "drug_type": mol.get("molecule_type", ""),
                "url": "https://www.ebi.ac.uk/chembl/compound_report_card/%s/" % chembl_id,
                "provenance": [self._prov(
                    url="https://www.ebi.ac.uk/chembl/compound_report_card/%s/" % chembl_id,
                    ext_id=chembl_id, confidence=1.0, reasoning="ChEMBL curated"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        url = "%s/molecule/%s.json" % (self.BASE, entity_id)
        data, meta = await self._cached_get(url)
        if not data:
            return None
        # data is the molecule JSON object returned by the ChEMBL REST API
        mol = data if isinstance(data, dict) else {}
        chembl_id = mol.get("molecule_chembl_id", entity_id)
        props = mol.get("molecule_properties") or {}
        name = mol.get("pref_name") or chembl_id
        return {
            "id": chembl_id,
            "entity_type": "molecule",
            "canonical_name": name,
            "name": name,
            "smiles": (mol.get("molecule_structures") or {}).get("canonical_smiles", ""),
            "formula": props.get("full_molformula", ""),
            "molecular_weight": float(props["full_mwt"]) if props.get("full_mwt") else None,
            "logp": float(props["alogp"]) if props.get("alogp") else None,
            "clinical_phase": str(mol.get("max_phase", "")),
            "drug_type": mol.get("molecule_type", ""),
            "url": "https://www.ebi.ac.uk/chembl/compound_report_card/%s/" % chembl_id,
            "provenance": [self._prov(
                url="https://www.ebi.ac.uk/chembl/compound_report_card/%s/" % chembl_id,
                ext_id=chembl_id, confidence=1.0, reasoning="ChEMBL curated direct fetch",
            ).to_dict()],
        }


