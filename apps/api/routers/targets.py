"""Targets API routes — Drug Designer §78.3, §122.

Handles target prioritization, ranking, and Dossier payload transfer.
All responses wrapped in Universal ResponseEnvelope (§78.1).
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, Request
from routers.auth import get_current_user
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from core.db import get_db
from models.db_tables import TargetRanking, Run
from models.envelope import build_envelope as _shared_envelope

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/targets", tags=["Targets"], dependencies=[Depends(get_current_user)])


class TargetRankingRequest(BaseModel):
    query_id: str
    candidates: List[str]


class SendToDossierRequest(BaseModel):
    target_symbols: List[str]
    run_id: Optional[str] = None
    project_id: str = "default"
    dossier_id: Optional[str] = None


class TargetResponse(BaseModel):
    """§78.1 ResponseEnvelope-compatible response."""
    request_id: str
    status: str
    data: Optional[Dict[str, Any]] = None
    warnings: List[str] = []
    errors: List[Dict[str, Any]] = []
    timing: Dict[str, Any] = {}
    provenance: Dict[str, Any] = {}


from services.job_queue import get_job_queue
from services.target_scorer import TargetScorer
from core.db import AsyncSessionLocal

async def target_ranking_job(query_id: str, candidates: List[str], run_id: str = None, project_id: str = "default") -> Dict[str, Any]:
    scorer = TargetScorer(query_id=query_id, candidates=candidates)
    results = await scorer.evaluate_candidates()

    # Persist structured rows to target_rankings table (§122)
    if run_id:
        try:
            async with AsyncSessionLocal() as session:
                # Create a Run record so the dossier builder can discover this ranking
                run_record = Run(
                    id=run_id,
                    project_id=project_id,
                    run_type="target.ranking",
                    module_name="target_prioritization",
                    state="COMPLETED",
                    query_text=", ".join(candidates),
                    started_at=datetime.now(timezone.utc),
                    finished_at=datetime.now(timezone.utc),
                )
                session.add(run_record)
                for idx, r in enumerate(results):
                    signals = r.get("signals", {})
                    row = TargetRanking(
                        id=str(uuid.uuid4()),
                        run_id=run_id,
                        project_id=project_id,
                        gene_symbol=r.get("gene_symbol", r.get("symbol", "")),
                        rank=idx + 1,
                        composite_score=r.get("composite_score", 0),
                        ucb_score=r.get("ucb_score", 0),
                        gwas_score=signals.get("gwas", 0),
                        druggability_score=signals.get("druggability", 0),
                        pathway_centrality=signals.get("pathways", 0),
                        expression_score=signals.get("expression", 0),
                        safety_score=signals.get("safety", 0),
                        novelty_score=signals.get("novelty", 0),
                        literature_score=signals.get("literature", 0),
                        explanation=r.get("explanation", ""),
                        score_breakdown=r.get("evidence_breakdown", {}),
                        evidence_breakdown=r.get("evidence_breakdown", {}),
                    )
                    session.add(row)
                await session.commit()
                log.info("target_rankings_persisted", run_id=run_id, count=len(results))
        except Exception as exc:
            log.error("target_rankings_persist_failed", run_id=run_id, error=str(exc))

    return {
        "query_id": query_id,
        "ranked_targets": [
            {
                **r,
                "attention_weights": {
                    k: round(v / max(sum(r.get("signals", {}).values()) or 1, 1e-9), 4)
                    for k, v in r.get("signals", {}).items()
                },
            }
            for r in results
        ],
        "metadata": {
            "total_candidates": len(candidates),
            "scoring_logic": "UCB"
        }
    }

@router.post("/rank", response_model=TargetResponse)
async def rank_targets(req: TargetRankingRequest, request: Request) -> Dict[str, Any]:
    """§78.3: POST /api/v1/targets/rank — Re-ranks candidate genes based on configurable profile."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    started_at = datetime.now(timezone.utc)
    
    job_run_id = str(uuid.uuid4())

    # Desktop mode: run synchronously for immediate results (no Redis/arq)
    try:
        result = await target_ranking_job(
            query_id=req.query_id,
            candidates=req.candidates,
            run_id=job_run_id,
        )
        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        log.info("target_ranking_completed_sync", run_id=job_run_id, candidates=len(req.candidates))
        return {
            "request_id": request_id,
            "status": "ok",
            "data": {
                "run_id": job_run_id,
                "status": "completed",
                "ranked_targets": result.get("ranked_targets", []),
                "metadata": result.get("metadata", {}),
                "stream_channel": f"/api/v1/runs/{job_run_id}/events",
            },
            "warnings": [],
            "errors": [],
            "timing": {"started_at": started_at.isoformat(), "elapsed_ms": elapsed_ms},
            "provenance": {"runtime_mode": "hosted"},
        }
    except Exception as exc:
        log.warning("target_ranking_sync_failed", error=str(exc))
        # Fallback to async queue
        queue = await get_job_queue()
        await queue.submit(
            name="target_prioritization_run",
            coro_fn=target_ranking_job,
            query_id=req.query_id,
            candidates=req.candidates,
            run_id=job_run_id,
        )
        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        return {
            "request_id": request_id,
            "status": "ok",
            "data": {
                "run_id": job_run_id,
                "status": "pending",
                "stream_channel": f"/api/v1/runs/{job_run_id}/events",
            },
            "warnings": [f"Sync execution failed, queued for background: {exc}"],
            "errors": [],
            "timing": {"started_at": started_at.isoformat(), "elapsed_ms": elapsed_ms},
            "provenance": {"runtime_mode": "hosted"},
        }


