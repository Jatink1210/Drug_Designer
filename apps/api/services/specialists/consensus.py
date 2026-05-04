"""Specialist Workflow Engine — Consensus Orchestrator (§40.3).

Coordinates multi-agent voting for high-risk scientific claims.
Spawns parallel specialists, collects votes, applies majority/unanimous rules.
"""

import asyncio
import json
import uuid
import structlog
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

log = structlog.get_logger(__name__)


class ConsensusVote(BaseModel):
    agent_id: str
    verdict: str  # 'support', 'refute', 'uncertain'
    confidence: float
    rationale: str


class ConsensusResult(BaseModel):
    claim_id: str
    status: str  # 'verified', 'canonical', 'conflict'
    votes: List[ConsensusVote]
    consensus_met: bool


class ConsensusOrchestrator:
    """Spawns parallel specialists to evaluate high-risk claims (§40.3)."""

    def __init__(self, engine: Any):
        self.engine = engine

    async def _invoke_agent(self, agent_type: str, claim: str, evidence: List[Any]) -> ConsensusVote:
        """Invoke a specialist via the engine and parse vote from response."""
        context = {
            "claim": claim,
            "evidence": evidence[:10],  # limit evidence items
            "task": "Evaluate whether the evidence supports or refutes this claim. "
                    "Respond with JSON: {\"verdict\": \"support|refute|uncertain\", "
                    "\"confidence\": 0.0-1.0, \"rationale\": \"...\"}",
        }

        try:
            result = await self.engine.invoke(
                role_id=agent_type,
                context=context,
                runtime_mode="hosted",
            )

            output = result.get("output", {})

            # Parse structured output
            if isinstance(output, dict):
                verdict = output.get("verdict", "uncertain")
                confidence = float(output.get("confidence", 0.5))
                rationale = output.get("rationale", "No rationale provided")
            elif isinstance(output, str):
                try:
                    parsed = json.loads(output)
                    verdict = parsed.get("verdict", "uncertain")
                    confidence = float(parsed.get("confidence", 0.5))
                    rationale = parsed.get("rationale", output[:200])
                except (json.JSONDecodeError, TypeError):
                    # Heuristic: look for keywords
                    lower = output.lower()
                    if "support" in lower:
                        verdict = "support"
                    elif "refute" in lower or "contradict" in lower:
                        verdict = "refute"
                    else:
                        verdict = "uncertain"
                    confidence = 0.6
                    rationale = output[:200]
            else:
                verdict = "uncertain"
                confidence = 0.5
                rationale = "Could not parse specialist output"

            # Clamp confidence
            confidence = max(0.0, min(1.0, confidence))

        except Exception as exc:
            log.warning("consensus.agent_failed", agent=agent_type, error=str(exc))
            verdict = "uncertain"
            confidence = 0.3
            rationale = f"Agent {agent_type} failed: {str(exc)[:100]}"

        return ConsensusVote(
            agent_id=f"{agent_type}",
            verdict=verdict,
            confidence=round(confidence, 4),
            rationale=rationale,
        )

    def _check_majority(self, votes: List[str]) -> bool:
        supp = sum(1 for v in votes if v == "support")
        return supp > len(votes) / 2

    def _check_unanimous(self, votes: List[str]) -> bool:
        return all(v == "support" for v in votes)

    async def evaluate_claim(
        self, claim: str, evidence: List[Any], mode: str = "majority"
    ) -> ConsensusResult:
        """Multi-agent claim evaluation (§40.3).

        1. Spawn 3 specialist instances in parallel  
        2. Collect ConsensusVote from each  
        3. Apply majority/unanimous logic  
        4. If conflict → trigger Truthful Pause for human arbitration
        """
        log.info("evaluating_consensus", claim=claim[:50], mode=mode)
        claim_id = str(uuid.uuid4())[:12]

        agents = ["lit_searcher", "graph_reasoner", "auditor"]
        tasks = [self._invoke_agent(agent, claim, evidence) for agent in agents]

        results = await asyncio.gather(*tasks)

        verdicts = [r.verdict for r in results]
        log.info("votes_collected", claim_id=claim_id, votes=verdicts)

        if mode == "majority" and self._check_majority(verdicts):
            status = "verified"
            consensus_met = True
        elif mode == "unanimous" and self._check_unanimous(verdicts):
            status = "canonical"
            consensus_met = True
        else:
            status = "conflict"
            consensus_met = False

        return ConsensusResult(
            claim_id=claim_id,
            status=status,
            votes=results,
            consensus_met=consensus_met,
        )
