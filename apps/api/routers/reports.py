"""Report Builder API — generate structured reports."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request
from routers.auth import get_current_user
from pydantic import BaseModel, Field

from config import settings
from models.envelope import build_envelope

router = APIRouter(prefix="/api/v1/reports", tags=["reports"], dependencies=[Depends(get_current_user)])
log = logging.getLogger(__name__)


class ReportRequest(BaseModel):
    title: str = "Research Report"
    query: str = ""
    sections: List[str] = Field(default_factory=lambda: [
        "summary", "results", "evidence", "structures", "docking", "pathways", "graph", "provenance"
    ])
    search_data: Dict[str, Any] = Field(default_factory=dict)
    structure_data: Dict[str, Any] = Field(default_factory=dict)
    docking_data: Dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


@router.post("/generate")
async def generate_report(req: ReportRequest, request: Request) -> Dict[str, Any]:
    """Generate a structured HTML/JSON report."""
    report_id = str(uuid.uuid4())[:8]
    reports_dir = os.path.join(settings.local_store_path, "reports")
    os.makedirs(reports_dir, exist_ok=True)

    report = {
        "report_id": report_id,
        "title": req.title,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "query": req.query,
        "sections": {},
    }

    if "summary" in req.sections:
        stats = req.search_data.get("summary_stats", {})
        report["sections"]["summary"] = {
            "title": "Query Summary",
            "query": req.query,
            "intent": req.search_data.get("intent", {}),
            "total_results": stats.get("total_results", 0),
            "pubmed_count": stats.get("pubmed_count"),
            "clinical_trials_count": stats.get("clinical_trials_count"),
            "sources_queried": stats.get("sources_queried", 0),
        }

    if "results" in req.sections and req.search_data.get("categories"):
        categories = req.search_data.get("categories", {})
        tables = {}
        for cat_name, cat_data in categories.items():
            tables[cat_name] = {
                "columns": cat_data.get("columns", []),
                "row_count": cat_data.get("total", 0),
                "rows": cat_data.get("rows", [])[:50],
            }
        report["sections"]["results"] = {"title": "Categorized Results", "tables": tables}

    if "evidence" in req.sections:
        report["sections"]["evidence"] = {
            "title": "Top Evidence",
            "note": "Evidence citations with provenance tracking",
        }

    if "structures" in req.sections and req.structure_data:
        report["sections"]["structures"] = {
            "title": "Structural Data",
            "data": req.structure_data,
        }

    if "docking" in req.sections and req.docking_data:
        report["sections"]["docking"] = {
            "title": "Docking Results",
            "data": req.docking_data,
        }

    if "provenance" in req.sections:
        report["sections"]["provenance"] = {
            "title": "Reproducibility Appendix",
            "sources": req.search_data.get("provenance", {}),
            "timings": req.search_data.get("timings", {}),
            "timestamp": time.time(),
            "api_version": "1.0.0",
        }

    if req.notes:
        report["sections"]["notes"] = {"title": "User Notes", "content": req.notes}

    # Generate HTML
    html = _render_html(report)
    report["html"] = html

    # Save
    with open(os.path.join(reports_dir, "%s.json" % report_id), "w") as f:
        json.dump(report, f, indent=2, default=str)
    with open(os.path.join(reports_dir, "%s.html" % report_id), "w") as f:
        f.write(html)

    return build_envelope(request, {
        "report_id": report_id,
        "status": "generated",
        "sections": list(report["sections"].keys()),
        "html_path": os.path.join(reports_dir, "%s.html" % report_id),
        "json_path": os.path.join(reports_dir, "%s.json" % report_id),
    })


@router.get("/list")
async def list_reports(request: Request) -> Dict[str, Any]:
    reports_dir = os.path.join(settings.local_store_path, "reports")
    if not os.path.exists(reports_dir):
        return build_envelope(request, [])
    reports = []
    for f in sorted(os.listdir(reports_dir), reverse=True):
        if f.endswith(".json"):
            try:
                with open(os.path.join(reports_dir, f)) as fh:
                    data = json.load(fh)
                    reports.append({
                        "report_id": data.get("report_id"),
                        "title": data.get("title"),
                        "generated_at": data.get("generated_at"),
                        "sections": list(data.get("sections", {}).keys()),
                    })
            except Exception:
                log.debug("Skipping malformed report file")
    return build_envelope(request, reports[:50])


@router.get("")
async def list_reports_v2(request: Request) -> Dict[str, Any]:
    """§129: GET /api/v1/reports — List all reports (spec-aligned path)."""
    return await list_reports(request)


@router.get("/{report_id}")
async def get_report(report_id: str, request: Request) -> Dict[str, Any]:
    """§25: Get a specific report by ID."""
    reports_dir = os.path.join(settings.local_store_path, "reports")
    json_path = os.path.join(reports_dir, f"{report_id}.json")
    if not os.path.exists(json_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Report not found")
    with open(json_path) as f:
        report = json.load(f)
    return build_envelope(request, report)


@router.post("")
async def create_report(req: ReportRequest, request: Request) -> Dict[str, Any]:
    """§129: POST /api/v1/reports — Create a report (alias for /generate)."""
    return await generate_report(req, request)


@router.post("/{report_id}/export")
async def export_report(report_id: str, request: Request, format: str = "html") -> Dict[str, Any]:
    """§129: POST /api/v1/reports/{reportId}/export — Export report in specified format."""
    reports_dir = os.path.join(settings.local_store_path, "reports")
    json_path = os.path.join(reports_dir, f"{report_id}.json")
    if not os.path.exists(json_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Report not found")
    with open(json_path) as f:
        report = json.load(f)
    return build_envelope(request, {
        "report_id": report_id,
        "format": format,
        "status": "exported",
        "html": _render_html(report) if format == "html" else None,
    })


def _render_html(report: Dict[str, Any]) -> str:
    """Render report as clean HTML."""
    sections_html = ""
    for key, sec in report.get("sections", {}).items():
        title = sec.get("title", key)
        content = ""
        if key == "summary":
            content = "<p>Query: <strong>%s</strong></p>" % sec.get("query", "")
            content += "<p>Results: %s | Sources: %s</p>" % (sec.get("total_results", 0), sec.get("sources_queried", 0))
            if sec.get("pubmed_count"):
                content += "<p>PubMed: %s | Trials: %s</p>" % (sec.get("pubmed_count"), sec.get("clinical_trials_count"))
        elif key == "results":
            for tname, tdata in sec.get("tables", {}).items():
                content += "<h3>%s (%d rows)</h3>" % (tname, tdata.get("row_count", 0))
                cols = tdata.get("columns", [])[:8]
                rows = tdata.get("rows", [])[:20]
                if cols and rows:
                    content += "<table><thead><tr>%s</tr></thead><tbody>" % "".join("<th>%s</th>" % c for c in cols)
                    for row in rows:
                        content += "<tr>%s</tr>" % "".join("<td>%s</td>" % str(row.get(c, ""))[:100] for c in cols)
                    content += "</tbody></table>"
        elif key == "provenance":
            content = "<pre>%s</pre>" % json.dumps(sec, indent=2, default=str)[:2000]
        elif key == "notes":
            content = "<p>%s</p>" % sec.get("content", "")
        else:
            content = "<pre>%s</pre>" % json.dumps(sec, indent=2, default=str)[:1000]

        sections_html += "<section><h2>%s</h2>%s</section>" % (title, content)

    return """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>%s</title>
