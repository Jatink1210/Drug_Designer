"""Enhanced Search Engine — Multi-source parallel aggregator with SearchResultEnvelope output."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple, Type

import structlog

from connectors.base import BaseConnector
from connectors.uniprot import UniProtConnector
from connectors.pubmed import PubMedConnector
from connectors.opentargets import OpenTargetsConnector
from connectors.rcsb import RCSBConnector
from connectors.chembl import ChEMBLConnector
from connectors.clinicaltrials import ClinicalTrialsConnector
from connectors.reactome import ReactomeConnector
from connectors.alphafold import AlphaFoldConnector
from connectors.pubchem import PubChemConnector
from connectors.europe_pmc import EuropePMCConnector
from connectors.string_db import STRINGConnector
from connectors.patents import PatentsViewConnector
from connectors.gwas_catalog import GWASCatalogConnector
from connectors.indigen_loader import IndiGenLoader
from connectors.igvdb_loader import IGVDBLoader
from connectors.genomeasia_loader import GenomeAsiaLoader
from core.provenance import ProvenanceBundle
from core.cache import cache_key as _cache_key, two_tier_get, two_tier_put
from models.entities import CategoryResult, SearchResultEnvelope
from services.query_router import detect_intent

log = structlog.get_logger()

# Map intent → connector classes
INTENT_CONNECTORS: Dict[str, List[Type[BaseConnector]]] = {
    "protein": [UniProtConnector, OpenTargetsConnector, STRINGConnector, ChEMBLConnector, PubMedConnector, ClinicalTrialsConnector],
    "gene": [OpenTargetsConnector, ChEMBLConnector, PubMedConnector, ClinicalTrialsConnector],
    "molecule": [ChEMBLConnector, PubChemConnector],
    "drug": [ChEMBLConnector, OpenTargetsConnector, PubMedConnector, ClinicalTrialsConnector],
    "disease": [OpenTargetsConnector, ChEMBLConnector, PubMedConnector, ClinicalTrialsConnector],
    "pathway": [ReactomeConnector],
    "structure": [RCSBConnector, AlphaFoldConnector],
    "clinical_trial": [ClinicalTrialsConnector],
    "publication": [PubMedConnector, EuropePMCConnector],
    "patent": [PatentsViewConnector],
    "variant": [GWASCatalogConnector, IndiGenLoader, IGVDBLoader, GenomeAsiaLoader],
    "general": [UniProtConnector, OpenTargetsConnector, PubMedConnector, ChEMBLConnector, ClinicalTrialsConnector],
}

# Per-type table columns
COLUMN_DEFS: Dict[str, List[str]] = {
    "protein": ["id", "name", "gene_symbol", "organism", "length", "pdb_ids", "url"],
    "gene": ["id", "name", "description", "association_score", "url"],
    "molecule": ["id", "name", "smiles", "formula", "molecular_weight", "logp", "url"],
    "drug": ["id", "name", "mechanism_of_action", "clinical_phase", "drug_type", "url"],
    "disease": ["id", "name", "description", "association_score", "url"],
    "pathway": ["id", "name", "source_db", "species", "gene_count", "url"],
    "structure": ["id", "name", "pdb_id", "method", "resolution", "r_free", "url"],
    "publication": ["id", "title", "authors", "journal", "year", "pmid", "pico_data", "url"],
    "clinical_trial": ["id", "name", "nct_id", "phase", "status", "conditions", "url"],
    "patent": ["id", "name", "patent_id", "assignee", "filing_date", "url"],
    "interaction": ["id", "name", "source_entity", "target_entity", "score", "url"],
    "variant": ["id", "name", "gene", "consequence", "clinical_significance", "gwas_significance", "indian_demographic_context", "url"],
}


async def execute_search(
    query: str,
    mode: str = "auto",
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 20,
    strict_evidence: bool = False,
) -> SearchResultEnvelope:
    """Run full multi-source search pipeline and return SearchResultEnvelope."""
    t0 = time.monotonic()

    # Cache lookup — envelope-level caching (15 min TTL)
    filter_hash = hashlib.md5(json.dumps(filters or {}, sort_keys=True).encode()).hexdigest()[:8]
    ck = _cache_key("search", query, "%s:%s:%d:%s" % (mode, filter_hash, limit, strict_evidence))
    cached = two_tier_get(ck)
    if cached is not None:
        log.info("cache_hit", query=query)
        return SearchResultEnvelope(**cached)

    timings: Dict[str, float] = {}
    errors: List[str] = []
    provenance = ProvenanceBundle()

    # 1. Intent detection
    intent, search_term, method = detect_intent(query)
    timings["intent_detection"] = time.monotonic() - t0
    log.info("intent_detected", intent=intent, term=search_term, method=method)

    # 2. Select connectors
    connector_classes = INTENT_CONNECTORS.get(intent, INTENT_CONNECTORS["general"]).copy()
    
    q_lower = query.lower()
    # Apply custom query heuristics
    if "gwas" in q_lower and GWASCatalogConnector not in connector_classes:
        connector_classes.append(GWASCatalogConnector)
        if OpenTargetsConnector not in connector_classes:
            connector_classes.append(OpenTargetsConnector)
            
    if "indian" in q_lower or "india" in q_lower:
        for loader in [IndiGenLoader, IGVDBLoader, GenomeAsiaLoader]:
            if loader not in connector_classes:
                connector_classes.append(loader)

    # Apply filters for optional connectors
    if filters:
        if not filters.get("include_patents", False):
            connector_classes = [c for c in connector_classes if c != PatentsViewConnector]
        if not filters.get("include_interactions", False):
            connector_classes = [c for c in connector_classes if c != STRINGConnector]

    # 3. Instantiate connectors
    connectors: List[BaseConnector] = [cls() for cls in connector_classes]

    # 4. Parallel search + enrichment
    t_fetch = time.monotonic()
    search_tasks = [c.search(search_term, limit=limit) for c in connectors]

    pubmed_counter = PubMedConnector()
    trials_counter = ClinicalTrialsConnector()
    count_tasks = [pubmed_counter.count(search_term), trials_counter.count(search_term)]

    all_results = await asyncio.gather(*search_tasks, *count_tasks, return_exceptions=True)
    timings["data_fetching"] = time.monotonic() - t_fetch

    # 5. Process search results
    search_results = all_results[:len(connectors)]
    count_results = all_results[len(connectors):]

    all_entities: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    seen_ids: Set[str] = set()

    for i, result in enumerate(search_results):
        if isinstance(result, Exception):
            errors.append("%s: %s" % (connectors[i].name, str(result)))
            continue
        if not isinstance(result, list):
            continue
        provenance.sources_hit.append(connectors[i].name)
        provenance.timestamps[connectors[i].name] = time.time()
        for entity in result:
            eid = entity.get("id", "")
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                etype = entity.get("entity_type", "unknown")
                all_entities[etype].append(entity)

    # 5.1 Enrich publications with PICO extraction
    publications = all_entities.get("publication", [])
    if publications:
        from services.pico_extractor import extract_pico_data
        async def enrich_pico(pub: Dict[str, Any]) -> None:
            text = pub.get("abstract") or pub.get("title", "")
            if text:
                pico = await extract_pico_data(text)
                pub["pico_data"] = pico

        pico_tasks = [enrich_pico(p) for p in publications[:2]]
        await asyncio.gather(*pico_tasks, return_exceptions=True)

    # 5.2 Evidence confidence + contradiction detection
    from services.contradiction_detector import (
        compute_confidence, build_citation_refs, detect_contradictions,
    )

    all_citation_refs: List[Dict[str, Any]] = []
    confidence_sum = 0.0
    confidence_count = 0

    for _etype, entities in all_entities.items():
        for ent in entities:
            conf = compute_confidence(ent, len(provenance.sources_hit))
            ent["_confidence"] = round(conf, 2)
            refs = build_citation_refs(ent, provenance.sources_hit)
            ent["_evidence_refs"] = refs
            all_citation_refs.extend(refs)
            confidence_sum += conf
            confidence_count += 1

    contradictions = await detect_contradictions(all_entities, search_term)

    # 6. Enrichment counts
    pubmed_count = count_results[0] if not isinstance(count_results[0], Exception) else None
    trials_count = count_results[1] if not isinstance(count_results[1], Exception) else None

    # 7. Build categorized results
    categories: Dict[str, CategoryResult] = {}
    for etype, entities in all_entities.items():
        columns = COLUMN_DEFS.get(etype, list(entities[0].keys()) if entities else [])
        categories[etype + "s" if not etype.endswith("s") else etype] = CategoryResult(
            columns=columns,
            rows=entities,
            total=len(entities),
        )

    # 8. Build preview graph (lightweight)
    preview_graph = _build_preview_graph(all_entities)

    # 9. Summary stats
    summary_stats = {
        "total_results": sum(len(e) for e in all_entities.values()),
        "categories_found": len(all_entities),
        "pubmed_count": pubmed_count,
        "clinical_trials_count": trials_count,
        "sources_queried": len(provenance.sources_hit),
    }

    # 10. Cleanup connectors
    cleanup = [c.close() for c in connectors] + [pubmed_counter.close(), trials_counter.close()]
    await asyncio.gather(*cleanup, return_exceptions=True)

    timings["total"] = time.monotonic() - t0

    # Build evidence summary
    avg_confidence = round(confidence_sum / confidence_count, 2) if confidence_count else 0.5
    # Deduplicate top citations by external_id
    seen_cites: Set[str] = set()
    top_citations: List[Dict[str, Any]] = []
    for ref in all_citation_refs:
        eid = ref.get("external_id", "")
        if eid and eid not in seen_cites:
            seen_cites.add(eid)
            top_citations.append(ref)
        if len(top_citations) >= 10:
            break

    envelope = SearchResultEnvelope(
        query=query,
        intent={"intent": intent, "search_term": search_term, "method": method},
        summary_stats=summary_stats,
        categories=categories,
        preview_graph=preview_graph,
        provenance={
            "sources_hit": provenance.sources_hit,
            "timestamps": provenance.timestamps,
        },
        timings=timings,
        errors=errors,
        evidence_summary={
            "contradictions": contradictions,
            "overall_confidence": avg_confidence,
            "evidence_count": len(all_citation_refs),
            "top_citations": top_citations,
        },
    )

    # Cache the result (15 min TTL for search results)
    try:
        two_tier_put(ck, "search_engine", query, envelope.model_dump(), ttl=900.0)
    except Exception:
        log.debug("Cache write failed for search result")  # Non-critical

    return envelope


def _build_preview_graph(entities_by_type: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Build a lightweight preview graph from search results for visualization."""
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    node_ids: Set[str] = set()

    for etype, entities in entities_by_type.items():
        for ent in entities[:10]:  # max 10 per type for preview
            nid = ent.get("id", "")
            if nid and nid not in node_ids:
                node_ids.add(nid)
                nodes.append({
                    "id": nid,
                    "label": ent.get("canonical_name", ent.get("name", nid))[:50],
                    "type": etype,
                })

    # Create edges for interactions
    for interaction in entities_by_type.get("interaction", []):
        src = interaction.get("source_entity", "")
        tgt = interaction.get("target_entity", "")
        if src and tgt:
            edges.append({
                "source": src,
                "target": tgt,
                "label": interaction.get("interaction_type", "interacts_with"),
                "weight": interaction.get("score", 1.0),
            })

    return {"nodes": nodes, "edges": edges}


# Keep backward compat for search.py model import
from typing import Optional  # noqa: E402
