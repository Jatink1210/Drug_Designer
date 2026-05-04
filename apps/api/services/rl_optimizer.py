"""Reinforcement Learning (RL) Optimization Modules (§84).

Provides:
1. PPO molecule optimization with GNN policy network (§84.2)
2. Bioisosteric replacements + ADMET scoring (baseline)
3. Retrosynthesis planning via reaction templates (§85)
4. Ontology design via graph analysis (§82.4)

Reward function (§84.2):
  R = w1×binding + w2×QED + w3×SA + w4×(1-toxicity) + w5×novelty - w6×penalty(MW>500)
"""
from __future__ import annotations

import hashlib
import logging
import math
from typing import Any, Dict, List, Optional, Tuple
import structlog
from pydantic import BaseModel, Field

from services.dl_models import DLModelService, RDKIT_AVAILABLE

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import numpy as np
    NP_AVAILABLE = True
except ImportError:
    NP_AVAILABLE = False

logger = structlog.get_logger(__name__)
log = logging.getLogger(__name__)

# List of SMARTS patterns representing restricted/illicit substance target logic.
# A full production system should use rigorous functional group parsing.
RESTRICTED_SUBSTRUCTS = [
    "C1C(C2=CC=CC=C2)C3C(C1)C4C3C5C4C5", # Synthetic dummy mask for illicit mapping
    "NC(C)Cc1ccccc1"                       # Amphetamine core (aromatic ring)
]

# ── Bioisosteric replacement pairs (pattern SMARTS → replacement SMILES) ──
# Each tuple: (name, query_smarts, replacement_smarts)
BIOISOSTERE_PAIRS: List[tuple] = [
    ("COOH_to_tetrazole", "[CX3](=O)[OX2H1]", "c1nn[nH]n1"),
    ("phenyl_to_pyridine", "c1ccccc1", "c1ccncc1"),
    ("amide_to_sulfonamide", "[NX3H1][CX3](=O)", "NS(=O)=O"),
    ("ester_to_amide", "[CX3](=O)[OX2][#6]", "[CX3](=O)[NX3H1][#6]"),
    ("OH_to_NH2", "[OX2H1]", "[NH2]"),
]

# ── PAINS (Pan-Assay Interference) filter SMARTS ──
PAINS_SMARTS = [
    "[#6]1:[#6]:[#6](:[#6]:[#6]:[#6]:1)-[#7]=[#7]-[#6]2:[#6]:[#6]:[#6]:[#6]:[#6]:2",  # azo compounds
    "[$([#6]=[#6]-[#6]=[OX1]),$([#6]=[#6]-[#6]=[SX1])]",  # Michael acceptors (partial)
]

# ── Retrosynthetic reaction templates (product → reactants) ──
# Each: (name, forward_smarts, description, confidence)
RETRO_TEMPLATES: List[tuple] = [
    ("Amide bond formation",
     "[#6:1](=O)-[#7:2]>>[#6:1](=O)O.[#7:2]",
     "Disconnect amide bond → carboxylic acid + amine", 0.90),
    ("Ester hydrolysis",
     "[#6:1](=O)-[#8:2]-[#6:3]>>[#6:1](=O)O.[#8:2][#6:3]",
     "Disconnect ester → carboxylic acid + alcohol", 0.85),
    ("Suzuki coupling",
     "[#6:1]-[#6:2]1:[#6]:[#6]:[#6]:[#6]:[#6]:1>>[#6:1]B(O)O.[#6:2]1:[#6]:[#6]:[#6]:[#6]:[#6]:1Br",
     "Disconnect C-aryl bond → boronic acid + aryl bromide", 0.75),
    ("N-alkylation",
     "[#7:1]-[CX4:2]>>[#7:1].[#6:2]Br",
     "Disconnect C-N bond → amine + alkyl bromide", 0.70),
    ("Reductive amination",
     "[#7:1]-[CX4H1:2]-[#6:3]>>[#7:1].[#6:2](=O)-[#6:3]",
     "Disconnect C-N bond → amine + aldehyde/ketone", 0.70),
    ("Williamson ether",
     "[#6:1]-[#8:2]-[#6:3]>>[#6:1][#8:2].[#6:3]Br",
     "Disconnect ether → alcohol + alkyl halide", 0.65),
    ("Fischer esterification",
     "[#6:1](=O)-[#8:2]-[#6:3]>>[#6:1](=O)O.[#8:2][#6:3]",
     "Disconnect ester → acid + alcohol (Fischer)", 0.80),
    ("Urea formation",
     "[#7:1]-[CX3:2](=O)-[#7:3]>>[#7:1].[#8]=[#6:2]=[#8].[#7:3]",
     "Disconnect urea → amine + CDI/phosgene equiv + amine", 0.60),
]


