"""Decision Dossier builder — assembles a complete reproducibility report per job."""

import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from html import escape as h

from config import settings
from services.job_logger import JobLogger
from services.evidence_store import EvidenceStore


class DossierBuilder:
    """Compiles evidence, trace, rankings, contradictions, and settings into a
    structured Decision Dossier that can be exported as JSON or HTML."""

    @classmethod
    def build(cls, job_id: str) -> Optional[Dict[str, Any]]:
        """Build the dossier data structure for a job. Returns None if job not found."""
        trace = JobLogger.get_job_trace(job_id)
        if not trace:
            return None

        recipe = JobLogger.get_job_recipe(job_id)
        evidence = EvidenceStore.get_job_evidence(job_id)
        artifacts = JobLogger.get_job_artifacts(job_id)

        steps = trace.get("steps", [])

        # ── Derive sections ──────────────────────────────────────
        question = trace.get("name", "")
        constraints = cls._extract_constraints(steps)
        evidence_table = cls._build_evidence_table(steps, evidence)
        rankings = cls._build_ranking_table(steps)
        contradictions = cls._extract_contradictions(steps)
        assumptions = cls._extract_assumptions(steps)
        next_experiments = cls._suggest_next_experiments(contradictions, rankings)

        dossier: Dict[str, Any] = {
            "schema_version": "1.0",
            "job_id": job_id,
            "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
            "question": question,
            "constraints": constraints,
            "evidence": evidence_table,
            "ranking_table": rankings,
            "contradictions": contradictions,
            "assumptions_and_overrides": assumptions,
            "recommended_next_experiments": next_experiments,
            "media_artifacts": [
                {
                    "artifact_id": a.get("artifact_id"),
                    "type": a.get("type"),
                    "title": a.get("title"),
                    "description": a.get("description"),
                }
                for a in artifacts
            ],
            "run_recipe": recipe or {"note": "Recipe not recorded at run time."},
            "trace_summary": {
                "status": trace.get("status"),
                "started_at": trace.get("started_at"),
                "duration_ms": trace.get("duration_ms"),
                "steps_total": len(steps),
            },
        }
        return dossier

    # ── Section builders ──────────────────────────────────────

    @classmethod
    def _extract_constraints(cls, steps: List[Dict]) -> Dict[str, Any]:
        for s in steps:
            d = s.get("details", {})
            if d.get("action_type") == "filter":
                summary = d.get("outputs_summary", "")
                return {"applied": True, "summary": summary, "step": s.get("name")}
        return {"applied": False, "summary": "No constraints applied.", "step": None}

    @classmethod
    def _build_evidence_table(cls, steps: List[Dict], evidence: Dict) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        ref_set: set = set()

        for s in steps:
            d = s.get("details", {})
            refs = d.get("evidence_refs", [])
            for ref in refs:
                if ref in ref_set:
                    continue
                ref_set.add(ref)
                rows.append({
                    "ref": ref,
                    "source_step": s.get("name"),
                    "tool": d.get("tool_name", ""),
                    "summary": d.get("outputs_summary", ""),
                    "locator": cls._ref_to_locator(ref),
                })

        # Merge any DB evidence edges
        for edge in evidence.get("edges", []):
            loc = edge.get("source_locator", "")
            src = edge.get("source", "")
            eid = edge.get("src_entity", "")
            if eid not in ref_set:
                ref_set.add(eid)
                rows.append({
                    "ref": eid,
                    "source_step": "Evidence Store",
                    "tool": src,
                    "summary": "",
                    "locator": loc,
                })

        return rows

    @classmethod
    def _ref_to_locator(cls, ref: str) -> str:
        if ref.startswith("ref_pubmed_"):
            pmid = ref.replace("ref_pubmed_", "")
            return f"PMID:{pmid}"
        if ref.startswith("ref_ot_"):
            return f"OpenTargets:{ref.replace('ref_ot_', '')}"
        if ref.startswith("ref_chembl_"):
            return f"ChEMBL:{ref.replace('ref_chembl_', '')}"
        if "#page=" in ref:
            return ref
        return ref

    @classmethod
    def _build_ranking_table(cls, steps: List[Dict]) -> List[Dict[str, Any]]:
        """Extract ranked targets from the synthesis step's stored top_targets_ranked data."""
        for s in steps:
            d = s.get("details", {})
            if d.get("action_type") == "synthesis":
                ranked = d.get("top_targets_ranked", [])
                if ranked:
                    # Assign rank positions and return data-driven table
                    rows = []
                    for idx, item in enumerate(ranked, start=1):
                        rows.append({
                            "rank": idx,
                            "target": item.get("name", f"Target {idx}"),
                            "score": round(float(item.get("score", 0.0)), 3),
                            "uncertainty": round(float(item.get("uncertainty", 0.1)), 3),
                            "note": item.get("note", ""),
                        })
                    return rows
                # Synthesis step found but no ranked data — try top_targets strings
                top_names = d.get("top_targets", [])
                if top_names and isinstance(top_names[0], str):
                    return [
                        {"rank": idx + 1, "target": name, "score": None, "uncertainty": None, "note": "Score not computed"}
                        for idx, name in enumerate(top_names)
                    ]
        return []

    @classmethod
    def _extract_contradictions(cls, steps: List[Dict]) -> List[Dict[str, Any]]:
        contras: List[Dict[str, Any]] = []
        for s in steps:
            d = s.get("details", {})
            if d.get("action_type") == "contradiction_check" or s.get("status") == "warning":
                contras.append({
                    "step": s.get("name"),
                    "summary": d.get("outputs_summary", ""),
                    "error_detail": d.get("errors", ""),
                    "refs": d.get("evidence_refs", []),
                })
        return contras

    @classmethod
    def _extract_assumptions(cls, steps: List[Dict]) -> List[str]:
        """Derive assumptions from actual trace step metadata."""
        assumptions: List[str] = []

        # Check whether LLM was available (tool_name = llm_generator vs rule_based)
        for s in steps:
            d = s.get("details", {})
            tool = d.get("tool_name", "")
            if d.get("action_type") == "synthesis":
                if tool == "llm_generator":
                    assumptions.append(
                        f"LLM-assisted synthesis was used (tool: {tool}). "
                        "Results reflect model-guided reasoning over retrieved evidence."
                    )
                elif tool:
                    assumptions.append(
                        f"Rule-based synthesis was used (tool: {tool}) — no LLM was available. "
                        "Targets are ranked by evidence confidence only."
                    )

        # Check whether constraint filtering was applied
        for s in steps:
            d = s.get("details", {})
            if d.get("action_type") == "filter":
                summary = d.get("outputs_summary", "")
                assumptions.append(
                    f"Constraint filtering was applied at step '{s.get('name', 'Filter')}': {summary}"
                )
                break
        else:
            assumptions.append("No constraint filtering was applied — all retrieved evidence was used.")

        # Check evidence sources used
        tools_used = set()
        for s in steps:
            d = s.get("details", {})
            tool = d.get("tool_name", "")
            if tool and d.get("action_type") == "evidence_retrieval":
                tools_used.add(tool)
        if tools_used:
            assumptions.append(f"Evidence retrieved from: {', '.join(sorted(tools_used))}.")

        # Check document intelligence
        doc_search_steps = [s for s in steps if "document" in s.get("name", "").lower()]
        if doc_search_steps:
            assumptions.append("Document intelligence (FTS5/BM25) was used for local corpus search.")

        if not assumptions:
            assumptions.append("Online-only data mode: results derived from live API queries.")

        return assumptions

    @classmethod
    def _suggest_next_experiments(cls, contradictions: List[Dict], rankings: List[Dict]) -> List[str]:
        """Suggest next experiments derived from actual contradictions and real ranked targets."""
        suggestions: List[str] = []

        # Contradiction-driven suggestions — use actual contradiction summaries and refs
        for c in contradictions[:3]:
            summary = c.get("summary", "").strip()
            refs = c.get("refs", [])
            ref_str = (", ".join(refs[:4])) if refs else "no citations on record"
            step_name = c.get("step", "an evidence step")
            if summary:
                suggestions.append(
                    f"Resolve contradiction detected at '{step_name}': \"{summary[:120]}\". "
                    f"Cited refs: {ref_str}."
                )

        # Ranking-driven suggestions — use actual top target names and scores
        if rankings:
            top = rankings[0]
            target_name = top.get("target", "top target")
            score = top.get("score")
            uncertainty = top.get("uncertainty")
            score_str = f"score={score}" if score is not None else "score not computed"
            uncert_str = f", uncertainty=±{uncertainty}" if uncertainty is not None else ""
            suggestions.append(
                f"Validate top-ranked target '{target_name}' ({score_str}{uncert_str}) "
                "with in-vitro binding assay or literature review."
            )
            if len(rankings) > 1:
                second = rankings[1]
                suggestions.append(
                    f"Compare '{top.get('target')}' vs '{second.get('target')}' "
                    "with a head-to-head selectivity panel."
                )

        if not suggestions:
            suggestions.append(
                "Re-run this query with additional data sources enabled to improve evidence coverage."
            )

        return suggestions

    # ── HTML renderer ─────────────────────────────────────────

    @classmethod
    def render_html(cls, dossier: Dict[str, Any]) -> str:
        """Render the dossier dict as a self-contained HTML document."""
        sections: List[str] = []
        sections.append(cls._html_head(dossier))
        sections.append(cls._html_section("Question", f'<p class="q">{h(dossier["question"])}</p>'))
        sections.append(cls._html_constraints(dossier["constraints"]))
        sections.append(cls._html_evidence(dossier["evidence"]))
        sections.append(cls._html_rankings(dossier["ranking_table"]))
        sections.append(cls._html_contradictions(dossier["contradictions"]))
        sections.append(cls._html_list("Assumptions &amp; Overrides", dossier["assumptions_and_overrides"]))
        sections.append(cls._html_list("Recommended Next Experiments", dossier["recommended_next_experiments"]))
        sections.append(cls._html_recipe(dossier["run_recipe"]))
        sections.append(cls._html_trace_summary(dossier["trace_summary"]))
        sections.append("</div></body></html>")
        return "\n".join(sections)

    @classmethod
    def _html_head(cls, d: Dict) -> str:
        return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Decision Dossier — {h(d['job_id'])}</title>
