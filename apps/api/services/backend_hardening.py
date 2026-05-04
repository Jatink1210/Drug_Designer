"""Backend Hardening Utilities — Phase CC.

CC-0.1: Connector coverage audit
CC-0.2: Entity ID normalization across pipelines
CC-0.3: Seed data for vector/graph stores
CC-0.4: Model runtime contract verification
CC-0.5: Degraded/demo state surfacing
CC-0.6: ESM/Forge credential wiring via env only
CC-0.7: Connector degradation visibility
"""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional

import structlog

from services.runtime.policy import get_runtime_policy, hosted_runtime_configured, ollama_enabled

log = structlog.get_logger(__name__)


# ── CC-0.1: Connector Coverage Audit ─────────────────────

# Maps each shipped module to the connectors it requires
MODULE_CONNECTOR_REQUIREMENTS: Dict[str, List[str]] = {
    "cockpit": ["pubmed", "europe_pmc", "opentargets", "chembl", "clinicaltrials", "uniprot"],
    "evidence-search": ["pubmed", "europe_pmc", "crossref", "semantic_scholar", "patents_view", "openalex"],
    "entity-intelligence": ["pubmed", "opentargets", "chembl", "uniprot", "ensembl", "string_db", "disgenet", "clinvar"],
    "knowledge-graph": ["pubmed", "opentargets", "chembl", "uniprot", "string_db", "reactome"],
    "pathways": ["reactome", "kegg", "wikipathways"],
    "structure": ["rcsb_pdb", "alphafold", "uniprot"],
    "design": ["chembl", "pubchem", "rcsb_pdb"],
    "clinical-design": ["clinicaltrials", "pubmed", "clinvar", "gnomad"],
    "syntharena": ["pubmed", "chembl"],
    "research-labs": ["chembl", "pubchem", "uniprot", "rcsb_pdb", "alphafold", "reactome"],
    "contradiction-similarity": ["pubmed", "europe_pmc", "opentargets"],
    "pico-verification": ["pubmed", "clinicaltrials"],
}

# All connectors registered in the system
ALL_CONNECTORS = [
    "pubmed", "europe_pmc", "crossref", "semantic_scholar", "patents_view",
    "openalex", "uniprot", "opentargets", "ensembl", "string_db",
    "chembl", "pubchem", "chebi", "drugbank", "reactome", "kegg",
    "wikipathways", "rcsb_pdb", "alphafold", "clinicaltrials", "clinvar",
    "gnomad", "gwas_catalog", "disgenet", "disease_ontology", "hpo",
    "biogrid", "intact", "interpro", "indigen",
]


def audit_connector_coverage() -> Dict[str, Any]:
    """CC-0.1: Audit connector coverage against all shipped modules.

    Returns a report showing which modules have full/partial/missing connector coverage.
    """
    report: Dict[str, Any] = {
        "modules": {},
        "unused_connectors": [],
        "total_connectors": len(ALL_CONNECTORS),
        "total_modules": len(MODULE_CONNECTOR_REQUIREMENTS),
    }

    used_connectors: set = set()

    for module, required in MODULE_CONNECTOR_REQUIREMENTS.items():
        available = [c for c in required if c in ALL_CONNECTORS]
        missing = [c for c in required if c not in ALL_CONNECTORS]
        used_connectors.update(available)

        coverage = len(available) / len(required) if required else 1.0
        report["modules"][module] = {
            "required": required,
            "available": available,
            "missing": missing,
            "coverage": round(coverage, 2),
            "status": "full" if coverage == 1.0 else "partial" if coverage >= 0.5 else "degraded",
        }

    report["unused_connectors"] = sorted(set(ALL_CONNECTORS) - used_connectors)
    report["overall_coverage"] = round(
        sum(m["coverage"] for m in report["modules"].values()) / len(report["modules"]),
        2,
    )

    log.info("connector_audit_complete",
             overall_coverage=report["overall_coverage"],
             modules_audited=len(report["modules"]))
    return report


# ── CC-0.2: Entity ID Normalization ──────────────────────