class RLStatusResult(BaseModel):
    molecule_optimization: str
    retrosynthesis: str
    ontology_design: str

class OptimizationConstraints(BaseModel):
    max_steps: int = 10
    enforce_drug_likeness: bool = True
    forbid_illicit_targets: bool = True

class RLService:
    @classmethod
    def get_status(cls) -> RLStatusResult:
        return RLStatusResult(
            molecule_optimization="bioisosteric_active" if RDKIT_AVAILABLE else "rdkit_unavailable",
            retrosynthesis="template_engine_active" if RDKIT_AVAILABLE else "rdkit_unavailable",
            ontology_design="graph_analysis_active"
        )

    @classmethod
    def _passes_guardrails(cls, smiles: str) -> bool:
        if not RDKIT_AVAILABLE:
            logger.warning("rl.guardrail_fallback", msg="RDKit unavailable. Using exact string heuristics.")
            for pattern in RESTRICTED_SUBSTRUCTS:
                if pattern in smiles:
                    logger.warning("rl.guardrail_triggered_fallback", match=pattern)
                    return False
            return True

        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return False

        for pattern in RESTRICTED_SUBSTRUCTS:
            pat = Chem.MolFromSmarts(pattern)
            if pat and mol.HasSubstructMatch(pat):
                logger.warning("rl.guardrail_triggered", match=pattern)
                return False

        return True

    @classmethod
    def _passes_pains_filter(cls, mol: Any) -> bool:
        """Return True if molecule does NOT match any PAINS filter."""
        if not RDKIT_AVAILABLE:
            return True
        from rdkit import Chem
        for smarts in PAINS_SMARTS:
            pat = Chem.MolFromSmarts(smarts)
            if pat and mol.HasSubstructMatch(pat):
                return False
        return True

    @classmethod
    def _compute_tanimoto(cls, mol_a: Any, mol_b: Any) -> float:
        """Compute Tanimoto similarity between two RDKit mol objects."""
        try:
            from rdkit.Chem import AllChem
            from rdkit import DataStructs
            fp_a = AllChem.GetMorganFingerprintAsBitVect(mol_a, 2, nBits=2048)
            fp_b = AllChem.GetMorganFingerprintAsBitVect(mol_b, 2, nBits=2048)
            return DataStructs.TanimotoSimilarity(fp_a, fp_b)
        except Exception:
            return 0.0

    @classmethod
    def generate_molecules(cls, base_smiles: str, constraints: OptimizationConstraints) -> Dict[str, Any]:
        """Generate optimized molecule candidates via bioisosteric replacements,
        substituent additions, and tautomer enumeration.  Score with ADMET +
        Tanimoto similarity to parent.
        """
        logger.info("rl.molecule_optimization", base=base_smiles)

        # 1. Guardrail Inspection
        if constraints.forbid_illicit_targets and not cls._passes_guardrails(base_smiles):
            return {
                "status": "rejected",
                "reason": "Guardrail violation: restricted structure detected in input or target."
            }

        if not RDKIT_AVAILABLE:
            # Minimal fallback without RDKit
            return {
                "status": "degraded",
                "candidates": [],
                "metadata": {"warning": "RDKit unavailable. Cannot generate molecule variants."},
            }

        from rdkit import Chem
        from rdkit.Chem import AllChem
        try:
            from rdkit.Chem import rdMolStandardize
            _HAS_TAUTOMER = True
        except ImportError:
            _HAS_TAUTOMER = False

        parent_mol = Chem.MolFromSmiles(base_smiles)
        if parent_mol is None:
            return {"status": "failed", "reason": "Invalid base SMILES."}

        seen_smiles: set = {Chem.MolToSmiles(parent_mol)}
        candidates_raw: List[Dict[str, Any]] = []

        # ── Strategy 1: bioisosteric replacements ──
        for name, query_smarts, repl_smarts in BIOISOSTERE_PAIRS:
            query = Chem.MolFromSmarts(query_smarts)
            repl = Chem.MolFromSmiles(repl_smarts)
            if query is None or repl is None:
                continue
            if not parent_mol.HasSubstructMatch(query):
                continue
            try:
                products = AllChem.ReplaceSubstructs(parent_mol, query, repl)
                for prod in products[:2]:  # limit expansions
                    try:
                        Chem.SanitizeMol(prod)
                        smi = Chem.MolToSmiles(prod)
                        if smi and smi not in seen_smiles:
                            seen_smiles.add(smi)
                            candidates_raw.append({"smiles": smi, "origin": f"bioisostere:{name}", "mol": prod})
                    except Exception:
                        continue
            except Exception:
                continue

        # ── Strategy 2: substituent additions (methyl, ethyl, F, Cl) ──
        substituents = [
            ("methyl", Chem.MolFromSmiles("C")),
            ("fluoro", Chem.MolFromSmiles("F")),
            ("chloro", Chem.MolFromSmiles("Cl")),
        ]
        for sub_name, sub_mol in substituents:
            if sub_mol is None:
                continue
            try:
                # Find aromatic carbons with free valence for substitution
                aromatic_carbons = [
                    atom.GetIdx()
                    for atom in parent_mol.GetAtoms()
                    if atom.GetIsAromatic()
                    and atom.GetAtomicNum() == 6
                    and atom.GetTotalNumHs() > 0
                ]
                for idx in aromatic_carbons[:2]:  # limit to first 2 positions
                    try:
                        rw = Chem.RWMol(parent_mol)
                        new_idx = rw.AddAtom(sub_mol.GetAtomWithIdx(0))
                        rw.AddBond(idx, new_idx, Chem.BondType.SINGLE)
                        Chem.SanitizeMol(rw)
                        smi = Chem.MolToSmiles(rw)
                        if smi and smi not in seen_smiles:
                            seen_smiles.add(smi)
                            mol_obj = Chem.MolFromSmiles(smi)
                            if mol_obj:
                                candidates_raw.append({"smiles": smi, "origin": f"substituent:{sub_name}", "mol": mol_obj})
                    except Exception:
                        continue
            except Exception:
                continue

        # ── Strategy 3: tautomer enumeration ──
        if _HAS_TAUTOMER:
            try:
                enumerator = rdMolStandardize.TautomerEnumerator()
                tautomers = enumerator.Enumerate(parent_mol)
                for t in list(tautomers)[:3]:
                    smi = Chem.MolToSmiles(t)
                    if smi and smi not in seen_smiles:
                        seen_smiles.add(smi)
                        candidates_raw.append({"smiles": smi, "origin": "tautomer", "mol": t})
            except Exception:
                log.debug("Tautomer enumeration failed")

        # ── Score candidates ──
        results: List[Dict[str, Any]] = []
        for cand in candidates_raw[:constraints.max_steps]:
            smi = cand["smiles"]
            mol = cand.get("mol") or Chem.MolFromSmiles(smi)
            if mol is None:
                continue

            # Guardrail check
            if constraints.forbid_illicit_targets and not cls._passes_guardrails(smi):
                continue

            # PAINS filter
            if not cls._passes_pains_filter(mol):
                continue

            # ADMET scoring
            admet = DLModelService.run_admet_prediction(smi)
            similarity = cls._compute_tanimoto(parent_mol, mol)

            # Composite reward: ADMET quality + parent similarity
            score = 0.3  # base
            if admet.status == "baseline_success":
                pred = admet.predictions
                if pred.get("drug_like"):
                    score += 0.3
                if pred.get("h_bond_donors", 0) <= 5:
                    score += 0.05
                if pred.get("h_bond_acceptors", 0) <= 10:
                    score += 0.05
                if pred.get("tpsa", 999) <= 140:
                    score += 0.05
            score += similarity * 0.25  # up to 0.25 for similarity

            results.append({
                "smiles": smi,
                "reward_score": round(score, 3),
                "similarity": round(similarity, 3),
                "origin": cand["origin"],
                "admet": admet.predictions,
            })

        results.sort(key=lambda x: x["reward_score"], reverse=True)

        return {
            "status": "success",
            "iterations": min(constraints.max_steps, len(results)),
            "candidates": results,
            "metadata": {
                "strategies": ["bioisosteric_replacement", "substituent_addition", "tautomer_enumeration"],
                "total_generated": len(candidates_raw),
                "after_filters": len(results),
            },
        }

    @classmethod
    def analyze_retrosynthesis(cls, target_smiles: str) -> Dict[str, Any]:
        """Retrosynthetic analysis via reaction template disconnection.

        Applies common retrosynthetic SMARTS templates to identify plausible
        precursor molecules.  Returns a disconnection tree with confidence
        scores.
        """
        logger.info("rl.retrosynthesis", target=target_smiles)

        if not RDKIT_AVAILABLE:
            return {
                "status": "degraded",
                "message": "RDKit unavailable — cannot run retrosynthesis.",
                "target": target_smiles,
                "steps": [],
            }

        from rdkit import Chem
        from rdkit.Chem import AllChem

        target_mol = Chem.MolFromSmiles(target_smiles)
        if target_mol is None:
            return {"status": "failed", "reason": "Invalid target SMILES.", "steps": []}

        steps: List[Dict[str, Any]] = []

        for name, rxn_smarts, description, confidence in RETRO_TEMPLATES:
            try:
                rxn = AllChem.ReactionFromSmarts(rxn_smarts)
                if rxn is None:
                    continue
                # RunReactants applies forward reaction; for retro we need
                # to check if the product substructure is present first
                products_sets = rxn.RunReactants((target_mol,))
                if not products_sets:
                    continue

                for product_set in products_sets[:2]:  # limit expansions
                    precursors = []
                    valid = True
                    for p in product_set:
                        try:
                            Chem.SanitizeMol(p)
                            smi = Chem.MolToSmiles(p)
                            if smi:
                                precursors.append(smi)
                            else:
                                valid = False
                        except Exception:
                            valid = False
                            break

                    if valid and precursors:
                        step_id = hashlib.md5(
                            f"{name}:{'|'.join(sorted(precursors))}".encode()
                        ).hexdigest()[:8]
                        steps.append({
                            "step_id": step_id,
                            "reaction": name,
                            "description": description,
                            "precursors": precursors,
                            "confidence": confidence,
                        })
            except Exception:
                continue

        # Deduplicate by precursor set
        seen: set = set()
        unique_steps: List[Dict[str, Any]] = []
        for step in steps:
            key = frozenset(step["precursors"])
            if key not in seen:
                seen.add(key)
                unique_steps.append(step)

        unique_steps.sort(key=lambda s: s["confidence"], reverse=True)

        return {
            "status": "success" if unique_steps else "no_templates_matched",
            "target": target_smiles,
            "steps": unique_steps,
            "metadata": {
                "templates_checked": len(RETRO_TEMPLATES),
                "disconnections_found": len(unique_steps),
            },
        }

    @classmethod
    def design_ontology(cls, criteria: Dict[str, Any]) -> Dict[str, Any]:
        """Graph-based pathway design using the embedded graph store.

        Finds hub nodes connecting the phenotype seed to drug targets,
        scored by graph centrality metrics.
        """
        phenotype_seed = criteria.get("phenotype_seed", "")
        logger.info("rl.ontology_design", phenotype=phenotype_seed)

        try:
            from services.graph_store import get_graph_store
            import networkx as nx
        except ImportError:
            return {
                "status": "degraded",
                "message": "Graph store or NetworkX unavailable.",
                "edges": [],
            }

        store = get_graph_store()

        # Only NetworkXGraphStore exposes the internal _graph
        graph = getattr(store, "_graph", None)
        if graph is None or graph.number_of_nodes() == 0:
            return {
                "status": "empty_graph",
                "message": "Knowledge graph is empty. Run searches first to populate it.",
                "edges": [],
            }

        # Find nodes matching the phenotype seed (case-insensitive substring)
        seed_lower = phenotype_seed.lower()
        matching_nodes = []
        for nid, data in graph.nodes(data=True):
            name = str(data.get("name", nid)).lower()
            label = str(data.get("label", "")).lower()
            if seed_lower and (seed_lower in name or seed_lower in nid.lower() or seed_lower in label):
                matching_nodes.append(nid)

        if not matching_nodes:
            # Fall back to all nodes if no match
            matching_nodes = list(graph.nodes())[:5]

        # Compute centrality metrics on undirected view
        undirected = graph.to_undirected()
        try:
            degree_cent = nx.degree_centrality(undirected)
        except Exception:
            degree_cent = {}
        try:
            betweenness = nx.betweenness_centrality(undirected)
        except Exception:
            betweenness = {}

        # Find hub nodes (highest combined centrality) connected to seed nodes
        hub_scores: Dict[str, float] = {}
        for node in matching_nodes[:10]:
            for neighbor in undirected.neighbors(node):
                dc = degree_cent.get(neighbor, 0)
                bc = betweenness.get(neighbor, 0)
                composite = 0.6 * dc + 0.4 * bc
                if neighbor not in hub_scores or composite > hub_scores[neighbor]:
                    hub_scores[neighbor] = composite

        # Build suggested ontology edges: phenotype → hub → connected targets
        edges: List[Dict[str, Any]] = []
        for hub_id, score in sorted(hub_scores.items(), key=lambda x: x[1], reverse=True)[:10]:
            hub_data = graph.nodes.get(hub_id, {})
            hub_label = hub_data.get("label", "Entity")
            edges.append({
                "source": phenotype_seed or "query",
                "target": hub_id,
                "hub_label": hub_label,
                "hub_name": hub_data.get("name", hub_id),
                "relation": "associated_with",
                "confidence": round(min(score * 5, 1.0), 3),  # normalize
                "centrality": {
                    "degree": round(degree_cent.get(hub_id, 0), 4),
                    "betweenness": round(betweenness.get(hub_id, 0), 4),
                },
            })

        return {
            "status": "success" if edges else "no_connections",
            "phenotype": phenotype_seed,
            "edges": edges,
            "metadata": {
                "graph_nodes": graph.number_of_nodes(),
                "graph_edges": graph.number_of_edges(),
                "seed_matches": len(matching_nodes),
                "hubs_found": len(edges),
            },
        }


