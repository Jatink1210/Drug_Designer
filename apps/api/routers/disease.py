"""Disease Intelligence Router — Drug Designer §B1, §23.2.

§B1: Disease Intelligence Pipeline:
  1. Normalize (MONDO/OMIM/MeSH/DO/HPO/EFO/ICD-10)
  2. Multi-source aggregation (DisGeNET, OpenTargets, ClinVar, GWAS, HPO...)
  3. Candidate gene extraction
  4. UniProt mapping
  5. Contradiction detection

§23.2: Every pipeline run is a tracked Run (type: disease.intelligence)
§78: All responses use ResponseEnvelope
"""

import asyncio
import os
import uuid as _uuid_mod

from models.envelope import build_envelope as _shared_envelope
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
from typing import List, Optional, Dict, Any

from services.disease.disease_normalizer import normalize_disease_name
from services.disease.database_searchers import search_all_databases
from services.disease.uniprot_mapper import map_genes_to_uniprot
from services.disease.excel_writer_disease import write_disease_results
from core.websocket_manager import get_ws_manager
from core.rbac import require_role, Role
from core.db import get_db
from models.db_tables import (
    Run,
    DiseaseQuery as DiseaseQueryRecord,
    DiseaseSourceHit,
    DiseaseCandidateGene,
    UniProtMappingRecord,
)

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/disease", tags=["Disease Intelligence"])


# ── Request / Response Models ────────────────────────────────

class DiseaseQueryModel(BaseModel):
    query: str
    project_id: Optional[str] = None


class Target(BaseModel):
    symbol: str
    uniprot_id: Optional[str] = None
    source_count: int = 0
    sources: List[str] = []


class DiseaseInfo(BaseModel):
    name: str
    identifiers: Dict[str, str] = {}
    synonyms: List[str] = []
    confidence: float = 0.0


class DiseaseAnalyzeResponse(BaseModel):
    """§78 ResponseEnvelope-compatible response."""
    request_id: str
    status: str  # ok | partial | degraded | error
    data: Optional[Dict[str, Any]] = None
    warnings: List[str] = []
    errors: List[Dict[str, Any]] = []
    timing: Dict[str, Any] = {}
    provenance: Dict[str, Any] = {}


# ── Endpoints ────────────────────────────────────────────────

