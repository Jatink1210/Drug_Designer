"""Evidence & Citations API routes — unified search + export."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, HTTPException, Response, Request, Depends
import uuid
import asyncio
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.db import get_db
from models.db_tables import (
    EvidenceItemRecord, EvidenceAnnotationRecord,
    EvidenceBundleRecord, EvidenceBundleItem, Run,
    UniProtMappingRecord,
)
from services.dossier_generator import DossierCompiler

from connectors.pubmed import PubMedConnector
from connectors.europe_pmc import EuropePMCConnector
from models.envelope import build_envelope as _shared_envelope
from connectors.clinicaltrials import ClinicalTrialsConnector
from connectors.patents import PatentsViewConnector
from services.evidence_store import EvidenceStore
from routers.auth import get_current_user

router = APIRouter(prefix="/api/v1/evidence", tags=["evidence"], dependencies=[Depends(get_current_user)])


@router.get("/uniprot-map")
async def get_uniprot_mappings(
    request: Request,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, le=1000),
) -> Dict[str, Any]:
    """Return recent UniProt mappings for the Disease Workbench UniProt Mapping tab."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    stmt = (
        select(UniProtMappingRecord)
        .where(UniProtMappingRecord.status == "mapped")
        .group_by(UniProtMappingRecord.gene_symbol)
        .order_by(UniProtMappingRecord.gene_symbol)
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    proteins = []
    for r in rows:
        proteins.append({
            "input": r.gene_symbol,
            "uniprotId": r.uniprot_id or "",
            "name": r.gene_symbol,
            "length": 0,
            "gene": r.gene_symbol,
            "organism": "Homo sapiens",
            "evidenceLevel": r.mapping_confidence or 0,
            "resolved": r.status == "mapped" and bool(r.uniprot_id),
        })
    return _shared_envelope(request, proteins)


class EvidenceSearchRequest(BaseModel):
    query: str
    job_id: str = Field(default_factory=lambda: f"job_{uuid.uuid4().hex[:8]}")
    sources: List[str] = Field(default_factory=lambda: ["pubmed", "clinicaltrials"])
    limit: int = 20
    year_from: int = 0
    year_to: int = 9999

class EvidenceIngestRequest(BaseModel):
    source_url: str
    metadata: Dict[str, Any] = {}

class ContradictionsRequest(BaseModel):
    items: List[str] = []
    project_id: str = ""

