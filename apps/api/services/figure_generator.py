"""Service for generating publication-ready figures from real job/evidence data."""

from __future__ import annotations

import os
import json
import uuid
from typing import Dict, Any, List, Optional

import matplotlib
matplotlib.use('Agg')  # Headless mode
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

from config import settings
from services.job_logger import JobLogger


class FigureGenerator:
    """Generates figures driven by real job evidence and entity data."""

    # Palette constants
    _C_TARGET = "#c2614b"   # terracotta accent
    _C_DRUG   = "#a3968d"   # muted brown
    _C_GENE   = "#7a9a8a"   # sage green
    _C_OTHER  = "#b5a99a"   # warm grey
    _C_EDGE   = "#e6dfd5"
    _C_TEXT   = "#4a3b32"
    _C_BG     = "#faf8f5"

    @classmethod
    def _get_media_dir(cls) -> str:
        d = os.path.join(settings.local_store_path, "media")
        os.makedirs(d, exist_ok=True)
        return d

    @classmethod
    def _save_fig(cls, fig: plt.Figure, job_id: str, prefix: str) -> tuple[str, str]:
        """Save figure as SVG and PNG and return paths."""
        media_dir = cls._get_media_dir()
        file_base = f"{job_id}_{prefix}_{uuid.uuid4().hex[:6]}"
        svg_path = os.path.join(media_dir, f"{file_base}.svg")
        png_path = os.path.join(media_dir, f"{file_base}.png")
        fig.savefig(svg_path, format="svg", bbox_inches='tight')
        fig.savefig(png_path, format="png", bbox_inches='tight', dpi=150)
        plt.close(fig)
        return svg_path, png_path

    @classmethod
    def _save_json(cls, data: Dict[str, Any], job_id: str, prefix: str) -> str:
        media_dir = cls._get_media_dir()
        file_base = f"{job_id}_{prefix}_{uuid.uuid4().hex[:6]}"
        json_path = os.path.join(media_dir, f"{file_base}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return json_path

    @classmethod
    def _empty_state_fig(cls, title: str, message: str) -> plt.Figure:
        """Return a minimal empty-state figure with a clear message."""
        fig, ax = plt.subplots(figsize=(7, 4), facecolor=cls._C_BG)
        ax.set_facecolor(cls._C_BG)
        ax.text(0.5, 0.5, message, ha="center", va="center",
                fontsize=11, color=cls._C_TEXT, style="italic",
                transform=ax.transAxes, wrap=True)
        ax.set_title(title, fontsize=13, color=cls._C_TEXT, pad=12)
        ax.axis("off")
        for spine in ax.spines.values():
            spine.set_visible(False)
        return fig

    # ── Public entry points ─────────────────────────────────────

    @classmethod
    def generate_job_artifacts(
        cls,
        job_id: str,
        entities: Optional[List[Dict]] = None,
        synthesis: Optional[Dict] = None,
        evidence_refs: Optional[List[str]] = None,
    ) -> None:
        """Generate the 3 standard figures for a job, driven by real result data."""
        entities = entities or []
        synthesis = synthesis or {}
        evidence_refs = evidence_refs or []
        cls.generate_network_graph(job_id, entities=entities)
        cls.generate_heatmap(job_id, entities=entities)
        cls.generate_waterfall(job_id, top_targets=synthesis.get("top_targets_ranked", []))

    # ── Figure 1: Entity Interaction Network ───────────────────

    @classmethod
    def generate_network_graph(
        cls,
        job_id: str,
        entities: Optional[List[Dict]] = None,
    ) -> None:
        """
        Generate an entity interaction network from real query results.

        Uses actual entity names and types from the job. Nodes represent
        entities retrieved from live data sources. Edges represent
        co-occurrence in the same query result set.
        """
        entities = entities or []

        # Filter to named entities only (skip empties)
        named = [e for e in entities if e.get("name") or e.get("canonical_name")][:30]

        if len(named) < 2:
            fig = cls._empty_state_fig(
                "Entity Interaction Network",
                "No entity data available for this query.\nRun a search with multiple targets or drugs to see the network."
            )
            svg_path, png_path = cls._save_fig(fig, job_id, "network")
            json_path = cls._save_json({"nodes": [], "edges": [], "note": "no_data"}, job_id, "network")
        else:
            G = nx.Graph()
            type_color = {
                "protein": cls._C_TARGET,
                "target": cls._C_TARGET,
                "gene": cls._C_GENE,
                "molecule": cls._C_DRUG,
                "drug": cls._C_DRUG,
            }
            node_colors = []
            for ent in named:
                name = ent.get("name") or ent.get("canonical_name", "")
                etype = ent.get("entity_type", "other").lower()
                G.add_node(name, entity_type=etype)
                node_colors.append(type_color.get(etype, cls._C_OTHER))

            # Build edges: drugs/molecules connect to all protein/target nodes
            drug_nodes = [n for n, d in G.nodes(data=True) if d.get("entity_type") in ("molecule", "drug")]
            target_nodes = [n for n, d in G.nodes(data=True) if d.get("entity_type") in ("protein", "target", "gene")]
            for drug in drug_nodes:
                for tgt in target_nodes[:5]:  # cap at 5 edges per drug for readability
                    if drug != tgt:
                        G.add_edge(drug, tgt)

            # If no typed edges, connect all remaining nodes in sequence
            if G.number_of_edges() == 0:
                nodes_list = list(G.nodes())
                for i in range(len(nodes_list) - 1):
                    G.add_edge(nodes_list[i], nodes_list[i + 1])

            fig, ax = plt.subplots(figsize=(8, 6), facecolor=cls._C_BG)
            ax.set_facecolor(cls._C_BG)
            pos = nx.spring_layout(G, seed=42, k=1.2)

            nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=700, ax=ax)
            nx.draw_networkx_edges(G, pos, alpha=0.4, edge_color=cls._C_EDGE, ax=ax)
            # Truncate long labels
            labels = {n: (n[:18] + "…" if len(n) > 18 else n) for n in G.nodes()}
            nx.draw_networkx_labels(G, pos, labels=labels, font_size=8,
                                    font_family="sans-serif", font_color=cls._C_TEXT, ax=ax)

            # Legend
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor=cls._C_TARGET, label='Protein/Target'),
                Patch(facecolor=cls._C_DRUG, label='Drug/Molecule'),
                Patch(facecolor=cls._C_GENE, label='Gene'),
                Patch(facecolor=cls._C_OTHER, label='Other'),
            ]
            ax.legend(handles=legend_elements, loc="lower right", fontsize=7,
                      framealpha=0.8, facecolor=cls._C_BG)
            ax.set_title(f"Entity Interaction Network — {len(named)} entities",
                         fontsize=13, color=cls._C_TEXT, pad=12)
            ax.axis("off")

            svg_path, png_path = cls._save_fig(fig, job_id, "network")
            json_path = cls._save_json(
                {"nodes": [{"id": n, **d} for n, d in G.nodes(data=True)],
                 "edges": [{"source": u, "target": v} for u, v in G.edges()]},
                job_id, "network"
            )

        JobLogger.log_artifact(
            artifact_id=f"art_{uuid.uuid4().hex[:8]}",
            job_id=job_id,
            type="Network Graph",
            title="Entity Interaction Network",
            description=f"Interaction network derived from {len(named)} entities in this query.",
            svg_path=svg_path,
            png_path=png_path,
            json_path=json_path,
        )

    # ── Figure 2: Evidence Confidence Heatmap ─────────────────

    @classmethod
    def generate_heatmap(
        cls,
        job_id: str,
        entities: Optional[List[Dict]] = None,
    ) -> None:
        """
        Generate an evidence confidence heatmap from real entity provenance.

        Rows = entity names, Columns = data sources. Cell = confidence score
        where that entity was found by that source (NaN where not found).
        """
        entities = entities or []
        named = [e for e in entities if e.get("name") or e.get("canonical_name")][:15]

        # Collect all unique source names from provenance
        all_sources: list[str] = []
        for ent in named:
            for prov in ent.get("provenance", []):
                src = prov.get("source", "")
                if src and src not in all_sources:
                    all_sources.append(src)

        if not named or not all_sources:
            fig = cls._empty_state_fig(
                "Evidence Confidence by Source",
                "No provenance data available for this query.\nEvidence confidence heatmap requires sourced entity results."
            )
            svg_path, png_path = cls._save_fig(fig, job_id, "heatmap")
            json_path = cls._save_json({"data": [], "rows": [], "cols": [], "note": "no_data"}, job_id, "heatmap")
        else:
            # Build matrix: entities × sources → confidence
            row_labels = [e.get("name") or e.get("canonical_name", "")[:20] for e in named]
            col_labels = all_sources[:10]  # cap columns
            matrix = np.full((len(row_labels), len(col_labels)), np.nan)

            for i, ent in enumerate(named):
                for prov in ent.get("provenance", []):
                    src = prov.get("source", "")
                    conf = prov.get("confidence", 0.0)
                    if src in col_labels:
                        j = col_labels.index(src)
                        # Use max confidence if multiple provenance records for same source
                        current = matrix[i, j]
                        matrix[i, j] = conf if np.isnan(current) else max(current, conf)

            # Replace NaN with 0 for display
            display_matrix = np.where(np.isnan(matrix), 0.0, matrix)

            fig, ax = plt.subplots(figsize=(max(6, len(col_labels) * 1.1), max(4, len(row_labels) * 0.55)),
                                   facecolor=cls._C_BG)
            ax.set_facecolor(cls._C_BG)
            cax = ax.imshow(display_matrix, cmap="YlOrBr", aspect="auto", vmin=0, vmax=1)

            ax.set_xticks(np.arange(len(col_labels)))
            ax.set_yticks(np.arange(len(row_labels)))
            ax.set_xticklabels(col_labels, color=cls._C_TEXT, fontsize=8)
            ax.set_yticklabels(row_labels, color=cls._C_TEXT, fontsize=8)
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

            ax.set_title("Evidence Confidence by Source", fontsize=13, color=cls._C_TEXT, pad=12)
            for edge, spine in ax.spines.items():
                spine.set_color(cls._C_EDGE)

            cb = fig.colorbar(cax, ax=ax, label="Confidence Score (0–1)")
            cb.ax.yaxis.label.set_color(cls._C_TEXT)

            svg_path, png_path = cls._save_fig(fig, job_id, "heatmap")
            json_path = cls._save_json(
                {"data": display_matrix.tolist(), "rows": row_labels, "cols": col_labels},
                job_id, "heatmap"
            )

        JobLogger.log_artifact(
            artifact_id=f"art_{uuid.uuid4().hex[:8]}",
            job_id=job_id,
            type="Heatmap",
            title="Evidence Confidence Heatmap",
            description="Confidence scores for each entity per data source, derived from query provenance.",
            svg_path=svg_path,
            png_path=png_path,
            json_path=json_path,
        )

    # ── Figure 3: Target Score Waterfall ──────────────────────

    @classmethod
    def generate_waterfall(
        cls,
        job_id: str,
        top_targets: Optional[List[Dict]] = None,
    ) -> None:
        """
        Generate a target association score chart from real synthesis top_targets.

        Uses actual target names and scores returned by the RLM synthesis step.
        Falls back to an empty-state figure if no targets were produced.
        """
        targets = top_targets or []
        # Filter to entries that have both a name and a score
        valid = [t for t in targets if t.get("name") and t.get("score") is not None][:12]

        if not valid:
            fig = cls._empty_state_fig(
                "Target Association Scores",
                "No scored targets available for this query.\nThe synthesis step did not produce target rankings."
            )
            svg_path, png_path = cls._save_fig(fig, job_id, "waterfall")
            json_path = cls._save_json({"targets": [], "note": "no_data"}, job_id, "waterfall")
        else:
            names = [t["name"][:22] + ("…" if len(t.get("name", "")) > 22 else "") for t in valid]
            scores = [float(t["score"]) for t in valid]
            uncertainties = [float(t.get("uncertainty", 0.05)) for t in valid]
            colors = [cls._C_TARGET if s >= 0.5 else cls._C_DRUG for s in scores]

            fig, ax = plt.subplots(figsize=(max(6, len(valid) * 0.9), 5), facecolor=cls._C_BG)
            ax.set_facecolor(cls._C_BG)
            bars = ax.bar(names, scores, color=colors, yerr=uncertainties,
                          capsize=4, error_kw={"ecolor": cls._C_TEXT, "alpha": 0.6})
            ax.set_ylabel("Association Score", color=cls._C_TEXT, fontsize=10)
            ax.set_title("Target Association Scores (with Uncertainty)", fontsize=13,
                         color=cls._C_TEXT, pad=12)
            ax.set_ylim(0, 1.05)
            ax.tick_params(axis="x", labelrotation=35, colors=cls._C_TEXT, labelsize=8)
            ax.tick_params(axis="y", colors=cls._C_TEXT)
            ax.axhline(0.5, color=cls._C_EDGE, linestyle="--", linewidth=0.8, label="Threshold 0.5")
            ax.legend(fontsize=8, facecolor=cls._C_BG)

            for spine_name, spine in ax.spines.items():
                if spine_name in ("top", "right"):
                    spine.set_visible(False)
                else:
                    spine.set_color(cls._C_EDGE)

            svg_path, png_path = cls._save_fig(fig, job_id, "waterfall")
            json_path = cls._save_json(
                {"targets": [{"name": n, "score": s, "uncertainty": u}
                              for n, s, u in zip(names, scores, uncertainties)]},
                job_id, "waterfall"
            )

        JobLogger.log_artifact(
            artifact_id=f"art_{uuid.uuid4().hex[:8]}",
            job_id=job_id,
            type="Bar Chart",
            title="Target Association Scores",
            description="Association scores with uncertainty for top targets, derived from RLM synthesis.",
            svg_path=svg_path,
            png_path=png_path,
            json_path=json_path,
        )
