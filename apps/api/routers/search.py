"""Search API route."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request, HTTPException
from routers.auth import get_current_user
from pydantic import BaseModel, Field
import structlog

from services.search_engine import execute_search
from models.envelope import build_envelope
from core.inference_engine import UniversalInferenceEngine

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["search"], dependencies=[Depends(get_current_user)])

_inference_engine: Optional[UniversalInferenceEngine] = None


def _get_inference_engine() -> UniversalInferenceEngine:
    global _inference_engine
    if _inference_engine is None:
        _inference_engine = UniversalInferenceEngine()
    return _inference_engine


class SearchRequest(BaseModel):
    query: str
    mode: str = "auto"
    filters: Dict[str, Any] = Field(default_factory=dict)
    limit: int = 100
    strict_evidence: bool = False
    sources: List[str] = Field(default_factory=list)
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    search_mode: str = "hybrid"  # "semantic" | "lexical" | "hybrid"


class SummaryRequest(BaseModel):
    query: str
    context: Dict[str, Any] = Field(default_factory=dict)


class EntityDetailRequest(BaseModel):
    entity_id: str
    entity_type: str
    entity_name: str = ""


@router.post("/search")
async def search(request_body: SearchRequest, request: Request) -> dict:
    """Multi-source biomedical search with categorized table results."""
    filters = dict(request_body.filters)
    if request_body.sources:
        filters["sources"] = request_body.sources
    if request_body.year_from is not None:
        filters["year_from"] = request_body.year_from
    if request_body.year_to is not None:
        filters["year_to"] = request_body.year_to
    result = await execute_search(
        query=request_body.query,
        mode=request_body.mode,
        filters=filters,
        limit=request_body.limit,
        strict_evidence=request_body.strict_evidence,
        search_mode=request_body.search_mode,
    )
    return build_envelope(request, result.dict())


@router.post("/search/summary")
async def generate_search_summary(request_body: SummaryRequest, request: Request) -> dict:
    """Generate a 12-line LLM summary about the search query and results."""
    query = request_body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    context = request_body.context
    total = context.get("total_results", 0)
    categories = context.get("categories_found", 0)
    sources = context.get("sources_queried", 0)
    top_entities = context.get("top_entities", [])
    contradictions = context.get("contradictions_count", 0)
    confidence = context.get("overall_confidence", 0)

    entities_text = ""
    if top_entities:
        entities_text = "Key entities found: " + ", ".join(str(e) for e in top_entities[:10]) + "."

    prompt = f"""You are a biomedical research assistant. Write a comprehensive 10-12 line summary about the following biomedical search topic.

Topic: "{query}"

Search Context:
- {total} results found across {categories} categories from {sources} databases
- Overall evidence confidence: {confidence:.0%}
- Contradictions detected: {contradictions}
{entities_text}

Write a clear, informative summary that covers:
1. What this topic is and why it matters in biomedical research
2. Key findings from the search results
3. Current state of research/clinical development
4. Notable relationships or interactions discovered
5. Any emerging trends or recent developments

