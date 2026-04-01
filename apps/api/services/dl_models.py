"""Deep Learning (DL) Baseline Modules for Drug-Synth.

Provides pluggable CPU-safe heuristic baselines for:
1. Ontology completion — graph topology analysis (NetworkX)
2. Target prioritization — evidence-weighted centrality scoring
3. ADMET prediction (RDKit)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import structlog
from pydantic import BaseModel

try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Lipinski
    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False

logger = structlog.get_logger(__name__)
log = logging.getLogger(__name__)

class InferenceResult(BaseModel):
    model_type: str
    status: str
    predictions: Any
    metadata: Dict[str, Any] = {}

class DLModelService:
    """Registry and baseline provider for DL inference modules."""

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        return {
            "rgcn_ontology": {"status": "graph_topology_active", "device": "cpu"},
            "gat_prioritization": {"status": "evidence_weighted_active", "device": "cpu"},
            "admet_prediction": {"status": "rdkit_active" if RDKIT_AVAILABLE else "unavailable", "device": "cpu"}
        }

    @classmethod
    def run_ontology_completion(cls, seed_nodes: List[str]) -> InferenceResult:
        """Graph-based ontology completion using NetworkX topology analysis.

        Queries the embedded graph store for edges around seed nodes,
        computes node-level metrics (degree, betweenness, clustering),
        and proposes new edges based on common-neighbor patterns.
        """
        logger.info("dl.ontology_completion", seeds=len(seed_nodes))

        try:
            from services.graph_store import get_graph_store
            import networkx as nx
        except ImportError:
            return cls._ontology_fallback(seed_nodes, "NetworkX or graph store unavailable")

        store = get_graph_store()
        graph = getattr(store, "_graph", None)

        if graph is None or graph.number_of_nodes() == 0:
            return cls._ontology_fallback(seed_nodes, "Knowledge graph is empty")

        undirected = graph.to_undirected()

        # Resolve seed nodes: find matching node IDs via substring search
        resolved_seeds: List[str] = []
        for seed in seed_nodes:
            seed_lower = seed.lower()
            for nid, data in graph.nodes(data=True):
                name = str(data.get("name", nid)).lower()
                if seed_lower in name or seed_lower in nid.lower():
                    resolved_seeds.append(nid)
                    break
            else:
                # If seed is itself a node ID
                if seed in graph:
                    resolved_seeds.append(seed)

        if not resolved_seeds:
            return cls._ontology_fallback(seed_nodes, "No seed nodes found in graph")

        # Compute centrality metrics
        try:
            degree_cent = nx.degree_centrality(undirected)
        except Exception:
            degree_cent = {}
        try:
            betweenness = nx.betweenness_centrality(undirected)
        except Exception:
            betweenness = {}
        try:
            clustering = nx.clustering(undirected)
        except Exception:
            clustering = {}

        # Find common neighbors between seed pairs → propose new edges
        predictions: List[Dict[str, Any]] = []
        seen_edges: set = set()

        # Strategy 1: common-neighbor link prediction
        for i, src in enumerate(resolved_seeds):
            src_neighbors = set(undirected.neighbors(src)) if src in undirected else set()
            for j, dst in enumerate(resolved_seeds):
                if i >= j:
                    continue
                dst_neighbors = set(undirected.neighbors(dst)) if dst in undirected else set()
                common = src_neighbors & dst_neighbors
                if common and not graph.has_edge(src, dst) and not graph.has_edge(dst, src):
                    # Jaccard coefficient as confidence
                    union_size = len(src_neighbors | dst_neighbors)
                    confidence = len(common) / union_size if union_size > 0 else 0
                    edge_key = (min(src, dst), max(src, dst))
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        predictions.append({
                            "source": src,
                            "target": dst,
                            "confidence": round(confidence, 3),
                            "rel_type": "predicted_link",
                            "evidence": f"common_neighbors:{len(common)}",
                            "common_neighbors": list(common)[:5],
                        })

        # Strategy 2: high-centrality neighbors as candidate edges
        for seed in resolved_seeds:
            if seed not in undirected:
                continue
            for neighbor in undirected.neighbors(seed):
                dc = degree_cent.get(neighbor, 0)
                bc = betweenness.get(neighbor, 0)
                cc = clustering.get(neighbor, 0)
                composite = 0.4 * dc + 0.4 * bc + 0.2 * cc

                if composite > 0.01:  # only non-trivial nodes
                    neighbor_data = graph.nodes.get(neighbor, {})
                    # Propose connections to 2nd-degree neighbors
                    for nn in list(undirected.neighbors(neighbor))[:5]:
                        if nn != seed and nn not in resolved_seeds:
                            edge_key = (min(seed, nn), max(seed, nn))
                            if edge_key not in seen_edges and not graph.has_edge(seed, nn):
                                seen_edges.add(edge_key)
                                predictions.append({
                                    "source": seed,
                                    "target": nn,
                                    "confidence": round(composite, 3),
                                    "rel_type": "topology_inferred",
                                    "evidence": f"via_hub:{neighbor}",
                                    "hub_centrality": {
                                        "degree": round(dc, 4),
                                        "betweenness": round(bc, 4),
                                        "clustering": round(cc, 4),
                                    },
                                })

        # Sort by confidence, limit output
        predictions.sort(key=lambda p: p["confidence"], reverse=True)
        predictions = predictions[:20]

        return InferenceResult(
            model_type="rgcn_ontology",
            status="graph_analysis_success",
            predictions=predictions,
            metadata={
                "method": "graph_topology",
                "seeds_resolved": len(resolved_seeds),
                "graph_nodes": graph.number_of_nodes(),
                "graph_edges": graph.number_of_edges(),
                "predictions_count": len(predictions),
            },
        )

    @classmethod
    def _ontology_fallback(cls, seed_nodes: List[str], reason: str) -> InferenceResult:
        """Fallback when graph store is unavailable or empty."""
        return InferenceResult(
            model_type="rgcn_ontology",
            status="fallback",
            predictions=[],
            metadata={"reason": reason, "seeds": seed_nodes},
        )

    @classmethod
    def run_target_prioritization(cls, disease_id: str) -> InferenceResult:
        """Evidence-weighted target prioritization using graph centrality
        and evidence store scoring.

        Queries the graph store for disease→gene edges, computes degree
        centrality for each gene node, and optionally weights by evidence
        counts and confidence from the evidence store.
        """
        logger.info("dl.target_prioritization", disease_id=disease_id)

        try:
            from services.graph_store import get_graph_store
            import networkx as nx
        except ImportError:
            return cls._prioritization_fallback(disease_id, "NetworkX or graph store unavailable")

        store = get_graph_store()
        graph = getattr(store, "_graph", None)

        if graph is None or graph.number_of_nodes() == 0:
            return cls._prioritization_fallback(disease_id, "Knowledge graph is empty")

        undirected = graph.to_undirected()

        # Find the disease node (case-insensitive substring)
        disease_lower = disease_id.lower()
        disease_node = None
        for nid, data in graph.nodes(data=True):
            name = str(data.get("name", nid)).lower()
            label = str(data.get("label", "")).lower()
            if disease_lower in name or disease_lower in nid.lower():
                disease_node = nid
                break

        if disease_node is None:
            return cls._prioritization_fallback(disease_id, f"Disease '{disease_id}' not found in graph")

        # Compute centrality
        try:
            degree_cent = nx.degree_centrality(undirected)
        except Exception:
            degree_cent = {}
        try:
            betweenness = nx.betweenness_centrality(undirected)
        except Exception:
            betweenness = {}

        # Collect gene/target nodes connected to the disease
        gene_labels = {"gene", "protein", "target", "drug_target"}
        candidate_genes: Dict[str, Dict[str, Any]] = {}

        # Direct neighbors
        if disease_node in undirected:
            for neighbor in undirected.neighbors(disease_node):
                ndata = graph.nodes.get(neighbor, {})
                nlabel = str(ndata.get("label", "")).lower()
                if nlabel in gene_labels or not gene_labels:
                    dc = degree_cent.get(neighbor, 0)
                    bc = betweenness.get(neighbor, 0)
                    candidate_genes[neighbor] = {
                        "degree_centrality": dc,
                        "betweenness_centrality": bc,
                        "label": ndata.get("label", "Entity"),
                        "name": ndata.get("name", neighbor),
                        "hops": 1,
                    }

            # 2nd-degree neighbors (through intermediaries)
            for neighbor in undirected.neighbors(disease_node):
                for nn in undirected.neighbors(neighbor):
                    if nn != disease_node and nn not in candidate_genes:
                        ndata = graph.nodes.get(nn, {})
                        nlabel = str(ndata.get("label", "")).lower()
                        if nlabel in gene_labels:
                            dc = degree_cent.get(nn, 0)
                            bc = betweenness.get(nn, 0)
                            candidate_genes[nn] = {
                                "degree_centrality": dc,
                                "betweenness_centrality": bc,
                                "label": ndata.get("label", "Entity"),
                                "name": ndata.get("name", nn),
                                "hops": 2,
                            }

        # If no specific gene labels found, include all connected nodes
        if not candidate_genes and disease_node in undirected:
            for neighbor in undirected.neighbors(disease_node):
                ndata = graph.nodes.get(neighbor, {})
                dc = degree_cent.get(neighbor, 0)
                bc = betweenness.get(neighbor, 0)
                candidate_genes[neighbor] = {
                    "degree_centrality": dc,
                    "betweenness_centrality": bc,
                    "label": ndata.get("label", "Entity"),
                    "name": ndata.get("name", neighbor),
                    "hops": 1,
                }

        # Try to weight by evidence store
        evidence_weights: Dict[str, float] = {}
        try:
            from services.evidence_store import EvidenceStore
            stats = EvidenceStore.get_stats()
            if stats.get("edges", 0) > 0:
                # Count edges involving each gene
                for gene_id in candidate_genes:
                    count = 0
                    # Quick scan of evidence edges table
                    try:
                        import sqlite3
                        conn = sqlite3.connect(EvidenceStore._db_path)
                        row = conn.execute(
                            "SELECT COUNT(*) FROM evidence_edges WHERE src_entity = ? OR dst_entity = ?",
                            (gene_id, gene_id),
                        ).fetchone()
                        count = row[0] if row else 0
                        conn.close()
                    except Exception:
                        log.debug("Evidence store query failed for gene %s", gene_id)
                    if count > 0:
                        evidence_weights[gene_id] = min(count / 10.0, 1.0)  # normalize
        except Exception:
            log.debug("Evidence weight computation failed")

        # Compute composite scores
        predictions: Dict[str, Dict[str, Any]] = {}
        for gene_id, info in candidate_genes.items():
            dc = info["degree_centrality"]
            bc = info["betweenness_centrality"]
            ev = evidence_weights.get(gene_id, 0)
            hop_penalty = 1.0 if info["hops"] == 1 else 0.7

            # Composite: 40% degree + 30% betweenness + 20% evidence + 10% hop
            composite = (0.4 * dc + 0.3 * bc + 0.2 * ev + 0.1 * hop_penalty)
            # Normalize to 0-1 range (soft cap)
            score = min(composite * 5, 1.0)

            predictions[gene_id] = {
                "score": round(score, 4),
                "name": info["name"],
                "label": info["label"],
                "evidence": f"graph_centrality+evidence",
                "details": {
                    "degree_centrality": round(dc, 4),
                    "betweenness_centrality": round(bc, 4),
                    "evidence_weight": round(ev, 4),
                    "hops_from_disease": info["hops"],
                },
            }

        # Sort by score
        sorted_predictions = dict(
            sorted(predictions.items(), key=lambda x: x[1]["score"], reverse=True)
        )

        return InferenceResult(
            model_type="gat_prioritization",
            status="graph_analysis_success",
            predictions=sorted_predictions,
            metadata={
                "method": "evidence_weighted_centrality",
                "disease_node": disease_node,
                "candidates_found": len(sorted_predictions),
                "evidence_available": len(evidence_weights) > 0,
            },
        )

    @classmethod
    def _prioritization_fallback(cls, disease_id: str, reason: str) -> InferenceResult:
        """Fallback when graph store is unavailable or empty."""
        return InferenceResult(
            model_type="gat_prioritization",
            status="fallback",
            predictions={},
            metadata={"reason": reason, "disease_id": disease_id},
        )

    @classmethod
    def run_admet_prediction(cls, smiles: str) -> InferenceResult:
        """
        Functional ADMET baseline using RDKit for Lipinski's Rule of 5 and physchem properties.
        """
        logger.info("dl.admet_prediction", smiles=smiles)

        if not RDKIT_AVAILABLE:
            return InferenceResult(
                model_type="admet_prediction",
                status="failed",
                predictions=None,
                metadata={"error": "RDKit not installed in environment."}
            )

        mol = Chem.MolFromSmiles(smiles)
        if not mol:
             return InferenceResult(
                model_type="admet_prediction",
                status="failed",
                predictions=None,
                metadata={"error": "Invalid SMILES sequence."}
            )

        mw = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        hba = Lipinski.NumHAcceptors(mol)
        hbd = Lipinski.NumHDonors(mol)
        tpsa = Descriptors.TPSA(mol)

        violations = 0
        if mw > 500: violations += 1
        if logp > 5: violations += 1
        if hba > 10: violations += 1
        if hbd > 5: violations += 1

        predictions = {
            "molecular_weight": round(mw, 2),
            "logp": round(logp, 2),
            "h_bond_acceptors": hba,
            "h_bond_donors": hbd,
            "tpsa": round(tpsa, 2),
            "lipinski_violations": violations,
            "drug_like": violations <= 1
        }

        return InferenceResult(
            model_type="admet_prediction",
            status="baseline_success",
            predictions=predictions,
            metadata={"source": "RDKit Baseline"}
        )