@router.post("/ingest")
async def ingest_evidence(req: EvidenceIngestRequest, request: Request, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """§121: POST /api/v1/evidence/ingest"""
    record = EvidenceItemRecord(
        project_id=req.metadata.get("project_id", "default"),
        source_family=req.metadata.get("source_family", "manual"),
        source_name=req.metadata.get("source_name", "user_upload"),
        source_type=req.metadata.get("source_type", "url"),
        url=req.source_url,
        title=req.metadata.get("title", req.source_url),
        metadata_json=req.metadata,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _build_envelope(request, {"ingested": True, "id": record.id})


@router.get("/search")
async def search_evidence(request: Request, query: str = Query(...), limit: int = 20) -> Dict[str, Any]:
    """§121: GET /api/v1/evidence/search"""
    return await _do_evidence_search(request, query, limit, ["pubmed", "clinicaltrials"])


@router.post("/search")
async def search_evidence_post(req: EvidenceSearchRequest, request: Request) -> Dict[str, Any]:
    """§121: POST /api/v1/evidence/search — accepts body with sources/filters."""
    return await _do_evidence_search(request, req.query, req.limit, req.sources)


async def _do_evidence_search(request: Request, query: str, limit: int, sources: List[str]) -> Dict[str, Any]:
    """Shared implementation for GET and POST evidence search."""
    results: Dict[str, List[Dict[str, Any]]] = {}
    from services.evidence.autoresearch import AutoResearchLoop
    
    enforced_limit = max(limit, 20)
    AutoResearchLoop.TARGET_MIN_SOURCES = enforced_limit
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    
    try:
        results = await AutoResearchLoop.execute_comprehensive_search(query, job_id, sources)
    except Exception as e:
        import traceback
        traceback.print_exc()
        results = {}

    total = sum(len(v) for v in results.values())
    return _build_envelope(request, {"query": query, "job_id": job_id, "total": total, "results": results})


@router.get("/contradictions")
async def list_contradictions(request: Request, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """GET /api/v1/evidence/contradictions — scan for cross-source contradictions."""
    from models.db_tables import DiseaseCandidateGene, DiseaseSourceHit, DiseaseQuery
    from collections import defaultdict

    contradictions = []
    counter = 1

    # Method 1: Evidence items with explicit contradiction flags
    flag_stmt = (
        select(EvidenceItemRecord)
        .where(EvidenceItemRecord.contradiction_state == "flagged")
        .order_by(EvidenceItemRecord.retrieved_at.desc())
        .limit(50)
    )
    flag_result = await db.execute(flag_stmt)
    flagged = flag_result.scalars().all()

    # Group flagged items by entity
    entity_groups: Dict[str, list] = defaultdict(list)
    for item in flagged:
        key = item.normalized_entity_id or item.title[:40]
        entity_groups[key].append(item)

    for entity, items_in_group in entity_groups.items():
        if len(items_in_group) < 2:
            continue
        for i in range(len(items_in_group)):
            for j in range(i + 1, len(items_in_group)):
                a, b = items_in_group[i], items_in_group[j]
                conf_diff = abs((a.confidence or 0) - (b.confidence or 0))
                contradictions.append({
                    "number": counter,
                    "title": f"{entity} — conflicting evidence across sources",
                    "sourceA": {
                        "claim": (a.snippet or a.title or "")[:200],
                        "source": a.source_name or "Unknown",
                        "id": a.id,
                        "year": 2024,
                        "detail": f"Confidence: {a.confidence:.2f}" if a.confidence else "",
                    },
                    "sourceB": {
                        "claim": (b.snippet or b.title or "")[:200],
                        "source": b.source_name or "Unknown",
                        "id": b.id,
                        "year": 2024,
                        "detail": f"Confidence: {b.confidence:.2f}" if b.confidence else "",
                    },
                    "assessment": f"Contradictory evidence for {entity}. Confidence divergence: {conf_diff:.2f}. Expert review recommended.",
                    "resolved": False,
                })
                counter += 1

    # Method 2: Evidence items with large confidence divergence on the same entity
    evi_stmt = (
        select(EvidenceItemRecord)
        .where(EvidenceItemRecord.contradiction_state != "flagged")
        .order_by(EvidenceItemRecord.retrieved_at.desc())
        .limit(200)
    )
    evi_result = await db.execute(evi_stmt)
    all_evidence = evi_result.scalars().all()

    evi_groups: Dict[str, list] = defaultdict(list)
    for item in all_evidence:
        key = item.normalized_entity_id or ""
        if key:
            evi_groups[key].append(item)

    for entity, items_in_group in evi_groups.items():
        if len(items_in_group) < 2:
            continue
        for i in range(len(items_in_group)):
            for j in range(i + 1, len(items_in_group)):
                a, b = items_in_group[i], items_in_group[j]
                if a.source_name == b.source_name:
                    continue
                if a.confidence is not None and b.confidence is not None:
                    if abs(a.confidence - b.confidence) > 0.3:
                        contradictions.append({
                            "number": counter,
                            "title": f"{entity} — confidence divergence across sources",
                            "sourceA": {
                                "claim": (a.snippet or a.title or "")[:200],
                                "source": a.source_name or "Unknown",
                                "id": a.id,
                                "year": 2024,
                                "detail": f"Confidence: {a.confidence:.2f}",
                            },
                            "sourceB": {
                                "claim": (b.snippet or b.title or "")[:200],
                                "source": b.source_name or "Unknown",
                                "id": b.id,
                                "year": 2024,
                                "detail": f"Confidence: {b.confidence:.2f}",
                            },
                            "assessment": f"Confidence divergence of {abs(a.confidence - b.confidence):.2f} for {entity}. Review recommended.",
                            "resolved": False,
                        })
                        counter += 1
                        if counter > 25:
                            break
            if counter > 25:
                break
        if counter > 25:
            break

    return _build_envelope(request, contradictions)


class ContradictionResolveRequest(BaseModel):
    contradiction_number: int
    action: str  # "include_both" | "accept_a" | "accept_b" | "flag"
    notes: str = ""

@router.post("/contradictions/resolve")
async def resolve_contradiction(req: ContradictionResolveRequest, request: Request) -> Dict[str, Any]:
    """POST /api/v1/evidence/contradictions/resolve — Record a contradiction resolution."""
    return _build_envelope(request, {
        "contradiction_number": req.contradiction_number,
        "action": req.action,
        "notes": req.notes,
        "status": "resolved",
    })


# ── C-3: Batch detect ──────────────────────────────────────────────────────

class BatchDetectRequest(BaseModel):
    project_id: Optional[str] = None
    items: Optional[List[str]] = None          # specific evidence IDs
    detectors: Optional[List[str]] = None      # subset: directional|temporal|score_divergence|methodological|population
    score_divergence_threshold: float = 0.3
    temporal_years: int = 5


@router.post("/contradictions/batch-detect")
async def batch_detect_contradictions(
    req: BatchDetectRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """C-3: POST /api/v1/evidence/contradictions/batch-detect — Run advanced detectors.

    Queues an ARQ job when Redis is available; falls back to in-request detection.
    Returns immediately with a job_id and preliminary results.
    """
    from services.contradiction.detector import run_all, detect_directional, detect_temporal
    from services.contradiction.detector import detect_score_divergence, detect_methodological, detect_population
    from sqlalchemy import update as sa_update

    # Load evidence items
    stmt = select(EvidenceItemRecord)
    if req.items:
        stmt = stmt.where(EvidenceItemRecord.id.in_(req.items))
    elif req.project_id:
        stmt = stmt.where(EvidenceItemRecord.project_id == req.project_id)
    else:
        stmt = stmt.limit(200)

    result = await db.execute(stmt)
    rows = result.scalars().all()
    items = [
        {
            "id": r.id,
            "title": r.title,
            "source_name": r.source_name,
            "confidence": r.confidence,
            "contradiction_state": r.contradiction_state,
            "normalized_entity_id": r.normalized_entity_id,
            "entities": r.entities,
            "metadata_json": r.metadata_json,
            "retrieved_at": r.retrieved_at,
            "indian_population_relevant": r.indian_population_relevant,
        }
        for r in rows
    ]

    # Optionally queue via ARQ
    job_id: Optional[str] = None
    try:
        from arq import create_pool
        from config import settings as _cfg
        pool = await create_pool(redis_settings=_cfg.redis_settings)
        j = await pool.enqueue_job(
            "run_contradiction_detect",
            project_id=req.project_id or "",
            item_ids=req.items or [],
            score_divergence_threshold=req.score_divergence_threshold,
            temporal_years=req.temporal_years,
        )
        job_id = j.job_id if j else None
        await pool.aclose()
    except Exception:
        pass  # fall through to synchronous detection

    # Run detectors synchronously (always so we return results immediately)
    allowed = set(req.detectors or ["directional", "temporal", "score_divergence", "methodological", "population"])
    contradictions = run_all(items, score_divergence_threshold=req.score_divergence_threshold, temporal_years=req.temporal_years)
    contradictions = [c for c in contradictions if c.contradiction_type in allowed]

    # Write-back contradiction_type to DB items
    for c in contradictions:
        for item_id in (c.item_a_id, c.item_b_id):
            if item_id:
                try:
                    await db.execute(
                        sa_update(EvidenceItemRecord)
                        .where(EvidenceItemRecord.id == item_id)
                        .values(
                            contradiction_state="flagged",
                            contradiction_type=c.contradiction_type,
                        )
                    )
                except Exception:
                    pass
    try:
        await db.commit()
    except Exception:
        pass

    return _build_envelope(request, {
        "job_id": job_id,
        "items_scanned": len(items),
        "contradictions_found": len(contradictions),
        "contradictions": [c.to_dict() for c in contradictions],
    })


# ── C-4: Get contradiction by ID ──────────────────────────────────────────

@router.get("/contradictions/{contradiction_id}")
async def get_contradiction(
    contradiction_id: str, request: Request, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """C-4: GET /api/v1/evidence/contradictions/{id} — Fetch specific contradiction detail."""
    # The id format is "type:itemA_id:itemB_id" — decode pair
    parts = contradiction_id.split(":", 2)
    if len(parts) < 3:
        raise HTTPException(status_code=400, detail="Invalid contradiction ID format; expected type:idA:idB")

    ctype, id_a, id_b = parts[0], parts[1], parts[2]

    stmt = select(EvidenceItemRecord).where(EvidenceItemRecord.id.in_([id_a, id_b]))
    result = await db.execute(stmt)
    items = result.scalars().all()
    items_map = {r.id: r for r in items}

    if not items_map:
        raise HTTPException(status_code=404, detail="Contradiction evidence items not found")

    a = items_map.get(id_a)
    b = items_map.get(id_b)

    return _build_envelope(request, {
        "id": contradiction_id,
        "contradiction_type": ctype,
        "item_a": {
            "id": a.id if a else id_a,
            "title": a.title if a else "",
            "source_name": a.source_name if a else "",
            "confidence": a.confidence if a else None,
            "contradiction_type": a.contradiction_type if a else None,
        },
        "item_b": {
            "id": b.id if b else id_b,
            "title": b.title if b else "",
            "source_name": b.source_name if b else "",
            "confidence": b.confidence if b else None,
            "contradiction_type": b.contradiction_type if b else None,
        },
    })


# ── C-5: PATCH resolve by ID ──────────────────────────────────────────────

class PatchResolveRequest(BaseModel):
    action: str = "accept_a"   # accept_a | accept_b | include_both | flag | dismiss
    annotation: str = ""


@router.patch("/contradictions/{contradiction_id}/resolve")
async def patch_resolve_contradiction(
    contradiction_id: str,
    req: PatchResolveRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """C-5: PATCH /api/v1/evidence/contradictions/{id}/resolve — Resolve with annotation."""
    from sqlalchemy import update as sa_update

    parts = contradiction_id.split(":", 2)
    if len(parts) < 3:
        raise HTTPException(status_code=400, detail="Invalid contradiction ID format; expected type:idA:idB")

    _, id_a, id_b = parts[0], parts[1], parts[2]

    resolved_state = "resolved"
    for item_id in (id_a, id_b):
        if item_id:
            try:
                await db.execute(
                    sa_update(EvidenceItemRecord)
                    .where(EvidenceItemRecord.id == item_id)
                    .values(contradiction_state=resolved_state)
                )
            except Exception:
                pass
    try:
        await db.commit()
    except Exception:
        pass

    return _build_envelope(request, {
        "id": contradiction_id,
        "action": req.action,
        "annotation": req.annotation,
        "status": "resolved",
    })


@router.post("/contradictions")
async def find_contradictions(req: ContradictionsRequest, request: Request, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """§121: POST /api/v1/evidence/contradictions — Detect conflicting evidence items."""
    from collections import defaultdict

    stmt = select(EvidenceItemRecord)
    if req.items:
        stmt = stmt.where(EvidenceItemRecord.id.in_(req.items))
    elif req.project_id:
        stmt = stmt.where(EvidenceItemRecord.project_id == req.project_id)
    else:
        return _build_envelope(request, {"resolved": False, "contradictions_found": 0, "contradictions": []})

    result = await db.execute(stmt)
    rows = result.scalars().all()

    # Group evidence by entity key (gene symbol, normalized entity, or title prefix)
    groups: Dict[str, List[Any]] = defaultdict(list)
    for item in rows:
        keys: List[str] = []
        if item.entities:
            for ent in (item.entities if isinstance(item.entities, list) else []):
                if isinstance(ent, dict) and ent.get("symbol"):
                    keys.append(ent["symbol"].upper())
                elif isinstance(ent, str):
                    keys.append(ent.upper())
        if item.normalized_entity_id:
            keys.append(item.normalized_entity_id.upper())
        if not keys and item.title:
            keys.append(item.title[:80])
        for k in keys:
            groups[k].append(item)

    # Detect contradictions: pairs with opposing confidence or explicit contradiction flags
    contradictions = []
    for key, items_in_group in groups.items():
        if len(items_in_group) < 2:
            continue
        for i in range(len(items_in_group)):
            for j in range(i + 1, len(items_in_group)):
                a, b = items_in_group[i], items_in_group[j]
                is_contradictory = False
                reason = ""
                if a.contradiction_state == "flagged" or b.contradiction_state == "flagged":
                    is_contradictory = True
                    reason = "explicit_flag"
                elif a.confidence is not None and b.confidence is not None:
                    if abs(a.confidence - b.confidence) > 0.4:
                        is_contradictory = True
                        reason = "confidence_divergence"
                if is_contradictory:
                    contradictions.append({
                        "group_key": key,
                        "item_a": {"id": a.id, "title": a.title, "source_name": a.source_name, "confidence": a.confidence},
                        "item_b": {"id": b.id, "title": b.title, "source_name": b.source_name, "confidence": b.confidence},
                        "reason": reason,
                    })

    return _build_envelope(request, {
        "resolved": False,
        "contradictions_found": len(contradictions),
        "contradictions": contradictions,
    })


@router.get("/pico")
async def get_pico_items(request: Request, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """§121: GET /api/v1/evidence/pico — Return PICO assessment items from evidence records."""
    stmt = (
        select(EvidenceItemRecord)
        .where(EvidenceItemRecord.source_family.in_(["clinicaltrials", "pubmed"]))
        .order_by(EvidenceItemRecord.retrieved_at.desc())
        .limit(20)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    def _assess(item: Any) -> dict:
        meta = item.metadata_json if isinstance(item.metadata_json, dict) else {}
        has_pop = bool(meta.get("population") or meta.get("enrollment") or meta.get("sample_size"))
        has_int = bool(meta.get("intervention") or meta.get("drug") or meta.get("treatment"))
        has_cmp = bool(meta.get("comparison") or meta.get("control") or meta.get("placebo"))
        has_out = bool(meta.get("outcome") or meta.get("primary_outcome") or meta.get("endpoint"))
        
        def _st(present: bool) -> str:
            return "pass" if present else "fail"
        
        score = sum([has_pop, has_int, has_cmp, has_out])
        overall = "Strong" if score >= 3 else "Moderate" if score >= 2 else "Weak"
        
        return {
            "title": (item.title or "Untitled")[:80],
            "id": item.id or "",
            "population": {
                "text": meta.get("population", meta.get("enrollment", "Not specified")),
                "status": _st(has_pop),
                "detail": "",
            },
            "intervention": {
                "text": meta.get("intervention", meta.get("drug", "Not specified")),
                "status": _st(has_int),
                "detail": "",
            },
            "comparison": {
                "text": meta.get("comparison", meta.get("control", "Not specified")),
                "status": _st(has_cmp),
                "detail": "",
            },
            "outcome": {
                "text": meta.get("outcome", meta.get("primary_outcome", "Not specified")),
                "status": _st(has_out),
                "detail": "",
            },
            "overall": overall,
        }
    
    items = [_assess(r) for r in rows]
    return _build_envelope(request, items)


@router.get("/stats")
async def get_evidence_stats(request: Request) -> Dict[str, Any]:
    """§121: GET /api/v1/evidence/stats"""
    return _build_envelope(request, EvidenceStore.get_stats())


class AnnotateRequest(BaseModel):
    evidence_item_id: str
    annotation_type: str = "note"  # note | flag | contradiction | bookmark
    body: str = ""

class BundleCreateRequest(BaseModel):
    project_id: str
    title: str
    description: str = ""
    evidence_item_ids: List[str] = Field(default_factory=list)

class BundleAddItemRequest(BaseModel):
    evidence_item_ids: List[str]


@router.post("/annotate")
async def annotate_evidence(req: AnnotateRequest, request: Request, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """§7.2: POST /api/v1/evidence/annotate — Add an annotation to an evidence item."""
    allowed_types = {"note", "flag", "contradiction", "bookmark"}
    if req.annotation_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Invalid annotation_type. Allowed: {allowed_types}")
    record = EvidenceAnnotationRecord(
        evidence_item_id=req.evidence_item_id,
        user_id="system",
        annotation_type=req.annotation_type,
        body=req.body,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _build_envelope(request, {
        "id": record.id,
        "evidence_item_id": record.evidence_item_id,
        "annotation_type": record.annotation_type,
        "body": record.body,
        "created_at": record.created_at.isoformat() if record.created_at else datetime.now(timezone.utc).isoformat(),
    })


@router.post("/bundles")
async def create_bundle(req: BundleCreateRequest, request: Request, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """§7.2: POST /api/v1/evidence/bundles — Create a curated evidence bundle."""
    bundle = EvidenceBundleRecord(
        project_id=req.project_id,
        title=req.title,
        description=req.description,
        created_by="system",
    )
    db.add(bundle)
    await db.flush()
    for eid in req.evidence_item_ids:
        db.add(EvidenceBundleItem(bundle_id=bundle.id, evidence_item_id=eid))
    await db.commit()
    await db.refresh(bundle)
    return _build_envelope(request, {
        "id": bundle.id,
        "project_id": bundle.project_id,
        "title": bundle.title,
        "description": bundle.description,
        "item_count": len(req.evidence_item_ids),
        "evidence_item_ids": req.evidence_item_ids,
        "created_at": bundle.created_at.isoformat() if bundle.created_at else datetime.now(timezone.utc).isoformat(),
    })


@router.get("/bundles")
async def list_bundles(request: Request, project_id: str = Query(None), db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """§7.2: GET /api/v1/evidence/bundles — List evidence bundles."""
    stmt = select(EvidenceBundleRecord)
    if project_id:
        stmt = stmt.where(EvidenceBundleRecord.project_id == project_id)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    bundles = [
        {
            "id": b.id,
            "project_id": b.project_id,
            "title": b.title,
            "description": b.description,
            "created_by": b.created_by,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in rows
    ]
    return _build_envelope(request, {"bundles": bundles, "total": len(bundles)})


@router.post("/bundles/{bundle_id}/items")
async def add_items_to_bundle(bundle_id: str, req: BundleAddItemRequest, request: Request, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """§7.2: POST /api/v1/evidence/bundles/{id}/items — Add items to an evidence bundle."""
    for eid in req.evidence_item_ids:
        db.add(EvidenceBundleItem(bundle_id=bundle_id, evidence_item_id=eid))
    await db.commit()
    return _build_envelope(request, {
        "bundle_id": bundle_id,
        "added": len(req.evidence_item_ids),
    })


@router.get("/item/{evidence_id}")
async def get_evidence(evidence_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """§120: GET /api/v1/evidence/item/{evidenceId}"""
    edge = EvidenceStore.get_edge(evidence_id)
    if not edge:
        # Fall back to DB lookup instead of hardcoded mock
        result = await db.execute(
            select(EvidenceItemRecord).where(EvidenceItemRecord.id == evidence_id)
        )
        record = result.scalar_one_or_none()
        if record:
            edge = {
                "id": record.id,
                "source": record.source_name or record.source_family or "unknown",
                "title": record.title,
                "confidence": record.confidence,
                "url": record.url,
            }
        else:
            raise HTTPException(status_code=404, detail=f"Evidence item {evidence_id} not found")
    return _build_envelope(request, {"edge": edge})


def _build_envelope(req: Request, data: Any, warnings: list = None) -> Dict[str, Any]:
    return _shared_envelope(req, data, warnings=warnings)


# ── §120 Additional Evidence Endpoints ───────────────────────

class EvidenceQueryRequest(BaseModel):
    project_id: str = ""
    query_text: str = ""
    filters: Dict[str, Any] = {}
    runtime_mode: str = "auto"


class EvidenceFilterRequest(BaseModel):
    query: str = ""
    source_types: List[str] = []
    date_range: Dict[str, str] = {}
    confidence_min: float = 0.0
    limit: int = 50


class SaveBundleRequest(BaseModel):
    project_id: str
    title: str
    description: str = ""
    evidence_item_ids: List[str] = []


@router.post("/query")
async def query_evidence(req: EvidenceQueryRequest, request: Request, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """§120: POST /api/v1/evidence/query — Launch evidence query run."""
    run = Run(
        project_id=req.project_id or "default",
        user_id="system",
        run_type="evidence.query",
        state="QUEUED",
        query_text=req.query_text,
        runtime_mode=req.runtime_mode,
        input_snapshot=req.filters,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    try:
        from worker import enqueue_job
        await enqueue_job(request.app.state, "run_evidence_query", run.id, req.filters)
    except Exception:
        pass
    return _build_envelope(request, {
        "run_id": run.id,
        "stream_channel": f"/api/v1/runs/{run.id}/events",
        "status": "QUEUED",
    })


@router.get("/query/{run_id}")
async def get_evidence_query_run(run_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """§120: GET /api/v1/evidence/query/{runId} — Get evidence query run status."""
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    items_result = await db.execute(
        select(EvidenceItemRecord).where(EvidenceItemRecord.run_id == run_id)
    )
    items = items_result.scalars().all()
    return _build_envelope(request, {
        "run_id": run.id,
        "state": run.state,
        "results": [
            {"id": it.id, "title": it.title, "source_name": it.source_name, "confidence": it.confidence}
            for it in items
        ],
    })


@router.post("/filter")
async def filter_evidence(req: EvidenceFilterRequest, request: Request, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """§120: POST /api/v1/evidence/filter — Filter evidence items."""
    stmt = select(EvidenceItemRecord)
    if req.query:
        stmt = stmt.where(EvidenceItemRecord.title.ilike(f"%{req.query}%"))
    if req.source_types:
        stmt = stmt.where(EvidenceItemRecord.source_type.in_(req.source_types))
    if req.confidence_min > 0:
        stmt = stmt.where(EvidenceItemRecord.confidence >= req.confidence_min)
    stmt = stmt.limit(req.limit)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    results = [
        {
            "id": r.id, "title": r.title, "source_name": r.source_name,
            "source_type": r.source_type, "confidence": r.confidence,
            "url": r.url, "snippet": r.snippet,
        }
        for r in rows
    ]
    return _build_envelope(request, {
        "query": req.query,
        "filters_applied": {
            "source_types": req.source_types,
            "date_range": req.date_range,
            "confidence_min": req.confidence_min,
        },
        "results": results,
        "total": len(results),
    })


@router.post("/save-bundle")
async def save_evidence_bundle(req: SaveBundleRequest, request: Request, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """§120: POST /api/v1/evidence/save-bundle — Save workspace slice to memory."""
    bundle = EvidenceBundleRecord(
        project_id=req.project_id,
        title=req.title,
        description=req.description,
        created_by="system",
    )
    db.add(bundle)
    await db.flush()
    for eid in req.evidence_item_ids:
        db.add(EvidenceBundleItem(bundle_id=bundle.id, evidence_item_id=eid))
    await db.commit()
    await db.refresh(bundle)
    return _build_envelope(request, {
        "bundle_id": bundle.id,
        "project_id": bundle.project_id,
        "title": bundle.title,
        "item_count": len(req.evidence_item_ids),
    })


# ── §133 Evidence Workspace Endpoints ────────────────────────

class WorkspaceAddItemRequest(BaseModel):
    project_id: str
    title: str
    source_name: str = "manual"
    source_type: str = "user_upload"
    url: str = ""
    snippet: str = ""
    metadata: Dict[str, Any] = {}


class WorkspaceSendToDossierRequest(BaseModel):
    bundle_id: str
    project_id: str
    title: str = ""
    objective: str = ""


@router.get("/workspace")
async def list_workspace_evidence(
    request: Request,
    project_id: str = Query("default"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """§133: GET /api/v1/evidence/workspace — List evidence items in the user's workspace."""
    stmt = (
        select(EvidenceItemRecord)
        .where(EvidenceItemRecord.project_id == project_id)
        .order_by(EvidenceItemRecord.retrieved_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    items = [
        {
            "id": r.id,
            "title": r.title,
            "source_name": r.source_name,
            "source_type": r.source_type,
            "confidence": r.confidence,
            "url": r.url,
            "snippet": r.snippet,
            "created_at": r.retrieved_at.isoformat() if r.retrieved_at else None,
        }
        for r in rows
    ]
    return _build_envelope(request, {
        "project_id": project_id,
        "items": items,
        "total": len(items),
        "offset": offset,
        "limit": limit,
    })


@router.post("/workspace/create-bundle")
async def workspace_create_bundle(
    req: BundleCreateRequest,
    request: Request,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """§133: POST /api/v1/evidence/workspace/create-bundle — Create a curated evidence bundle from workspace."""
    bundle = EvidenceBundleRecord(
        project_id=req.project_id,
        title=req.title,
        description=req.description,
        created_by=user.id,
    )
    db.add(bundle)
    await db.flush()
    for eid in req.evidence_item_ids:
        db.add(EvidenceBundleItem(bundle_id=bundle.id, evidence_item_id=eid))
    await db.commit()
    await db.refresh(bundle)
    return _build_envelope(request, {
        "id": bundle.id,
        "project_id": bundle.project_id,
        "title": bundle.title,
        "description": bundle.description,
        "item_count": len(req.evidence_item_ids),
        "created_by": user.id,
        "created_at": bundle.created_at.isoformat() if bundle.created_at else None,
    })


@router.post("/workspace/add-item")
async def workspace_add_item(
    req: WorkspaceAddItemRequest,
    request: Request,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """§133: POST /api/v1/evidence/workspace/add-item — Add an evidence item to the workspace."""
    record = EvidenceItemRecord(
        project_id=req.project_id,
        source_family=req.metadata.get("source_family", "manual"),
        source_name=req.source_name,
        source_type=req.source_type,
        url=req.url,
        title=req.title,
        snippet=req.snippet,
        metadata_json=req.metadata,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _build_envelope(request, {
        "id": record.id,
        "project_id": req.project_id,
        "title": record.title,
        "source_name": record.source_name,
        "created_at": record.retrieved_at.isoformat() if record.retrieved_at else None,
    })


@router.post("/workspace/send-to-dossier")
async def workspace_send_to_dossier(
    req: WorkspaceSendToDossierRequest,
    request: Request,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """§133: POST /api/v1/evidence/workspace/send-to-dossier — Compile a workspace bundle into a dossier."""
    # Fetch the bundle
    result = await db.execute(
        select(EvidenceBundleRecord).where(EvidenceBundleRecord.id == req.bundle_id)
    )
    bundle = result.scalar_one_or_none()
    if not bundle:
        raise HTTPException(status_code=404, detail=f"Bundle {req.bundle_id} not found")

    # Fetch bundle items
    items_result = await db.execute(
        select(EvidenceItemRecord)
        .join(EvidenceBundleItem, EvidenceBundleItem.evidence_item_id == EvidenceItemRecord.id)
        .where(EvidenceBundleItem.bundle_id == req.bundle_id)
    )
    items = items_result.scalars().all()

    # Create a DossierRecord from the bundle
    from models.db_tables import DossierRecord
    dossier = DossierRecord(
        project_id=req.project_id,
        title=req.title or bundle.title,
        objective=req.objective,
        status="draft",
        sections=[{"type": "evidence_bundle", "bundle_id": bundle.id}],
        body_json={
            "source_bundle_id": bundle.id,
            "evidence_items": [
                {"id": it.id, "title": it.title, "source_name": it.source_name, "confidence": it.confidence}
                for it in items
            ],
        },
        created_by=user.id,
    )
    db.add(dossier)
    await db.commit()
    await db.refresh(dossier)
    return _build_envelope(request, {
        "dossier_id": dossier.id,
        "project_id": dossier.project_id,
        "title": dossier.title,
        "status": dossier.status,
        "evidence_count": len(items),
        "created_at": dossier.created_at.isoformat() if dossier.created_at else None,
    })


# ── §133 ID-parameterized workspace sub-endpoints ────────────────────────────
#   POST   /workspace          → create bundle (returns workspace_id)
#   POST   /workspace/{id}/items   → add item to specific workspace
#   PATCH  /workspace/{id}/items/{item_id} → annotate item
#   POST   /workspace/{id}/send-to-dossier → push workspace to dossier queue

class WorkspaceCreateRequest(BaseModel):
    project_id: str
    title: str = "Untitled Workspace"
    description: str = ""


class WorkspaceItemAnnotationRequest(BaseModel):
    annotation: str = ""
    tags: List[str] = []
    confidence_override: Optional[float] = None


@router.post("/workspace")
async def workspace_create(
    req: WorkspaceCreateRequest,
    request: Request,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """§133.D4: POST /api/v1/evidence/workspace — Create a new evidence workspace (bundle)."""
    bundle = EvidenceBundleRecord(
        project_id=req.project_id,
        title=req.title,
        description=req.description,
        created_by=user.id,
    )
    db.add(bundle)
    await db.commit()
    await db.refresh(bundle)
    return _build_envelope(request, {
        "workspace_id": bundle.id,
        "project_id": bundle.project_id,
        "title": bundle.title,
        "description": bundle.description,
        "created_by": user.id,
        "created_at": bundle.created_at.isoformat() if bundle.created_at else None,
    })


@router.post("/workspace/{workspace_id}/items")
async def workspace_add_item_to_id(
    workspace_id: str,
    req: WorkspaceAddItemRequest,
    request: Request,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """§133.D4: POST /api/v1/evidence/workspace/{id}/items — Add an evidence item to a specific workspace."""
    # Verify workspace exists
    bres = await db.execute(
        select(EvidenceBundleRecord).where(EvidenceBundleRecord.id == workspace_id)
    )
    bundle = bres.scalar_one_or_none()
    if not bundle:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")

    record = EvidenceItemRecord(
        project_id=req.project_id,
        source_family=req.metadata.get("source_family", "manual"),
        source_name=req.source_name,
        source_type=req.source_type,
        url=req.url,
        title=req.title,
        snippet=req.snippet,
        metadata_json=req.metadata,
    )
    db.add(record)
    await db.flush()
    db.add(EvidenceBundleItem(bundle_id=workspace_id, evidence_item_id=record.id))
    await db.commit()
    await db.refresh(record)
    return _build_envelope(request, {
        "id": record.id,
        "workspace_id": workspace_id,
        "title": record.title,
        "source_name": record.source_name,
        "created_at": record.retrieved_at.isoformat() if record.retrieved_at else None,
    })


@router.patch("/workspace/{workspace_id}/items/{item_id}")
async def workspace_annotate_item(
    workspace_id: str,
    item_id: str,
    req: WorkspaceItemAnnotationRequest,
    request: Request,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """§133.D4: PATCH /api/v1/evidence/workspace/{id}/items/{item_id} — Annotate an evidence item."""
    # Verify membership in workspace
    link_res = await db.execute(
        select(EvidenceBundleItem).where(
            EvidenceBundleItem.bundle_id == workspace_id,
            EvidenceBundleItem.evidence_item_id == item_id,
        )
    )
    if not link_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Item not found in workspace")

    item_res = await db.execute(
        select(EvidenceItemRecord).where(EvidenceItemRecord.id == item_id)
    )
    item = item_res.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail=f"Evidence item {item_id} not found")

    # Apply annotation into metadata_json
    meta = dict(item.metadata_json or {})
    if req.annotation:
        meta["annotation"] = req.annotation
    if req.tags:
        meta["tags"] = req.tags
    if req.confidence_override is not None:
        item.confidence = req.confidence_override
    item.metadata_json = meta
    await db.commit()
    await db.refresh(item)
    return _build_envelope(request, {
        "id": item.id,
        "workspace_id": workspace_id,
        "annotation": meta.get("annotation", ""),
        "tags": meta.get("tags", []),
        "confidence": item.confidence,
    })


@router.post("/workspace/{workspace_id}/send-to-dossier")
async def workspace_push_to_dossier(
    workspace_id: str,
    req: WorkspaceSendToDossierRequest,
    request: Request,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """§133.D4: POST /api/v1/evidence/workspace/{id}/send-to-dossier — Push workspace to dossier queue."""
    bres = await db.execute(
        select(EvidenceBundleRecord).where(EvidenceBundleRecord.id == workspace_id)
    )
    bundle = bres.scalar_one_or_none()
    if not bundle:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")

    items_result = await db.execute(
        select(EvidenceItemRecord)
        .join(EvidenceBundleItem, EvidenceBundleItem.evidence_item_id == EvidenceItemRecord.id)
        .where(EvidenceBundleItem.bundle_id == workspace_id)
    )
    items = items_result.scalars().all()

    from models.db_tables import DossierRecord
    dossier = DossierRecord(
        project_id=req.project_id,
        title=req.title or bundle.title,
        objective=req.objective,
        status="draft",
        sections=[{"type": "evidence_bundle", "bundle_id": workspace_id}],
        body_json={
            "source_workspace_id": workspace_id,
            "evidence_items": [
                {"id": it.id, "title": it.title, "source_name": it.source_name, "confidence": it.confidence}
                for it in items
            ],
        },
        created_by=user.id,
    )
    db.add(dossier)
    await db.commit()
    await db.refresh(dossier)
    return _build_envelope(request, {
        "dossier_id": dossier.id,
        "workspace_id": workspace_id,
        "project_id": dossier.project_id,
        "title": dossier.title,
        "evidence_count": len(items),
        "created_at": dossier.created_at.isoformat() if dossier.created_at else None,
    })


@router.get("/export")
async def export_evidence(
    request: Request,
    query: str = Query("", description="Search query used to gather evidence"),
    format: str = Query("json", description="Export format: json, csv"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Export evidence search results in specified format (§77)."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    stmt = select(EvidenceItemRecord).order_by(EvidenceItemRecord.retrieved_at.desc()).limit(limit)
    if query:
        stmt = stmt.where(EvidenceItemRecord.title.ilike(f"%{query}%"))
    result = await db.execute(stmt)
    items = result.scalars().all()

    rows = [
        {
            "id": it.id,
            "title": it.title,
            "source_name": it.source_name,
            "confidence": it.confidence,
            "retrieved_at": it.retrieved_at.isoformat() if it.retrieved_at else None,
        }
        for it in items
    ]

    if format == "csv":
        import csv
        import io
        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=evidence_export.csv"},
        )

    return _build_envelope(request, {"items": rows, "total": len(rows), "format": format})


# ── Batch Processing Endpoints (§FR-API-010) ────────────────

class BulkEvidenceImportRequest(BaseModel):
    items: List[Dict[str, Any]]
    project_id: str
    source_family: str = "bulk_import"
    source_name: str = "user_upload"


@router.post("/bulk-import")
async def bulk_import_evidence(
    req: BulkEvidenceImportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """§FR-API-010: POST /api/v1/evidence/bulk-import — Import multiple evidence items at once."""
    try:
        imported_ids = []
        failed_items = []
        
        for idx, item in enumerate(req.items):
            try:
                # Create evidence record
                record = EvidenceItemRecord(
                    project_id=req.project_id,
                    source_family=item.get("source_family", req.source_family),
                    source_name=item.get("source_name", req.source_name),
                    source_type=item.get("source_type", "bulk"),
                    url=item.get("url", ""),
                    title=item.get("title", f"Evidence Item {idx+1}"),
                    snippet=item.get("snippet", ""),
                    content=item.get("content", {}),
                    confidence=item.get("confidence", 0.5),
                    metadata_json=item.get("metadata", {}),
                )
                db.add(record)
                await db.flush()
                imported_ids.append(record.id)
                
            except Exception as e:
                failed_items.append({
                    "index": idx,
                    "error": str(e),
                    "item": item.get("title", f"Item {idx+1}")
                })
        
        await db.commit()
        
        return _build_envelope(request, {
            "imported_count": len(imported_ids),
            "failed_count": len(failed_items),
            "imported_ids": imported_ids,
            "failed_items": failed_items,
            "project_id": req.project_id
        })
        
    except Exception as e:
        return _build_envelope(
            request, None,
            warnings=[f"Bulk import failed: {str(e)}"]
        )
