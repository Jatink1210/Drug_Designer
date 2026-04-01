"""Evidence & Citations API routes — unified search + export."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from fastapi import APIRouter, Query, HTTPException, Response
import uuid
import asyncio
from pydantic import BaseModel, Field
from services.dossier_generator import DossierCompiler

from connectors.pubmed import PubMedConnector
from connectors.europe_pmc import EuropePMCConnector
from connectors.clinicaltrials import ClinicalTrialsConnector
from connectors.patents import PatentsViewConnector
from services.evidence_store import EvidenceStore

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


class EvidenceSearchRequest(BaseModel):
    query: str
    job_id: str = Field(default_factory=lambda: f"job_{uuid.uuid4().hex[:8]}")
    sources: List[str] = Field(default_factory=lambda: ["pubmed", "clinicaltrials"])
    limit: int = 20
    year_from: int = 0
    year_to: int = 9999


@router.post("/search")
async def search_evidence(req: EvidenceSearchRequest) -> Dict[str, Any]:
    """Unified evidence search across publications, trials, and patents, directly storing into the canonical DB."""

    results: Dict[str, List[Dict[str, Any]]] = {}
    # Enforce strictly >= 20 sources by handing off execution to the AutoResearch Engine
    from services.evidence.autoresearch import AutoResearchLoop
    
    # 20 source mandate override: irrespective of frontend request limits < 20
    enforced_limit = max(req.limit, 20)
    AutoResearchLoop.TARGET_MIN_SOURCES = enforced_limit
    
    try:
        results = await AutoResearchLoop.execute_comprehensive_search(req.query, req.job_id, req.sources)
    except Exception as e:
        import traceback
        traceback.print_exc()
        results = {}
    # Apply year filters natively to the results returned from AutoResearch
    for category in list(results.keys()):
        entries = results[category]
        if req.year_from > 0 or req.year_to < 9999:
            entries = [e for e in entries if req.year_from <= (e.get("year") or 0) <= req.year_to]
        results[category] = entries

    total = sum(len(v) for v in results.values())
    return {"query": req.query, "job_id": req.job_id, "total": total, "results": results}

@router.get("/jobs/{job_id}/evidence")
async def get_job_evidence(job_id: str) -> Dict[str, Any]:
    """Retrieve all entities and provenance edges associated with a specific job."""
    return EvidenceStore.get_job_evidence(job_id)

@router.get("/edge/{edge_id}")
async def get_edge_evidence(edge_id: str) -> Dict[str, Any]:
    """Retrieve deep provenance details for a single evidence edge."""
    edge = EvidenceStore.get_edge(edge_id)
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")
    return {"edge": edge}

@router.get("/stats")
async def get_evidence_stats() -> Dict[str, int]:
    return EvidenceStore.get_stats()

@router.post("/clear")
async def clear_evidence_cache() -> Dict[str, Any]:
    """Wipe all cached entities and edges (Development/Verification)."""
    count = EvidenceStore.clear_cache()
    return {"status": "success", "cleared_records": count, "message": "Evidence cache flushed strictly."}


@router.get("/export")
async def export_citations(
    query: str = Query(...),
    format: str = Query("json", pattern="^(json|csv|bibtex|ris)$"),
    limit: int = Query(50, le=200),
) -> Dict[str, Any]:
    """Export evidence as BibTeX, RIS, CSV, or JSON."""
    pubmed = PubMedConnector()
    results = await pubmed.search(query, limit=limit)
    await pubmed.close()

    if format == "bibtex":
        entries = []
        for r in results:
            pmid = r.get("pmid", "")
            title = r.get("title", "")
            authors = ", ".join(r.get("authors", []))
            journal = r.get("journal", "")
            year = r.get("year", "")
            entries.append(
                "@article{pmid%s,\n  title={%s},\n  author={%s},\n  journal={%s},\n  year={%s}\n}" % (pmid, title, authors, journal, year)
            )
        return {"format": "bibtex", "count": len(entries), "content": "\n\n".join(entries)}

    elif format == "ris":
        entries = []
        for r in results:
            lines = ["TY  - JOUR"]
            lines.append("TI  - %s" % r.get("title", ""))
            for a in r.get("authors", []):
                lines.append("AU  - %s" % a)
            lines.append("JO  - %s" % r.get("journal", ""))
            lines.append("PY  - %s" % r.get("year", ""))
            lines.append("AN  - PMID:%s" % r.get("pmid", ""))
            lines.append("ER  -")
            entries.append("\n".join(lines))
        return {"format": "ris", "count": len(entries), "content": "\n\n".join(entries)}

    elif format == "csv":
        header = "pmid,title,authors,journal,year,doi,url"
        rows = []
        for r in results:
            rows.append(",".join([
                '"%s"' % str(r.get(f, "")).replace('"', '""')
                for f in ["pmid", "title", "authors", "journal", "year", "doi", "url"]
            ]))
        return {"format": "csv", "count": len(rows), "content": header + "\n" + "\n".join(rows)}

    else:
        return {"format": "json", "count": len(results), "content": results}


class DossierRequest(BaseModel):
    target_id: str
    llm_consensus: str = ""
    binding_energy: float = 0.0
    rmsd: float = 0.0
    evidence_array: list = []
    graph_topology: dict = {}

@router.post("/export_dossier")
async def export_decision_dossier(req: DossierRequest):
    """Compiles multi-engine project state into a reproducible Decision Dossier ZIP."""
    zip_bytes = DossierCompiler.generate_dossier_zip(req.model_dump())
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=decision_dossier_{req.target_id}.zip"}
    )
