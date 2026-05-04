"""Enhanced Search Engine — Multi-source parallel aggregator with SearchResultEnvelope output."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import time
from collections import defaultdict
from typing import Any, Dict, List, Literal, Optional, Set, Tuple, Type

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
from connectors.kegg import KEGGConnector
from connectors.wikipathways import WikiPathwaysConnector
from connectors.interpro import InterProConnector
from connectors.intact import IntActConnector
from connectors.ensembl import EnsemblConnector
from connectors.disease_ontology import DiseaseOntologyConnector
from connectors.chebi import ChEBIConnector
from connectors.crossref import CrossRefConnector
from connectors.openalex import OpenAlexConnector
from connectors.clinvar import ClinVarConnector
from connectors.gnomad import GnomadConnector
from connectors.hpo import HPOConnector
from connectors.pharos import PharosConnector
from core.provenance import ProvenanceBundle
from core.cache import cache_key as _cache_key, two_tier_get, two_tier_put
from models.entities import CategoryResult, SearchResultEnvelope
from services.query_router import detect_intent

log = structlog.get_logger()

# Map intent → connector classes
INTENT_CONNECTORS: Dict[str, List[Type[BaseConnector]]] = {
    "protein": [UniProtConnector, OpenTargetsConnector, STRINGConnector, ChEMBLConnector, PubMedConnector, ClinicalTrialsConnector, InterProConnector, PharosConnector, AlphaFoldConnector, EuropePMCConnector],
    "gene": [OpenTargetsConnector, ChEMBLConnector, PubMedConnector, ClinicalTrialsConnector, EnsemblConnector, PharosConnector, STRINGConnector, EuropePMCConnector],
    "molecule": [ChEMBLConnector, PubChemConnector, ChEBIConnector],
    "drug": [ChEMBLConnector, OpenTargetsConnector, PubMedConnector, ClinicalTrialsConnector, PubChemConnector, PharosConnector, EuropePMCConnector],
    "disease": [OpenTargetsConnector, ChEMBLConnector, PubMedConnector, ClinicalTrialsConnector, DiseaseOntologyConnector, HPOConnector, PharosConnector, EuropePMCConnector],
    "pathway": [ReactomeConnector, KEGGConnector, WikiPathwaysConnector],
    "structure": [RCSBConnector, AlphaFoldConnector, InterProConnector],
    "clinical_trial": [ClinicalTrialsConnector, EuropePMCConnector],
    "publication": [PubMedConnector, EuropePMCConnector, OpenAlexConnector, CrossRefConnector],
    "patent": [PatentsViewConnector, EuropePMCConnector],
    "variant": [GWASCatalogConnector, ClinVarConnector, GnomadConnector, EnsemblConnector, IndiGenLoader, IGVDBLoader, GenomeAsiaLoader],
    "general": [UniProtConnector, OpenTargetsConnector, PubMedConnector, ChEMBLConnector, ClinicalTrialsConnector, ReactomeConnector, STRINGConnector, PubChemConnector, EuropePMCConnector, PharosConnector],
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

# ---------------------------------------------------------------------------
# BM25 helpers
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"\w+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


def _entity_text(entity: Dict[str, Any]) -> str:
    """Produce a searchable text blob from common entity fields."""
    parts = [
        entity.get("name", ""),
        entity.get("canonical_name", ""),
        entity.get("title", ""),
        entity.get("abstract", ""),
        entity.get("description", ""),
        entity.get("gene_symbol", ""),
        entity.get("mechanism_of_action", ""),
    ]
    return " ".join(str(p) for p in parts if p)


class _BM25Index:
    """Minimal BM25 implementation (k1=1.5, b=0.75) — no external deps."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._corpus: List[List[str]] = []
        self._ids: List[str] = []
        self._tf: List[Dict[str, int]] = []
        self._idf: Dict[str, float] = {}
        self._avg_dl: float = 0.0

    def build(self, entities: List[Dict[str, Any]]) -> None:
        self._corpus = [_tokenize(_entity_text(e)) for e in entities]
        self._ids = [e.get("id", str(i)) for i, e in enumerate(entities)]
        n = len(self._corpus)
        if n == 0:
            return
        self._avg_dl = sum(len(d) for d in self._corpus) / n
        self._tf = [defaultdict(int) for _ in self._corpus]  # type: ignore[assignment]
        df: Dict[str, int] = defaultdict(int)
        for i, doc in enumerate(self._corpus):
            for tok in doc:
                self._tf[i][tok] += 1  # type: ignore[index]
            for tok in set(doc):
                df[tok] += 1
        self._idf = {
            tok: math.log((n - cnt + 0.5) / (cnt + 0.5) + 1.0)
            for tok, cnt in df.items()
        }

    def scores(self, query: str) -> Dict[str, float]:
        """Return {entity_id: bm25_score} for all indexed docs."""
        qtokens = _tokenize(query)
        result: Dict[str, float] = {}
        for i, doc_tf in enumerate(self._tf):
            dl = len(self._corpus[i])
            score = 0.0
            for tok in qtokens:
                if tok not in self._idf:
                    continue
                tf_val = doc_tf.get(tok, 0)  # type: ignore[union-attr]
                norm = tf_val * (self.k1 + 1) / (
                    tf_val + self.k1 * (1 - self.b + self.b * dl / max(self._avg_dl, 1))
                )
                score += self._idf[tok] * norm
            result[self._ids[i]] = score
        return result