Keep the summary factual, concise, and scientifically accurate. Write exactly 10-12 lines."""

    engine = _get_inference_engine()
    try:
        result = await engine.generate(
            prompt=prompt,
            max_tokens=600,
            temperature=0.4,
            system_prompt="You are an expert biomedical research analyst. Provide accurate, concise scientific summaries.",
        )
        summary_text = result.get("text", "").strip()
        if not summary_text:
            summary_text = _generate_fallback_summary(query, context)
    except Exception as e:
        log.warning("llm_summary_failed", error=str(e))
        summary_text = _generate_fallback_summary(query, context)

    return build_envelope(request, {
        "query": query,
        "summary": summary_text,
        "model_used": result.get("model_used", "fallback") if 'result' in dir() else "fallback",
        "latency_ms": result.get("latency_ms", 0) if 'result' in dir() else 0,
    })


def _generate_fallback_summary(query: str, context: Dict[str, Any]) -> str:
    """Generate a structured fallback summary when LLM is unavailable."""
    total = context.get("total_results", 0)
    categories = context.get("categories_found", 0)
    sources = context.get("sources_queried", 0)
    pubmed = context.get("pubmed_count")
    trials = context.get("clinical_trials_count")
    confidence = context.get("overall_confidence", 0)
    contradictions = context.get("contradictions_count", 0)
    top_entities = context.get("top_entities", [])

    lines = [
        f'Comprehensive biomedical search for "{query}" returned {total} results across {categories} entity categories.',
        f"Data was aggregated from {sources} authoritative biomedical databases including UniProt, OpenTargets, ChEMBL, PubMed, and ClinicalTrials.gov.",
    ]
    if pubmed:
        lines.append(f"PubMed contains {pubmed} indexed publications related to this query, indicating substantial research interest.")
    if trials:
        lines.append(f"There are {trials} clinical trials registered on ClinicalTrials.gov, suggesting active clinical development.")
    if top_entities:
        lines.append(f"Key entities identified include: {', '.join(str(e) for e in top_entities[:8])}.")
    lines.append(f"The overall evidence confidence across sources is {confidence:.0%}, reflecting the strength of cross-source corroboration.")
    if contradictions > 0:
        lines.append(f"{contradictions} contradiction(s) were detected across sources, which may warrant further investigation.")
    lines.append("Results span multiple entity types including proteins, genes, drugs, diseases, pathways, structures, publications, and clinical trials.")
    lines.append("Each entity has been cross-referenced across databases to ensure data quality and provide comprehensive coverage.")
    lines.append("Evidence citations are linked to their original sources for full traceability and provenance tracking.")
    lines.append("This search provides a holistic view for drug discovery, target identification, and translational research workflows.")
    # Pad to 12 lines
    while len(lines) < 12:
        lines.append("Further analysis may reveal additional insights through pathway enrichment, interaction network exploration, and literature mining.")
    return "\n".join(lines[:12])


@router.post("/search/entity-detail")
async def get_entity_detail(request_body: EntityDetailRequest, request: Request) -> dict:
    """Get comprehensive detail for a single entity (papers, patents, descriptions, etc.)."""
    eid = request_body.entity_id
    etype = request_body.entity_type
    ename = request_body.entity_name

    detail: Dict[str, Any] = {
        "entity_id": eid,
        "entity_type": etype,
        "entity_name": ename,
    }

    # Generate a 5-6 line LLM description
    engine = _get_inference_engine()
    desc_prompt = f"""Write a concise 5-6 line scientific description of the following biomedical entity.

Entity: {ename or eid}
Type: {etype}