class PrioritizeRequest(BaseModel):
    """Request schema used by the DiseaseWorkbench frontend."""
    disease: str = ""
    genes: List[str] = []


@router.post("/prioritize", response_model=TargetResponse)
async def prioritize_targets(req: PrioritizeRequest, request: Request) -> Dict[str, Any]:
    """Frontend-facing endpoint that accepts {disease, genes} and delegates to the ranking pipeline."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    started_at = datetime.now(timezone.utc)
    job_run_id = str(uuid.uuid4())

    candidates = [g for g in req.genes if g]
    if not candidates:
        return {
            "request_id": request_id,
            "status": "ok",
            "data": {"targets": [], "run_id": None},
            "warnings": ["No gene candidates provided"],
            "errors": [],
            "timing": {"started_at": started_at.isoformat(), "elapsed_ms": 0},
            "provenance": {"runtime_mode": "hosted"},
        }

    try:
        result = await target_ranking_job(
            query_id=req.disease or "unknown",
            candidates=candidates,
            run_id=job_run_id,
        )
        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        ranked = result.get("ranked_targets", [])
        # Sort by composite_score descending and assign proper ranks
        ranked.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
        targets = []
        for idx, t in enumerate(ranked):
            signals = t.get("signals", {})
            targets.append({
                "symbol": t.get("gene_symbol", t.get("symbol", "")),
                "rank": idx + 1,
                "composite_score": round(t.get("composite_score", 0), 4),
                "ucb_score": round(t.get("ucb_score", 0), 4),
                "uncertainty": round(t.get("ucb_score", 0) - t.get("composite_score", 0), 4),
                "contradiction_flag": t.get("contradiction_flag", False),
                "signals": signals,
                "explanation": t.get("explanation", ""),
                "evidence_count": sum(1 for v in signals.values() if v and v > 0),
                "sources": [k for k, v in signals.items() if v and v > 0],
            })
        return {
            "request_id": request_id,
            "status": "ok",
            "data": {"targets": targets, "run_id": job_run_id},
            "warnings": [],
            "errors": [],
            "timing": {"started_at": started_at.isoformat(), "elapsed_ms": elapsed_ms},
            "provenance": {"runtime_mode": "hosted"},
        }
    except Exception as exc:
        log.warning("prioritize_targets_failed", error=str(exc))
        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        return {
            "request_id": request_id,
            "status": "error",
            "data": {"targets": [], "run_id": None},
            "warnings": [],
            "errors": [str(exc)],
            "timing": {"started_at": started_at.isoformat(), "elapsed_ms": elapsed_ms},
            "provenance": {"runtime_mode": "hosted"},
        }


@router.get("/{symbol}", response_model=TargetResponse)
async def get_target_details(symbol: str, request: Request, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """§78.3: GET /api/v1/targets/{symbol} — Detailed target object."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    started_at = datetime.now(timezone.utc)
    sources: list[str] = []
    warnings: list[str] = []

    # Try DB first
    stmt = select(TargetRanking).where(TargetRanking.gene_symbol == symbol.upper()).order_by(TargetRanking.rank.asc()).limit(1)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()

    if row:
        sources.append("postgres")
        data = {
            "symbol": row.gene_symbol,
            "uniprot_id": row.uniprot_id or "",
            "pathways": [],
            "score_breakdown": {
                "gwas": row.gwas_score,
                "druggability": row.druggability_score,
                "literature": row.literature_score,
                "pathway_centrality": row.pathway_centrality,
                "expression": row.expression_score,
                "safety": row.safety_score,
                "novelty": row.novelty_score,
            },
            "composite_score": row.composite_score,
            "rank": row.rank,
            "explanation": row.explanation or "",
        }
    else:
        # Fallback: try live connectors
        warnings.append("No DB record found; attempted live connector lookup")
        data = {
            "symbol": symbol.upper(),
            "uniprot_id": "",
            "pathways": [],
            "score_breakdown": {},
        }
        try:
            from connectors.uniprot import UniProtConnector
            up = UniProtConnector()
            up_results = await up.search(symbol, limit=1)
            if up_results:
                data["uniprot_id"] = up_results[0].get("id", "")
                sources.append("uniprot")
        except Exception as exc:
            log.warning("target_detail_uniprot_failed", symbol=symbol, error=str(exc))

    elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
    return {
        "request_id": request_id,
        "status": "ok",
        "data": data,
        "warnings": warnings,
        "errors": [],
        "timing": {"started_at": started_at.isoformat(), "elapsed_ms": elapsed_ms},
        "provenance": {"runtime_mode": "hosted", "sources": sources}
    }


