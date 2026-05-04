"""Truthful Pause Service

This service handles conflict resolution when MAV consensus cannot reach a majority.
Implements the "truthful pause" mechanism where human experts make final decisions.

Requirements: FR-API-002, FR-SUB-002
"""

from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.db_tables import ConsensusResult
from core.audit import log_audit


async def truthful_pause_service(
    db: AsyncSession,
    user_id: str,
    consensus_id: str,
    human_decision: str,
    rationale: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resolve consensus conflict with human decision.
    
    When MAV consensus reaches a conflict state (no majority), this service
    allows a human expert to make the final decision and update the consensus.
    
    Args:
        db: Database session
        user_id: User ID making the decision
        consensus_id: Consensus result UUID
        human_decision: Human decision (accept_verified | accept_contradicted | request_more_evidence)
        rationale: Optional rationale for the decision
    
    Returns:
        Dictionary with updated consensus data
    """
    try:
        # Fetch consensus result
        result = await db.execute(
            select(ConsensusResult).where(ConsensusResult.id == consensus_id)
        )
        consensus = result.scalar_one_or_none()
        
        if not consensus:
            raise Exception(f"Consensus {consensus_id} not found")
        
        # Verify consensus is in conflict state
        if consensus.status != "conflict":
            raise Exception(f"Consensus {consensus_id} is not in conflict state (status: {consensus.status})")
        
        # Update consensus based on human decision
        if human_decision == "accept_verified":
            new_status = "verified"
            final_verdict = "verified"
        elif human_decision == "accept_contradicted":
            new_status = "contradicted"
            final_verdict = "contradicted"
        elif human_decision == "request_more_evidence":
            new_status = "pending_evidence"
            final_verdict = "insufficient_evidence"
        else:
            raise Exception(f"Invalid human decision: {human_decision}")
        
        # Update consensus record
        resolved_at = datetime.utcnow().isoformat()
        consensus.status = new_status
        
        # Update votes dictionary
        votes = consensus.votes.copy() if consensus.votes else {}
        votes["final_verdict"] = final_verdict
        votes["human_override"] = True
        votes["human_decision"] = human_decision
        votes["human_rationale"] = rationale
        votes["resolved_by"] = user_id
        votes["resolved_at"] = resolved_at
        consensus.votes = votes
        
        # Update consensus trace
        trace = consensus.consensus_trace.copy() if consensus.consensus_trace else {}
        trace["truthful_pause_resolution"] = {
            "human_decision": human_decision,
            "rationale": rationale,
            "resolved_by": user_id,
            "resolved_at": resolved_at,
            "original_status": "conflict",
            "new_status": new_status
        }
        consensus.consensus_trace = trace
        
        await db.commit()
        await db.refresh(consensus)
        
        # Log audit event
        await log_audit(
            session=db,
            user_id=user_id,
            action="consensus.truthful_pause",
            resource_type="consensus_results",
            resource_id=consensus_id,
            details={
                "human_decision": human_decision,
                "rationale": rationale,
                "original_status": "conflict",
                "new_status": new_status
            }
        )
        
        return {
            "data": {
                "consensus_id": consensus.id,
                "claim": consensus.claim,
                "original_status": "conflict",
                "new_status": new_status,
                "final_verdict": final_verdict,
                "human_decision": human_decision,
                "rationale": rationale,
                "resolved_by": user_id,
                "resolved_at": resolved_at,
                "complete_audit_trail": {
                    "original_votes": consensus.consensus_trace.get("votes", []) if consensus.consensus_trace else [],
                    "vote_summary": consensus.consensus_trace.get("vote_summary", {}) if consensus.consensus_trace else {},
                    "truthful_pause_resolution": consensus.consensus_trace.get("truthful_pause_resolution", {}) if consensus.consensus_trace else {}
                }
            }
        }
        
    except Exception as e:
        raise Exception(f"Truthful pause resolution failed: {str(e)}")