Cover: what it is, its biological function/role, clinical relevance, and key interactions or pathways. Be factual and precise."""

    try:
        desc_result = await engine.generate(
            prompt=desc_prompt,
            max_tokens=300,
            temperature=0.3,
            system_prompt="You are a biomedical knowledge expert. Provide precise, factual descriptions.",
        )
        detail["description"] = desc_result.get("text", "").strip()
    except Exception:
        detail["description"] = f"{ename or eid} is a {etype} entity identified through multi-source biomedical database search. Further details require manual curation or an active LLM backend."

    # Fetch related publications, patents, trials in parallel
    from connectors.pubmed import PubMedConnector
    from connectors.patents import PatentsViewConnector
    from connectors.clinicaltrials import ClinicalTrialsConnector
    from connectors.chembl import ChEMBLConnector

    search_term = ename or eid
    pubmed = PubMedConnector()
    patents = PatentsViewConnector()
    trials = ClinicalTrialsConnector()
    chembl = ChEMBLConnector()

    try:
        pub_task = pubmed.search(search_term, limit=10)
        pat_task = patents.search(search_term, limit=10)
        trial_task = trials.search(search_term, limit=10)
        chembl_task = chembl.search(search_term, limit=10)

        results = await asyncio.gather(pub_task, pat_task, trial_task, chembl_task, return_exceptions=True)

        detail["publications"] = results[0] if not isinstance(results[0], Exception) else []
        detail["patents"] = results[1] if not isinstance(results[1], Exception) else []
        detail["clinical_trials"] = results[2] if not isinstance(results[2], Exception) else []
        detail["chembl_data"] = results[3] if not isinstance(results[3], Exception) else []
    except Exception as e:
        log.warning("entity_detail_fetch_failed", error=str(e))
        detail["publications"] = []
        detail["patents"] = []
        detail["clinical_trials"] = []
        detail["chembl_data"] = []
    finally:
        await asyncio.gather(
            pubmed.close(), patents.close(), trials.close(), chembl.close(),
            return_exceptions=True,
        )

    return build_envelope(request, detail)


# ── D-3: Cross-modal search ──────────────────────────────────────────────

class CrossModalSearchRequest(BaseModel):
    query: str
    modalities: List[str] = Field(default_factory=lambda: ["molecule", "literature", "protein"])
    limit: int = 20


@router.post("/search/cross-modal")
async def cross_modal_search(req: CrossModalSearchRequest, request: Request) -> Dict[str, Any]:
    """D-3: POST /api/v1/search/cross-modal.

    Embeds *query* with SciBERT → 512-d, then searches each requested modality
    collection in Qdrant and returns a unified ranked list.

    Modality → Qdrant collection mapping:
      - ``molecule``   → ``molecules``
      - ``literature`` → ``literature``
      - ``protein``    → ``proteins``
    """
    MODALITY_COLLECTIONS = {
        "molecule": "molecules",
        "literature": "literature",
        "protein": "proteins",
    }

    # Only keep recognised modalities
    modalities = [m for m in req.modalities if m in MODALITY_COLLECTIONS]
    if not modalities:
        modalities = list(MODALITY_COLLECTIONS.keys())

    # Encode query with SciBERT → align to 512-d
    try:
        from services.ml.scibert_model import get_scibert_model
        scibert = get_scibert_model()
        raw, _ = await scibert.embed_text(req.query)
        import numpy as _np
        import torch as _torch
        from models.alignment_model import AlignmentModel
        aligner = AlignmentModel(target_dim=512)
        with _torch.no_grad():
            aligned_tensor = aligner(_torch.tensor(raw, dtype=_torch.float32).unsqueeze(0), modality="text")
        query_vector = aligned_tensor.squeeze(0).numpy().tolist()
    except Exception as embed_err:
        log.warning("cross_modal_embed_failed", error=str(embed_err))
        # Gracefully degrade: return empty result with warning
        return build_envelope(
            request,
            {"query": req.query, "results": [], "total": 0},
            warnings=[f"Embedding failed: {embed_err}"],
        )

    # Search each modality in Qdrant in parallel
    async def _search_collection(modality: str, collection: str) -> List[Dict[str, Any]]:
        try:
            from qdrant_client import AsyncQdrantClient
            from config import settings as _cfg

            client = AsyncQdrantClient(host=_cfg.qdrant_host, port=_cfg.qdrant_port)
            hits = await client.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=req.limit,
                with_payload=True,
            )
            return [
                {
                    "id": h.id,
                    "score": h.score,
                    "modality": modality,
                    "collection": collection,
                    "payload": h.payload or {},
                }
                for h in hits
            ]
        except Exception as exc:
            log.warning("cross_modal_collection_search_failed", collection=collection, error=str(exc))
            return []

    results_per_modality = await asyncio.gather(
        *[_search_collection(m, MODALITY_COLLECTIONS[m]) for m in modalities]
    )

    # Flatten, sort by score desc, trim to limit
    flat: List[Dict[str, Any]] = []
    for hits in results_per_modality:
        flat.extend(hits)
    flat.sort(key=lambda x: x["score"], reverse=True)
    flat = flat[: req.limit]

    return build_envelope(
        request,
        {
            "query": req.query,
            "modalities_searched": modalities,
            "results": flat,
            "total": len(flat),
        },
    )
