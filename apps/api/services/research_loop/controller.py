"""Research Loop Controller (Drug Designer §42.1).

Runs iterative generate → evaluate → learn cycles for:
  - Molecule optimization (PPO-based, §84)
  - Target scoring refinement
  - ADMET threshold tuning
  - Graph hypothesis testing

Each iteration logs its state and can be paused/resumed.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import structlog

log = structlog.get_logger()


class ResearchLoopConfig:
    """Configuration for a research loop run."""

    def __init__(
        self,
        max_iterations: int = 50,
        convergence_threshold: float = 0.01,
        early_stop_patience: int = 5,
        objective: str = "maximize",  # maximize | minimize
    ):
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold
        self.early_stop_patience = early_stop_patience
        self.objective = objective


class ResearchLoopController:
    """Controls iterative scientific research loops.

    Usage:
        controller = ResearchLoopController(run_manager=run_manager)
        result = await controller.run_loop(
            config=ResearchLoopConfig(max_iterations=50),
            generator=molecule_generator_fn,
            evaluator=admet_evaluator_fn,
            updater=weight_update_fn,
        )
    """

    def __init__(self, run_manager=None):
        self._run_manager = run_manager

    async def run_loop(
        self,
        config: ResearchLoopConfig,
        generator: Callable,
        evaluator: Callable,
        updater: Optional[Callable] = None,
        project_id: str = "",
    ) -> Dict[str, Any]:
        """Execute one research loop.

        Each iteration:
        1. GENERATE: Create candidate (molecule, hypothesis, etc.)
        2. EVALUATE: Score against objective (ADMET, docking, etc.)
        3. LEARN: Update weights/parameters based on evaluation
        4. LOG: Emit progress event
        """
        log.info(
            "research_loop.start",
            max_iterations=config.max_iterations,
            objective=config.objective,
        )

        best_score = float("-inf") if config.objective == "maximize" else float("inf")
        best_candidate = None
        no_improvement_count = 0
        history: List[Dict[str, Any]] = []

        for iteration in range(config.max_iterations):
            # Step 1: Generate candidate
            candidate = await generator(iteration=iteration, history=history)

            # Step 2: Evaluate
            score = await evaluator(candidate=candidate)

            # Step 3: Check improvement
            improved = (
                (config.objective == "maximize" and score > best_score)
                or (config.objective == "minimize" and score < best_score)
            )

            if improved:
                best_score = score
                best_candidate = candidate
                no_improvement_count = 0
            else:
                no_improvement_count += 1

            # Step 4: Update weights (if updater provided)
            if updater is not None:
                await updater(candidate=candidate, score=score, iteration=iteration)

            history.append({
                "iteration": iteration,
                "score": score,
                "improved": improved,
            })

            # Emit progress
            if self._run_manager:
                await self._run_manager.emit_progress(
                    run_id=project_id,
                    stage="research_loop",
                    progress_pct=int((iteration + 1) / config.max_iterations * 100),
                    message=f"Iteration {iteration + 1}/{config.max_iterations}, best={best_score:.4f}",
                )

            # Early stopping
            if no_improvement_count >= config.early_stop_patience:
                log.info(
                    "research_loop.early_stop",
                    iteration=iteration,
                    best_score=best_score,
                )
                break

            # Convergence check
            if len(history) >= 2:
                delta = abs(history[-1]["score"] - history[-2]["score"])
                if delta < config.convergence_threshold:
                    log.info(
                        "research_loop.converged",
                        iteration=iteration,
                        delta=delta,
                    )
                    break

        log.info(
            "research_loop.complete",
            iterations=len(history),
            best_score=best_score,
        )

        return {
            "best_score": best_score,
            "best_candidate": best_candidate,
            "iterations_completed": len(history),
            "history": history,
        }