# Canonical ID prefixes for each entity type
ENTITY_ID_PREFIXES: Dict[str, List[str]] = {
    "disease": ["MONDO:", "OMIM:", "MESH:", "DOID:", "ICD10:", "ICD11:", "EFO:"],
    "gene": ["HGNC:", "ENSG"],
    "protein": ["UniProt:", "PDB:", "AF-"],
    "drug": ["CHEMBL", "DB", "CID:", "CHEBI:"],
    "variant": ["rs", "ClinVar:", "PharmVar:"],
    "pathway": ["R-HSA-", "hsa", "WP"],
}


def normalize_entity_id(raw_id: str, entity_type: str) -> Dict[str, Any]:
    """CC-0.2: Normalize an entity ID to canonical form.

    Returns the normalized ID, detected source, and confidence.
    """
    raw_id = raw_id.strip()
    if not raw_id:
        return {"normalized_id": "", "source": "unknown", "confidence": 0.0, "original": raw_id}

    prefixes = ENTITY_ID_PREFIXES.get(entity_type, [])

    for prefix in prefixes:
        if raw_id.upper().startswith(prefix.upper()):
            return {
                "normalized_id": raw_id,
                "source": prefix.rstrip(":").rstrip("-"),
                "confidence": 1.0,
                "original": raw_id,
            }

    # Heuristic detection
    if entity_type == "protein" and len(raw_id) == 4 and raw_id[0].isdigit():
        return {"normalized_id": raw_id.upper(), "source": "PDB", "confidence": 0.9, "original": raw_id}
    if entity_type == "protein" and len(raw_id) >= 6 and raw_id[0].isalpha():
        return {"normalized_id": raw_id.upper(), "source": "UniProt", "confidence": 0.7, "original": raw_id}
    if entity_type == "gene" and raw_id.isalpha() and raw_id.isupper():
        return {"normalized_id": raw_id, "source": "HGNC_symbol", "confidence": 0.8, "original": raw_id}
    if entity_type == "variant" and raw_id.startswith("rs"):
        return {"normalized_id": raw_id, "source": "dbSNP", "confidence": 1.0, "original": raw_id}

    return {"normalized_id": raw_id, "source": "unresolved", "confidence": 0.3, "original": raw_id}


