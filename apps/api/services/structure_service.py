"""Deep RCSB PDB structure service — RCSB-grade detail fetching."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

import structlog

from core.http_client import ResilientClient
from core.cache import cache_key, async_two_tier_get, async_two_tier_put

log = structlog.get_logger()

DATA_API = "https://data.rcsb.org/rest/v1/core"
SEARCH_API = "https://search.rcsb.org/rcsbsearch/v2/query"


class StructureService:
    """Full RCSB PDB structure data fetcher."""

    def __init__(self) -> None:
        self._client = ResilientClient()

    async def close(self) -> None:
        await self._client.close()

    async def _get(self, url: str) -> Optional[Any]:
        key = cache_key("rcsb_deep", url, "")
        cached = await async_two_tier_get(key)
        if cached is not None:
            return cached
        body, meta = await self._client.get(url)
        if body is not None:
            await async_two_tier_put(key, "rcsb", url, body, ttl=172800)
        return body

    # ── Search ──────────────────────────────────────────
    async def search_structures(self, query: str, limit: int = 25) -> Dict[str, Any]:
        body = {
            "query": {"type": "terminal", "service": "full_text", "parameters": {"value": query}},
            "return_type": "entry",
            "request_options": {
                "results_content_type": ["experimental"],
                "paginate": {"start": 0, "rows": limit},
                "sort": [{"sort_by": "score", "direction": "desc"}],
            },
        }
        key = cache_key("rcsb_search", query, str(limit))
        cached = await async_two_tier_get(key)
        if cached is not None:
            return cached
        data, _ = await self._client.post(SEARCH_API, json_body=body)
        if data:
            await async_two_tier_put(key, "rcsb", SEARCH_API, data, ttl=43200)
        return data or {"result_set": [], "total_count": 0}

    # ── Full Structure Summary ──────────────────────────
    async def get_structure_summary(self, pdb_id: str) -> Dict[str, Any]:
        pdb_id = pdb_id.upper().strip()
        entry, polymer_entities, nonpolymer_entities, assemblies = await asyncio.gather(
            self._get("%s/entry/%s" % (DATA_API, pdb_id)),
            self._get("%s/polymer_entity/%s" % (DATA_API, pdb_id)),
            self._get_nonpolymer_entities(pdb_id),
            self._get("%s/assembly/%s" % (DATA_API, pdb_id)),
            return_exceptions=True,
        )

        if isinstance(entry, Exception) or entry is None:
            return {"error": "Structure %s not found" % pdb_id}

        struct = entry.get("struct", {})
        
        def _get_first(key: str) -> Dict[str, Any]:
            val = entry.get(key)
            if not val:
                return {}
            if isinstance(val, list):
                return val[0] if val else {}
            return val
            
        exptl = _get_first("exptl")
        refine = _get_first("refine")
        cell = _get_first("cell")
        citation = _get_first("citation")
        pdbx_audit = entry.get("pdbx_audit_revision_history", [])
        acc = entry.get("rcsb_accession_info", {})

        # Parse polymer entities (chains)
        macromolecules = self._parse_polymer_entities(polymer_entities if not isinstance(polymer_entities, Exception) else None)

        # Ligands
        ligands = self._parse_nonpolymer_entities(nonpolymer_entities if not isinstance(nonpolymer_entities, Exception) else [])

        # Assemblies
        assembly_list = self._parse_assemblies(assemblies if not isinstance(assemblies, Exception) else None)

        return {
            "pdb_id": pdb_id,
            "title": struct.get("title", ""),
            "classification": entry.get("struct_keywords", {}).get("pdbx_keywords", ""),
            "organism": self._extract_organism(entry),
            "expression_system": self._extract_expression_system(entry),
            "method": exptl.get("method", ""),
            "resolution": refine.get("ls_d_res_high"),
            "r_work": refine.get("ls_R_factor_R_work"),
            "r_free": refine.get("ls_R_factor_R_free"),
            "space_group": cell.get("space_group_name_H_M", ""),
            "cell_dimensions": {
                "a": cell.get("length_a"), "b": cell.get("length_b"), "c": cell.get("length_c"),
                "alpha": cell.get("angle_alpha"), "beta": cell.get("angle_beta"), "gamma": cell.get("angle_gamma"),
            },
            "deposition_date": acc.get("deposit_date", ""),
            "release_date": acc.get("initial_release_date", ""),
            "revision_date": acc.get("revision_date", ""),
            "primary_citation": {
                "title": citation.get("title", ""),
                "journal": citation.get("journal_abbrev", ""),
                "year": citation.get("year"),
                "doi": citation.get("pdbx_database_id_DOI", ""),
                "pmid": citation.get("pdbx_database_id_PubMed", ""),
            },
            "macromolecules": macromolecules,
            "ligands": ligands,
            "assemblies": assembly_list,
            "revision_count": len(pdbx_audit),
            "revision_history": [
                {"version": r.get("major_revision"), "date": r.get("revision_date", ""), "type": r.get("data_content_type", "")}
                for r in pdbx_audit[:20]
            ],
            "downloads": {
                "mmcif": "https://files.rcsb.org/download/%s.cif" % pdb_id,
                "pdb": "https://files.rcsb.org/download/%s.pdb" % pdb_id,
                "fasta": "https://www.rcsb.org/fasta/entry/%s" % pdb_id,
                "validation_xml": "https://files.rcsb.org/pub/pdb/validation_reports/%s/%s/%s_validation.xml.gz" % (pdb_id[1:3].lower(), pdb_id.lower(), pdb_id.lower()),
                "validation_pdf": "https://files.rcsb.org/pub/pdb/validation_reports/%s/%s/%s_full_validation.pdf.gz" % (pdb_id[1:3].lower(), pdb_id.lower(), pdb_id.lower()),
            },
            "url": "https://www.rcsb.org/structure/%s" % pdb_id,
        }

    async def _get_nonpolymer_entities(self, pdb_id: str) -> List[Any]:
        data = await self._get("%s/nonpolymer_entity/%s" % (DATA_API, pdb_id))
        if data is None:
            return []
        return data if isinstance(data, list) else [data]

    def _parse_polymer_entities(self, data: Any) -> List[Dict[str, Any]]:
        if not data:
            return []
        entities = data if isinstance(data, list) else [data]
        result = []
        for ent in entities:
            entity_id = ent.get("rcsb_id", "")
            poly = ent.get("entity_poly", {})
            src = (ent.get("rcsb_entity_source_organism") or [{}])[0]
            uniprot_ids = []
            for xref in ent.get("rcsb_polymer_entity_container_identifiers", {}).get("uniprot_ids", []):
                if isinstance(xref, str):
                    uniprot_ids.append(xref)

            result.append({
                "entity_id": entity_id,
                "type": poly.get("type", ""),
                "chains": poly.get("pdbx_strand_id", "").split(","),
                "length": poly.get("rcsb_sample_sequence_length"),
                "sequence": poly.get("pdbx_seq_one_letter_code_can", "")[:200],
                "organism": src.get("ncbi_scientific_name", ""),
                "uniprot_ids": uniprot_ids,
                "gene_names": [g.get("value", "") for g in (ent.get("rcsb_gene_name") or [])],
                "description": ent.get("rcsb_polymer_entity", {}).get("pdbx_description", ""),
            })
        return result

    def _parse_nonpolymer_entities(self, entities: List[Any]) -> List[Dict[str, Any]]:
        result = []
        for ent in entities:
            if not isinstance(ent, dict):
                continue
            comp_id = ent.get("rcsb_id", "").split("_")[-1] if "_" in ent.get("rcsb_id", "") else ent.get("rcsb_id", "")
            ne = ent.get("rcsb_nonpolymer_entity", {})
            result.append({
                "comp_id": comp_id,
                "name": ne.get("pdbx_description", ""),
                "formula": ne.get("formula_weight"),
                "type": "ligand",
            })
        return result

    def _parse_assemblies(self, data: Any) -> List[Dict[str, Any]]:
        if not data:
            return []
        assemblies = data if isinstance(data, list) else [data]
        result = []
        for asm in assemblies:
            info = asm.get("rcsb_struct_symmetry", [{}])
            rcsb_asm = asm.get("rcsb_assembly_info", {})
            result.append({
                "assembly_id": asm.get("rcsb_id", "").split("-")[-1] if "-" in asm.get("rcsb_id", "") else "1",
                "polymer_entity_count": rcsb_asm.get("polymer_entity_count"),
                "oligomeric_state": (info[0].get("oligomeric_state", "") if info else ""),
                "kind": (info[0].get("kind", "") if info else ""),
            })
        return result

    def _extract_organism(self, entry: Dict) -> str:
        src = entry.get("rcsb_entry_info", {}).get("deposited_polymer_entity_instance_count", 0)
        for poly in (entry.get("polymer_entities") or []):
            srcs = poly.get("rcsb_entity_source_organism", [])
            if srcs:
                return srcs[0].get("ncbi_scientific_name", "")
        return ""

    def _extract_expression_system(self, entry: Dict) -> str:
        for poly in (entry.get("polymer_entities") or []):
            hosts = poly.get("rcsb_entity_host_organism", [])
            if hosts:
                return hosts[0].get("ncbi_scientific_name", "")
        return ""

    # ── Annotations (Pfam, GO, InterPro) ────────────────
    async def get_annotations(self, pdb_id: str) -> Dict[str, Any]:
        pdb_id = pdb_id.upper().strip()
        entry = await self._get("%s/entry/%s" % (DATA_API, pdb_id))
        if not entry:
            return {"error": "not found"}
        polymer = await self._get("%s/polymer_entity/%s" % (DATA_API, pdb_id))
        entities = polymer if isinstance(polymer, list) else [polymer] if polymer else []

        annotations = {"pfam": [], "interpro": [], "go": [], "ec": [], "ptms": []}
        for ent in entities:
            if not isinstance(ent, dict):
                continue
            for feat in (ent.get("rcsb_polymer_entity_feature") or []):
                ftype = feat.get("type", "")
                if "Pfam" in ftype:
                    annotations["pfam"].append({"id": feat.get("feature_id", ""), "name": feat.get("name", ""), "type": ftype})
                elif "InterPro" in ftype:
                    annotations["interpro"].append({"id": feat.get("feature_id", ""), "name": feat.get("name", "")})
            for go in (ent.get("rcsb_polymer_entity_annotation") or []):
                if go.get("type") == "GO":
                    annotations["go"].append({"id": go.get("annotation_id", ""), "name": go.get("name", "")})
            ec = ent.get("rcsb_polymer_entity", {}).get("rcsb_ec_lineage", [])
            for e in ec:
                annotations["ec"].append({"id": e.get("id", ""), "name": e.get("name", "")})
        return annotations

    # ── Experiment Details ──────────────────────────────
    async def get_experiment(self, pdb_id: str) -> Dict[str, Any]:
        entry = await self._get("%s/entry/%s" % (DATA_API, pdb_id))
        if not entry:
            return {"error": "not found"}
        exptl = (entry.get("exptl") or [{}])[0]
        refine = (entry.get("refine") or [{}])[0]
        cell = (entry.get("cell") or [{}])[0]
        diffrn = (entry.get("diffrn") or [{}])[0]
        diffrn_source = (entry.get("diffrn_source") or [{}])[0]
        software = entry.get("software", [])

        return {
            "method": exptl.get("method", ""),
            "crystal_growth": {
                "method": (entry.get("exptl_crystal_grow") or [{}])[0].get("method", ""),
                "pH": (entry.get("exptl_crystal_grow") or [{}])[0].get("pH"),
                "temp": (entry.get("exptl_crystal_grow") or [{}])[0].get("temp"),
            },
            "data_collection": {
                "temperature": diffrn.get("ambient_temp"),
                "source": diffrn_source.get("source", ""),
                "type": diffrn_source.get("type", ""),
                "wavelength": (entry.get("diffrn_radiation_wavelength") or [{}])[0].get("wavelength") if entry.get("diffrn_radiation_wavelength") else None,
            },
            "refinement": {
                "resolution": refine.get("ls_d_res_high"),
                "r_work": refine.get("ls_R_factor_R_work"),
                "r_free": refine.get("ls_R_factor_R_free"),
                "reflections_observed": refine.get("ls_number_reflns_obs"),
                "reflections_rfree": refine.get("ls_number_reflns_R_free"),
            },
            "cell": {
                "space_group": cell.get("space_group_name_H_M", ""),
                "a": cell.get("length_a"), "b": cell.get("length_b"), "c": cell.get("length_c"),
                "alpha": cell.get("angle_alpha"), "beta": cell.get("angle_beta"), "gamma": cell.get("angle_gamma"),
                "z_pdb": cell.get("Z_PDB"),
            },
            "software": [{"name": s.get("name", ""), "version": s.get("version", ""), "classification": s.get("classification", "")} for s in (software or [])[:10]],
        }

    # ── Sequence per chain ──────────────────────────────
    async def get_sequences(self, pdb_id: str) -> List[Dict[str, Any]]:
        polymer = await self._get("%s/polymer_entity/%s" % (DATA_API, pdb_id))
        entities = polymer if isinstance(polymer, list) else [polymer] if polymer else []
        result = []
        for ent in entities:
            if not isinstance(ent, dict):
                continue
            poly = ent.get("entity_poly", {})
            features = []
            for inst in (ent.get("rcsb_polymer_entity_feature") or []):
                features.append({
                    "type": inst.get("type", ""),
                    "name": inst.get("name", ""),
                    "start": inst.get("feature_positions", [{}])[0].get("beg_seq_id") if inst.get("feature_positions") else None,
                    "end": inst.get("feature_positions", [{}])[0].get("end_seq_id") if inst.get("feature_positions") else None,
                })
            result.append({
                "entity_id": ent.get("rcsb_id", ""),
                "chains": poly.get("pdbx_strand_id", "").split(","),
                "length": poly.get("rcsb_sample_sequence_length"),
                "sequence": poly.get("pdbx_seq_one_letter_code_can", ""),
                "type": poly.get("type", ""),
                "features": features,
            })
        return result

    # ── AlphaFold fallback ──────────────────────────────
    async def get_alphafold(self, uniprot_id: str) -> Optional[Dict[str, Any]]:
        url = "https://alphafold.ebi.ac.uk/api/prediction/%s" % uniprot_id.strip()
        data = await self._get(url)
        if not data:
            return None
        entry = data[0] if isinstance(data, list) else data
        uid = entry.get("uniprotAccession", uniprot_id)
        return {
            "uniprot_id": uid,
            "model_url": entry.get("pdbUrl", ""),
            "cif_url": entry.get("cifUrl", ""),
            "pae_image_url": entry.get("paeImageUrl", ""),
            "model_version": entry.get("latestVersion"),
            "confidence": "pLDDT-based (predicted)",
            "url": "https://alphafold.ebi.ac.uk/entry/%s" % uid,
            "downloads": {
                "pdb": entry.get("pdbUrl", ""),
                "cif": entry.get("cifUrl", ""),
                "pae_json": entry.get("paeDocUrl", ""),
            },
        }

    # ── ESM → AlphaFold → RCSB Fallback Chain (Req 6.2, 6.5) ──
    async def get_structure_with_fallback(self, protein_id: str) -> Dict[str, Any]:
        """Fetch structure using ESM → AlphaFold → RCSB PDB fallback chain.

        Returns structure data with 'source' field indicating which source provided it.
        """
        # 1. Try ESM API first
        try:
            esm_url = f"https://api.esmatlas.com/fetchPredictedStructure/{protein_id.strip()}"
            esm_data = await self._get(esm_url)
            if esm_data:
                return {
                    "source": "esm",
                    "data": esm_data,
                    "protein_id": protein_id,
                    "degraded": False,
                }
        except Exception as e:
            log.debug("esm_fetch_failed", protein_id=protein_id, error=str(e))

        # 2. Try AlphaFold
        try:
            af_data = await self.get_alphafold(protein_id)
            if af_data:
                return {
                    "source": "alphafold",
                    "data": af_data,
                    "protein_id": protein_id,
                    "degraded": False,
                }
        except Exception as e:
            log.debug("alphafold_fetch_failed", protein_id=protein_id, error=str(e))

        # 3. Try RCSB PDB
        try:
            pdb_data = await self.get_structure_summary(protein_id)
            if pdb_data and "error" not in pdb_data:
                return {
                    "source": "rcsb",
                    "data": pdb_data,
                    "protein_id": protein_id,
                    "degraded": True,  # Fell back to RCSB
                }
        except Exception as e:
            log.debug("rcsb_fetch_failed", protein_id=protein_id, error=str(e))

        # All sources failed
        return {
            "source": "no_structure_available",
            "data": None,
            "protein_id": protein_id,
            "degraded": True,
            "error": f"No structure found for {protein_id} from ESM, AlphaFold, or RCSB PDB",
        }
