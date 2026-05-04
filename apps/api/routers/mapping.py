"""UniProt Mapping — Drug Designer §123, §11, §B1 Step 4.

Gene-to-protein resolution with fallback strategies.
Silent dropping of unmapped entities is forbidden.

§78: All responses use ResponseEnvelope.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from models.db_tables import UniProtMappingRecord, DiseaseQuery, DiseaseCandidateGene
from routers.auth import get_current_user, User

router = APIRouter(prefix="/api/v1/mapping", tags=["UniProt Mapping"])
log = structlog.get_logger(__name__)


# ── Pydantic schemas ──────────────────────────────────────

class MappingStartRequest(BaseModel):
    disease_query_id: str
    gene_symbols: List[str] = Field(default_factory=list, description="If empty, maps all genes from disease query")

class MappingResolveRequest(BaseModel):
    query_id: str
    gene_symbol: str
    uniprot_id: str
    method: str = "manual"

class MappingItem(BaseModel):
    gene_symbol: str
    uniprot_id: Optional[str] = None
    status: str
    mapping_method: str
    mapping_confidence: float

class MappingResult(BaseModel):
    query_id: str
    disease_query_id: str
    total: int
    mapped: int
    unmapped: int
    items: List[MappingItem]


def _envelope(data: Any, *, req: Request, warnings: list | None = None):
    return {
        "request_id": getattr(req.state, "request_id", str(uuid.uuid4())),
        "trace_id": getattr(req.state, "trace_id", ""),
        "status": "ok",
        "data": data,
        "warnings": warnings or [],
        "errors": [],
        "timing": {},
        "provenance": {},
    }


# ── POST /mapping/uniprot/start ──────────────────────────

MAX_MAPPING_BATCH_SIZE = 5000  # §97 drill 9: prevent 10K+ overflow


@router.post("/uniprot/start")
async def start_mapping(
    body: MappingStartRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start UniProt mapping for genes from a disease query (§123)."""
    # §97 drill 9: reject payloads exceeding mapping batch limit
    if body.gene_symbols and len(body.gene_symbols) > MAX_MAPPING_BATCH_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Batch too large: {len(body.gene_symbols)} genes exceeds limit of {MAX_MAPPING_BATCH_SIZE}",
        )

    query_id = str(uuid.uuid4())

    # Fetch gene symbols from disease query if not provided
    gene_symbols = body.gene_symbols
    if not gene_symbols:
        rows = (await db.execute(
            select(DiseaseCandidateGene.gene_symbol)
            .where(DiseaseCandidateGene.disease_query_id == body.disease_query_id)
        )).scalars().all()
        gene_symbols = list(rows)

    items: list[dict] = []
    for sym in gene_symbols:
        record = UniProtMappingRecord(
            id=str(uuid.uuid4()),
            disease_query_id=body.disease_query_id,
            gene_symbol=sym,
            status="pending",
            mapping_method="",
            mapping_confidence=0.0,
        )
        db.add(record)
        items.append({"gene_symbol": sym, "status": "pending", "uniprot_id": None,
                       "mapping_method": "", "mapping_confidence": 0.0})

    await db.commit()
    log.info("uniprot_mapping_started", query_id=query_id, gene_count=len(gene_symbols))

    return _envelope({
        "query_id": query_id,
        "disease_query_id": body.disease_query_id,
        "total": len(gene_symbols),
        "mapped": 0,
        "unmapped": len(gene_symbols),
        "items": items,
    }, req=request)


# ── GET /mapping/uniprot/{queryId} ───────────────────────

@router.get("/uniprot/{query_id}")
async def get_mapping(
    query_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get UniProt mapping results for a query (§123)."""
    rows = (await db.execute(
        select(UniProtMappingRecord).where(
            UniProtMappingRecord.disease_query_id == query_id
        )
    )).scalars().all()

    items = [
        MappingItem(
            gene_symbol=r.gene_symbol,
            uniprot_id=r.uniprot_id,
            status=r.status,
            mapping_method=r.mapping_method,
            mapping_confidence=r.mapping_confidence,
        )
        for r in rows
    ]
    mapped = sum(1 for i in items if i.status == "mapped")
    return _envelope(MappingResult(
        query_id=query_id,
        disease_query_id=query_id,
        total=len(items),
        mapped=mapped,
        unmapped=len(items) - mapped,
        items=items,
    ).model_dump(), req=request)


# ── GET /mapping/uniprot/{queryId}/unmapped ──────────────

@router.get("/uniprot/{query_id}/unmapped")
async def get_unmapped(
    query_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List genes that could not be mapped (§B1 Step 4 — never silently drop)."""
    rows = (await db.execute(
        select(UniProtMappingRecord).where(
            UniProtMappingRecord.disease_query_id == query_id,
            UniProtMappingRecord.status.in_(["pending", "ambiguous", "failed"]),
        )
    )).scalars().all()

    items = [
        {"gene_symbol": r.gene_symbol, "status": r.status, "notes": r.notes}
        for r in rows
    ]
    return _envelope({"unmapped": items, "count": len(items)}, req=request)


# ── POST /mapping/uniprot/resolve ────────────────────────

@router.post("/uniprot/resolve")
async def resolve_mapping(
    body: MappingResolveRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Manually resolve an ambiguous or failed mapping (§123)."""
    await db.execute(
        update(UniProtMappingRecord)
        .where(
            UniProtMappingRecord.disease_query_id == body.query_id,
            UniProtMappingRecord.gene_symbol == body.gene_symbol,
        )
        .values(
            uniprot_id=body.uniprot_id,
            mapping_method=body.method,
            mapping_confidence=1.0,
            status="mapped",
        )
    )
    await db.commit()
    log.info("mapping_resolved", gene=body.gene_symbol, uniprot=body.uniprot_id)
    return _envelope({"resolved": True, "gene_symbol": body.gene_symbol,
                       "uniprot_id": body.uniprot_id}, req=request)


# ── §123 Spec-Aligned Additional Endpoints ───────────────

@router.post("/uniprot")
async def run_mapping(
    body: MappingStartRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """§123: POST /api/v1/mapping/uniprot — Primary mapping endpoint."""
    return await start_mapping(body, request, db, user)


class MappingRetryRequest(BaseModel):
    query_id: str
    gene_symbols: List[str] = Field(default_factory=list)


@router.post("/uniprot/retry")
async def retry_mapping(
    body: MappingRetryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """§123: POST /api/v1/mapping/uniprot/retry — Retry failed mappings."""
    return _envelope({
        "query_id": body.query_id,
        "retried_count": len(body.gene_symbols),
        "status": "retrying",
    }, req=request, warnings=["Retry logic pending full implementation"])


class MappingAcceptRequest(BaseModel):
    query_id: str
    gene_symbol: str
    uniprot_id: str


@router.post("/uniprot/accept")
async def accept_mapping(
    body: MappingAcceptRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """§123: POST /api/v1/mapping/uniprot/accept — Accept a proposed mapping."""
    await db.execute(
        update(UniProtMappingRecord)
        .where(
            UniProtMappingRecord.disease_query_id == body.query_id,
            UniProtMappingRecord.gene_symbol == body.gene_symbol,
        )
        .values(
            uniprot_id=body.uniprot_id,
            mapping_method="accepted",
            mapping_confidence=1.0,
            status="mapped",
        )
    )
    await db.commit()
    return _envelope({
        "accepted": True,
        "gene_symbol": body.gene_symbol,
        "uniprot_id": body.uniprot_id,
    }, req=request)
