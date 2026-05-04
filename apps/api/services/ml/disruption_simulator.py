"""Disruption modeling simulator for mutation effect prediction."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import structlog
from scipy.integrate import odeint

log = structlog.get_logger()


class PathwayDisruptionSimulator:
    """
    ODE-based pathway simulation engine for modeling mutation effects.
    
    Simulates how genetic mutations disrupt biological pathways by modeling
    pathway dynamics as systems of ordinary differential equations (ODEs).
    """
    
    def __init__(
        self,
        pathway_model: Optional[Dict[str, Any]] = None,
        time_points: int = 100,
        simulation_time: float = 10.0
    ):
        """
        Initialize disruption simulator.
        
        Args:
            pathway_model: Pathway model definition with reactions and parameters
            time_points: Number of time points for simulation
            simulation_time: Total simulation time
        """
        self.pathway_model = pathway_model or {}
        self.time_points = time_points
        self.simulation_time = simulation_time
        self.t = np.linspace(0, simulation_time, time_points)
        
        log.info("disruption_simulator_initialized", time_points=time_points)
    
    def simulate_pathway(
        self,
        initial_conditions: np.ndarray,
        parameters: Dict[str, float],
        mutation_effects: Optional[Dict[str, float]] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Simulate pathway dynamics with optional mutation effects.
        
        Args:
            initial_conditions: Initial concentrations of pathway components
            parameters: Kinetic parameters (rate constants, etc.)
            mutation_effects: Mutation-induced parameter changes
            
        Returns:
            Tuple of (time series data, simulation metadata)
        """
        # Apply mutation effects to parameters
        if mutation_effects:
            parameters = parameters.copy()
            for param, effect in mutation_effects.items():
                if param in parameters:
                    parameters[param] *= effect
        
        # Define ODE system
        def pathway_odes(y, t, params):
            """
            Pathway ODEs representing reaction kinetics.
            
            Example: Simple signaling cascade
            dA/dt = k1 - k2*A*B
            dB/dt = k2*A*B - k3*B
            dC/dt = k3*B - k4*C
            """
            A, B, C = y
            
            k1 = params.get('k1', 1.0)
            k2 = params.get('k2', 0.1)
            k3 = params.get('k3', 0.5)
            k4 = params.get('k4', 0.2)
            
            dA_dt = k1 - k2 * A * B
            dB_dt = k2 * A * B - k3 * B
            dC_dt = k3 * B - k4 * C
            
            return [dA_dt, dB_dt, dC_dt]
        
        # Solve ODEs
        try:
            solution = odeint(pathway_odes, initial_conditions, self.t, args=(parameters,))
            
            metadata = {
                "simulation_time": self.simulation_time,
                "time_points": self.time_points,
                "parameters": parameters,
                "mutation_applied": mutation_effects is not None
            }
            
            log.info("pathway_simulation_complete", mutation_applied=mutation_effects is not None)
            return solution, metadata
            
        except Exception as e:
            log.error("pathway_simulation_failed", error=str(e))
            raise
    
    def compute_disruption_score(
        self,
        wildtype_trajectory: np.ndarray,
        mutant_trajectory: np.ndarray
    ) -> Dict[str, float]:
        """
        Compute disruption scores comparing wildtype and mutant trajectories.
        
        Args:
            wildtype_trajectory: Wildtype pathway dynamics
            mutant_trajectory: Mutant pathway dynamics
            
        Returns:
            Dictionary of disruption metrics
        """
        # Compute various disruption metrics
        
        # 1. Mean absolute deviation
        mad = np.mean(np.abs(mutant_trajectory - wildtype_trajectory))
        
        # 2. Maximum deviation
        max_dev = np.max(np.abs(mutant_trajectory - wildtype_trajectory))
        
        # 3. Steady-state disruption (last 10% of simulation)
        steady_state_idx = int(0.9 * len(self.t))
        wt_steady = np.mean(wildtype_trajectory[steady_state_idx:], axis=0)
        mut_steady = np.mean(mutant_trajectory[steady_state_idx:], axis=0)
        steady_state_disruption = np.linalg.norm(mut_steady - wt_steady)
        
        # 4. Temporal disruption (area between curves)
        temporal_disruption = np.trapz(
            np.linalg.norm(mutant_trajectory - wildtype_trajectory, axis=1),
            self.t
        )
        
        # 5. Overall disruption score (normalized)
        overall_score = (mad + max_dev + steady_state_disruption) / 3.0
        
        return {
            "mean_absolute_deviation": float(mad),
            "maximum_deviation": float(max_dev),
            "steady_state_disruption": float(steady_state_disruption),
            "temporal_disruption": float(temporal_disruption),
            "overall_disruption_score": float(overall_score)
        }
    
    def simulate_mutation_effect(
        self,
        mutation_id: str,
        gene_symbol: str,
        mutation_type: str,
        initial_conditions: np.ndarray,
        parameters: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Simulate the effect of a specific mutation on pathway dynamics.
        
        Args:
            mutation_id: Mutation identifier
            gene_symbol: Gene affected by mutation
            mutation_type: Type of mutation (missense, nonsense, etc.)
            initial_conditions: Initial pathway state
            parameters: Baseline kinetic parameters
            
        Returns:
            Simulation results with disruption analysis
        """
        # Define mutation effects based on type
        mutation_effects = self._get_mutation_effects(mutation_type, gene_symbol)
        
        # Simulate wildtype
        wt_trajectory, wt_meta = self.simulate_pathway(
            initial_conditions, parameters, mutation_effects=None
        )
        
        # Simulate mutant
        mut_trajectory, mut_meta = self.simulate_pathway(
            initial_conditions, parameters, mutation_effects=mutation_effects
        )
        
        # Compute disruption scores
        disruption_scores = self.compute_disruption_score(wt_trajectory, mut_trajectory)
        
        # Analyze affected pathways
        affected_pathways = self._identify_affected_pathways(
            wt_trajectory, mut_trajectory, disruption_scores
        )
        
        return {
            "mutation_id": mutation_id,
            "gene_symbol": gene_symbol,
            "mutation_type": mutation_type,
            "wildtype_trajectory": wt_trajectory.tolist(),
            "mutant_trajectory": mut_trajectory.tolist(),
            "time_points": self.t.tolist(),
            "disruption_scores": disruption_scores,
            "affected_pathways": affected_pathways,
            "mutation_effects": mutation_effects
        }
    
    def _get_mutation_effects(
        self,
        mutation_type: str,
        gene_symbol: str
    ) -> Dict[str, float]:
        """
        Determine parameter changes based on mutation type.
        
        Args:
            mutation_type: Type of mutation
            gene_symbol: Affected gene
            
        Returns:
            Dictionary of parameter multipliers
        """
        effects = {}
        
        if mutation_type == "loss_of_function":
            # Reduce activity parameters
            effects = {"k2": 0.1, "k3": 0.1}
        elif mutation_type == "gain_of_function":
            # Increase activity parameters
            effects = {"k2": 2.0, "k3": 2.0}
        elif mutation_type == "missense":
            # Moderate effect
            effects = {"k2": 0.5, "k3": 0.7}
        elif mutation_type == "nonsense":
            # Severe loss of function
            effects = {"k2": 0.01, "k3": 0.01}
        else:
            # Default: mild effect
            effects = {"k2": 0.8, "k3": 0.8}
        
        return effects
    
    def _identify_affected_pathways(
        self,
        wt_trajectory: np.ndarray,
        mut_trajectory: np.ndarray,
        disruption_scores: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        Identify which pathways are most affected by the mutation.
        
        Args:
            wt_trajectory: Wildtype dynamics
            mut_trajectory: Mutant dynamics
            disruption_scores: Computed disruption metrics
            
        Returns:
            List of affected pathways with severity scores
        """
        affected = []
        
        # Analyze each pathway component
        num_components = wt_trajectory.shape[1]
        component_names = ["Component_A", "Component_B", "Component_C"][:num_components]
        
        for i, name in enumerate(component_names):
            component_disruption = np.mean(np.abs(
                mut_trajectory[:, i] - wt_trajectory[:, i]
            ))
            
            if component_disruption > 0.1:  # Threshold for significance
                affected.append({
                    "pathway_component": name,
                    "disruption_magnitude": float(component_disruption),
                    "severity": "high" if component_disruption > 0.5 else "moderate"
                })
        
        return affected
    
    def simulate_transcriptional_impact(
        self,
        mutation_id: str,
        target_genes: List[str],
        baseline_expression: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Simulate transcriptional regulation changes due to mutation.
        
        Args:
            mutation_id: Mutation identifier
            target_genes: List of genes regulated by mutated factor
            baseline_expression: Baseline expression levels
            
        Returns:
            Predicted expression changes
        """
        expression_changes = {}
        
        for gene in target_genes:
            baseline = baseline_expression.get(gene, 1.0)
            
            # Simulate expression change (simplified model)
            fold_change = np.random.lognormal(0, 0.5)  # Log-normal distribution
            new_expression = baseline * fold_change
            
            expression_changes[gene] = {
                "baseline_expression": baseline,
                "predicted_expression": new_expression,
                "fold_change": fold_change,
                "log2_fold_change": np.log2(fold_change)
            }
        
        return {
            "mutation_id": mutation_id,
            "num_target_genes": len(target_genes),
            "expression_changes": expression_changes
        }
    
    def simulate_immune_dysregulation(
        self,
        mutation_id: str,
        immune_components: List[str]
    ) -> Dict[str, Any]:
        """
        Simulate immune system dysregulation due to mutation.
        
        Args:
            mutation_id: Mutation identifier
            immune_components: List of immune system components
            
        Returns:
            Predicted immune dysregulation effects
        """
        dysregulation_effects = {}
        
        for component in immune_components:
            # Simulate dysregulation (simplified model)
            dysregulation_score = np.random.beta(2, 5)  # Beta distribution
            
            dysregulation_effects[component] = {
                "dysregulation_score": float(dysregulation_score),
                "severity": "high" if dysregulation_score > 0.7 else "moderate" if dysregulation_score > 0.4 else "low",
                "predicted_impact": "increased_inflammation" if dysregulation_score > 0.6 else "normal"
            }
        
        return {
            "mutation_id": mutation_id,
            "num_immune_components": len(immune_components),
            "dysregulation_effects": dysregulation_effects,
            "overall_immune_impact": np.mean([e["dysregulation_score"] for e in dysregulation_effects.values()])
        }
