"""Unified Entity Intelligence router.

Merges disease, target, gene/protein, pathway, graph, and PPI analysis behind
one canonical endpoint for the frontend Entity Intelligence page.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Literal, Optional

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from models.envelope import build_envelope
from routers.auth import get_current_user
from services.disease.database_searchers import search_all_databases
from services.disease.disease_normalizer import normalize_disease_name
from services.disease.uniprot_mapper import map_genes_to_uniprot
from services.graph.analytics import GraphAnalytics
from services.target_scorer import TargetScorer

log = structlog.get_logger(__name__)
router = APIRouter(
    prefix="/api/v1/entity-intelligence",
    tags=["Entity Intelligence"],
    dependencies=[Depends(get_current_user)],
)

SlotType = Literal["drug", "disease", "molecule", "gene", "protein", "blank", "variant"]


class EntitySlotInput(BaseModel):
    slot_index: int = Field(ge=0, le=4)
    declared_type: SlotType = "blank"
    value: str = ""
    values: List[str] = Field(default_factory=list)


class EntityIntelligenceAnalyzeRequest(BaseModel):
    slots: List[EntitySlotInput] = Field(default_factory=list, max_length=5)
    graph_max_nodes: int = 600
    graph_depth: int = 2


def _clean_entries(slot: EntitySlotInput) -> List[str]:
    entries = [slot.value, *slot.values]
    cleaned: List[str] = []
    seen: set[str] = set()
    for entry in entries:
        for part in str(entry or "").replace("\t", ",").split(","):
            normalized = part.strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(normalized)
    return cleaned


def _infer_type(value: str) -> SlotType:
    upper = value.upper().strip()
    if upper.startswith("RS") or "*" in value:
        return "variant"
    if upper.startswith("DB") or len(value) > 12 and any(ch.isdigit() for ch in value):
        return "drug"
    if len(upper) <= 8 and upper.isalnum() and any(ch.isalpha() for ch in upper):
        return "gene"
    return "blank"


def _shared_entity(
    entity_id: str,
    entity_type: str,
    entity_name: str,
    source_category: str,
    identifiers: Optional[Dict[str, str]] = None,
    attributes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "entityId": entity_id,
        "entityType": entity_type,
        "entityName": entity_name,
        "sourceCategory": source_category,
        "identifiers": identifiers or {},
        "attributes": attributes or {},
    }


def _shared_provenance(
    source: str,
    *,
    confidence: Optional[float] = None,
    source_record_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "source": source,
        "sourceRecordId": source_record_id,
        "confidence": confidence,
        "retrievedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


async def _resolve_disease(value: str) -> Dict[str, Any]:
    normalized = await asyncio.to_thread(normalize_disease_name, value)
    identifiers = {
        key.upper(): str(val)
        for key, val in (normalized.get("identifiers") or {}).items()
        if val
    }
    entity = _shared_entity(
        entity_id=identifiers.get("MONDO") or identifiers.get("OMIM") or f"disease:{value.lower().replace(' ', '_')}",
        entity_type="disease",
        entity_name=normalized.get("preferred_name") or value,
        source_category="entity-intelligence",
        identifiers=identifiers,
        attributes={
            "synonyms": normalized.get("synonyms") or [],
            "resolutionConfidence": normalized.get("confidence") or 0,
            "alternatives": normalized.get("synonyms") or [],
            "conflicts": [],
        },
    )
    return {
        "slotType": "disease",
        "query": value,
        "resolved": [entity],
        "alternatives": normalized.get("synonyms") or [],
        "conflicts": [],
        "provenance": [_shared_provenance("disease_normalizer", confidence=normalized.get("confidence") or 0)],
    }


async def _resolve_gene(value: str) -> Dict[str, Any]:
    from connectors.ensembl import EnsemblConnector

    connector = EnsemblConnector()
    try:
        matches = await connector.search(value, limit=5)
    finally:
        await connector.close()

    resolved = []
    for match in matches[:5]:
        identifiers = {"HGNC": value.upper()}
        if match.get("id"):
            identifiers["ENSEMBL"] = str(match["id"])
        resolved.append(_shared_entity(
            entity_id=match.get("id") or value.upper(),
            entity_type="gene",
            entity_name=value.upper(),
            source_category="entity-intelligence",
            identifiers=identifiers,
            attributes={
                "description": match.get("type") or "Gene symbol match",
                "resolutionConfidence": 0.85 if match.get("id") else 0.55,
                "alternatives": [m.get("id") for m in matches[1:4] if m.get("id")],
                "conflicts": [],
            },
        ))

    if not resolved:
        resolved = [_shared_entity(
            entity_id=value.upper(),
            entity_type="gene",
            entity_name=value.upper(),
            source_category="entity-intelligence",
            identifiers={"HGNC": value.upper()},
            attributes={"resolutionConfidence": 0.4, "alternatives": [], "conflicts": ["No Ensembl cross-match found"]},
        )]

    return {
        "slotType": "gene",
        "query": value,
        "resolved": resolved,
        "alternatives": [m.get("id") for m in matches[1:4] if m.get("id")],
        "conflicts": [],
        "provenance": [_shared_provenance("ensembl", confidence=0.85)],
    }


async def _resolve_protein(value: str) -> Dict[str, Any]:
    from connectors.uniprot import UniProtConnector

    connector = UniProtConnector()
    try:
        matches = await connector.search(value, limit=5)
    finally:
        await connector.close()

    resolved = []
    for match in matches[:5]:
        uniprot_id = str(match.get("uniprot_id") or match.get("id") or value)
        pdb_ids = [str(p) for p in (match.get("pdb_ids") or [])[:5]]
        identifiers = {"UNIPROT": uniprot_id, "ALPHAFOLD": f"AF-{uniprot_id}-F1"}
        if pdb_ids:
            identifiers["PDB"] = pdb_ids[0]
        resolved.append(_shared_entity(
            entity_id=uniprot_id,
            entity_type="protein",
            entity_name=match.get("canonical_name") or match.get("name") or value,
            source_category="entity-intelligence",
            identifiers=identifiers,
            attributes={
                "geneSymbol": match.get("gene_symbol") or value.upper(),
                "organism": match.get("organism") or "",
                "pdbIds": pdb_ids,
                "resolutionConfidence": 0.92,
                "alternatives": [m.get("uniprot_id") or m.get("id") for m in matches[1:4]],
                "conflicts": [],
            },
        ))

    if not resolved:
        resolved = [_shared_entity(
            entity_id=value,
            entity_type="protein",
            entity_name=value,
            source_category="entity-intelligence",
            identifiers={"UNIPROT": value},
            attributes={"resolutionConfidence": 0.35, "alternatives": [], "conflicts": ["No UniProt match found"]},
        )]

    return {
        "slotType": "protein",
        "query": value,
        "resolved": resolved,
        "alternatives": [m.get("uniprot_id") or m.get("id") for m in matches[1:4]],
        "conflicts": [],
        "provenance": [_shared_provenance("UniProt", confidence=0.92)],
    }


async def _resolve_molecule_or_drug(value: str, declared_type: SlotType) -> Dict[str, Any]:
    from connectors.chembl import ChEMBLConnector
    from connectors.pubchem import PubChemConnector
    from connectors.drugbank import DrugBankConnector
    from connectors.drugcentral import DrugCentralConnector
    from connectors.chebi import ChEBIConnector

    connectors = [
        ("ChEMBL", ChEMBLConnector()),
        ("PubChem", PubChemConnector()),
        ("DrugBank", DrugBankConnector()),
        ("DrugCentral", DrugCentralConnector()),
        ("ChEBI", ChEBIConnector()),
    ]
    degraded: List[str] = []
    source_hits: Dict[str, List[Dict[str, Any]]] = {}
    try:
        results = await asyncio.gather(*(connector.search(value, limit=3) for _, connector in connectors), return_exceptions=True)
        for (source_name, _connector), result in zip(connectors, results):
            if isinstance(result, Exception):
                log.warning("entity_resolution_failed", source=source_name, query=value, error=str(result))
                degraded.append(source_name)
                continue
            source_hits[source_name] = result[:3]
    finally:
        await asyncio.gather(*(connector.close() for _, connector in connectors), return_exceptions=True)

    identifiers: Dict[str, str] = {}
    alternatives: List[str] = []
    for source_name, matches in source_hits.items():
        if not matches:
            continue
        first = matches[0]
        source_key = source_name.upper().replace(" ", "_")
        if first.get("id"):
            identifiers[source_key] = str(first["id"])
        if first.get("cid") and "PUBCHEM" not in identifiers:
            identifiers["PUBCHEM"] = str(first["cid"])
        if first.get("smiles") and "SMILES" not in identifiers:
            identifiers["SMILES"] = str(first["smiles"])
        alternatives.extend(str(m.get("id") or m.get("canonical_name") or "") for m in matches[1:3] if m)

    entity_kind = "drug" if declared_type == "drug" else "molecule"
    resolved = [_shared_entity(
        entity_id=identifiers.get("CHEMBL") or identifiers.get("PUBCHEM") or identifiers.get("DRUGBANK") or value,
        entity_type=entity_kind,
        entity_name=value,
        source_category="entity-intelligence",
        identifiers=identifiers,
        attributes={
            "resolutionConfidence": 0.9 if identifiers else 0.45,
            "alternatives": [alt for alt in alternatives if alt],
            "conflicts": [f"Unavailable sources: {', '.join(degraded)}"] if degraded else [],
            "degradedSources": degraded,
        },
    )]
    return {
        "slotType": entity_kind,
        "query": value,
        "resolved": resolved,
        "alternatives": [alt for alt in alternatives if alt],
        "conflicts": [f"Unavailable sources: {', '.join(degraded)}"] if degraded else [],
        "provenance": [_shared_provenance(source_name, confidence=0.85) for source_name in source_hits.keys()],
        "degradedSources": degraded,
    }


async def _resolve_variant(value: str) -> Dict[str, Any]:
    from connectors.clinvar import ClinVarConnector
    from connectors.dbsnp import DbSnpConnector
    from connectors.pharmvar import PharmVarConnector
    from connectors.cpic import CPICConnector
    from connectors.gnomad import GnomadConnector
    from connectors.indigen_loader import IndiGenLoader
    from connectors.igvdb_loader import IGVDBLoader
    from connectors.genomeasia_loader import GenomeAsiaLoader

    connectors = [
        ("ClinVar", ClinVarConnector()),
        ("dbSNP", DbSnpConnector()),
        ("PharmVar", PharmVarConnector()),
        ("CPIC", CPICConnector()),
        ("gnomAD", GnomadConnector()),
        ("IndiGen", IndiGenLoader()),
        ("IGVDB", IGVDBLoader()),
        ("GenomeAsia", GenomeAsiaLoader()),
    ]
    source_hits: Dict[str, List[Dict[str, Any]]] = {}
    degraded: List[str] = []
    try:
        results = await asyncio.gather(*(connector.search(value, limit=3) for _, connector in connectors), return_exceptions=True)
        for (source_name, _connector), result in zip(connectors, results):
            if isinstance(result, Exception):
                degraded.append(source_name)
                log.warning("variant_resolution_failed", source=source_name, query=value, error=str(result))
                continue
            source_hits[source_name] = result[:3]
    finally:
        await asyncio.gather(*(connector.close() for _, connector in connectors), return_exceptions=True)

    identifiers: Dict[str, str] = {}
    alternatives: List[str] = []
    for source_name, matches in source_hits.items():
        if not matches:
            continue
        first = matches[0]
        if first.get("id"):
            identifiers[source_name.upper().replace(" ", "_")] = str(first["id"])
        if source_name == "dbSNP" and first.get("id"):
            identifiers["DBSNP"] = str(first["id"])
        alternatives.extend(str(m.get("id") or m.get("canonical_name") or "") for m in matches[1:3] if m)

    resolved = [_shared_entity(
        entity_id=identifiers.get("DBSNP") or identifiers.get("CLINVAR") or value,
        entity_type="variant",
        entity_name=value,
        source_category="entity-intelligence",
        identifiers=identifiers,
        attributes={
            "resolutionConfidence": 0.82 if identifiers else 0.35,
            "alternatives": [alt for alt in alternatives if alt],
            "conflicts": [f"Unavailable sources: {', '.join(degraded)}"] if degraded else [],
            "degradedSources": degraded,
        },
    )]
    return {
        "slotType": "variant",
        "query": value,
        "resolved": resolved,
        "alternatives": [alt for alt in alternatives if alt],
        "conflicts": [f"Unavailable sources: {', '.join(degraded)}"] if degraded else [],
        "provenance": [_shared_provenance(source_name, confidence=0.8) for source_name in source_hits.keys()],
        "degradedSources": degraded,
    }


async def _resolve_slot(slot: EntitySlotInput) -> Dict[str, Any]:
    entries = _clean_entries(slot)
    if not entries:
        return {
            "slotIndex": slot.slot_index,
            "declaredType": slot.declared_type,
            "resolvedType": slot.declared_type,
            "queryValues": [],
            "results": [],
            "alternatives": [],
            "conflicts": [],
            "provenance": [],
            "degradedSources": [],
        }

    resolved_results = []
    provenance = []
    alternatives = []
    conflicts = []
    degraded_sources = []
    resolved_type: SlotType = slot.declared_type
    for entry in entries:
        entry_type = slot.declared_type if slot.declared_type != "blank" else _infer_type(entry)
        resolved_type = entry_type
        if entry_type == "disease":
            result = await _resolve_disease(entry)
        elif entry_type == "gene":
            result = await _resolve_gene(entry)
        elif entry_type == "protein":
            result = await _resolve_protein(entry)
        elif entry_type in {"molecule", "drug"}:
            result = await _resolve_molecule_or_drug(entry, entry_type)
        elif entry_type == "variant":
            result = await _resolve_variant(entry)
        else:
            result = await _resolve_gene(entry)
            resolved_type = "gene"
        resolved_results.extend(result.get("resolved") or [])
        provenance.extend(result.get("provenance") or [])
        alternatives.extend(result.get("alternatives") or [])
        conflicts.extend(result.get("conflicts") or [])
        degraded_sources.extend(result.get("degradedSources") or [])

    return {
        "slotIndex": slot.slot_index,
        "declaredType": slot.declared_type,
        "resolvedType": resolved_type,
        "queryValues": entries,
        "results": resolved_results,
        "alternatives": [alt for alt in alternatives if alt],
        "conflicts": conflicts,
        "provenance": provenance,
        "degradedSources": sorted(set(degraded_sources)),
    }


async def _analyze_disease_queries(disease_queries: List[str]) -> Dict[str, Any]:
    if not disease_queries:
        return {"queries": [], "candidateGenes": [], "degradedSources": []}

    query_results = []
    all_candidates: Dict[str, Dict[str, Any]] = {}
    degraded_sources: set[str] = set()
    for query in disease_queries:
        normalized = await asyncio.to_thread(normalize_disease_name, query)
        search_results = await asyncio.to_thread(search_all_databases, normalized)
        gene_details: Dict[str, Dict[str, Any]] = {}
        gene_source_map: Dict[str, List[str]] = defaultdict(list)
        for source_result in search_results:
            source_name = str(source_result.get("database") or "unknown")
            genes = source_result.get("genes") or []
            if not genes:
                degraded_sources.add(source_name)
            for gene in genes:
                gene_source_map[gene].append(source_name)
            for gene, details in (source_result.get("gene_details") or {}).items():
                best = gene_details.get(gene, {})
                if details.get("score", 0) >= best.get("score", 0):
                    gene_details[gene] = details
        uniprot_map = await map_genes_to_uniprot(list(gene_source_map.keys()))
        candidates = []
        for gene, sources in gene_source_map.items():
            details = gene_details.get(gene, {})
            candidate = {
                "symbol": gene,
                "name": details.get("name") or gene,
                "target_id": details.get("target_id") or "",
                "overall_score": round(float(details.get("score") or 0), 4),
                "uniprot_id": uniprot_map.get(gene),
                "source_count": len(sources),
                "sources": sorted(set(sources)),
            }
            candidates.append(candidate)
            existing = all_candidates.get(gene)
            if not existing or candidate["overall_score"] >= existing["overall_score"]:
                all_candidates[gene] = candidate
        candidates.sort(key=lambda item: item["overall_score"], reverse=True)
        query_results.append({
            "query": query,
            "normalized": normalized.get("preferred_name") or query,
            "identifiers": normalized.get("identifiers") or {},
            "candidateGenes": candidates[:25],
        })

    return {
        "queries": query_results,
        "candidateGenes": sorted(all_candidates.values(), key=lambda item: item["overall_score"], reverse=True)[:50],
        "degradedSources": sorted(degraded_sources),
    }


async def _prioritize_targets(disease_label: str, genes: List[str]) -> Dict[str, Any]:
    if not genes:
        return {"targets": [], "degradedSources": []}
    scorer = TargetScorer(query_id=disease_label or "entity-intelligence", candidates=genes[:25])
    ranked = await scorer.evaluate_candidates()
    ranked.sort(key=lambda item: item.get("composite_score", 0), reverse=True)
    targets = []
    for index, item in enumerate(ranked, start=1):
        signals = item.get("signals") or {}
        targets.append({
            "symbol": item.get("gene_symbol") or item.get("symbol") or "",
            "rank": index,
            "composite_score": round(float(item.get("composite_score") or 0), 4),
            "ucb_score": round(float(item.get("ucb_score") or 0), 4),
            "uncertainty": round(float((item.get("ucb_score") or 0) - (item.get("composite_score") or 0)), 4),
            "contradiction_flag": bool(item.get("contradiction_flag")),
            "signals": signals,
            "explanation": item.get("explanation") or "",
            "evidence_count": sum(1 for score in signals.values() if score and score > 0),
            "sources": [name for name, score in signals.items() if score and score > 0],
        })
    return {"targets": targets[:25], "degradedSources": []}


async def _build_ppi_network(genes: List[str]) -> Dict[str, Any]:
    if not genes:
        return {"nodes": [], "edges": [], "queryGenes": []}
    from connectors.string_db import STRINGConnector

    connector = STRINGConnector()
    try:
        interactions = await connector.search("%0d".join(genes[:20]), limit=200)
    finally:
        await connector.close()

    node_map: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    query_genes = {gene.upper() for gene in genes[:20]}
    for interaction in interactions:
        source = str(interaction.get("source_entity") or "")
        target = str(interaction.get("target_entity") or "")
        if not source or not target:
            continue
        score = float(interaction.get("score") or 0)
        node_map.setdefault(source, {"id": source, "label": source, "type": "protein", "properties": {"isQueryGene": source.upper() in query_genes}})
        node_map.setdefault(target, {"id": target, "label": target, "type": "protein", "properties": {"isQueryGene": target.upper() in query_genes}})
        edges.append({
            "id": interaction.get("id") or f"{source}-{target}",
            "source": source,
            "target": target,
            "label": "INTERACTS_WITH",
            "type": "interaction",
            "properties": {
                "confidence": score,
                "source_name": "STRING DB",
                "source_family": "ppi",
            },
        })
    for gene in query_genes:
        node_map.setdefault(gene, {"id": gene, "label": gene, "type": "protein", "properties": {"isQueryGene": True}})
    return {"nodes": list(node_map.values()), "edges": edges, "queryGenes": sorted(query_genes)}


async def _build_pathway_enrichment(genes: List[str]) -> Dict[str, Any]:
    if not genes:
        return {"enrichedPathways": [], "goTerms": []}
    from connectors.reactome import ReactomeConnector
    from connectors.gene_ontology import GeneOntologyConnector

    reactome = ReactomeConnector()
    go = GeneOntologyConnector()
    pathway_hits: Dict[str, Dict[str, Any]] = {}
    go_hits: Dict[str, Dict[str, Any]] = {}
    try:
        for gene in genes[:12]:
            pathways = await reactome.search(gene, limit=5)
            for pathway in pathways:
                pathway_id = str(pathway.get("stId") or pathway.get("id") or pathway.get("pathway_id") or uuid.uuid4())
                entry = pathway_hits.setdefault(pathway_id, {
                    "pathway_id": pathway_id,
                    "name": pathway.get("displayName") or pathway.get("canonical_name") or pathway.get("name") or pathway_id,
                    "genes": [],
                    "hit_count": 0,
                    "source": "Reactome",
                })
                entry["genes"].append(gene)
                entry["hit_count"] += 1

            annotations = await go.get_annotations(gene, limit=8)
            for annotation in annotations:
                go_id = str(annotation.get("go_id") or "")
                if not go_id:
                    continue
                entry = go_hits.setdefault(go_id, {
                    "go_id": go_id,
                    "name": annotation.get("go_name") or go_id,
                    "aspect": annotation.get("aspect") or "",
                    "genes": [],
                    "hit_count": 0,
                })
                entry["genes"].append(gene)
                entry["hit_count"] += 1
    finally:
        await reactome.close()
        await go.close()

    enriched = sorted(pathway_hits.values(), key=lambda item: item["hit_count"], reverse=True)[:25]
    go_terms = sorted(go_hits.values(), key=lambda item: item["hit_count"], reverse=True)[:25]
    return {"enrichedPathways": enriched, "goTerms": go_terms}


async def _build_graph_payload(request: Request, query: str, max_nodes: int, depth: int) -> Dict[str, Any]:
    from routers.graph import GraphBuildRequest, _build_graph_inner

    envelope = await _build_graph_inner(GraphBuildRequest(query=query, max_nodes=max_nodes, depth=depth), request, time.time())
    return envelope.get("data") or {"nodes": [], "edges": [], "stats": {}}


def _structure_candidates(resolved_slots: List[Dict[str, Any]], disease_candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    structures: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for slot in resolved_slots:
        for entity in slot.get("results") or []:
            identifiers = entity.get("identifiers") or {}
            if entity.get("entityType") not in {"protein", "gene"}:
                continue
            key = str(identifiers.get("UNIPROT") or entity.get("entityName") or entity.get("entityId"))
            if key in seen:
                continue
            seen.add(key)
            structures.append({
                "entityName": entity.get("entityName"),
                "geneSymbol": entity.get("attributes", {}).get("geneSymbol") or entity.get("entityName"),
                "uniprotId": identifiers.get("UNIPROT") or "",
                "pdbId": identifiers.get("PDB") or "",
                "alphafoldId": identifiers.get("ALPHAFOLD") or "",
            })
    for candidate in disease_candidates[:10]:
        key = str(candidate.get("uniprot_id") or candidate.get("symbol") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        structures.append({
            "entityName": candidate.get("symbol") or "",
            "geneSymbol": candidate.get("symbol") or "",
            "uniprotId": candidate.get("uniprot_id") or "",
            "pdbId": "",
            "alphafoldId": f"AF-{candidate.get('uniprot_id')}-F1" if candidate.get("uniprot_id") else "",
        })
    return structures[:20]


def _flatten_entities(resolved_slots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    flattened: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for slot in resolved_slots:
        for entity in slot.get("results") or []:
            key = f"{entity.get('entityType')}::{entity.get('entityId')}"
            if key in seen:
                continue
            seen.add(key)
            flattened.append(entity)
    return flattened


@router.post("/analyze")
async def analyze_entity_intelligence(req: EntityIntelligenceAnalyzeRequest, request: Request) -> Dict[str, Any]:
    started = time.time()
    active_slots = [slot for slot in req.slots if _clean_entries(slot)]
    if not active_slots:
        return build_envelope(
            request,
            {"resolvedSlots": [], "entities": []},
            status="error",
            errors=[{"code": "EMPTY_INPUT", "message": "At least one slot must contain text or CSV values"}],
        )

    resolved_slots = await asyncio.gather(*(_resolve_slot(slot) for slot in active_slots))
    flattened_entities = _flatten_entities(resolved_slots)
    disease_queries = [
        entity.get("entityName")
        for slot in resolved_slots
        for entity in slot.get("results") or []
        if entity.get("entityType") == "disease"
    ]
    disease_section = await _analyze_disease_queries(disease_queries)

    explicit_genes = {
        str(entity.get("entityName") or "").upper()
        for slot in resolved_slots
        for entity in slot.get("results") or []
        if entity.get("entityType") in {"gene", "protein", "target"}
    }
    candidate_genes = {str(item.get("symbol") or "").upper() for item in disease_section.get("candidateGenes") or []}
    gene_pool = sorted(gene for gene in explicit_genes.union(candidate_genes) if gene)

    primary_disease = disease_queries[0] if disease_queries else ""
    target_section = await _prioritize_targets(primary_disease, gene_pool)

    graph_query_parts = [entity.get("entityName") for entity in flattened_entities[:6] if entity.get("entityName")]
    if primary_disease and primary_disease not in graph_query_parts:
        graph_query_parts.insert(0, primary_disease)
    graph_query = " ".join(graph_query_parts) if graph_query_parts else " ".join(gene_pool[:4])
    graph_section = await _build_graph_payload(request, graph_query or primary_disease or gene_pool[0], req.graph_max_nodes, req.graph_depth)
    ppi_section = await _build_ppi_network(gene_pool)
    pathway_section = await _build_pathway_enrichment(gene_pool)
    structure_section = _structure_candidates(resolved_slots, disease_section.get("candidateGenes") or [])

    analytics = GraphAnalytics()
    communities = analytics.detect_communities(graph_section.get("nodes") or [], graph_section.get("edges") or [], algorithm="louvain") if graph_section.get("nodes") else {"communities": [], "num_communities": 0, "modularity": 0, "algorithm": "louvain"}
    centrality = analytics.calculate_centrality(graph_section.get("nodes") or [], graph_section.get("edges") or [], metrics=["degree", "pagerank"]) if graph_section.get("nodes") else {"top_nodes": {}, "metrics": []}

    degraded_sources = sorted({
        source
        for slot in resolved_slots
        for source in slot.get("degradedSources") or []
    }.union(disease_section.get("degradedSources") or []))
    warnings = []
    if degraded_sources:
        warnings.append(f"Some resolution sources degraded: {', '.join(degraded_sources)}")

    data = {
        "run_id": str(uuid.uuid4()),
        "resolvedSlots": resolved_slots,
        "entities": flattened_entities,
        "provenance": [
            provenance
            for slot in resolved_slots
            for provenance in slot.get("provenance") or []
        ],
        "diseaseIntelligence": disease_section,
        "targetPrioritization": target_section,
        "graph": graph_section,
        "ppi": ppi_section,
        "pathways": pathway_section,
        "structures": structure_section,
        "enrichment": {
            "communities": communities,
            "centrality": centrality,
            "goTerms": pathway_section.get("goTerms") or [],
        },
        "summary": {
            "slotCount": len(resolved_slots),
            "entityCount": len(flattened_entities),
            "geneCount": len(gene_pool),
            "diseaseCount": len(disease_queries),
            "graphQuery": graph_query,
            "elapsed_ms": int((time.time() - started) * 1000),
        },
        "degraded_sources": degraded_sources,
    }
    return build_envelope(
        request,
        data,
        status="partial" if warnings else "ok",
        warnings=warnings,
        provenance={
            "sources": sorted({
                provenance.get("source")
                for slot in resolved_slots
                for provenance in slot.get("provenance") or []
                if provenance.get("source")
            }),
            "runtime_mode": "hosted",
            "run_id": data["run_id"],
        },
    )