<style>
body{font-family:Inter,-apple-system,sans-serif;max-width:900px;margin:0 auto;padding:24px;color:#1e293b;line-height:1.6}
h1{font-size:1.5rem;border-bottom:2px solid #e2e8f0;padding-bottom:8px}
h2{font-size:1.1rem;color:#475569;margin-top:24px}
h3{font-size:0.95rem;color:#6366f1}
table{width:100%%;border-collapse:collapse;font-size:0.8rem;margin:8px 0}
th{background:#f8fafc;text-align:left;padding:6px 8px;border:1px solid #e2e8f0;font-size:0.7rem;text-transform:uppercase}
td{padding:4px 8px;border:1px solid #f1f5f9}
pre{background:#f8fafc;padding:12px;border-radius:6px;font-size:0.75rem;overflow-x:auto}
section{margin-bottom:16px}
.footer{margin-top:32px;font-size:0.7rem;color:#94a3b8;border-top:1px solid #e2e8f0;padding-top:8px}
</style></head><body>
<h1>%s</h1>
<p style="color:#94a3b8;font-size:0.8rem">Generated: %s | Drug Designer API v1.0.0</p>
%s
<div class="footer">Drug Designer Platform — Research report. Verify all claims against primary sources.</div>
</body></html>""" % (report["title"], report["title"], report.get("generated_at", ""), sections_html)
