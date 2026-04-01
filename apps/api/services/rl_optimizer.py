"""Reinforcement Learning (RL) Optimization Modules.

Provides guarded pipeline execution for:
1. Molecule Optimization — bioisosteric replacements + ADMET scoring
2. Retrosynthesis Planning — reaction template disconnection
3. Ontology Design — graph-based pathway analysis
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional
import structlog
from pydantic import BaseModel, Field

from services.dl_models import DLModelService, RDKIT_AVAILABLE

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
