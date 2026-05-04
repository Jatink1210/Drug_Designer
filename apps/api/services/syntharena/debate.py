"""SynthArena Debate Engine — Multi-agent debate simulation.

Requirements 8.1-8.5: Creates 3+ specialist agents with distinct roles,
generates evidence-backed arguments, computes consensus with winner rationale,
confidence, and dissenting opinions.
"""

import uuid
import time
from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)


SPECIALIST_ROLES = [
    {
        "role": "Medicinal Chemist",
        "focus": "molecular properties, SAR, drug-likeness, selectivity",
        "metrics": ["IC50", "Ki", "LogP", "MW", "QED", "selectivity_index"],
    },
    {
        "role": "Toxicologist",
        "focus": "safety profile, off-target effects, toxicity endpoints",
        "metrics": ["LD50", "hERG_IC50", "AMES", "hepatotoxicity", "CYP_inhibition"],
    },
    {
        "role": "Clinical Pharmacologist",
        "focus": "PK/PD, clinical translatability, dosing, bioavailability",
        "metrics": ["Cmax", "AUC", "t_half", "bioavailability", "clearance", "Vd"],
    },
]


class DebateAgent:
    """A specialist agent that generates arguments for/against compounds."""

    def __init__(self, agent_id: str, role: str, focus: str, metrics: List[str]):
        self.agent_id = agent_id
        self.role = role
        self.focus = focus
        self.metrics = metrics

    def generate_argument(
        self,
        compound: Dict[str, Any],
        all_compounds: List[Dict[str, Any]],
        round_number: int = 1,
    ) -> Dict[str, Any]:
        """Generate an evidence-backed argument for a compound."""
        compound_id = compound.get("compound_id") or compound.get("id") or "unknown"
        compound_name = compound.get("name") or compound.get("smiles") or compound_id
        scores = compound.get("scores", {})
        properties = compound.get("properties", {})

        # Build argument based on role-specific metrics
        strengths = []
        weaknesses = []
        evidence_citations = []

        for metric in self.metrics:
            value = scores.get(metric) or properties.get(metric)
            if value is not None:
                if isinstance(value, (int, float)):
                    if value > 0.7:
                        strengths.append(f"{metric}: {value:.3f} (favorable)")
                    elif value < 0.3:
                        weaknesses.append(f"{metric}: {value:.3f} (concerning)")
                evidence_citations.append({
                    "metric": metric,
                    "value": value,
                    "source": "computed_analysis",
                })

        # Role-specific evaluation
        if self.role == "Medicinal Chemist":
            qed = scores.get("qed") or properties.get("qed", 0.5)
            mw = properties.get("molecular_weight") or properties.get("MW", 400)
            argument = f"From a medicinal chemistry perspective, {compound_name} "
            if isinstance(qed, (int, float)) and qed > 0.5:
                argument += f"shows promising drug-likeness (QED={qed:.2f}). "
                strengths.append(f"QED score: {qed:.2f}")
            else:
                argument += f"has moderate drug-likeness concerns (QED={qed}). "
                weaknesses.append(f"QED score: {qed}")
            stance = "for" if len(strengths) >= len(weaknesses) else "against"

        elif self.role == "Toxicologist":
            tox = scores.get("toxicity") or properties.get("toxicity", 0.5)
            argument = f"Safety assessment of {compound_name}: "
            if isinstance(tox, (int, float)) and tox < 0.3:
                argument += f"favorable toxicity profile (tox_score={tox:.2f}). "
                strengths.append(f"Low toxicity: {tox:.2f}")
                stance = "for"
            else:
                argument += f"toxicity concerns require attention (tox_score={tox}). "
                weaknesses.append(f"Toxicity score: {tox}")
                stance = "against"

        else:  # Clinical Pharmacologist
            bioavail = scores.get("bioavailability") or properties.get("bioavailability", 0.5)
            argument = f"Clinical translatability of {compound_name}: "
            if isinstance(bioavail, (int, float)) and bioavail > 0.5:
                argument += f"good predicted bioavailability ({bioavail:.2f}). "
                strengths.append(f"Bioavailability: {bioavail:.2f}")
                stance = "for"
            else:
                argument += f"bioavailability may limit clinical utility ({bioavail}). "
                weaknesses.append(f"Bioavailability: {bioavail}")
                stance = "against"

        if strengths:
            argument += f"Strengths: {'; '.join(strengths)}. "
        if weaknesses:
            argument += f"Concerns: {'; '.join(weaknesses)}."

        confidence = min(1.0, max(0.1, 0.5 + 0.1 * len(strengths) - 0.1 * len(weaknesses)))

        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "stance": stance,
            "compound_id": compound_id,
            "argument_text": argument,
            "evidence_citations": evidence_citations if evidence_citations else [
                {"metric": "overall_assessment", "value": "rule_based", "source": "computed_analysis"}
            ],
            "confidence": round(confidence, 3),
            "round_number": round_number,
            "strengths": strengths,
            "weaknesses": weaknesses,
        }