def normalize_entity_ids_batch(
    items: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """CC-0.2: Batch normalize entity IDs across pipelines."""
    return [
        normalize_entity_id(item.get("id", ""), item.get("type", "unknown"))
        for item in items
    ]


# ── CC-0.4: Model Runtime Contract Verification ─────────

def verify_model_contracts() -> Dict[str, Any]:
    """CC-0.4: Verify Gemma, ESM, embedding, diffusion, and ADMET runtime contracts.

    Checks each model's availability and returns honest status.
    """
    contracts: Dict[str, Any] = {}
    policy = get_runtime_policy()

    # Gemma / LLM
    if ollama_enabled():
        try:
            import httpx
            resp = httpx.get(f"{policy['ollama_base_url']}/api/tags", timeout=5.0)
            models = resp.json().get("models", []) if resp.status_code == 200 else []
            model_names = [m.get("name", "") for m in models]
            contracts["llm"] = {
                "status": "available" if models else "not_installed",
                "models": model_names[:5],
                "engine": "ollama",
                "policy": policy,
            }
        except Exception:
            contracts["llm"] = {"status": "unavailable", "models": [], "engine": "ollama", "policy": policy}
    else:
        contracts["llm"] = {
            "status": "configured" if hosted_runtime_configured() else "degraded",
            "models": [],
            "engine": "remote",
            "policy": policy,
            "note": "Local Ollama probing is disabled unless LLM_ENABLE_OLLAMA=true or LLM_RUNTIME_MODE=local.",
        }

    # ESM Forge
    esm_key = os.environ.get("ESM_FORGE_API_KEY", "")
    contracts["esm_forge"] = {
        "status": "configured" if esm_key else "not_configured",
        "key_set": bool(esm_key),
        "endpoint": "https://forge.evolutionaryscale.ai",
    }

    # PyTorch / Diffusion / ADMET
    try:
        import torch
        contracts["pytorch"] = {
            "status": "available",
            "version": torch.__version__,
            "cuda": torch.cuda.is_available(),
            "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        }
    except ImportError:
        contracts["pytorch"] = {"status": "not_installed", "version": None, "cuda": False}

    # RDKit
    try:
        from rdkit import Chem  # noqa: F401
        contracts["rdkit"] = {"status": "available"}
    except ImportError:
        contracts["rdkit"] = {"status": "not_installed"}

    # Embedding models
    contracts["embeddings"] = {
        "status": "degraded" if not contracts.get("pytorch", {}).get("status") == "available" else "available",
        "note": "Requires PyTorch for neural embeddings; falls back to TF-IDF",
    }

    # Diffusion model
    contracts["diffusion"] = {
        "status": "available" if contracts.get("pytorch", {}).get("status") == "available" else "degraded",
        "note": "GraphDiffusionModel requires PyTorch; returns degraded results without it",
    }

    # ADMET
    contracts["admet"] = {
        "status": "available",
        "engine": "rdkit" if contracts.get("rdkit", {}).get("status") == "available" else "rule_based",
        "conformal_prediction": contracts.get("pytorch", {}).get("status") == "available",
    }

    log.info("model_contracts_verified", contracts={k: v.get("status") for k, v in contracts.items()})
    return contracts


# ── CC-0.5: Degraded/Demo State Surfacing ────────────────

def get_degraded_states() -> Dict[str, Any]:
    """CC-0.5: Return honest degraded/demo states for all model and plugin dependencies."""
    contracts = verify_model_contracts()
    degraded: List[str] = []
    demo: List[str] = []

    for name, info in contracts.items():
        status = info.get("status", "unknown")
        if status in ("not_installed", "not_configured", "unavailable"):
            degraded.append(name)
        elif status == "degraded":
            demo.append(name)

    return {
        "degraded_components": degraded,
        "demo_mode_components": demo,
        "all_healthy": len(degraded) == 0 and len(demo) == 0,
        "contracts": contracts,
    }


# ── CC-0.6: Credential Wiring ────────────────────────────

REQUIRED_CREDENTIALS = {
    "ESM_FORGE_API_KEY": "ESM-3 Forge protein structure prediction",
    "NCBI_API_KEY": "NCBI E-utilities (PubMed, ClinVar) — increases rate limit",
    "DISGENET_API_KEY": "DisGeNET gene-disease associations",
    "OPENAI_API_KEY": "OpenAI hosted LLM (optional)",
}


def verify_credentials() -> Dict[str, Any]:
    """CC-0.6: Verify all credentials are wired via environment variables only.

    Never returns raw credential values — only boolean presence.
    """
    result: Dict[str, Any] = {}
    for env_var, description in REQUIRED_CREDENTIALS.items():
        value = os.environ.get(env_var, "")
        result[env_var] = {
            "configured": bool(value),
            "description": description,
            "source": "environment" if value else "not_set",
        }
    return result


# ── CC-0.7: Connector Degradation Visibility ─────────────

async def check_connector_health_all() -> Dict[str, Any]:
    """CC-0.7: Check health of all connectors and return degradation status.

    Returns per-connector status with latency and error details.
    """
    from core.circuit_breaker import CircuitBreakerRegistry

    results: Dict[str, Any] = {}
    registry = CircuitBreakerRegistry()

    for connector_name in ALL_CONNECTORS:
        cb = registry.get(connector_name)
        if cb:
            results[connector_name] = {
                "status": "healthy" if cb.state == "closed" else "degraded" if cb.state == "half_open" else "open",
                "circuit_state": cb.state,
                "failure_count": cb.failure_count,
                "last_failure": str(cb.last_failure_time) if cb.last_failure_time else None,
            }
        else:
            results[connector_name] = {
                "status": "unknown",
                "circuit_state": "no_breaker",
                "failure_count": 0,
            }

    healthy = sum(1 for v in results.values() if v["status"] == "healthy")
    degraded = sum(1 for v in results.values() if v["status"] == "degraded")
    down = sum(1 for v in results.values() if v["status"] == "open")

    return {
        "connectors": results,
        "summary": {
            "total": len(results),
            "healthy": healthy,
            "degraded": degraded,
            "down": down,
        },
    }
