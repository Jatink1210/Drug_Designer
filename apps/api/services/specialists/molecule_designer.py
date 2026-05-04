"""G-5: Molecule Designer specialist.

Generates candidate SMILES from a target + ADMET constraints
using the PPO optimization loop.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)


class MoleculeDesignerSpecialist:
    """Specialist: generates and optimises molecule candidates via PPO.

    Wraps `services.ml.ppo_optimizer.PPOOptimizer` and returns candidate SMILES
    with predicted ADMET profiles.
    """

    ROLE_ID = "molecule_designer"

    def __init__(self, engine: Optional[Any] = None) -> None:
        self.engine = engine
        log.info("molecule_designer_initialized")

    async def design(
        self,
        target_id: str,
        target_symbol: str = "",
        constraints: Optional[Dict[str, Any]] = None,
        n_candidates: int = 10,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate candidate molecules for a target.

        Args:
            target_id: Target identifier
            target_symbol: Human-readable symbol
            constraints: ADMET constraints dict (e.g. {"mw_max": 500, "logp_max": 5})
            n_candidates: Number of candidates to generate
            run_id: Optional run ID for progress reporting

        Returns:
            Dict with candidates, admet_scores, optimization_steps, specialist
        """
        constraints = constraints or {}
        candidates = await self._generate_candidates(
            target_id, target_symbol, constraints, n_candidates, run_id
        )

        return {
            "status": "ok",
            "target_id": target_id,
            "target_symbol": target_symbol,
            "candidates": candidates,
            "n_generated": len(candidates),
            "constraints_applied": constraints,
            "specialist": self.ROLE_ID,
        }

    async def _generate_candidates(
        self,
        target_id: str,
        target_symbol: str,
        constraints: Dict[str, Any],
        n_candidates: int,
        run_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Run PPO loop to generate candidates."""
        try:
            from services.ml.ppo_optimizer import PPOOptimizer

            optimizer = PPOOptimizer()
            result = await optimizer.optimize(
                target_id=target_id,
                constraints=constraints,
                n_steps=constraints.get("ppo_steps", 50),
                n_candidates=n_candidates,
            )
            return result.get("candidates", [])
        except Exception as exc:
            log.warning("molecule_designer_ppo_failed", target=target_id, error=str(exc))
            # Fallback: deterministic template-based generation
            return self._template_candidates(target_symbol, n_candidates)

    def _template_candidates(
        self, target_symbol: str, n: int
    ) -> List[Dict[str, Any]]:
        """Return placeholder candidates when PPO is unavailable."""
        templates = [
            "CC(=O)Nc1ccc(O)cc1",   # paracetamol scaffold
            "c1ccc(cc1)C(=O)O",      # benzoic acid scaffold
            "CC(C)Cc1ccc(cc1)C(C)C(=O)O",  # ibuprofen scaffold
        ]
        return [
            {
                "smiles": templates[i % len(templates)],
                "mol_weight": None,
                "qed": None,
                "sa_score": None,
                "status": "template",
                "note": "PPO optimizer not available — template scaffold",
                "target_symbol": target_symbol,
            }
            for i in range(min(n, 3))
        ]