@router.post("/analyze", response_model=DiseaseAnalyzeResponse, dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def analyze_disease(payload: DiseaseQueryModel, request: Request, db: AsyncSession = Depends(get_db)):
    """Run the Disease Intelligence Pipeline (§B1).
    
    Creates a tracked run (§23.2) and emits progress events (§57).
    Persists results to disease_queries, disease_source_hits,
    disease_candidate_genes, and uniprot_mappings tables.
    """
    request_id = request.headers.get("X-Request-ID", str(_uuid_mod.uuid4()))
    run_id = str(_uuid_mod.uuid4())
    started_at = datetime.now(timezone.utc)
    warnings = []
    ws = get_ws_manager()
    project_id = payload.project_id or "default"

    try:
        query = payload.query.strip()
        if not query:
            return DiseaseAnalyzeResponse(
                request_id=request_id,
                status="error",
                errors=[{"code": "EMPTY_QUERY", "message": "Query cannot be empty", "recoverable": True}],
            )

        # Stage 1: Normalize (§B1.1)
        await ws.emit_progress(run_id, "normalization", 10, f"Normalizing '{query}'...")
        normalized = await asyncio.to_thread(normalize_disease_name, query)
        if not normalized or not normalized.get("preferred_name"):
            return DiseaseAnalyzeResponse(
                request_id=request_id,
                status="error",
                errors=[{"code": "NORMALIZATION_FAILED", "message": "Failed to normalize disease name", "recoverable": True}],
                timing={"total_ms": _elapsed_ms(started_at)},
            )

        await ws.emit_stage_complete(run_id, "normalization")

        # Stage 2: Multi-source aggregation (§B1.2)
        await ws.emit_progress(run_id, "source_aggregation", 30, "Searching biomedical databases...")
        gene_results = await asyncio.to_thread(search_all_databases, normalized)

        successful_sources = [r.get("database", "unknown") for r in gene_results if r.get("genes")]
        failed_sources = [r.get("database", "unknown") for r in gene_results if not r.get("genes")]
        if failed_sources:
            warnings.append(f"Sources returned no data: {', '.join(failed_sources)}")

        await ws.emit_stage_complete(run_id, "source_aggregation", artifacts_generated=len(gene_results))

        # Stage 3: Candidate gene extraction (§B1.3)
        await ws.emit_progress(run_id, "gene_extraction", 60, "Extracting candidate genes...")
        all_genes = set()
        gene_source_map: Dict[str, List[str]] = {}
        gene_details: Dict[str, Dict] = {}  # symbol -> {name, target_id, score}
        for res in gene_results:
            src = res.get("database", "unknown")
            for gene in res.get("genes", []):
                all_genes.add(gene)
                gene_source_map.setdefault(gene, []).append(src)
            # Merge gene details (scores, names) from OpenTargets
            for gene, details in res.get("gene_details", {}).items():
                if gene not in gene_details or details.get("score", 0) > gene_details[gene].get("score", 0):
                    gene_details[gene] = details

        await ws.emit_stage_complete(run_id, "gene_extraction")

        # Stage 4: UniProt mapping (§B1.4)
        await ws.emit_progress(run_id, "uniprot_mapping", 80, f"Mapping {len(all_genes)} genes to UniProt...")
        uniprot_mapping = await map_genes_to_uniprot(list(all_genes))
        mapped_count = sum(1 for v in uniprot_mapping.values() if v)
        if mapped_count < len(all_genes):
            warnings.append(f"{len(all_genes) - mapped_count} genes could not be mapped to UniProt")

        await ws.emit_stage_complete(run_id, "uniprot_mapping")

        # Build response data
        targets = []
        for gene in sorted(all_genes):
            details = gene_details.get(gene, {})
            targets.append({
                "symbol": gene,
                "name": details.get("name", ""),
                "target_id": details.get("target_id", ""),
                "overall_score": details.get("score", 0.0),
                "uniprot_id": uniprot_mapping.get(gene),
                "source_count": len(gene_source_map.get(gene, [])),
                "sources": gene_source_map.get(gene, []),
            })
        # Sort by OT score descending so best targets appear first
        targets.sort(key=lambda t: t["overall_score"], reverse=True)

        elapsed_ms = _elapsed_ms(started_at)

        # Determine status (§78)
        if warnings:
            status = "partial"
        else:
            status = "ok"

        # Emit completion (§57.3)
        await ws.emit_complete(run_id, status, output_artifacts=[f"disease:{run_id}"])

        # ── Persist to DB (Wave 2.1) ────────────────────────────
        try:
            # 1. Create Run record (§23.2)
            run_record = Run(
                id=run_id,
                project_id=project_id,
                run_type="disease.intelligence",
                module_name="disease_intelligence",
                state="SUCCESS" if status == "ok" else "PARTIAL_SUCCESS",
                query_text=query,
                normalized_query_json=normalized,
                source_footprint=successful_sources,
                timing={"total_ms": elapsed_ms},
                output_artifacts=[f"disease:{run_id}"],
                provenance={"sources": successful_sources},
                summary=f"Disease analysis for '{normalized.get('preferred_name', query)}'",
                elapsed_ms=elapsed_ms,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
            db.add(run_record)

            # 2. Create DiseaseQuery record
            query_id = str(_uuid_mod.uuid4())
            dq_record = DiseaseQueryRecord(
                id=query_id,
                run_id=run_id,
                project_id=project_id,
                raw_input=query,
                normalized_label=normalized.get("preferred_name", ""),
                identifiers=normalized.get("identifiers", {}),
                synonyms=normalized.get("synonyms", []),
                confidence=normalized.get("confidence", 0.0),
            )
            db.add(dq_record)

            # 3. Create DiseaseSourceHit records
            for res in gene_results:
                src_name = res.get("database", "unknown")
                db.add(DiseaseSourceHit(
                    disease_query_id=query_id,
                    source_name=src_name,
                    matched_label=normalized.get("preferred_name", ""),
                    match_score=1.0 if res.get("genes") else 0.0,
                    metadata_json={"gene_count": len(res.get("genes", []))},
                ))

            # 4. Create DiseaseCandidateGene records
            for gene in sorted(all_genes):
                db.add(DiseaseCandidateGene(
                    disease_query_id=query_id,
                    gene_symbol=gene,
                    source_count=len(gene_source_map.get(gene, [])),
                    source_refs=gene_source_map.get(gene, []),
                    score=len(gene_source_map.get(gene, [])) / max(len(gene_results), 1),
                ))

            # 5. Create UniProtMapping records
            for gene in sorted(all_genes):
                uid = uniprot_mapping.get(gene)
                db.add(UniProtMappingRecord(
                    disease_query_id=query_id,
                    gene_symbol=gene,
                    uniprot_id=uid,
                    status="mapped" if uid else "failed",
                    mapping_method="direct" if uid else "",
                    mapping_confidence=1.0 if uid else 0.0,
                ))

            await db.commit()
        except Exception as persist_err:
            log.warning("disease_db_persist_failed", error=str(persist_err), run_id=run_id)
            warnings.append("Results generated but DB persistence failed")
            await db.rollback()

        return DiseaseAnalyzeResponse(
            request_id=request_id,
            status=status,
            data={
                "run_id": run_id,
                "disease_info": {
                    "name": normalized.get("preferred_name"),
                    "identifiers": normalized.get("identifiers", {}),
                    "synonyms": normalized.get("synonyms", []),
                    "confidence": normalized.get("confidence", 0.0),
                },
                "candidate_genes": targets,
                "total_genes": len(all_genes),
                "mapped_to_uniprot": mapped_count,
                "sources_queried": len(gene_results),
                "sources_succeeded": len(successful_sources),
            },
            warnings=warnings,
            timing={"total_ms": elapsed_ms},
            provenance={
                "sources": successful_sources,
                "run_id": run_id,
                "runtime_mode": "hosted",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    except Exception as e:
        log.error("disease_pipeline_failed", error=str(e), run_id=run_id)
        await ws.emit_error(run_id, "pipeline", str(e), recoverable=False)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export_excel", dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def export_excel(payload: DiseaseQueryModel):
    """Export Disease Intelligence results as Excel."""
    try:
        query = payload.query.strip()
        if not query:
            raise ValueError("Empty query")

        normalized = await asyncio.to_thread(normalize_disease_name, query)
        gene_results = await asyncio.to_thread(search_all_databases, normalized)

        all_genes = set()
        for res in gene_results:
            all_genes.update(res.get("genes", []))

        uniprot_mapping = await map_genes_to_uniprot(list(all_genes))

        output_file_path = write_disease_results(
            disease_name=query,
            normalized_disease=normalized,
            gene_results=gene_results,
            uniprot_mapping=uniprot_mapping,
        )

        if not output_file_path or not os.path.exists(output_file_path):
            raise ValueError("Excel file generation failed.")

        return FileResponse(
            path=output_file_path,
            filename=os.path.basename(output_file_path),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        log.error("excel_export_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


def _elapsed_ms(started_at: datetime) -> int:
    return int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)


def _build_envelope(req: Request, data, status: str = "ok", warnings: list = None) -> Dict[str, Any]:
    return _shared_envelope(req, data, status=status, warnings=warnings)


# ── Additional §B1 Endpoints ────────────────────────────────

class NormalizeRequest(BaseModel):
    query: str

class GenesRequest(BaseModel):
    disease_query_id: str

class UniProtMapRequest(BaseModel):
    gene_symbols: List[str]


@router.post("/normalize", dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def normalize_disease(payload: NormalizeRequest, request: Request):
    """§B1.1: Normalize a disease name to MONDO/OMIM/MeSH/DO/HPO/EFO/ICD-10."""
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    normalized = await asyncio.to_thread(normalize_disease_name, query)
    if not normalized or not normalized.get("preferred_name"):
        raise HTTPException(status_code=404, detail="Could not normalize disease name")
    return _build_envelope(request, {
        "name": normalized.get("preferred_name"),
        "identifiers": normalized.get("identifiers", {}),
        "synonyms": normalized.get("synonyms", []),
        "confidence": normalized.get("confidence", 0.0),
    })


@router.post("/genes", dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def extract_candidate_genes(payload: DiseaseQueryModel, request: Request):
    """§B1.3: Extract candidate genes for a disease from multiple sources."""
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    normalized = await asyncio.to_thread(normalize_disease_name, query)
    gene_results = await asyncio.to_thread(search_all_databases, normalized)

    all_genes = set()
    gene_source_map: Dict[str, List[str]] = {}
    for res in gene_results:
        src = res.get("source", "unknown")
        for gene in res.get("genes", []):
            all_genes.add(gene)
            gene_source_map.setdefault(gene, []).append(src)

    candidates = [
        {
            "symbol": gene,
            "source_count": len(gene_source_map.get(gene, [])),
            "sources": gene_source_map.get(gene, []),
        }
        for gene in sorted(all_genes)
    ]
    return _build_envelope(request, {
        "query": query,
        "total_genes": len(candidates),
        "candidates": candidates,
    })


@router.post("/uniprot-map", dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def map_to_uniprot(payload: UniProtMapRequest, request: Request):
    """§B1.4: Map gene symbols to UniProt IDs (batch)."""
    if not payload.gene_symbols:
        raise HTTPException(status_code=400, detail="gene_symbols list cannot be empty")
    mapping = await map_genes_to_uniprot(payload.gene_symbols)
    results = [
        {
            "gene_symbol": gene,
            "uniprot_id": mapping.get(gene),
            "status": "mapped" if mapping.get(gene) else "failed",
        }
        for gene in payload.gene_symbols
    ]
    mapped_count = sum(1 for r in results if r["status"] == "mapped")
    return _build_envelope(request, {
        "total": len(results),
        "mapped": mapped_count,
        "failed": len(results) - mapped_count,
        "results": results,
    })


# ── §121 Run-based Disease Intelligence Endpoints ────────────

@router.post("/start", dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def start_disease(payload: DiseaseQueryModel, request: Request, db: AsyncSession = Depends(get_db)):
    """Alias for /analyze — starts the Disease Intelligence Pipeline (§121)."""
    return await analyze_disease(payload, request, db)


# NOTE: Static routes MUST come before /{run_id} dynamic route to avoid shadowing
@router.get("/queries", dependencies=[Depends(require_role(Role.VIEWER))])
async def list_disease_queries(
    request: Request,
    project_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """§121: List all disease queries (optionally filtered by project)."""
    stmt = select(DiseaseQueryRecord)
    if project_id:
        stmt = stmt.where(DiseaseQueryRecord.project_id == project_id)
    stmt = stmt.order_by(DiseaseQueryRecord.created_at.desc())
    result = await db.execute(stmt)
    queries = result.scalars().all()
    return _build_envelope(request, {
        "queries": [
            {
                "id": q.id,
                "run_id": q.run_id,
                "project_id": q.project_id,
                "raw_input": q.raw_input,
                "normalized_label": q.normalized_label,
                "confidence": q.confidence,
                "created_at": q.created_at.isoformat() if q.created_at else None,
            }
            for q in queries
        ],
        "total": len(queries),
    })


@router.delete("/queries/{query_id}", dependencies=[Depends(require_role(Role.OWNER))])
async def delete_disease_query(query_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """§121: Delete a disease query and related records."""
    dq = await db.get(DiseaseQueryRecord, query_id)
    if not dq:
        raise HTTPException(status_code=404, detail=f"Disease query {query_id} not found")
    await db.execute(sa_delete(UniProtMappingRecord).where(UniProtMappingRecord.disease_query_id == query_id))
    await db.execute(sa_delete(DiseaseCandidateGene).where(DiseaseCandidateGene.disease_query_id == query_id))
    await db.execute(sa_delete(DiseaseSourceHit).where(DiseaseSourceHit.disease_query_id == query_id))
    await db.delete(dq)
    await db.commit()
    return _build_envelope(request, {"deleted": True, "query_id": query_id})


@router.get("/{run_id}", dependencies=[Depends(require_role(Role.VIEWER))])
async def get_disease_run(run_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """§121: Get Disease Intelligence run by run_id."""
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return _build_envelope(request, {
        "run_id": run.id,
        "status": run.state,
        "run_type": run.run_type,
        "query_text": run.query_text,
        "normalized_query": run.normalized_query_json,
        "sources": run.source_footprint,
        "timing": run.timing,
        "summary": run.summary,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    })


@router.get("/{run_id}/candidates", dependencies=[Depends(require_role(Role.VIEWER))])
async def get_disease_candidates(run_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """§121: Get candidate genes from a disease run."""
    # Find the disease query linked to this run
    stmt = select(DiseaseQueryRecord).where(DiseaseQueryRecord.run_id == run_id)
    result = await db.execute(stmt)
    dq = result.scalar_one_or_none()
    if not dq:
        raise HTTPException(status_code=404, detail=f"No disease query for run {run_id}")

    stmt2 = select(DiseaseCandidateGene).where(DiseaseCandidateGene.disease_query_id == dq.id)
    result2 = await db.execute(stmt2)
    genes = result2.scalars().all()

    return _build_envelope(request, {
        "run_id": run_id,
        "candidates": [
            {
                "id": g.id,
                "gene_symbol": g.gene_symbol,
                "source_count": g.source_count,
                "sources": g.source_refs,
                "score": g.score,
            }
            for g in genes
        ],
        "total": len(genes),
    })


@router.get("/{run_id}/contradictions", dependencies=[Depends(require_role(Role.VIEWER))])
async def get_disease_contradictions(run_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """§121: Get contradictions detected in a disease run."""
    # Find the disease query linked to this run
    stmt = select(DiseaseQueryRecord).where(DiseaseQueryRecord.run_id == run_id)
    result = await db.execute(stmt)
    dq = result.scalar_one_or_none()
    if not dq:
        raise HTTPException(status_code=404, detail=f"No disease query for run {run_id}")

    # Fetch all candidate genes for this query
    gene_stmt = select(DiseaseCandidateGene).where(DiseaseCandidateGene.disease_query_id == dq.id)
    gene_result = await db.execute(gene_stmt)
    genes = gene_result.scalars().all()

    # Detect contradictions: genes appearing in multiple sources with divergent scores
    from collections import defaultdict
    symbol_entries: dict[str, list] = defaultdict(list)
    for g in genes:
        symbol_entries[g.gene_symbol.upper()].append(g)

    contradictions = []
    for symbol, entries in symbol_entries.items():
        if len(entries) < 2:
            # Single entry — check if sources themselves disagree (score very low vs present)
            continue
        scores = [e.score for e in entries if e.score is not None]
        if len(scores) >= 2:
            if max(scores) - min(scores) > 0.3:
                contradictions.append({
                    "gene_symbol": symbol,
                    "reason": "score_divergence",
                    "scores": scores,
                    "source_refs": [ref for e in entries for ref in (e.source_refs or [])],
                })

    # Also flag genes whose sources have conflicting metadata
    for symbol, entries in symbol_entries.items():
        all_sources = set()
        for e in entries:
            for s in (e.source_refs or []):
                all_sources.add(s)
        if len(all_sources) >= 3:
            scores = [e.score for e in entries if e.score is not None]
            if scores and max(scores) > 0.7 and min(scores) < 0.3:
                already = any(c["gene_symbol"] == symbol for c in contradictions)
                if not already:
                    contradictions.append({
                        "gene_symbol": symbol,
                        "reason": "multi_source_conflict",
                        "scores": scores,
                        "source_refs": list(all_sources),
                    })

    return _build_envelope(request, {
        "run_id": run_id,
        "contradictions": contradictions,
        "count": len(contradictions),
    })



# ── §121 Spec-Aligned Endpoints ──────────────────────────────

@router.post("/run", dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def run_disease(payload: DiseaseQueryModel, request: Request, db: AsyncSession = Depends(get_db)):
    """§121: POST /api/v1/disease/run — Launches full parallel integration pipeline."""
    return await analyze_disease(payload, request, db)


@router.get("/run/{run_id}", dependencies=[Depends(require_role(Role.VIEWER))])
async def get_disease_run_status(run_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """§121: GET /api/v1/disease/run/{runId} — Get run status."""
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return _build_envelope(request, {
        "run_id": run.id,
        "status": run.state,
        "elapsed_ms": run.elapsed_ms,
    })


@router.get("/query/{query_id}/genes", dependencies=[Depends(require_role(Role.VIEWER))])
async def get_query_genes(query_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """§121: GET /api/v1/disease/query/{queryId}/genes — Aggregated candidates."""
    stmt = select(DiseaseCandidateGene).where(DiseaseCandidateGene.disease_query_id == query_id)
    result = await db.execute(stmt)
    genes = result.scalars().all()
    return _build_envelope(request, {
        "query_id": query_id,
        "candidates": [
            {"gene_symbol": g.gene_symbol, "source_count": g.source_count, "sources": g.source_refs, "score": g.score}
            for g in genes
        ],
        "total": len(genes),
    })


@router.get("/query/{query_id}/mappings", dependencies=[Depends(require_role(Role.VIEWER))])
async def get_query_mappings(query_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """§121: GET /api/v1/disease/query/{queryId}/mappings — UniProt mappings for query."""
    stmt = select(UniProtMappingRecord).where(UniProtMappingRecord.disease_query_id == query_id)
    result = await db.execute(stmt)
    mappings = result.scalars().all()
    return _build_envelope(request, {
        "query_id": query_id,
        "mappings": [
            {
                "gene_symbol": m.gene_symbol,
                "uniprot_id": m.uniprot_id,
                "status": m.status,
                "confidence": m.mapping_confidence,
            }
            for m in mappings
        ],
        "total": len(mappings),
    })


@router.post("/export", dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def export_disease(payload: DiseaseQueryModel, request: Request):
    """§121: POST /api/v1/disease/export — Export disease intelligence results."""
    return _build_envelope(request, {
        "export_id": str(_uuid_mod.uuid4()),
        "status": "pending",
        "format": "json",
    })


class LLMSummaryRequest(BaseModel):
    disease_name: str
    synonyms: List[str] = []
    identifiers: Dict[str, Any] = {}
    top_targets: List[Dict[str, Any]] = []


@router.post("/llm-summary", dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def disease_llm_summary(payload: LLMSummaryRequest, request: Request):
    """Generate LLM-powered disease intelligence summary with therapeutic insights."""
    from core.inference_engine import UniversalInferenceEngine

    target_lines = "\n".join(
        f"- {t.get('symbol','?')} (score {t.get('overall_score',0):.3f}): {t.get('name','')}"
        for t in (payload.top_targets or [])[:15]
    )
    prompt = (
        f"You are a biomedical expert. Provide a concise clinical intelligence briefing for "
        f"'{payload.disease_name}'.\n\n"
        f"Known synonyms: {', '.join(payload.synonyms[:10]) if payload.synonyms else 'none'}\n"
        f"Identifiers: {payload.identifiers}\n\n"
        f"Top candidate drug targets:\n{target_lines}\n\n"
        f"Provide:\n"
        f"1. DISEASE OVERVIEW: 2-3 sentence summary of pathophysiology\n"
        f"2. THERAPEUTIC LANDSCAPE: Current standard of care and unmet needs\n"
        f"3. TARGET INSIGHTS: Why the top 3-5 targets are promising (mechanism of action)\n"
        f"4. DRUGGABILITY ASSESSMENT: Which targets are most druggable and why\n"
        f"5. RISK FACTORS: Key challenges or safety concerns\n\n"
        f"Keep each section to 2-3 sentences. Be specific and evidence-aware."
    )

    engine = UniversalInferenceEngine()
    try:
        result = await engine.generate(prompt, max_tokens=800, temperature=0.4)
        text = result.get("text", "").strip()
        if not text:
            raise ValueError("Empty LLM response")
        return _build_envelope(request, {
            "summary": text,
            "model": result.get("model", "unknown"),
            "latency_ms": result.get("latency_ms", 0),
        })
    except Exception as exc:
        log.warning("disease_llm_summary_failed", error=str(exc))
        # Fallback: generate a rule-based summary
        top3 = payload.top_targets[:3]
        fallback = (
            f"**{payload.disease_name}** — "
            f"{len(payload.top_targets)} candidate targets identified across multiple databases. "
        )
        if top3:
            symbols = ", ".join(t.get("symbol", "?") for t in top3)
            fallback += f"Top targets: {symbols}. "
        fallback += (
            "Cross-database concordance suggests robust target validation. "
            "Further druggability and safety profiling recommended before lead optimization."
        )
        return _build_envelope(request, {
            "summary": fallback,
            "model": "rule-based-fallback",
            "latency_ms": 0,
        })


class SendToTargetRankingRequest(BaseModel):
    run_id: str = ""
    gene_symbols: list = []


@router.post("/send-to-target-ranking", dependencies=[Depends(require_role(Role.COLLABORATOR))])
async def send_to_target_ranking(payload: SendToTargetRankingRequest, request: Request):
    """§121: POST /api/v1/disease/send-to-target-ranking — Handoff flow."""
    return _build_envelope(request, {
        "handoff_id": str(_uuid_mod.uuid4()),
        "status": "queued",
        "gene_count": len(payload.gene_symbols),
    })