<style>
  :root {{ --bg: #faf8f5; --surface: #fff; --text: #4a3b32; --muted: #78685d;
           --accent: #c2614b; --border: #e6dfd5; --font: 'Inter', sans-serif; }}
  body {{ font-family: var(--font); background: var(--bg); color: var(--text);
          margin: 0; padding: 2rem; line-height: 1.6; }}
  .wrap {{ max-width: 860px; margin: 0 auto; }}
  h1 {{ font-size: 1.5rem; border-bottom: 2px solid var(--accent); padding-bottom: .5rem; }}
  h2 {{ font-size: 1.1rem; margin-top: 2rem; color: var(--accent); }}
  table {{ width: 100%; border-collapse: collapse; margin: .75rem 0; font-size: .85rem; }}
  th, td {{ text-align: left; padding: .5rem .75rem; border-bottom: 1px solid var(--border); }}
  th {{ background: var(--bg); font-weight: 600; text-transform: uppercase; font-size: .7rem;
       letter-spacing: .05em; color: var(--muted); }}
  .q {{ font-size: 1.15rem; font-weight: 600; }}
  .badge {{ display: inline-block; padding: .15rem .5rem; border-radius: 4px; font-size: .7rem;
            font-weight: 700; text-transform: uppercase; }}
  .badge-ok {{ background: #ecfdf5; color: #065f46; }}
  .badge-warn {{ background: #fff7ed; color: #9a3412; }}
  .meta {{ color: var(--muted); font-size: .8rem; }}
  ul {{ padding-left: 1.25rem; }}
  li {{ margin-bottom: .4rem; }}
  pre {{ background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
         padding: 1rem; overflow-x: auto; font-size: .8rem; }}
  @media print {{ body {{ padding: 0; }} }}
</style>
</head><body><div class="wrap">
<h1>Decision Dossier</h1>
<p class="meta">Job <code>{h(d['job_id'])}</code> &middot; Generated {h(d['generated_at'])}</p>"""

    @classmethod
    def _html_section(cls, title: str, body: str) -> str:
        return f"<h2>{title}</h2>\n{body}"

    @classmethod
    def _html_constraints(cls, c: Dict) -> str:
        badge = '<span class="badge badge-ok">Applied</span>' if c["applied"] else '<span class="badge badge-warn">None</span>'
        return cls._html_section("Constraints", f"{badge} {h(c['summary'])}")

    @classmethod
    def _html_evidence(cls, rows: List[Dict]) -> str:
        if not rows:
            return cls._html_section("Evidence", "<p>No evidence collected.</p>")
        header = "<tr><th>Ref</th><th>Source Step</th><th>Tool</th><th>Summary</th><th>Locator</th></tr>"
        body = ""
        for r in rows:
            body += f"<tr><td><code>{h(r['ref'])}</code></td><td>{h(r['source_step'])}</td><td>{h(r['tool'])}</td><td>{h(r['summary'])}</td><td>{h(r['locator'])}</td></tr>\n"
        return cls._html_section("Evidence with Citations", f"<table>{header}{body}</table>")

    @classmethod
    def _html_rankings(cls, rows: List[Dict]) -> str:
        if not rows:
            return cls._html_section("Ranking Table", "<p>No rankings produced.</p>")
        header = "<tr><th>#</th><th>Target</th><th>Score</th><th>Uncertainty</th><th>Note</th></tr>"
        body = ""
        for r in rows:
            body += f"<tr><td>{r['rank']}</td><td><strong>{h(r['target'])}</strong></td><td>{r['score']}</td><td>&plusmn;{r['uncertainty']}</td><td>{h(r['note'])}</td></tr>\n"
        return cls._html_section("Ranking Table (with Uncertainty)", f"<table>{header}{body}</table>")

    @classmethod
    def _html_contradictions(cls, items: List[Dict]) -> str:
        if not items:
            return cls._html_section("Contradictions", "<p>None detected.</p>")
        parts: List[str] = []
        for c in items:
            refs_str = ", ".join(f"<code>{h(r)}</code>" for r in c.get("refs", []))
            parts.append(f'<li><strong>{h(c["step"])}</strong>: {h(c["summary"])}<br>'
                         f'<span class="meta">Detail: {h(c["error_detail"])}</span><br>'
                         f'<span class="meta">Refs: {refs_str}</span></li>')
        return cls._html_section("Contradictions &amp; Warnings", f"<ul>{''.join(parts)}</ul>")

    @classmethod
    def _html_list(cls, title: str, items: List[str]) -> str:
        if not items:
            return cls._html_section(title, "<p>None.</p>")
        li = "".join(f"<li>{h(i)}</li>" for i in items)
        return cls._html_section(title, f"<ul>{li}</ul>")

    @classmethod
    def _html_recipe(cls, recipe: Dict) -> str:
        return cls._html_section("Run Recipe Reference", f"<pre>{h(json.dumps(recipe, indent=2, default=str))}</pre>")

    @classmethod
    def _html_trace_summary(cls, ts: Dict) -> str:
        badge = "badge-ok" if ts.get("status") == "completed" else "badge-warn"
        return cls._html_section("Trace Summary",
            f'<p>Status: <span class="badge {badge}">{h(str(ts.get("status", "")))}</span> &middot; '
            f'Duration: {ts.get("duration_ms", 0)}ms &middot; '
            f'Steps: {ts.get("steps_total", 0)} &middot; '
            f'Started: {h(str(ts.get("started_at", "")))}</p>')