@router.post("/send-to-dossier", response_model=TargetResponse)
async def send_to_dossier(req: SendToDossierRequest, request: Request, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """§78.3: POST /api/v1/targets/send-to-dossier — Push top ranked targets payload to draft dossier."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    started_at = datetime.now(timezone.utc)
    warnings: list[str] = []

    # Create a tracked Run for dossier generation
    run_id = str(uuid.uuid4())
    run_record = Run(
        id=run_id,
        project_id=req.project_id,
        run_type="dossier.generate",
        module_name="dossier_generation",
        state="QUEUED",
        query_text=", ".join(req.target_symbols),
        input_snapshot={
            "target_symbols": req.target_symbols,
            "source_run_id": req.run_id,
            "dossier_id": req.dossier_id,
        },
        started_at=started_at,
    )
    db.add(run_record)
    await db.commit()

    # Enqueue ARQ job for background dossier generation
    try:
        from worker import enqueue_job
        await enqueue_job(
            request.app.state,
            "run_dossier_generation",
            run_id,
            req.project_id,
            {"target_symbols": req.target_symbols, "dossier_id": req.dossier_id},
            queue_name="reports.dossiers",
            idempotency_key=f"dossier:{run_id}",
        )
    except Exception as exc:
        log.warning("dossier_enqueue_failed", run_id=run_id, error=str(exc))
        warnings.append("Job enqueue failed; run created but background processing may be delayed")

    log.info("targets_sent_to_dossier", run_id=run_id, targets=req.target_symbols)

    elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
    return {
        "request_id": request_id,
        "status": "ok",
        "data": {
            "run_id": run_id,
            "dossier_id": req.dossier_id,
            "status": "QUEUED",
            "stream_channel": f"/api/v1/runs/{run_id}/events",
        },
        "warnings": warnings,
        "errors": [],
        "timing": {"started_at": started_at.isoformat(), "elapsed_ms": elapsed_ms},
        "provenance": {"runtime_mode": "hosted"}
    }


@router.get("/{symbol}/druggability", response_model=TargetResponse)
async def get_druggability(symbol: str, request: Request) -> Dict[str, Any]:
    """§10.3: GET /api/v1/targets/{symbol}/druggability — Druggability assessment.

    Returns structural druggability, pocket prediction, existing ligands,
    and competitive landscape from ChEMBL/PubChem.
    """
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    started_at = datetime.now(timezone.utc)

    data = {
        "symbol": symbol.upper(),
        "druggability_score": 0.0,
        "has_known_ligands": False,
        "pocket_count": 0,
        "binding_site_confidence": 0.0,
        "competitive_compounds": 0,
        "assessment": "pending",
        "sources": [],
    }

    try:
        from connectors.chembl import ChEMBLConnector
        chembl = ChEMBLConnector()
        chembl_results = await chembl.search(symbol, limit=5)
        if chembl_results:
            data["has_known_ligands"] = True
            data["competitive_compounds"] = len(chembl_results)
            data["sources"].append("chembl")
    except Exception as exc:
        log.warning("druggability_chembl_failed", symbol=symbol, error=str(exc))

    try:
        from connectors.opentargets import OpenTargetsConnector
        ot = OpenTargetsConnector()
        ot_results = await ot.search(symbol, limit=1)
        if ot_results:
            data["sources"].append("opentargets")
            data["druggability_score"] = 0.75 if data["has_known_ligands"] else 0.3
    except Exception as exc:
        log.warning("druggability_opentargets_failed", symbol=symbol, error=str(exc))

    data["assessment"] = "druggable" if data["druggability_score"] > 0.5 else "challenging"

    elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
    return {
        "request_id": request_id,
        "status": "ok",
        "data": data,
        "warnings": [],
        "errors": [],
        "timing": {"started_at": started_at.isoformat(), "elapsed_ms": elapsed_ms},
        "provenance": {"runtime_mode": "hosted", "sources": data["sources"]},
    }


# ── §122 Additional Target Endpoints ────────────────────────


@router.get("/rank/{run_id}")
async def get_ranking_run(run_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """§122: GET /api/v1/targets/rank/{runId} — Get target ranking run result."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    started_at = datetime.now(timezone.utc)
    warnings: list[str] = []

    # Check run exists
    run_stmt = select(Run).where(Run.id == run_id)
    run_result = await db.execute(run_stmt)
    run_row = run_result.scalar_one_or_none()
    run_status = run_row.state if run_row else "unknown"
    if not run_row:
        warnings.append(f"Run {run_id} not found in database")

    # Fetch ranked targets
    stmt = select(TargetRanking).where(TargetRanking.run_id == run_id).order_by(TargetRanking.rank.asc())
    result = await db.execute(stmt)
    rows = result.scalars().all()

    ranked_targets = [
        {
            "gene_symbol": r.gene_symbol,
            "uniprot_id": r.uniprot_id or "",
            "rank": r.rank,
            "composite_score": r.composite_score,
            "ucb_score": r.ucb_score,
            "explanation": r.explanation or "",
            "contradiction_flag": r.contradiction_flag,
        }
        for r in rows
    ]

    elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
    return {
        "request_id": request_id,
        "status": "ok",
        "data": {"run_id": run_id, "status": run_status, "ranked_targets": ranked_targets},
        "warnings": warnings,
        "errors": [],
        "timing": {"started_at": started_at.isoformat(), "elapsed_ms": elapsed_ms},
        "provenance": {"runtime_mode": "hosted"},
    }


def _build_envelope(req: Request, data, status: str = "ok", warnings: list = None) -> Dict[str, Any]:
    return _shared_envelope(req, data, status=status, warnings=warnings)


@router.get("/{run_id}/scores")
async def get_target_scores(run_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """§122: Get detailed score breakdown for a target ranking run."""
    stmt = select(TargetRanking).where(TargetRanking.run_id == run_id).order_by(TargetRanking.rank.asc())
    result = await db.execute(stmt)
    rows = result.scalars().all()

    scores = [
        {
            "gene_symbol": r.gene_symbol,
            "rank": r.rank,
            "composite_score": r.composite_score,
            "gwas_score": r.gwas_score,
            "druggability_score": r.druggability_score,
            "pathway_centrality": r.pathway_centrality,
            "expression_score": r.expression_score,
            "safety_score": r.safety_score,
            "novelty_score": r.novelty_score,
            "literature_score": r.literature_score,
            "ucb_score": r.ucb_score,
            "score_breakdown": r.score_breakdown or {},
            "evidence_breakdown": r.evidence_breakdown or {},
        }
        for r in rows
    ]

    return _build_envelope(request, {
        "run_id": run_id,
        "scores": scores,
    })


@router.get("/compare")
async def compare_targets(request: Request, symbols: str = "", db: AsyncSession = Depends(get_db)):
    """§122: Compare multiple targets side-by-side."""
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()] if symbols else []
    warnings: list[str] = []

    if not symbol_list:
        return _build_envelope(request, {"symbols": [], "comparison": []}, warnings=["No symbols provided"])

    stmt = select(TargetRanking).where(TargetRanking.gene_symbol.in_(symbol_list)).order_by(TargetRanking.gene_symbol, TargetRanking.rank.asc())
    result = await db.execute(stmt)
    rows = result.scalars().all()

    # Group best rank per symbol
    seen: dict[str, dict] = {}
    for r in rows:
        if r.gene_symbol not in seen:
            seen[r.gene_symbol] = {
                "gene_symbol": r.gene_symbol,
                "uniprot_id": r.uniprot_id or "",
                "composite_score": r.composite_score,
                "gwas_score": r.gwas_score,
                "druggability_score": r.druggability_score,
                "pathway_centrality": r.pathway_centrality,
                "expression_score": r.expression_score,
                "safety_score": r.safety_score,
                "novelty_score": r.novelty_score,
                "literature_score": r.literature_score,
            }

    missing = [s for s in symbol_list if s not in seen]
    if missing:
        warnings.append(f"No DB records for: {', '.join(missing)}")

    return _build_envelope(request, {
        "symbols": symbol_list,
        "comparison": list(seen.values()),
    }, warnings=warnings if warnings else None)


class ExportTargetsRequest(BaseModel):
    run_id: Optional[str] = None
    symbols: List[str] = []
    format: str = "csv"


@router.post("/export")
async def export_targets(body: ExportTargetsRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """§122: Export target rankings as CSV."""
    import csv
    import io
    from fastapi.responses import StreamingResponse

    stmt = select(TargetRanking)
    if body.run_id:
        stmt = stmt.where(TargetRanking.run_id == body.run_id)
    elif body.symbols:
        stmt = stmt.where(TargetRanking.gene_symbol.in_([s.upper() for s in body.symbols]))
    else:
        return _build_envelope(request, {
            "export_format": body.format,
            "status": "error",
        }, warnings=["Provide run_id or symbols to export"])

    stmt = stmt.order_by(TargetRanking.rank.asc())
    result = await db.execute(stmt)
    rows = result.scalars().all()

    if not rows:
        return _build_envelope(request, {
            "export_format": body.format,
            "status": "empty",
            "count": 0,
        }, warnings=["No target rankings found for the given criteria"])

    # Generate CSV
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "rank", "gene_symbol", "uniprot_id", "composite_score",
        "gwas_score", "druggability_score", "pathway_centrality",
        "expression_score", "safety_score", "novelty_score",
        "literature_score", "ucb_score", "contradiction_flag", "explanation",
    ])
    for r in rows:
        writer.writerow([
            r.rank, r.gene_symbol, r.uniprot_id or "", r.composite_score,
            r.gwas_score, r.druggability_score, r.pathway_centrality,
            r.expression_score, r.safety_score, r.novelty_score,
            r.literature_score, r.ucb_score or "", r.contradiction_flag, r.explanation or "",
        ])

    content = buf.getvalue()
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=target_rankings_{body.run_id or 'custom'}.csv"},
    )


