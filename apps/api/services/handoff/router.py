"""Workflow Baton Router (Drug Designer §26.3).

Each handoff carries a 'baton' — a structured payload with the
upstream module's outputs, provenance, and recommended next actions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger()

# Map target_module names to ARQ queue names for job dispatch
_MODULE_QUEUE_MAP: Dict[str, str] = {
    "target_ranking": "target.ranking",
    "graph": "graph.enrichment",
    "evidence_workspace": "retrieval.deep",
    "structure": "target.ranking",
    "design": "chemistry.design",
    "syntharena": "chemistry.design",
    "dossier": "reports.dossiers",
}


class BatonPayload:
    """Structured handoff payload between workflow stages (§26).

    Contains the upstream module outputs, provenance, and downstream
    routing hints. Carries all 8 spec-mandated fields.
    """

    def __init__(
        self,
        source_module: str,
        target_module: str,
        run_id: str,
        project_id: str,
        data: Dict[str, Any] = None,
        evidence_ids: List[str] = None,
        provenance: Dict[str, Any] = None,
        # §26 required baton fields
        normalized_entities: List[Dict[str, Any]] = None,
        source_footprint: List[str] = None,
        provisional_evidence: List[Dict[str, Any]] = None,
        runtime_context: Dict[str, Any] = None,
        unresolved_questions: List[str] = None,
        confidence_signals: Dict[str, float] = None,
        contradiction_signals: List[Dict[str, Any]] = None,
        output_contract_for_next: Dict[str, Any] = None,
    ):
        self.source_module = source_module
        self.target_module = target_module
        self.run_id = run_id
        self.project_id = project_id
        self.data = data or {}
        self.evidence_ids = evidence_ids or []
        self.provenance = provenance or {}
        # §26 Baton fields
        self.normalized_entities = normalized_entities or []
        self.source_footprint = source_footprint or []
        self.provisional_evidence = provisional_evidence or []
        self.runtime_context = runtime_context or {}
        self.unresolved_questions = unresolved_questions or []
        self.confidence_signals = confidence_signals or {}
        self.contradiction_signals = contradiction_signals or []
        self.output_contract_for_next = output_contract_for_next or {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize baton for queue dispatch."""
        return {
            "source_module": self.source_module,
            "target_module": self.target_module,
            "run_id": self.run_id,
            "project_id": self.project_id,
            "data": self.data,
            "evidence_ids": self.evidence_ids,
            "provenance": self.provenance,
            "normalized_entities": self.normalized_entities,
            "source_footprint": self.source_footprint,
            "provisional_evidence": self.provisional_evidence,
            "runtime_context": self.runtime_context,
            "unresolved_questions": self.unresolved_questions,
            "confidence_signals": self.confidence_signals,
            "contradiction_signals": self.contradiction_signals,
            "output_contract_for_next": self.output_contract_for_next,
        }


class HandoffRouter:
    """Routes workflow batons between modules.

    Registered handoff paths (§26.2):
      disease → target_ranking
      disease → graph
      disease → evidence_workspace
      target_ranking → structure
      target_ranking → design
      target_ranking → dossier
      design → syntharena
      design → dossier
      evidence_workspace → dossier
    """

    VALID_HANDOFFS = {
        ("disease", "target_ranking"),
        ("disease", "graph"),
        ("disease", "evidence_workspace"),
        ("target_ranking", "structure"),
        ("target_ranking", "design"),
        ("target_ranking", "dossier"),
        ("design", "syntharena"),
        ("design", "dossier"),
        ("evidence_workspace", "dossier"),
        ("syntharena", "dossier"),
        ("graph", "dossier"),
    }

    def __init__(self, run_manager=None, context_fabric=None):
        self._run_manager = run_manager
        self._context_fabric = context_fabric

    async def handoff(self, baton: BatonPayload) -> Dict[str, Any]:
        """Execute a workflow handoff.

        1. Validate the handoff path
        2. Persist baton to Context Fabric
        3. Trigger downstream module
        4. Return confirmation with new run_id
        """
        path = (baton.source_module, baton.target_module)

        if path not in self.VALID_HANDOFFS:
            log.error(
                "handoff.invalid_path",
                source=baton.source_module,
                target=baton.target_module,
            )
            return {"error": f"Invalid handoff: {baton.source_module} → {baton.target_module}"}

        log.info(
            "handoff.execute",
            source=baton.source_module,
            target=baton.target_module,
            run_id=baton.run_id,
        )

        # §26.3: Persist baton to Context Fabric L2 (project memory)
        if self._context_fabric:
            try:
                await self._context_fabric.store(
                    project_id=baton.project_id,
                    tier="L2",
                    key=f"handoff:{baton.run_id}:{baton.source_module}->{baton.target_module}",
                    value={
                        "source_module": baton.source_module,
                        "target_module": baton.target_module,
                        "data": baton.data,
                        "evidence_ids": baton.evidence_ids,
                        "provenance": baton.provenance,
                    },
                )
                log.info("handoff.baton_persisted", run_id=baton.run_id)
            except Exception as exc:
                log.warning("handoff.persist_failed", error=str(exc))

        # §26.1: Create downstream run via run manager
        downstream_run_id = None
        if self._run_manager:
            try:
                downstream_run = await self._run_manager.create_run(
                    project_id=baton.project_id,
                    run_type=baton.target_module,
                    input_snapshot={
                        "handoff_from": baton.source_module,
                        "source_run_id": baton.run_id,
                        **baton.data,
                    },
                )
                downstream_run_id = downstream_run.get("run_id") if isinstance(downstream_run, dict) else getattr(downstream_run, "id", None)
                log.info("handoff.downstream_created", downstream_run_id=downstream_run_id)
            except Exception as exc:
                log.warning("handoff.downstream_failed", error=str(exc))

        # §26.1: Enqueue the appropriate worker job so the run actually executes
        if downstream_run_id:
            queue_name = _MODULE_QUEUE_MAP.get(baton.target_module)
            if queue_name:
                try:
                    from arq import create_pool
                    from worker import redis_settings, QUEUE_MAP
                    pool = await create_pool(redis_settings)
                    func_name = QUEUE_MAP.get(queue_name, queue_name)
                    await pool.enqueue_job(
                        func_name,
                        run_id=downstream_run_id,
                        project_id=baton.project_id,
                        _queue_name=queue_name,
                    )
                    await pool.close()
                    log.info("handoff.job_enqueued", queue=queue_name, func=func_name, run_id=downstream_run_id)
                except Exception as exc:
                    log.warning("handoff.enqueue_failed", queue=queue_name, error=str(exc))
            else:
                log.warning("handoff.no_queue_mapping", target_module=baton.target_module)

        return {
            "status": "accepted",
            "source_module": baton.source_module,
            "target_module": baton.target_module,
            "source_run_id": baton.run_id,
            "downstream_run_id": downstream_run_id,
        }
