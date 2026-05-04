"""Decision Dossier builder — assembles a complete reproducibility report per job."""

import json
import os
import uuid as _uuid_mod
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from html import escape as h

import structlog
from config import settings
from services.job_logger import JobLogger
from services.evidence_store import EvidenceStore

_log = structlog.get_logger(__name__)


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

    @classmethod
    async def build_from_project(
        cls,
        project_id: str,
        evidence_bundle_ids: Optional[List[str]] = None,
        target_ranking_id: Optional[str] = None,
        disease_run_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Build a dossier from project-level data (§A10, §129).

        Queries the runs table for all runs belonging to the project,
        collects evidence, target rankings and disease results, and
        compiles them into a structured dossier.
        """
        from core.db import AsyncSessionLocal
        from models.db_tables import Run, DossierRecord
        from sqlalchemy import select

        async with AsyncSessionLocal() as session:
            # Gather all project runs
            stmt = select(Run).where(Run.project_id == project_id).order_by(Run.created_at.desc())
            result = await session.execute(stmt)
            runs = result.scalars().all()

        if not runs:
            _log.warning("build_from_project_no_runs", project_id=project_id)

        # Auto-discover target_ranking_id and disease_run_id from runs if not provided
        if not target_ranking_id:
            for run in runs:
                if run.run_type and "target" in run.run_type.lower():
                    target_ranking_id = str(run.id)
                    break
        if not disease_run_id:
            for run in runs:
                if run.run_type and "disease" in run.run_type.lower():
                    disease_run_id = str(run.id)
                    break

        # Compile evidence from evidence store for each run
        evidence_items: List[Dict[str, Any]] = []
        source_footprint: set = set()
        for run in runs:
            run_evidence = EvidenceStore.get_job_evidence(str(run.id))
            if run_evidence:
                for edge in run_evidence.get("edges", []):
                    evidence_items.append({
                        "ref": edge.get("src_entity", ""),
                        "source_step": f"Run {run.run_type}",
                        "tool": edge.get("source", ""),
                        "summary": edge.get("summary", ""),
                        "locator": edge.get("source_locator", ""),
                    })
                    source_footprint.add(edge.get("source", "unknown"))

        # Compile target rankings if available
        ranking_table: List[Dict[str, Any]] = []
        if target_ranking_id:
            # Try to load from target_rankings table directly (preferred source)
            try:
                from models.db_tables import TargetRanking
                async with AsyncSessionLocal() as session:
                    from sqlalchemy import select as sa_select
                    stmt = sa_select(TargetRanking).where(TargetRanking.run_id == target_ranking_id).order_by(TargetRanking.rank.asc())
                    result = await session.execute(stmt)
                    tr_rows = result.scalars().all()
                    for r in tr_rows:
                        ucb = float(r.ucb_score or r.composite_score or 0)
                        comp = float(r.composite_score or 0)
                        ranking_table.append({
                            "rank": r.rank,
                            "target": r.gene_symbol,
                            "score": round(comp, 3),
                            "ucb_score": round(ucb, 3),
                            "uncertainty": round(abs(ucb - comp), 3),
                            "note": r.explanation or "all signals live",
                        })
            except Exception as rank_err:
                _log.warning("dossier_ranking_load_failed", error=str(rank_err))
            # Fallback: try run output_artifacts
            if not ranking_table:
                for run in runs:
                    oa = run.output_artifacts
                    if str(run.id) == target_ranking_id and oa and isinstance(oa, dict):
                        ranked = oa.get("ranked_targets", [])
                        for idx, t in enumerate(ranked, 1):
                            ranking_table.append({
                                "rank": idx,
                                "target": t.get("symbol", f"Target {idx}"),
                                "score": round(float(t.get("composite_score", 0)), 3),
                                "uncertainty": round(float(t.get("ucb_score", 0) - t.get("composite_score", 0)), 3),
                                "note": ", ".join(t.get("degraded_signals", [])) or "all signals live",
                            })

        # Compile disease results if available
        disease_summary = ""
        if disease_run_id:
            # Try to load from disease_candidate_genes table directly
            try:
                from models.db_tables import DiseaseQuery, DiseaseCandidateGene
                async with AsyncSessionLocal() as session:
                    from sqlalchemy import select as sa_select
                    dq_stmt = sa_select(DiseaseQuery).where(DiseaseQuery.run_id == disease_run_id)
                    dq_result = await session.execute(dq_stmt)
                    dq = dq_result.scalar_one_or_none()
                    if dq:
                        gene_stmt = sa_select(DiseaseCandidateGene).where(
                            DiseaseCandidateGene.disease_query_id == dq.id
                        ).order_by(DiseaseCandidateGene.score.desc()).limit(10)
                        gene_result = await session.execute(gene_stmt)
                        genes = gene_result.scalars().all()
                        if genes:
                            gene_names = [g.gene_symbol for g in genes]
                            disease_summary = f"Disease: {dq.normalized_label or dq.raw_input}. Top candidate genes: {', '.join(gene_names)}"
            except Exception as dis_err:
                _log.warning("dossier_disease_load_failed", error=str(dis_err))
            # Fallback: try run output_artifacts
            if not disease_summary:
                for run in runs:
                    oa = run.output_artifacts
                    if str(run.id) == disease_run_id and oa and isinstance(oa, dict):
                        genes = oa.get("genes", [])
                        if genes:
                            gene_names = [g.get("symbol", "") for g in genes[:10]]
                            disease_summary = f"Top candidate genes: {', '.join(gene_names)}"

        # Build evidence bundle subset if specified
        if evidence_bundle_ids:
            _log.info("build_from_project_bundle_filter", bundles=evidence_bundle_ids)

        # Derive contradictions from runs with warnings
        contradictions: List[Dict[str, Any]] = []
        for run in runs:
            oa = run.output_artifacts
            if oa and isinstance(oa, dict) and oa.get("warnings"):
                contradictions.append({
                    "step": f"Run {run.run_type} ({run.id})",
                    "summary": "; ".join(oa["warnings"]),
                    "error_detail": "",
                    "refs": [],
                })

        # Build assumptions
        assumptions = [
            f"Dossier assembled from {len(runs)} project run(s).",
            f"Evidence collected from {len(source_footprint)} unique source(s): {', '.join(sorted(source_footprint)) or 'none'}.",
        ]
        if not target_ranking_id:
            assumptions.append("No target ranking run was specified for this dossier.")
        if not disease_run_id:
            assumptions.append("No disease intelligence run was specified for this dossier.")

        next_experiments = cls._suggest_next_experiments(contradictions, ranking_table)

        now_iso = datetime.now(timezone.utc).isoformat() + "Z"
        dossier: Dict[str, Any] = {
            "schema_version": "1.0",
            "project_id": project_id,
            "generated_at": now_iso,
            "objective": f"Decision Dossier for project {project_id}",
            "evidence_summary": evidence_items,
            "ranked_options": ranking_table,
            "contradictions": contradictions,
            "assumptions_and_overrides": assumptions,
            "recommendations": next_experiments,
            "provenance": cls._build_provenance_appendix(
                steps=steps,
                runs=runs,
                source_footprint=source_footprint,
                contradictions=contradictions,
                project_id=project_id,
                now_iso=now_iso,
            ),
            "disease_summary": disease_summary,
            # Include all section names expected by the router
            "objective_text": f"Decision Dossier for project {project_id}",
            "evidence": evidence_items,
            "ranking_table": ranking_table,
            "source_footprint": list(source_footprint),
            "title": f"Decision Dossier — {project_id[:8]}",
        }
        return dossier

    # ── Section builders ──────────────────────────────────────

    @classmethod
    def _build_provenance_appendix(
        cls,
        steps: List[Dict],
        runs: list,
        source_footprint: set,
        contradictions: List[Dict],
        project_id: str,
        now_iso: str,
    ) -> Dict[str, Any]:
        """Build provenance appendix (§D5): MD5 hashes, API query log, MAV jury, run metadata."""
        import hashlib

        # MD5 hash for each cited source document (content or URL)
        source_hashes: List[Dict[str, str]] = []
        seen_urls: set = set()
        for step in steps:
            d = step.get("details", {})
            for ref in d.get("evidence_refs", []):
                url = d.get("source_url", ref)
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                content = d.get("content") or url
                md5 = hashlib.md5(str(content).encode("utf-8", errors="replace")).hexdigest()
                source_hashes.append({"ref": ref, "url": url, "md5": md5})

        # API query log: URL + timestamp from trace steps
        api_queries: List[Dict[str, str]] = []
        for step in steps:
            d = step.get("details", {})
            url = d.get("source_url") or d.get("api_url") or d.get("tool_url") or ""
            ts = step.get("timestamp") or now_iso
            if url:
                api_queries.append({"url": url, "timestamp": ts})

        # MAV jury votes: extract specialist agent verdicts per claim
        mav_jury: List[Dict[str, Any]] = []
        for ctr in contradictions:
            claim = ctr.get("claim") or ctr.get("statement") or ctr.get("summary", "")
            agents = ctr.get("agents") or ctr.get("jury") or []
            if isinstance(agents, list) and agents:
                votes = agents
            else:
                # Derive from source/target fields if present
                votes = [
                    {"agent": "agent_a", "verdict": ctr.get("source_verdict", "uncertain")},
                    {"agent": "agent_b", "verdict": ctr.get("target_verdict", "uncertain")},
                    {"agent": "agent_c", "verdict": "uncertain"},
                ]
            mav_jury.append({"claim": claim[:200], "votes": votes[:3]})

        # Run metadata
        run_metadata: List[Dict[str, Any]] = []
        for r in runs:
            run_metadata.append({
                "run_id": str(getattr(r, "id", "")),
                "model_used": getattr(r, "model_used", "") or getattr(r, "agent_model", "") or "",
                "duration_ms": getattr(r, "duration_ms", None),
                "created_at": str(getattr(r, "created_at", "") or ""),
            })

        return {
            "source_footprint": list(source_footprint),
            "run_count": len(runs),
            "generated_at": now_iso,
            "project_id": project_id,
            "source_document_hashes": source_hashes,
            "api_query_log": api_queries,
            "mav_jury_votes": mav_jury,
            "run_metadata": run_metadata,
        }

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

    # ── E-7: Indian Population Insight section ────────────────

    @classmethod
    async def build_indian_population_section(
        cls,
        project_id: str,
        disease: str = "",
    ) -> Dict[str, Any]:
        """E-7: Build 'Indian Regulatory & Population Context' section for the dossier.

        Queries EvidenceItemRecord where indian_population_relevant=True for
        the given project, then structures results for the dossier template.
        """
        from core.db import AsyncSessionLocal
        from models.db_tables import EvidenceItemRecord
        from sqlalchemy import select as sa_select

        trials: list = []
        variants: list = []
        cdsco_items: list = []
        warnings: list = []

        try:
            async with AsyncSessionLocal() as session:
                stmt = (
                    sa_select(EvidenceItemRecord)
                    .where(
                        EvidenceItemRecord.project_id == project_id,
                        EvidenceItemRecord.indian_population_relevant.is_(True),
                    )
                    .order_by(EvidenceItemRecord.retrieved_at.desc())
                    .limit(100)
                )
                result = await session.execute(stmt)
                rows = result.scalars().all()

                for r in rows:
                    src = (r.source_name or "").upper()
                    item = {
                        "id": r.id,
                        "title": r.title or "",
                        "source": r.source_name,
                        "confidence": r.confidence,
                        "url": (r.metadata_json or {}).get("url", ""),
                    }
                    if "CTRI" in src:
                        trials.append(item)
                    elif "CDSCO" in src:
                        cdsco_items.append(item)
                    else:
                        variants.append(item)
        except Exception as exc:
            warnings.append(f"Indian population DB query failed: {exc}")

        # If disease provided, also try live CTRI fetch for completeness
        if disease and not trials:
            try:
                from services.specialists.indian_population_specialist import IndianPopulationSpecialist
                specialist = IndianPopulationSpecialist()
                live_result = await specialist.analyze(target_id="", disease=disease, limit=10, submit_vote=False)
                trials = live_result.get("trials", [])
                variants = live_result.get("variants", [])
            except Exception as exc:
                warnings.append(f"Live Indian population fetch failed: {exc}")

        return {
            "section_id": "indian_population_context",
            "title": "Indian Regulatory & Population Context",
            "description": (
                "Evidence sourced from Indian-specific databases: CTRI, CDSCO, IndiGen, "
                "GenomeAsia 100K, and IGVDB. Provides context on Indian regulatory status "
                "and population-specific genomic variants."
            ),
            "ctri_trials": trials,
            "cdsco_approvals": cdsco_items,
            "population_variants": variants,
            "total_evidence": len(trials) + len(cdsco_items) + len(variants),
            "disease": disease or "unspecified",
            "warnings": warnings,
        }

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

        # Objective / Question
        question = dossier.get("question") or dossier.get("objective_text") or dossier.get("objective") or ""
        if question:
            sections.append(cls._html_section("Objective", f'<p class="q">{h(str(question))}</p>'))

        # Disease summary
        disease = dossier.get("disease_summary", "")
        if disease:
            sections.append(cls._html_section("Disease Summary", f"<p>{h(str(disease))}</p>"))

        # Constraints
        constraints = dossier.get("constraints")
        if constraints and isinstance(constraints, dict):
            sections.append(cls._html_constraints(constraints))

        # Evidence
        evidence = dossier.get("evidence") or dossier.get("evidence_summary") or []
        sections.append(cls._html_evidence(evidence))

        # Rankings
        rankings = dossier.get("ranking_table") or dossier.get("ranked_options") or []
        sections.append(cls._html_rankings(rankings))

        # Contradictions
        contradictions = dossier.get("contradictions") or []
        sections.append(cls._html_contradictions(contradictions))

        # Assumptions
        assumptions = dossier.get("assumptions_and_overrides") or []
        sections.append(cls._html_list("Assumptions &amp; Overrides", assumptions))

        # Recommendations
        recs = dossier.get("recommendations") or dossier.get("recommended_next_experiments") or []
        sections.append(cls._html_list("Recommendations", recs))

        # Run recipe (optional)
        recipe = dossier.get("run_recipe")
        if recipe:
            sections.append(cls._html_recipe(recipe))

        # Trace summary (optional)
        trace = dossier.get("trace_summary")
        if trace:
            sections.append(cls._html_trace_summary(trace))

        # Provenance
        prov = dossier.get("provenance") or {}
        if prov:
            sections.append(cls._html_section("Provenance",
                f'<p class="meta">Runs: {prov.get("run_count", "—")} &middot; '
                f'Generated: {h(str(prov.get("generated_at", "—")))}</p>'))

        sections.append("</div></body></html>")
        return "\n".join(sections)

    @classmethod
    def _html_head(cls, d: Dict) -> str:
        title = d.get("title") or d.get("job_id") or "Decision Dossier"
        job_id = d.get("job_id") or d.get("project_id") or "—"
        generated = d.get("generated_at") or ""
        return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Decision Dossier — {h(str(title))}</title>
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
<h1>{h(str(title))}</h1>
<p class="meta">ID <code>{h(str(job_id))}</code> &middot; Generated {h(str(generated))}</p>"""

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
        # Handle both legacy format (ref/source_step/tool/summary/locator) and new format
        header_cols = []
        if rows and "ref" in rows[0]:
            header_cols = ["Ref", "Source Step", "Tool", "Summary", "Locator"]
        else:
            header_cols = ["#", "Source", "Summary"]
        header = "<tr>" + "".join(f"<th>{c}</th>" for c in header_cols) + "</tr>"
        body = ""
        for i, r in enumerate(rows):
            if "ref" in r:
                body += f"<tr><td><code>{h(str(r.get('ref','')))}</code></td><td>{h(str(r.get('source_step','')))}</td><td>{h(str(r.get('tool','')))}</td><td>{h(str(r.get('summary','')))}</td><td>{h(str(r.get('locator','')))}</td></tr>\n"
            else:
                source = r.get("source") or r.get("title") or f"Item {i+1}"
                summary = r.get("summary") or r.get("description") or str(r)
                body += f"<tr><td>{i+1}</td><td>{h(str(source))}</td><td>{h(str(summary))}</td></tr>\n"
        return cls._html_section("Evidence with Citations", f"<table>{header}{body}</table>")

    @classmethod
    def _html_rankings(cls, rows: List[Dict]) -> str:
        if not rows:
            return cls._html_section("Ranking Table", "<p>No rankings produced.</p>")
        has_ucb = any(r.get("ucb_score") for r in rows)
        if has_ucb:
            header = "<tr><th>#</th><th>Target</th><th>Score</th><th>UCB Score</th><th>Uncertainty</th><th>Note</th></tr>"
        else:
            header = "<tr><th>#</th><th>Target</th><th>Score</th><th>Uncertainty</th><th>Note</th></tr>"
        body = ""
        for r in rows:
            rank = r.get("rank", "")
            target = r.get("target", "")
            score = r.get("score", "")
            uncertainty = r.get("uncertainty", "")
            note = r.get("note", "")
            if has_ucb:
                ucb = r.get("ucb_score", "")
                body += f"<tr><td>{rank}</td><td><strong>{h(str(target))}</strong></td><td>{score}</td><td>{ucb}</td><td>&plusmn;{uncertainty}</td><td>{h(str(note))}</td></tr>\n"
            else:
                body += f"<tr><td>{rank}</td><td><strong>{h(str(target))}</strong></td><td>{score}</td><td>&plusmn;{uncertainty}</td><td>{h(str(note))}</td></tr>\n"
        return cls._html_section("Ranking Table (with Uncertainty)", f"<table>{header}{body}</table>")

    @classmethod
    def _html_contradictions(cls, items: List) -> str:
        if not items:
            return cls._html_section("Contradictions", "<p>None detected.</p>")
        parts: List[str] = []
        for c in items:
            if isinstance(c, dict):
                refs = c.get("refs", [])
                refs_str = ", ".join(f"<code>{h(str(r))}</code>" for r in refs) if refs else ""
                step = c.get("step") or c.get("title") or "—"
                summary = c.get("summary") or c.get("description") or c.get("error_detail") or str(c)
                detail = c.get("error_detail", "")
                parts.append(f'<li><strong>{h(str(step))}</strong>: {h(str(summary))}'
                             + (f'<br><span class="meta">Detail: {h(str(detail))}</span>' if detail else "")
                             + (f'<br><span class="meta">Refs: {refs_str}</span>' if refs_str else "")
                             + '</li>')
            else:
                parts.append(f"<li>{h(str(c))}</li>")
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