class PPIRequest(BaseModel):
    genes: List[str]
    score_threshold: float = 0.4


@router.post("/ppi-network")
async def get_ppi_network(body: PPIRequest, request: Request):
    """Fetch protein-protein interaction network from STRING DB for given genes."""
    from connectors.string_db import STRINGConnector

    if not body.genes:
        return _build_envelope(request, {"nodes": [], "edges": []}, warnings=["No genes provided"])

    connector = STRINGConnector()
    genes_str = "%0d".join(g.strip().upper() for g in body.genes[:50])
    edges = []
    nodes_set = set()
    warnings_list: list[str] = []

    try:
        interactions = await connector.search(genes_str, limit=200)
        for inter in interactions:
            score = inter.get("score", 0)
            if score < body.score_threshold:
                continue
            src = inter.get("source_entity", "")
            tgt = inter.get("target_entity", "")
            if src and tgt:
                nodes_set.add(src)
                nodes_set.add(tgt)
                edges.append({
                    "source": src,
                    "target": tgt,
                    "score": score,
                    "id": inter.get("id", f"{src}-{tgt}"),
                })
    except Exception as exc:
        log.warning("ppi_network_fetch_failed", error=str(exc))
        warnings_list.append(f"STRING DB query failed: {str(exc)[:100]}")

    input_genes = set(g.strip().upper() for g in body.genes)
    nodes = []
    for n in nodes_set:
        nodes.append({
            "id": n,
            "label": n,
            "is_query_gene": n.upper() in input_genes,
        })
    # Include input genes that had no interactions
    for g in input_genes:
        if g not in nodes_set:
            nodes.append({"id": g, "label": g, "is_query_gene": True})

    return _build_envelope(request, {
        "nodes": nodes,
        "edges": edges,
        "query_genes": list(input_genes),
        "total_interactions": len(edges),
    }, warnings=warnings_list if warnings_list else None)


