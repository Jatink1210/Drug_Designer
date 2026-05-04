"""MAV Consensus Service — collect and aggregate specialist votes per run/entity.

B-1: collect_vote() → writes individual rows to consensus_votes table.
     aggregate_votes() → computes mean score, confidence, minority dissent.

FR-API-002, FR-SUB-002.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.db_tables import ConsensusVote


# ────────────────────────────────────────────────────────────────────────────
# B-1a: collect_vote
# ────────────────────────────────────────────────────────────────────────────

async def collect_vote(
    db: AsyncSession,
    run_id: str,
    entity_id: str,
    specialist_role: str,
    vote_payload: Dict[str, Any],
) -> ConsensusVote:
    """Write one specialist vote to consensus_votes.

    vote_payload must include at least:
      - verdict: "verified" | "contradicted" | "uncertain"
      - score:   float 0-1
      - confidence: float 0-1
      - reasoning: str
    """
    vote = ConsensusVote(
        id=str(uuid.uuid4()),
        run_id=run_id,
        entity_id=entity_id,
        specialist_role=specialist_role,
        vote={
            "verdict": vote_payload.get("verdict", "uncertain"),
            "score": float(vote_payload.get("score", 0.5)),
            "confidence": float(vote_payload.get("confidence", 0.5)),
            "reasoning": str(vote_payload.get("reasoning", "")),
            "key_evidence_cited": vote_payload.get("key_evidence_cited", []),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    db.add(vote)
    await db.flush()  # make row available in same transaction
    return vote


# ────────────────────────────────────────────────────────────────────────────
# B-1b: aggregate_votes
# ────────────────────────────────────────────────────────────────────────────

async def aggregate_votes(
    db: AsyncSession,
    run_id: str,
    entity_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Aggregate all votes for a run (optionally filtered by entity_id).

    Returns:
        {
          "run_id":          str,
          "entity_id":       str | None,
          "vote_count":      int,
          "mean_score":      float,
          "mean_confidence": float,
          "verdict":         "verified" | "contradicted" | "uncertain" | "conflict",
          "consensus_met":   bool,
          "minority_dissent": [vote_dicts] (votes that disagree with majority),
          "full_trace":      [vote_dicts],
        }
    """
    stmt = select(ConsensusVote).where(ConsensusVote.run_id == run_id)
    if entity_id:
        stmt = stmt.where(ConsensusVote.entity_id == entity_id)
    result = await db.execute(stmt)
    rows: List[ConsensusVote] = result.scalars().all()

    if not rows:
        return {
            "run_id": run_id,
            "entity_id": entity_id,
            "vote_count": 0,
            "mean_score": 0.0,
            "mean_confidence": 0.0,
            "verdict": "no_votes",
            "consensus_met": False,
            "minority_dissent": [],
            "full_trace": [],
        }

    vote_dicts = [row.vote for row in rows]
    scores = [v.get("score", 0.5) for v in vote_dicts]
    confidences = [v.get("confidence", 0.5) for v in vote_dicts]
    verdicts = [v.get("verdict", "uncertain") for v in vote_dicts]

    mean_score = sum(scores) / len(scores)
    mean_confidence = sum(confidences) / len(confidences)

    # Majority vote (simple plurality)
    counts = {"verified": 0, "contradicted": 0, "uncertain": 0}
    for v in verdicts:
        counts[v if v in counts else "uncertain"] += 1

    majority = max(counts, key=counts.__getitem__)
    majority_threshold = len(rows) // 2 + 1
    consensus_met = counts[majority] >= majority_threshold

    if not consensus_met:
        majority = "conflict"

    # Minority dissent: votes that differ from majority verdict
    minority_dissent = []
    if consensus_met and majority != "conflict":
        minority_dissent = [
            {"specialist_role": rows[i].specialist_role, "vote": vote_dicts[i]}
            for i, v in enumerate(verdicts)
            if v != majority
        ]

    full_trace = [
        {
            "id": row.id,
            "specialist_role": row.specialist_role,
            "entity_id": row.entity_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            **row.vote,
        }
        for row in rows
    ]

    return {
        "run_id": run_id,
        "entity_id": entity_id,
        "vote_count": len(rows),
        "mean_score": round(mean_score, 4),
        "mean_confidence": round(mean_confidence, 4),
        "verdict": majority,
        "consensus_met": consensus_met,
        "verdict_counts": counts,
        "minority_dissent": minority_dissent,
        "full_trace": full_trace,
    }