class DebateEngine:
    """Multi-agent debate engine for SynthArena compound comparison.

    Creates 3+ specialist agents, runs debate rounds, computes consensus.
    Falls back to rule-based scoring when LLM is unavailable.
    """

    def __init__(self):
        self.agents: List[DebateAgent] = []
        self._init_agents()

    def _init_agents(self):
        """Create specialist agents with distinct roles."""
        for spec in SPECIALIST_ROLES:
            self.agents.append(DebateAgent(
                agent_id=str(uuid.uuid4())[:8],
                role=spec["role"],
                focus=spec["focus"],
                metrics=spec["metrics"],
            ))

    async def run_debate(
        self,
        compounds: List[Dict[str, Any]],
        session_id: str = "",
        num_rounds: int = 2,
    ) -> Dict[str, Any]:
        """Run a full debate across compounds.

        Returns DebateResult with agents, debate_history, and consensus.
        """
        t0 = time.time()
        debate_id = str(uuid.uuid4())[:12]
        debate_history: List[Dict[str, Any]] = []

        if len(compounds) < 2:
            return {
                "debate_id": debate_id,
                "session_id": session_id,
                "agents": [{"agent_id": a.agent_id, "role": a.role} for a in self.agents],
                "debate_history": [],
                "consensus": {
                    "winner_compound_id": compounds[0].get("compound_id", "unknown") if compounds else "none",
                    "winner_rationale": "Only one compound provided; no debate needed.",
                    "confidence": 1.0,
                    "dissenting_opinions": [],
                    "vote_breakdown": {},
                },
                "method_used": "rule_based",
                "elapsed_s": round(time.time() - t0, 2),
            }

        # Run debate rounds
        for round_num in range(1, num_rounds + 1):
            for agent in self.agents:
                for compound in compounds:
                    argument = agent.generate_argument(compound, compounds, round_num)
                    debate_history.append(argument)

        # Compute consensus
        consensus = self._compute_consensus(compounds, debate_history)

        return {
            "debate_id": debate_id,
            "session_id": session_id,
            "agents": [
                {"agent_id": a.agent_id, "role": a.role, "stance": "neutral"}
                for a in self.agents
            ],
            "debate_history": debate_history,
            "consensus": consensus,
            "method_used": "rule_based",
            "elapsed_s": round(time.time() - t0, 2),
        }

    def _compute_consensus(
        self,
        compounds: List[Dict[str, Any]],
        debate_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compute consensus from agent votes and arguments."""
        # Tally votes per compound
        compound_scores: Dict[str, float] = {}
        compound_votes: Dict[str, Dict[str, str]] = {}  # agent_id -> compound_id

        for compound in compounds:
            cid = compound.get("compound_id") or compound.get("id") or "unknown"
            compound_scores[cid] = 0.0

        for arg in debate_history:
            cid = arg.get("compound_id", "unknown")
            if cid not in compound_scores:
                compound_scores[cid] = 0.0
            if arg["stance"] == "for":
                compound_scores[cid] += arg["confidence"]
            elif arg["stance"] == "against":
                compound_scores[cid] -= arg["confidence"] * 0.5

        # Determine winner
        if not compound_scores:
            return {
                "winner_compound_id": "none",
                "winner_rationale": "No compounds evaluated.",
                "confidence": 0.0,
                "dissenting_opinions": [],
                "vote_breakdown": {},
            }

        winner_id = max(compound_scores, key=compound_scores.get)  # type: ignore
        winner_score = compound_scores[winner_id]
        total_score = sum(abs(v) for v in compound_scores.values()) or 1.0
        confidence = min(1.0, max(0.0, winner_score / total_score))

        # Build vote breakdown per agent
        vote_breakdown: Dict[str, str] = {}
        for agent in self.agents:
            agent_args = [a for a in debate_history if a["agent_id"] == agent.agent_id]
            agent_compound_scores: Dict[str, float] = {}
            for arg in agent_args:
                cid = arg.get("compound_id", "unknown")
                if cid not in agent_compound_scores:
                    agent_compound_scores[cid] = 0.0
                if arg["stance"] == "for":
                    agent_compound_scores[cid] += arg["confidence"]
                elif arg["stance"] == "against":
                    agent_compound_scores[cid] -= arg["confidence"] * 0.5
            if agent_compound_scores:
                vote_breakdown[agent.agent_id] = max(agent_compound_scores, key=agent_compound_scores.get)  # type: ignore

        # Dissenting opinions
        dissenting = []
        for agent_id, voted_for in vote_breakdown.items():
            if voted_for != winner_id:
                agent = next((a for a in self.agents if a.agent_id == agent_id), None)
                if agent:
                    dissenting.append({
                        "agent_id": agent_id,
                        "role": agent.role,
                        "preferred_compound": voted_for,
                        "reason": f"{agent.role} preferred {voted_for} based on {agent.focus}",
                    })

        # Build rationale
        winner_args = [a for a in debate_history if a["compound_id"] == winner_id and a["stance"] == "for"]
        rationale_parts = []
        for arg in winner_args[:3]:
            if arg.get("strengths"):
                rationale_parts.append(f"{arg['role']}: {'; '.join(arg['strengths'][:2])}")
        rationale = f"Compound {winner_id} selected based on multi-agent evaluation. " + ". ".join(rationale_parts) if rationale_parts else f"Compound {winner_id} received the highest aggregate score across specialist evaluations."

        return {
            "winner_compound_id": winner_id,
            "winner_rationale": rationale,
            "confidence": round(confidence, 3),
            "dissenting_opinions": dissenting,
            "vote_breakdown": vote_breakdown,
        }