# ── Batch Processing Endpoints (§FR-API-010) ────────────────

class BulkTargetScoreRequest(BaseModel):
    targets: List[Dict[str, Any]]  # List of {symbol, disease, context}
    project_id: str = "default"


@router.post("/bulk-score")
async def bulk_score_targets(
    req: BulkTargetScoreRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """§FR-API-010: POST /api/v1/targets/bulk-score — Score multiple targets at once."""
    try:
        scored_targets = []
        failed_targets = []
        
        for idx, target_data in enumerate(req.targets):
            try:
                symbol = target_data.get("symbol", "")
                disease = target_data.get("disease", "")
                
                if not symbol:
                    failed_targets.append({
                        "index": idx,
                        "error": "Missing symbol",
                        "target": target_data
                    })
                    continue
                
                # Use TargetScorer for evaluation
                scorer = TargetScorer(
                    query_id=disease or "bulk_score",
                    candidates=[symbol]
                )
                results = await scorer.evaluate_candidates()
                
                if results:
                    scored_targets.append({
                        "symbol": symbol,
                        "disease": disease,
                        "score": results[0].get("composite_score", 0),
                        "signals": results[0].get("signals", {}),
                        "explanation": results[0].get("explanation", ""),
                        "evidence_breakdown": results[0].get("evidence_breakdown", {})
                    })
                else:
                    failed_targets.append({
                        "index": idx,
                        "error": "No scoring results",
                        "target": target_data
                    })
                    
            except Exception as e:
                failed_targets.append({
                    "index": idx,
                    "error": str(e),
                    "target": target_data
                })
        
        return _build_envelope(request, {
            "scored_count": len(scored_targets),
            "failed_count": len(failed_targets),
            "scored_targets": scored_targets,
            "failed_targets": failed_targets,
            "project_id": req.project_id
        })
        
    except Exception as e:
        log.error("bulk_score_failed", error=str(e))
        return _build_envelope(
            request, None,
            warnings=[f"Bulk scoring failed: {str(e)}"]
        )


# ── D-6: Attention-weight explanation endpoint ───────────────────────────────

@router.get("/{symbol}/explanation", response_model=TargetResponse)
async def get_target_explanation(
    symbol: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """D-6: GET /api/v1/targets/{symbol}/explanation.

    Returns GAT-derived attention weights for a target, approximated as
    normalised signal contributions from the TargetRanking record's
    score_breakdown column.
    """
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    started_at = datetime.now(timezone.utc)

    stmt = (
        select(TargetRanking)
        .where(TargetRanking.gene_symbol == symbol.upper())
        .order_by(TargetRanking.rank.asc())
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        return {
            "request_id": request_id,
            "status": "not_found",
            "data": {},
            "warnings": [f"No ranking record for {symbol.upper()}"],
            "errors": [],
            "timing": {"started_at": started_at.isoformat(), "elapsed_ms": elapsed_ms},
            "provenance": {"runtime_mode": "hosted"},
        }

    raw_signals: dict = {
        "gwas":             row.gwas_score or 0.0,
        "druggability":     row.druggability_score or 0.0,
        "pathway_centrality": row.pathway_centrality or 0.0,
        "expression":       row.expression_score or 0.0,
        "safety":           row.safety_score or 0.0,
        "novelty":          row.novelty_score or 0.0,
        "literature":       row.literature_score or 0.0,
    }

    # Normalise to sum=1 (attention weight approximation)
    total = sum(raw_signals.values()) or 1.0
    attention_weights = {k: round(v / total, 4) for k, v in raw_signals.items()}

    # Optional: score_breakdown may have extra fields from target_scorer
    breakdown: dict = row.score_breakdown or {}

    elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
    return {
        "request_id": request_id,
        "status": "ok",
        "data": {
            "symbol": row.gene_symbol,
            "composite_score": row.composite_score,
            "attention_weights": attention_weights,
            "raw_signals": raw_signals,
            "score_breakdown": breakdown,
            "explanation": row.explanation or "",
            "rank": row.rank,
        },
        "warnings": [],
        "errors": [],
        "timing": {"started_at": started_at.isoformat(), "elapsed_ms": elapsed_ms},
        "provenance": {"runtime_mode": "hosted"},
    }
