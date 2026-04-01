"""Recursive Language Model (RLM) engine for long-horizon scientific workflows.

Replaces the simulation-only version with real LLM calls, real connector
searches, contradiction detection, and document intelligence.  Falls back
gracefully when the LLM runtime is unavailable.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from services.job_logger import JobLogger

logger = logging.getLogger(__name__)
log = logging.getLogger(__name__)


class RLMEngine:
    """Multi-step recursive reasoning orchestrator.

    Steps:
      1. Planning — LLM decomposes query into sub-tasks (keyword fallback)
      2. Evidence Retrieval — ``execute_search()`` per sub-task
      3. Constraint Filtering — exclude/require from user constraints
      4. Counter-Evidence — ``detect_contradictions()``
      5. Document Search — ``DocTreeService.search_nodes()``
      6. Synthesis — LLM summary (rule-based fallback)
      7. Figure Generation — matplotlib artifacts
    """

    def __init__(
        self,
        query: str,
        constraints: Dict[str, Any],
        project_id: Optional[str] = None,
    ):
        self.query = query
        self.constraints = constraints
        self.project_id = project_id
        self.max_steps = 10
        self.current_step = 0
        self.memory: List[Dict[str, Any]] = []
        self.evidence_refs: List[str] = []

    # ── helpers ────────────────────────────────────────────────

    @staticmethod
    def _get_runtime():
        """Return the active LLM runtime or ``None`` if unavailable."""
        try:
            from services.runtime.selector import RuntimeSelector

            runtime = RuntimeSelector.get_active_runtime()
            health = runtime.health_check()
            if isinstance(health, dict) and health.get("status") == "PASS":
                return runtime
        except Exception:
            log.debug("Runtime health check failed during resolution")
        return None

    async def _llm_call(
        self,
        messages: List[Dict[str, str]],
        fallback: str = "",
    ) -> str:
        """Attempt an LLM chat call; return *fallback* on any failure."""
        runtime = self._get_runtime()
        if runtime is None:
            return fallback
        try:
            result = await runtime.chat(messages)
            if isinstance(result, str):
                return result
            return str(result)
        except Exception as exc:
            logger.debug("LLM call failed: %s", exc)
            return fallback

    def _log_step(
        self,
        job_logger: JobLogger,
        step_name: str,
        status: str,
        duration_ms: int,
        details: Dict[str, Any],
        step_queue: Optional[asyncio.Queue] = None,
    ) -> None:
        """Log a step and optionally push to the SSE queue."""
        self.current_step += 1
        job_logger.log_step(
            step_name=step_name,
            status=status,
            duration_ms=duration_ms,
            details=details,
        )
        self.memory.append({"step": step_name, "status": status})
        if step_queue is not None:
            try:
                step_queue.put_nowait({
                    "type": "step",
                    "step": self.current_step,
                    "name": step_name,
                    "status": status,
                    "duration_ms": duration_ms,
                })
            except Exception:
                log.debug("Failed to push step update to queue")

    # ── individual phases ──────────────────────────────────────

    async def _plan_subtasks(self) -> List[str]:
        """Use LLM to decompose query, or fall back to keyword split."""
        prompt = (
            "Decompose this biomedical research query into 2-4 specific "
            "search sub-tasks.  Return ONLY a JSON array of strings.\n\n"
            f"Query: {self.query}"
        )
        response = await self._llm_call(
            [
                {"role": "system", "content": "You are a biomedical research assistant."},
                {"role": "user", "content": prompt},
            ],
            fallback="",
        )
        if response:
            try:
                start = response.find("[")
                end = response.rfind("]")
                if start >= 0 and end > start:
                    parsed = json.loads(response[start : end + 1])
                    if isinstance(parsed, list) and all(isinstance(s, str) for s in parsed):
                        return parsed[:4]
            except (json.JSONDecodeError, ValueError):
                pass

        # Keyword fallback: split on common conjunctions / semicolons
        parts = re.split(r"\band\b|\bor\b|;|,", self.query, flags=re.IGNORECASE)
        subtasks = [p.strip() for p in parts if p.strip()]
        return subtasks[:4] if subtasks else [self.query]

    async def _gather_evidence(
        self,
        subtasks: List[str],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Run ``execute_search()`` per subtask and merge entity dicts."""
        from services.search_engine import execute_search

        merged: Dict[str, List[Dict[str, Any]]] = {}
        seen_ids: set = set()
        sources: List[str] = []

        for task in subtasks[:3]:
            try:
                envelope = await execute_search(task, limit=10)
                for cat_name, cat in envelope.categories.items():
                    etype = cat_name.rstrip("s")  # "proteins" → "protein"
                    if etype not in merged:
                        merged[etype] = []
                    for row in cat.rows:
                        eid = row.get("id", "")
                        if eid and eid not in seen_ids:
                            seen_ids.add(eid)
                            merged[etype].append(row)
                sources.extend(envelope.provenance.get("sources_hit", []))
                # Collect evidence refs
                for ref in (envelope.evidence_summary or {}).get("top_citations", []):
                    eid = ref.get("external_id", "")
                    if eid:
                        self.evidence_refs.append(eid)
            except Exception as exc:
                logger.warning("Sub-search '%s' failed: %s", task, exc)

        return merged

    def _apply_constraints(
        self,
        entities: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Filter entities by user-specified exclude / require constraints."""
        exclude_terms = [t.lower() for t in self.constraints.get("exclude", [])]
        require_terms = [t.lower() for t in self.constraints.get("require", [])]

        filtered: Dict[str, List[Dict[str, Any]]] = {}
        removed = 0
        for etype, ents in entities.items():
            kept: List[Dict[str, Any]] = []
            for ent in ents:
                name = str(ent.get("name", "") or ent.get("canonical_name", "")).lower()
                desc = str(ent.get("description", "") or ent.get("function_description", "")).lower()
                text = f"{name} {desc}"

                if any(ex in text for ex in exclude_terms):
                    removed += 1
                    continue
                if require_terms and not any(req in text for req in require_terms):
                    removed += 1
                    continue
                kept.append(ent)
            if kept:
                filtered[etype] = kept

        logger.debug("Constraint filter removed %d entities", removed)
        return filtered

    async def _check_contradictions(
        self,
        entities: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Run contradiction detection on gathered evidence."""
        try:
            from services.contradiction_detector import detect_contradictions

            return await detect_contradictions(entities, self.query)
        except Exception as exc:
            logger.debug("Contradiction check skipped: %s", exc)
            return []

    def _search_documents(self) -> List[Dict[str, Any]]:
        """Search uploaded documents via DocTreeService (sync, FTS5)."""
        try:
            from services.doc_tree import DocTreeService

            results = DocTreeService.search_nodes(self.query, limit=5)
            for r in results:
                ref = f"{r.get('doc_id', '')}#page={r.get('page_start', '')}"
                self.evidence_refs.append(ref)
            return results
        except Exception as exc:
            logger.debug("Doc search skipped: %s", exc)
            return []

    async def _synthesize(
        self,
        entities: Dict[str, List[Dict[str, Any]]],
        contradictions: List[Dict[str, Any]],
        doc_hits: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Produce final synthesis via LLM or rule-based fallback."""
        # Collect all entity names sorted by confidence
        all_entities_flat: List[Dict[str, Any]] = []
        for ents in entities.values():
            all_entities_flat.extend(ents)
        all_entities_flat.sort(key=lambda e: e.get("_confidence", 0), reverse=True)

        top_names = []
        top_ranked = []  # structured: {name, score, uncertainty}
        seen = set()
        for ent in all_entities_flat:
            name = ent.get("canonical_name") or ent.get("name") or ent.get("id", "")
            if name and name not in seen:
                seen.add(name)
                top_names.append(name)
                conf = float(ent.get("_confidence", 0.0))
                # Uncertainty is inverse of confidence variance proxy
                uncertainty = round(max(0.01, min(0.3, 0.15 - conf * 0.1)), 3)
                top_ranked.append({"name": name, "score": round(conf, 3), "uncertainty": uncertainty})
            if len(top_names) >= 10:
                break

        warnings: List[str] = []
        for c in contradictions:
            warnings.append(
                f"Contradiction ({c.get('severity', 'moderate')}): "
                f"{c.get('explanation', 'Conflicting evidence found')}"
            )

        # Try LLM synthesis
        runtime = self._get_runtime()
        if runtime and all_entities_flat:
            entity_summary = "\n".join(
                f"- {e.get('name', e.get('id', '?'))}: {str(e.get('description', ''))[:100]}"
                for e in all_entities_flat[:15]
            )
            contra_summary = "\n".join(
                f"- {c.get('explanation', '')}" for c in contradictions[:5]
            ) or "None found."
            doc_summary = "\n".join(
                f"- {d.get('title', d.get('section_path', ''))}: {str(d.get('summary', ''))[:100]}"
                for d in doc_hits[:5]
            ) or "No documents searched."

            prompt = (
                f"Synthesize findings for: {self.query}\n\n"
                f"Top entities found:\n{entity_summary}\n\n"
                f"Contradictions:\n{contra_summary}\n\n"
                f"Document hits:\n{doc_summary}\n\n"
                "Provide a concise (3-5 sentence) scientific synthesis of the "
                "key findings.  Highlight the most promising targets and note "
                "any contradictions that require further investigation."
            )
            llm_text = await self._llm_call(
                [
                    {"role": "system", "content": "You are a biomedical research assistant."},
                    {"role": "user", "content": prompt},
                ],
                fallback="",
            )
            if llm_text:
                return {
                    "top_targets": top_names[:5],
                    "top_targets_ranked": top_ranked[:5],
                    "warnings": warnings,
                    "synthesis": llm_text,
                }

        # Rule-based fallback
        if top_names:
            synthesis = (
                f"Found {len(all_entities_flat)} entities across "
                f"{len(entities)} categories for '{self.query}'. "
                f"Top results: {', '.join(top_names[:5])}."
            )
            if contradictions:
                synthesis += f" {len(contradictions)} contradiction(s) detected."
            if doc_hits:
                synthesis += f" {len(doc_hits)} document(s) contained relevant information."
        else:
            synthesis = f"No results found for '{self.query}'."

        return {
            "top_targets": top_names[:5],
            "top_targets_ranked": top_ranked[:5],
            "warnings": warnings,
            "synthesis": synthesis,
        }

    # ── main run loop ──────────────────────────────────────────

    async def run(
        self,
        job_logger: JobLogger,
        step_queue: Optional[asyncio.Queue] = None,
    ) -> Dict[str, Any]:
        """Execute the full recursive reasoning loop."""
        llm_available = self._get_runtime() is not None

        # 1. Planning
        t0 = time.monotonic()
        subtasks = await self._plan_subtasks()
        dur = int((time.monotonic() - t0) * 1000)
        self._log_step(
            job_logger, "Query Decomposition & Planning", "success", dur,
            {
                "action_type": "plan",
                "tool_name": "internal_planner" if not llm_available else "llm_planner",
                "inputs_hash": hash(self.query),
                "outputs_summary": f"Decomposed into {len(subtasks)} sub-task(s): {subtasks}",
                "llm_used": llm_available,
                "evidence_refs": [],
            },
            step_queue,
        )

        # 2. Evidence Retrieval
        t0 = time.monotonic()
        all_entities = await self._gather_evidence(subtasks)
        dur = int((time.monotonic() - t0) * 1000)
        total_found = sum(len(v) for v in all_entities.values())
        self._log_step(
            job_logger, "Evidence Retrieval", "success", dur,
            {
                "action_type": "tool_call",
                "tool_name": "multi_source_search",
                "inputs_hash": hash(str(subtasks)),
                "outputs_summary": f"Found {total_found} entities across {len(all_entities)} categories.",
                "evidence_refs": self.evidence_refs[:10],
            },
            step_queue,
        )

        # 3. Constraint Filtering
        t0 = time.monotonic()
        before_count = sum(len(v) for v in all_entities.values())
        filtered_entities = self._apply_constraints(all_entities)
        after_count = sum(len(v) for v in filtered_entities.values())
        dur = int((time.monotonic() - t0) * 1000)
        exclude_list = self.constraints.get("exclude", [])
        self._log_step(
            job_logger, "Constraint Filtering", "success", dur,
            {
                "action_type": "filter",
                "tool_name": "constraint_filter",
                "inputs_hash": hash(",".join(exclude_list)),
                "outputs_summary": (
                    f"Filtered {before_count} → {after_count} entities. "
                    f"Excluded: {exclude_list or 'none'}."
                ),
                "evidence_refs": [],
            },
            step_queue,
        )

        # 4. Counter-Evidence Analysis
        t0 = time.monotonic()
        contradictions = await self._check_contradictions(filtered_entities)
        dur = int((time.monotonic() - t0) * 1000)
        status = "warning" if contradictions else "success"
        self._log_step(
            job_logger, "Counter-Evidence Analysis", status, dur,
            {
                "action_type": "contradiction_check",
                "tool_name": "contradiction_detector",
                "inputs_hash": hash(self.query),
                "outputs_summary": (
                    f"Found {len(contradictions)} contradiction(s)."
                    + (f" Severities: {[c.get('severity') for c in contradictions]}" if contradictions else "")
                ),
                "evidence_refs": [
                    c.get("source_a", {}).get("external_id", "")
                    for c in contradictions[:5]
                ],
            },
            step_queue,
        )

        # 5. Document Intelligence
        t0 = time.monotonic()
        doc_hits = self._search_documents()
        dur = int((time.monotonic() - t0) * 1000)
        self._log_step(
            job_logger, "Document Intelligence (Doc-Tree)", "success", dur,
            {
                "action_type": "tool_call",
                "tool_name": "doc_tree_search",
                "inputs_hash": hash(self.query),
                "outputs_summary": (
                    f"Found {len(doc_hits)} document section(s)."
                    + (f" Top: {doc_hits[0].get('title', '')[:60]}" if doc_hits else "")
                ),
                "evidence_refs": [
                    f"{d.get('doc_id', '')}#page={d.get('page_start', '')}"
                    for d in doc_hits[:5]
                ],
            },
            step_queue,
        )

        # 6. Final Synthesis
        t0 = time.monotonic()
        synthesis = await self._synthesize(filtered_entities, contradictions, doc_hits)
        dur = int((time.monotonic() - t0) * 1000)
        self._log_step(
            job_logger, "Final Synthesis", "success", dur,
            {
                "action_type": "synthesis",
                "tool_name": "llm_generator" if llm_available else "rule_based",
                "inputs_hash": hash("synthesize"),
                "outputs_summary": synthesis.get("synthesis", "")[:200],
                "evidence_refs": self.evidence_refs,
                "top_targets_ranked": synthesis.get("top_targets_ranked", []),
            },
            step_queue,
        )

        # 7. Generate figures driven by real job results
        try:
            from services.figure_generator import FigureGenerator

            FigureGenerator.generate_job_artifacts(
                job_logger.job_id,
                entities=filtered_entities,
                synthesis=synthesis,
                evidence_refs=self.evidence_refs,
            )
        except Exception as exc:
            logger.debug("Figure generation skipped: %s", exc)

        result = {
            "query": self.query,
            "status": "completed",
            "steps_taken": self.current_step,
            "llm_available": llm_available,
            "result": {
                "top_targets": synthesis.get("top_targets", []),
                "warnings": synthesis.get("warnings", []),
                "evidence_count": len(self.evidence_refs),
                "contradictions_found": len(contradictions),
                "documents_searched": len(doc_hits),
                "synthesis": synthesis.get("synthesis", ""),
            },
        }

        # Push done event to queue
        if step_queue is not None:
            try:
                step_queue.put_nowait({"type": "done", "result": result})
            except Exception:
                log.debug("Failed to push final result to queue")

        return result
