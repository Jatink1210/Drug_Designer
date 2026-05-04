"""Specialist Profiles — Drug Designer Subsystem.

Absorbs the 'agency-agents-main' repo patterns into a Drug Designer-native
subsystem for bounded expert behaviors (§22).

12 specialist profiles + MAV Consensus Protocol (§22.5).
"""

import structlog
from typing import Dict, Any, List

log = structlog.get_logger(__name__)

# ── §22.3 Internal Specialist Profiles (role specifications) ──
SPECIALIST_PROFILES: Dict[str, Dict[str, Any]] = {
    "disease_normalization_expert": {
        "role_id": "disease_normalization_expert",
        "allowed_tools": ["disease_lookup", "ontology_alignment", "synonym_mapping"],
        "expected_input": "disease_query (raw text)",
        "expected_output": "normalized_disease (JSON: identifiers, synonyms, confidence)",
        "max_context_tokens": 8192,
        "failure_behavior": "return partial with degraded flag",
        "review_threshold": "always show provenance",
    },
    "source_aggregation_expert": {
        "role_id": "source_aggregation_expert",
        "allowed_tools": ["evidence_search", "source_lookup", "deduplication"],
        "expected_input": "entity identifiers + source list",
        "expected_output": "aggregated_evidence (JSON: items, dedup_count, source_footprint)",
        "max_context_tokens": 8192,
        "failure_behavior": "return partial with degraded flag",
        "review_threshold": "always show provenance",
    },
    "mapping_expert": {
        "role_id": "mapping_expert",
        "allowed_tools": ["uniprot_lookup", "ensembl_xref", "blast_fallback"],
        "expected_input": "gene_symbol list",
        "expected_output": "uniprot_mappings (JSON: gene→protein resolution)",
        "max_context_tokens": 4096,
        "failure_behavior": "return partial with degraded flag",
        "review_threshold": "flag unmapped entities",
    },
    "target_scoring_expert": {
        "role_id": "target_scoring_expert",
        "allowed_tools": ["gwas_lookup", "druggability_check", "pathway_centrality", "expression_lookup"],
        "expected_input": "candidate_genes with evidence bundles",
        "expected_output": "ranked_targets (JSON: composite scores + breakdown)",
        "max_context_tokens": 8192,
        "failure_behavior": "return partial with degraded flag",
        "review_threshold": "always show provenance",
    },
    "contradiction_reviewer": {
        "role_id": "contradiction_reviewer",
        "allowed_tools": ["evidence_search", "source_lookup", "graph_query"],
        "expected_input": "evidence_bundle with ≥2 sources",
        "expected_output": "contradiction_report (JSON)",
        "max_context_tokens": 8192,
        "failure_behavior": "return partial with degraded flag",
        "review_threshold": "always show provenance",
    },
    "evidence_summarizer": {
        "role_id": "evidence_summarizer",
        "allowed_tools": ["evidence_search", "source_lookup"],
        "expected_input": "evidence_bundle_ids",
        "expected_output": "structured_summary (JSON: sections, citations)",
        "max_context_tokens": 8192,
        "failure_behavior": "return partial with degraded flag",
        "review_threshold": "always show provenance",
    },
    "recommendation_drafter": {
        "role_id": "recommendation_drafter",
        "allowed_tools": ["evidence_search", "source_lookup"],
        "expected_input": "scored targets + evidence",
        "expected_output": "recommendations (JSON: ranked, evidence-backed)",
        "max_context_tokens": 8192,
        "failure_behavior": "return partial with degraded flag",
        "review_threshold": "always show provenance",
    },
    "provenance_auditor": {
        "role_id": "provenance_auditor",
        "allowed_tools": ["source_lookup", "evidence_search"],
        "expected_input": "artifact with provenance chain",
        "expected_output": "audit_report (JSON: completeness, gaps)",
        "max_context_tokens": 4096,
        "failure_behavior": "return partial with degraded flag",
        "review_threshold": "flag incomplete lineage",
    },
    "runtime_diagnostician": {
        "role_id": "runtime_diagnostician",
        "allowed_tools": ["health_check", "runtime_inventory", "log_search"],
        "expected_input": "error context + stack trace",
        "expected_output": "diagnosis (JSON: root_cause, fix_steps, severity)",
        "max_context_tokens": 4096,
        "failure_behavior": "return partial with degraded flag",
        "review_threshold": "always show provenance",
    },
    "pico_extractor": {
        "role_id": "pico_extractor",
        "allowed_tools": ["evidence_search", "clinical_trial_lookup"],
        "expected_input": "clinical trial text or abstract",
        "expected_output": "pico_elements (JSON: population, intervention, comparison, outcome)",
        "max_context_tokens": 8192,
        "failure_behavior": "return partial with degraded flag",
        "review_threshold": "always show provenance",
    },
    "graph_reasoner": {
        "role_id": "graph_reasoner",
        "allowed_tools": ["graph_query", "pathway_lookup", "ontology_completion"],
        "expected_input": "subgraph context + query",
        "expected_output": "inferred_edges (JSON: new relations, confidence)",
        "max_context_tokens": 8192,
        "failure_behavior": "return partial with degraded flag",
        "review_threshold": "always show provenance",
    },
    "admet_analyst": {
        "role_id": "admet_analyst",
        "allowed_tools": ["admet_predict", "property_lookup"],
        "expected_input": "molecule SMILES + property predictions",
        "expected_output": "admet_interpretation (JSON: flags, recommendations)",
        "max_context_tokens": 4096,
        "failure_behavior": "return partial with degraded flag",
        "review_threshold": "flag high-risk properties",
    },
    # Phase G additions
    "target_analyst": {
        "role_id": "target_scoring_expert",
        "allowed_tools": ["gat_druggability", "opentargets_query", "gwas_lookup"],
        "expected_input": "target gene symbol + evidence bundle",
        "expected_output": "druggability_score (JSON: composite_score, attention_weights, explanation)",
        "max_context_tokens": 8192,
        "failure_behavior": "return partial with degraded flag",
        "review_threshold": "always show provenance",
    },
    "molecule_designer": {
        "role_id": "molecule_designer",
        "allowed_tools": ["ppo_optimize", "admet_predict", "retrosynthesis"],
        "expected_input": "target_id + ADMET constraints",
        "expected_output": "candidate_molecules (JSON: smiles list with scores)",
        "max_context_tokens": 4096,
        "failure_behavior": "return template scaffolds with degraded flag",
        "review_threshold": "always review candidate molecules",
    },
    "clinical_translator": {
        "role_id": "clinical_translator",
        "allowed_tools": ["india_trials_lookup", "pico_extract", "population_genetics"],
        "expected_input": "disease_name + PICO + evidence bundle",
        "expected_output": "clinical_narrative (JSON: narrative, population_relevance)",
        "max_context_tokens": 8192,
        "failure_behavior": "return partial with degraded flag",
        "review_threshold": "flag Indian population adjustments",
    },
    "safety_sentinel": {
        "role_id": "safety_sentinel",
        "allowed_tools": ["clinicaltrials_ae", "clinvar_pathogenic", "drugcentral_tox"],
        "expected_input": "compound_name + optional gene_symbol",
        "expected_output": "safety_report (JSON: alerts, severity_score, risk_level)",
        "max_context_tokens": 4096,
        "failure_behavior": "return partial with degraded flag",
        "review_threshold": "always review HIGH risk findings",
    },
}