def _reciprocal_rank_fusion(
    ranked_lists: List[List[str]],
    k: int = 60,
) -> List[str]:
    """Combine multiple ranked lists into one using RRF.

    ``score = Σ 1 / (k + rank_i)`` for each list where the item appears.
    Returns IDs sorted by descending RRF score.
    """
    scores: Dict[str, float] = defaultdict(float)
    for ranked in ranked_lists:
        for rank, item_id in enumerate(ranked, start=1):
            scores[item_id] += 1.0 / (k + rank)
    return sorted(scores, key=lambda x: scores[x], reverse=True)


# ---------------------------------------------------------------------------
# Main search entry point
# ---------------------------------------------------------------------------



async def execute_search(
    query: str,
    mode: str = "auto",
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 20,
    strict_evidence: bool = False,
    search_mode: Literal["semantic", "lexical", "hybrid"] = "hybrid",
) -> SearchResultEnvelope:
    """Run full multi-source search pipeline and return SearchResultEnvelope.

    Args:
        query:        Free-text search query.
        mode:         Intent-detection mode (``"auto"`` or specific intent).
        filters:      Optional filter dict (sources, year_from, …).
        limit:        Max results per connector.
        strict_evidence: Require high-confidence evidence only.
        search_mode:  Ranking strategy:
                      ``"semantic"``  — connector scores only (default prior behaviour);
                      ``"lexical"``   — BM25 scores only;
                      ``"hybrid"``    — RRF fusion of semantic + BM25 ranks (default).
    """
    t0 = time.monotonic()

    # Cache lookup — envelope-level caching (15 min TTL)
    filter_hash = hashlib.md5(json.dumps(filters or {}, sort_keys=True).encode()).hexdigest()[:8]
    ck = _cache_key("search", query, "%s:%s:%d:%s:%s" % (mode, filter_hash, limit, strict_evidence, search_mode))
    cached = two_tier_get(ck)
    if cached is not None:
        log.info("cache_hit", query=query)
        envelope = SearchResultEnvelope(**cached)
        provenance = dict(envelope.provenance or {})
        cache_summary = dict(provenance.get("cache_summary") or {})
        cache_summary["response_cache_hit"] = True
        provenance["cache_summary"] = cache_summary
        envelope.provenance = provenance
        return envelope

    timings: Dict[str, float] = {}
    errors: List[str] = []
    provenance = ProvenanceBundle()
    connector_timings_ms: Dict[str, float] = {}
    connector_cache_hits: Dict[str, bool] = {}

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

    # 4. Parallel search + enrichment (with 15s per-connector timeout)
    t_fetch = time.monotonic()

    async def _guarded_search(c: BaseConnector, term: str, lim: int) -> Any:
        """Run a connector search with a per-connector timeout so a single
        slow/hung external API cannot hold up the entire search response."""
        started = time.monotonic()
        try:
            return await asyncio.wait_for(c.search(term, limit=lim), timeout=30.0)
        except asyncio.TimeoutError:
            log.warning("connector_timeout", connector=c.name, timeout_s=30)
            return []  # degrade gracefully — return empty rather than block
        finally:
            connector_timings_ms[c.name] = round((time.monotonic() - started) * 1000, 1)

    async def _guarded_count(c: BaseConnector, term: str) -> Any:
        try:
            return await asyncio.wait_for(c.count(term), timeout=10.0)
        except asyncio.TimeoutError:
            log.warning("counter_timeout", connector=c.name)
            return None

    search_tasks = [_guarded_search(c, search_term, limit) for c in connectors]

    pubmed_counter = PubMedConnector()
    trials_counter = ClinicalTrialsConnector()
    count_tasks = [_guarded_count(pubmed_counter, search_term),
                   _guarded_count(trials_counter, search_term)]

    all_results = await asyncio.gather(*search_tasks, *count_tasks, return_exceptions=True)
    timings["data_fetching"] = time.monotonic() - t_fetch

    # 5. Process search results
    search_results = all_results[:len(connectors)]
    count_results = all_results[len(connectors):]

    all_entities: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    seen_ids: Set[str] = set()

    for i, result in enumerate(search_results):
        connector_name = connectors[i].name
        timings[f"connector.{connector_name}.ms"] = connector_timings_ms.get(connector_name, 0.0)
        if isinstance(result, Exception):
            connector_cache_hits[connector_name] = False
            errors.append("%s: %s" % (connector_name, str(result)))
            continue
        if not isinstance(result, list):
            connector_cache_hits[connector_name] = False
            continue
        connector_cache_hits[connector_name] = any(
            isinstance(entity, dict) and bool(
                entity.get("from_cache")
                or entity.get("_from_cache")
                or entity.get("cache_hit")
            )
            for entity in result
        )
        provenance.sources_hit.append(connector_name)
        provenance.timestamps[connector_name] = time.time()
        for entity in result:
            eid = entity.get("id", "")
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                etype = entity.get("entity_type", "unknown")
                all_entities[etype].append(entity)
            elif eid and eid in seen_ids:
                # Merge missing fields from duplicate (e.g. abstract from EuropePMC)
                etype = entity.get("entity_type", "unknown")
                for existing in all_entities.get(etype, []):
                    if existing.get("id") == eid:
                        for k, v in entity.items():
                            if v and not existing.get(k):
                                existing[k] = v
                        break

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

    # 5.3 Hybrid re-ranking (BM25 + semantic → RRF)
    if search_mode in ("lexical", "hybrid"):
        t_bm25 = time.monotonic()
        flat_entities: List[Dict[str, Any]] = [e for ents in all_entities.values() for e in ents]
        bm25_idx = _BM25Index()
        bm25_idx.build(flat_entities)
        bm25_scores = bm25_idx.scores(query)

        if search_mode == "hybrid":
            # Semantic rank: order of arrival (already deduped, first=most relevant)
            semantic_rank = [e.get("id", "") for e in flat_entities if e.get("id")]
            # BM25 rank: sorted by score descending
            bm25_rank = sorted(bm25_scores, key=lambda x: bm25_scores[x], reverse=True)
            rrf_order = _reciprocal_rank_fusion([semantic_rank, bm25_rank])
        else:
            # lexical only
            rrf_order = sorted(bm25_scores, key=lambda x: bm25_scores[x], reverse=True)

        # Rebuild all_entities dict preserving RRF order per type
        id_to_entity: Dict[str, Dict[str, Any]] = {e.get("id", ""): e for ents in all_entities.values() for e in ents}
        reordered: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        seen_reorder: Set[str] = set()
        for eid in rrf_order:
            e = id_to_entity.get(eid)
            if e and eid not in seen_reorder:
                seen_reorder.add(eid)
                reordered[e.get("entity_type", "unknown")].append(e)
        # Add any entities that had no id (shouldn't happen, but guard)
        for etype, ents in all_entities.items():
            for e in ents:
                if e.get("id", "") not in seen_reorder:
                    reordered[etype].append(e)
        all_entities = reordered  # type: ignore[assignment]
        timings["bm25_rerank"] = time.monotonic() - t_bm25

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
            "cache_summary": {
                "response_cache_hit": False,
                "connector_cache_hits": connector_cache_hits,
                "uncached_query": True,
            },
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