# ──────────────────────────────────────────────────────────────────────────
# §84.2: PPO Molecule Optimization
# ──────────────────────────────────────────────────────────────────────────

class PPORewardFunction:
    """Multi-objective reward for molecule design (§84.2).

    R = w1×binding + w2×QED + w3×SA + w4×(1-toxicity) + w5×novelty - w6×penalty(MW>500)
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or {
            "binding": 0.30,
            "qed": 0.20,
            "sa": 0.15,
            "toxicity": 0.15,
            "novelty": 0.10,
            "mw_penalty": 0.10,
        }

    def compute(self, smiles: str, seen_smiles: set,
                binding_score: float = 0.5) -> float:
        """Compute composite reward for a candidate molecule."""
        if not RDKIT_AVAILABLE:
            return 0.0

        from rdkit import Chem
        from rdkit.Chem import Descriptors, QED

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return -1.0

        w = self.weights

        # QED (Quantitative Estimate of Drug-Likeness)
        try:
            qed_score = QED.qed(mol)
        except Exception:
            qed_score = 0.0

        # Synthetic Accessibility Score (approximation via descriptor complexity)
        try:
            from rdkit.Chem import RDConfig
            import sys, os
            sa_path = os.path.join(RDConfig.RDContribDir, "SA_Score")
            if sa_path not in sys.path:
                sys.path.insert(0, sa_path)
            try:
                from sascorer import calculateScore
                sa_raw = calculateScore(mol)  # 1 (easy) to 10 (hard)
                sa_score = 1.0 - (sa_raw - 1.0) / 9.0  # normalise to 0-1
            except ImportError:
                # Fallback: inverse of heavy atom count (crude proxy)
                heavy = mol.GetNumHeavyAtoms()
                sa_score = max(0, 1.0 - heavy / 50.0)
        except Exception:
            sa_score = 0.5

        # Toxicity proxy from ADMET (hERG liability)
        admet = DLModelService.run_admet_prediction(smiles)
        toxicity = 0.5
        if admet.predictions and isinstance(admet.predictions, dict):
            neural = admet.predictions.get("neural_admet", {})
            if "herg" in neural:
                toxicity = abs(neural["herg"].get("value", 0.5))

        # Novelty: is this a new molecule?
        novelty = 1.0 if smiles not in seen_smiles else 0.0

        # Molecular weight penalty
        mw = Descriptors.MolWt(mol)
        mw_penalty = 1.0 if mw > 500 else 0.0

        reward = (
            w["binding"] * binding_score
            + w["qed"] * qed_score
            + w["sa"] * sa_score
            + w["toxicity"] * (1.0 - toxicity)
            + w["novelty"] * novelty
            - w["mw_penalty"] * mw_penalty
        )
        return round(reward, 4)


class PPOBuffer:
    """Experience buffer for PPO training (§84.2)."""

    def __init__(self):
        self.states: List[Any] = []
        self.actions: List[int] = []
        self.rewards: List[float] = []
        self.log_probs: List[float] = []
        self.values: List[float] = []
        self.dones: List[bool] = []

    def store(self, state, action: int, reward: float,
              log_prob: float, value: float, done: bool):
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
        self.log_probs.append(log_prob)
        self.values.append(value)
        self.dones.append(done)

    def clear(self):
        self.states.clear()
        self.actions.clear()
        self.rewards.clear()
        self.log_probs.clear()
        self.values.clear()
        self.dones.clear()

    def compute_gae(self, gamma: float = 0.99, lam: float = 0.95) -> Tuple[List[float], List[float]]:
        """Generalised Advantage Estimation (GAE)."""
        advantages = []
        returns = []
        gae = 0.0
        next_value = 0.0
        for t in reversed(range(len(self.rewards))):
            if self.dones[t]:
                next_value = 0.0
                gae = 0.0
            delta = self.rewards[t] + gamma * next_value - self.values[t]
            gae = delta + gamma * lam * gae
            advantages.insert(0, gae)
            returns.insert(0, gae + self.values[t])
            next_value = self.values[t]
        return advantages, returns


if TORCH_AVAILABLE:
    class PPOMoleculeOptimizer:
        """PPO-based molecule optimization (§84.2).

        Uses MoleculeGNNPolicy for action selection and PPO clipping
        update for policy improvement.
        """

        def __init__(self, atom_dim: int = 32, hidden_dim: int = 128,
                     num_actions: int = 32, lr: float = 3e-4,
                     clip_eps: float = 0.2, entropy_coeff: float = 0.01,
                     value_coeff: float = 0.5, max_grad_norm: float = 0.5):
            from services.dl_models import MoleculeGNNPolicy

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.policy = MoleculeGNNPolicy(
                atom_dim=atom_dim, hidden_dim=hidden_dim,
                num_actions=num_actions
            ).to(self.device)
            self.optimizer = torch.optim.Adam(self.policy.parameters(), lr=lr)
            self.clip_eps = clip_eps
            self.entropy_coeff = entropy_coeff
            self.value_coeff = value_coeff
            self.max_grad_norm = max_grad_norm
            self.buffer = PPOBuffer()
            self.reward_fn = PPORewardFunction()

        def select_action(self, atom_features: torch.Tensor,
                          edge_index: Optional[torch.Tensor] = None) -> Tuple[int, float, float]:
            """Select action from policy, return (action, log_prob, value)."""
            self.policy.eval()
            with torch.no_grad():
                logits, value = self.policy(
                    atom_features.to(self.device),
                    edge_index.to(self.device) if edge_index is not None else None,
                )
                dist = torch.distributions.Categorical(logits=logits.squeeze(0))
                action = dist.sample()
                log_prob = dist.log_prob(action)
            return action.item(), log_prob.item(), value.item()

        def update(self, epochs: int = 4, batch_size: int = 32) -> Dict[str, float]:
            """PPO clipping update (§84.2)."""
            if len(self.buffer.states) == 0:
                return {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}

            advantages, returns = self.buffer.compute_gae()

            # Convert to tensors
            old_log_probs = torch.tensor(self.buffer.log_probs, dtype=torch.float32, device=self.device)
            actions = torch.tensor(self.buffer.actions, dtype=torch.long, device=self.device)
            adv_t = torch.tensor(advantages, dtype=torch.float32, device=self.device)
            ret_t = torch.tensor(returns, dtype=torch.float32, device=self.device)

            # Normalise advantages
            if len(adv_t) > 1:
                adv_t = (adv_t - adv_t.mean()) / (adv_t.std() + 1e-8)

            total_policy_loss = 0.0
            total_value_loss = 0.0
            total_entropy = 0.0
            n_updates = 0

            self.policy.train()
            for _ in range(epochs):
                # For simplicity, process all at once (no mini-batch for small buffers)
                for i, state in enumerate(self.buffer.states):
                    atom_feats = state["atom_features"].to(self.device)
                    edge_idx = state.get("edge_index")
                    if edge_idx is not None:
                        edge_idx = edge_idx.to(self.device)

                    logits, value = self.policy(atom_feats, edge_idx)
                    dist = torch.distributions.Categorical(logits=logits.squeeze(0))
                    new_log_prob = dist.log_prob(actions[i])
                    entropy = dist.entropy().mean()

                    # PPO clipping
                    ratio = (new_log_prob - old_log_probs[i]).exp()
                    surr1 = ratio * adv_t[i]
                    surr2 = torch.clamp(ratio, 1.0 - self.clip_eps, 1.0 + self.clip_eps) * adv_t[i]
                    policy_loss = -torch.min(surr1, surr2)
                    value_loss = F.mse_loss(value.squeeze(), ret_t[i])

                    loss = policy_loss + self.value_coeff * value_loss - self.entropy_coeff * entropy

                    self.optimizer.zero_grad()
                    loss.backward()
                    nn.utils.clip_grad_norm_(self.policy.parameters(), self.max_grad_norm)
                    self.optimizer.step()

                    total_policy_loss += policy_loss.item()
                    total_value_loss += value_loss.item()
                    total_entropy += entropy.item()
                    n_updates += 1

            self.buffer.clear()

            n = max(n_updates, 1)
            return {
                "policy_loss": round(total_policy_loss / n, 6),
                "value_loss": round(total_value_loss / n, 6),
                "entropy": round(total_entropy / n, 6),
            }

        def optimize_molecule(self, base_smiles: str, n_episodes: int = 10,
                              max_steps: int = 20) -> Dict[str, Any]:
            """Run PPO optimization loop on a molecule (§84.2).

            Each episode:
              1. Featurise current molecule as graph
              2. Select action (add atom, remove atom, modify bond, etc.)
              3. Apply action to get new molecule
              4. Compute reward
              5. Store transition in buffer
            After episodes, run PPO update.
            """
            if not RDKIT_AVAILABLE:
                return {"status": "failed", "reason": "RDKit required for PPO optimization"}

            from rdkit import Chem

            seen_smiles: set = {base_smiles}
            best_candidates: List[Dict[str, Any]] = []
            episode_rewards: List[float] = []

            for episode in range(n_episodes):
                current_smiles = base_smiles
                episode_reward = 0.0

                for step in range(max_steps):
                    # Featurise molecule
                    mol = Chem.MolFromSmiles(current_smiles)
                    if mol is None:
                        break

                    atom_features, edge_index = self._featurise_mol(mol)
                    action, log_prob, value = self.select_action(atom_features, edge_index)

                    # Apply action to molecule
                    new_smiles = self._apply_action(current_smiles, action)
                    if new_smiles is None:
                        reward = -0.1
                        done = True
                    else:
                        reward = self.reward_fn.compute(new_smiles, seen_smiles)
                        seen_smiles.add(new_smiles)
                        done = step == max_steps - 1

                    self.buffer.store(
                        state={"atom_features": atom_features, "edge_index": edge_index},
                        action=action, reward=reward,
                        log_prob=log_prob, value=value, done=done,
                    )

                    episode_reward += reward

                    if new_smiles and reward > 0:
                        best_candidates.append({
                            "smiles": new_smiles,
                            "reward": round(reward, 4),
                            "episode": episode,
                            "step": step,
                        })

                    if done or new_smiles is None:
                        break
                    current_smiles = new_smiles

                episode_rewards.append(episode_reward)

            # PPO update
            update_stats = self.update()

            # Sort and deduplicate candidates
            seen = set()
            unique_candidates = []
            for c in sorted(best_candidates, key=lambda x: x["reward"], reverse=True):
                if c["smiles"] not in seen:
                    seen.add(c["smiles"])
                    unique_candidates.append(c)

            return {
                "status": "success",
                "candidates": unique_candidates[:20],
                "episode_rewards": [round(r, 4) for r in episode_rewards],
                "ppo_update": update_stats,
                "metadata": {
                    "method": "ppo_gnn",
                    "episodes": n_episodes,
                    "max_steps": max_steps,
                    "total_candidates": len(unique_candidates),
                },
            }

        def _featurise_mol(self, mol) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
            """Convert RDKit mol to atom feature tensor and edge index."""
            from rdkit import Chem

            atoms = mol.GetAtoms()
            n = len(atoms)

            features = []
            for atom in atoms:
                feat = [
                    atom.GetAtomicNum() / 100.0,
                    atom.GetDegree() / 6.0,
                    atom.GetTotalValence() / 8.0,
                    float(atom.GetIsAromatic()),
                    float(atom.IsInRing()),
                    (atom.GetFormalCharge() + 3) / 6.0,
                    atom.GetNumRadicalElectrons() / 2.0,
                    float(atom.GetHybridization()) / 6.0,
                ]
                # Pad to 32 dims
                feat.extend([0.0] * (32 - len(feat)))
                features.append(feat[:32])

            atom_features = torch.tensor(features, dtype=torch.float32)

            # Build edge index from bonds (bidirectional)
            src, dst = [], []
            for bond in mol.GetBonds():
                i, j = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
                src.extend([i, j])
                dst.extend([j, i])

            if src:
                edge_index = torch.tensor([src, dst], dtype=torch.long)
            else:
                edge_index = None

            return atom_features, edge_index

        def _apply_action(self, smiles: str, action: int) -> Optional[str]:
            """Apply a molecular editing action and return new SMILES.

            Actions:
              0-7:   Add atom type at random position
              8-15:  Remove atom at position
              16-23: Toggle bond type
              24-31: Bioisosteric replacement
            """
            from rdkit import Chem

            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return None

            try:
                rw = Chem.RWMol(mol)

                if action < 8:
                    # Add atom
                    atom_types = [6, 7, 8, 9, 16, 17, 35, 15]  # C,N,O,F,S,Cl,Br,P
                    new_atom = Chem.Atom(atom_types[action % len(atom_types)])
                    idx = rw.AddAtom(new_atom)
                    # Bond to a random existing atom
                    n_atoms = rw.GetNumAtoms() - 1
                    if n_atoms > 0:
                        target = action % n_atoms
                        rw.AddBond(target, idx, Chem.BondType.SINGLE)
                elif action < 16:
                    # Remove atom
                    n_atoms = rw.GetNumAtoms()
                    if n_atoms > 2:
                        target = (action - 8) % n_atoms
                        rw.RemoveAtom(target)
                elif action < 24:
                    # Toggle bond type
                    bonds = list(rw.GetBonds())
                    if bonds:
                        bond = bonds[(action - 16) % len(bonds)]
                        current = bond.GetBondType()
                        if current == Chem.BondType.SINGLE:
                            bond.SetBondType(Chem.BondType.DOUBLE)
                        elif current == Chem.BondType.DOUBLE:
                            bond.SetBondType(Chem.BondType.SINGLE)
                else:
                    # Bioisosteric replacement
                    pair_idx = (action - 24) % len(BIOISOSTERE_PAIRS)
                    name, query_smarts, repl_smarts = BIOISOSTERE_PAIRS[pair_idx]
                    from rdkit.Chem import AllChem
                    query = Chem.MolFromSmarts(query_smarts)
                    repl = Chem.MolFromSmiles(repl_smarts)
                    if query and repl and mol.HasSubstructMatch(query):
                        products = AllChem.ReplaceSubstructs(mol, query, repl)
                        if products:
                            Chem.SanitizeMol(products[0])
                            return Chem.MolToSmiles(products[0])
                    return None

                Chem.SanitizeMol(rw)
                return Chem.MolToSmiles(rw)
            except Exception:
                return None
