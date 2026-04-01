"""UniProt REST API connector — using enhanced base."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector


class UniProtConnector(BaseConnector):
    name = "UniProt"
    BASE = "https://rest.uniprot.org"

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        url = "%s/uniprotkb/search" % self.BASE
        params = {
            "query": query,
            "format": "json",
            "size": min(limit, 50),
            "fields": "accession,gene_names,organism_name,protein_name,length,xref_pdb,sequence",
        }
        data, meta = await self._cached_get(url, params=params)
        if not data:
            return []
        results: List[Dict[str, Any]] = []
        for entry in data.get("results", []):
            acc = entry.get("primaryAccession", "")
            gene_names = entry.get("genes", [{}])
            gene = gene_names[0].get("geneName", {}).get("value", "") if gene_names else ""
            prot_name = (
                entry.get("proteinDescription", {})
                .get("recommendedName", {})
                .get("fullName", {})
                .get("value", acc)
            )
            organism = entry.get("organism", {}).get("scientificName", "")
            length = entry.get("sequence", {}).get("length")
            pdb_refs = entry.get("uniProtKBCrossReferences", [])
            pdb_ids = [x.get("id", "") for x in pdb_refs if x.get("database") == "PDB"]
            results.append({
                "id": acc,
                "entity_type": "protein",
                "canonical_name": prot_name,
                "name": prot_name,
                "description": "%s (%s)" % (prot_name, gene) if gene else prot_name,
                "gene_symbol": gene,
                "organism": organism,
                "length": length,
                "uniprot_id": acc,
                "pdb_ids": pdb_ids[:10],
                "url": "https://www.uniprot.org/uniprotkb/%s" % acc,
                "provenance": [self._prov(
                    url="https://www.uniprot.org/uniprotkb/%s" % acc,
                    ext_id=acc, confidence=1.0, reasoning="UniProt reviewed entry"
                ).to_dict()],
            })
        return results

    async def fetch_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        results = await self.search(entity_id, limit=1)
        return results[0] if results else None


