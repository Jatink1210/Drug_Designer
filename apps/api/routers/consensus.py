"""MAV Consensus Protocol API Endpoints

This router implements the Multi-Agent Voting (MAV) consensus protocol for
scientific claim verification with specialist agents.

Requirements: FR-API-002, FR-SUB-002
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from core.db import get_db
from core.rbac import require_role, Role
from routers.auth import get_current_user
from models.user import User
from models.db_tables import ConsensusResult

router = APIRouter(prefix="/api/v1/consensus", tags=["consensus"])


# ═══════════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════════

class MAVConsensusRequest(BaseModel):
    """Request model for MAV consensus voting."""
    claim: str = Field(..., description="Scientific claim to verify")
    evidence_bundle_id: str = Field(..., description="Evidence bundle UUID")
    jury_size: int = Field(5, description="Number of specialist agents (3, 5, or 7)")
    project_id: str = Field(..., description="Project UUID")


class MAVConsensusResponse(BaseModel):
    """Response model for MAV consensus voting."""
    status: str
    data: Dict[str, Any]
    provenance: Dict[str, Any]


class TruthfulPauseRequest(BaseModel):
    """Request model for truthful pause resolution."""
    consensus_id: str = Field(..., description="Consensus result UUID")
    human_decision: str = Field(..., description="accept_verified | accept_contradicted | request_more_evidence")
    rationale: Optional[str] = Field(None, description="Human decision rationale")


class TruthfulPauseResponse(BaseModel):
    """Response model for truthful pause resolution."""
    status: str
    data: Dict[str, Any]


# ═══════════════════════════════════════════════════════════
# MAV Consensus Endpoint
# ═══════════════════════════════════════════════════════════

@router.post("/mav", response_model=MAVConsensusResponse)
async def create_mav_consensus(
    request: MAVConsensusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Multi-agent voting consensus with configurable jury size.
    
    Requirements: FR-API-002, FR-SUB-002
    Performance: p95 <30s for 5-agent consensus
    """
    from services.agency.mav_consensus import mav_consensus_service
    
    try:
        # Validate jury size
        if request.jury_size not in [3, 5, 7]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Jury size must be 3, 5, or 7"
            )
        
        result = await mav_consensus_service(
            db=db,
            user_id=current_user.id,
            project_id=request.project_id,
            claim=request.claim,
            evidence_bundle_id=request.evidence_bundle_id,
            jury_size=request.jury_size
        )
        
        return MAVConsensusResponse(
            status="success",
            data=result["data"],
            provenance=result["provenance"]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MAV consensus failed: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════
# Get Consensus Result Endpoint
# ═══════════════════════════════════════════════════════════

@router.get("/mav/{consensus_id}")
async def get_consensus_result(
    consensus_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve consensus results with complete vote trace.
    
    Requirements: FR-API-002
    """
    from sqlalchemy import select
    
    try:
        # Fetch consensus result
        result = await db.execute(
            select(ConsensusResult).where(ConsensusResult.id == consensus_id)
        )
        consensus = result.scalar_one_or_none()
        
        if not consensus:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Consensus {consensus_id} not found"
            )
        
        return {
            "status": "success",
            "data": {
                "consensus_id": consensus.id,
                "claim": consensus.claim,
                "evidence_bundle_id": consensus.evidence_bundle_id,
                "jury_size": consensus.jury_size,
                "status": consensus.status,
                "votes": consensus.votes,
                "consensus_trace": consensus.consensus_trace,
                "final_verdict": consensus.votes.get("final_verdict") if consensus.votes else None,
                "confidence": consensus.votes.get("confidence") if consensus.votes else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve consensus: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════
# Truthful Pause Endpoint
# ═══════════════════════════════════════════════════════════

@router.post("/truthful-pause", response_model=TruthfulPauseResponse)
async def resolve_truthful_pause(
    request: TruthfulPauseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Handle conflict resolution when no majority reached.
    
    Requirements: FR-API-002, FR-SUB-002
    """
    from services.agency.truthful_pause import truthful_pause_service
    
    try:
        # Validate human decision
        valid_decisions = ["accept_verified", "accept_contradicted", "request_more_evidence"]
        if request.human_decision not in valid_decisions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid decision. Must be one of: {', '.join(valid_decisions)}"
            )
        
        result = await truthful_pause_service(
            db=db,
            user_id=current_user.id,
            consensus_id=request.consensus_id,
            human_decision=request.human_decision,
            rationale=request.rationale
        )
        
        return TruthfulPauseResponse(
            status="success",
            data=result["data"]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Truthful pause resolution failed: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════
# B-2: POST /api/v1/consensus/vote — record individual specialist vote
# ═══════════════════════════════════════════════════════════

class VoteRequest(BaseModel):
    """Individual specialist vote for a run/entity (B-2)."""
    run_id: str = Field(..., description="Run UUID")
    entity_id: str = Field(..., description="Target gene_symbol or entity id")
    specialist_role: str = Field(..., description="Specialist role name")
    verdict: str = Field(..., description="verified | contradicted | uncertain")
    score: float = Field(0.5, ge=0.0, le=1.0)
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    reasoning: str = Field("", description="Free-text reasoning")
    key_evidence_cited: List[str] = Field(default_factory=list)


@router.post("/vote")
async def submit_vote(
    body: VoteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role(Role.COLLABORATOR)),
) -> Dict[str, Any]:
    """Record one specialist vote for a run/entity pair.

    Requirements: B-2 (FR-API-002)
    RBAC: COLLABORATOR+
    """
    from services.consensus.mav_service import collect_vote
    from core.audit import log_audit

    if body.verdict not in ("verified", "contradicted", "uncertain"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="verdict must be one of: verified, contradicted, uncertain",
        )

    vote = await collect_vote(
        db=db,
        run_id=body.run_id,
        entity_id=body.entity_id,
        specialist_role=body.specialist_role,
        vote_payload={
            "verdict": body.verdict,
            "score": body.score,
            "confidence": body.confidence,
            "reasoning": body.reasoning,
            "key_evidence_cited": body.key_evidence_cited,
        },
    )
    await db.commit()

    try:
        await log_audit(
            db, user_id=getattr(user, "id", "system"),
            action="consensus.vote",
            resource_type="consensus_votes",
            resource_id=vote.id,
            details={"run_id": body.run_id, "entity_id": body.entity_id,
                     "specialist_role": body.specialist_role, "verdict": body.verdict},
        )
        await db.commit()
    except Exception:
        pass

    return {"status": "ok", "vote_id": vote.id}


# ═══════════════════════════════════════════════════════════
# B-3: GET /api/v1/consensus/{run_id} — full vote trace per run
# ═══════════════════════════════════════════════════════════

@router.get("/{run_id}")
async def get_run_consensus(
    run_id: str,
    entity_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return aggregated MAV vote trace for a run (optionally filtered by entity_id).

    Requirements: B-3 (FR-API-002)
    """
    from services.consensus.mav_service import aggregate_votes

    agg = await aggregate_votes(db=db, run_id=run_id, entity_id=entity_id)
    return {"status": "ok", "data": agg}