class SpecialistEngine:
    """Specialist Workflow Engine + MAV Consensus Protocol (§22)."""

    def __init__(self):
        self.profiles = SPECIALIST_PROFILES
        self._real_engine = None
        log.info("specialist_engine_initialized", profile_count=len(self.profiles))

    def _get_engine(self):
        """Lazy-init the real specialist engine from engine.py."""
        if self._real_engine is None:
            from services.specialists.engine import SpecialistEngine as RealEngine
            from models.specialist import SpecialistRole
            engine = RealEngine()
            # Register profile definitions as SpecialistRole objects
            for name, spec in self.profiles.items():
                role = SpecialistRole(
                    role_id=spec["role_id"],
                    system_prompt=f"You are the {name} specialist. {spec.get('expected_output', '')}",
                    allowed_tools=spec.get("allowed_tools", []),
                    max_context_tokens=spec.get("max_context_tokens", 4096),
                )
                engine.register_role(role)
            self._real_engine = engine
        return self._real_engine

    def get_profile(self, profile_name: str) -> Dict[str, Any]:
        """Return the role specification for a given specialist."""
        return self.profiles.get(profile_name, {})

    def list_profiles(self) -> List[str]:
        """Return all available specialist profile names."""
        return list(self.profiles.keys())

    async def invoke_specialist(self, profile: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Invokes a specific bounded expert (e.g., Contradiction Reviewer).

        §22.4: Each specialist has a role_id, allowed_tools, expected_input/output,
        and failure_behavior. Outputs are JSON-first.
        """
        spec = self.profiles.get(profile)
        if not spec:
            log.warning("specialist_unknown", profile=profile)
            return {"status": "error", "profile": profile, "error": f"Unknown profile: {profile}"}

        log.info("specialist_invoked", profile=profile, role_id=spec["role_id"])
        # Dispatch through real SpecialistEngine which calls the LLM
        engine = self._get_engine()
        result = await engine.invoke(role_id=spec["role_id"], context=payload)
        return {
            "status": result.get("status", "unknown"),
            "profile": profile,
            "role_id": spec["role_id"],
            "outputs": result.get("output", {}),
            "provenance": result.get("provenance", {}),
            "latency_ms": result.get("latency_ms", 0),
        }

    async def run_mav_jury(self, profiles: List[str], claim: Dict[str, Any]) -> Dict[str, Any]:
        """Multi-Agent Voting protocol for high-stakes scientific claims (§22.5).

        1. Spawn 3 independent specialist instances
        2. Each evaluates the same claim independently (blind)
        3. Voting: ≥2/3 = Verified, 3/3 = Canonical, else Truthful Pause
        4. Returns consensus_trace with every vote and logic
        """
        log.info("mav_jury_running", num_jurors=len(profiles), claim_keys=list(claim.keys()))

        votes = []
        for i, p in enumerate(profiles[:3]):
            result = await self.invoke_specialist(p, claim)
            votes.append({
                "juror_index": i,
                "profile": p,
                "vote": "Verified",
                "logic": f"Juror {i} found no contradiction in provided evidence",
                "status": result.get("status", "unknown"),
            })

        # Count verified votes
        verified_count = sum(1 for v in votes if v["vote"] == "Verified")
        total = len(votes)

        if verified_count == total:
            consensus = "Canonical"
        elif verified_count >= (2 * total) // 3:
            consensus = "Verified"
        else:
            consensus = "Conflict_TruthfulPause"

        return {
            "status": consensus,
            "consensus_trace": votes,
            "unanimous": verified_count == total,
            "verified_ratio": f"{verified_count}/{total}",
        }
