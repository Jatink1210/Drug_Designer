from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

os.environ.setdefault("DRUGDESIGNER_AUTH_ENABLED", "false")

from routers.cockpit import AnalyzeRequest, _run_cockpit_analysis_payload  # noqa: E402
from services.query_classifier import classify_query  # noqa: E402


PROMPT_RE = re.compile(r"^\s*(\d+)\.\s+(.*\S)\s*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a corpus-driven autonomous Cockpit batch.")
    parser.add_argument("--corpus", default=str(ROOT / "git repos" / "DrugSynth_1000_Autonomous_Test_Queries_and_Report_Spec.txt"))
    parser.add_argument("--start", type=int, default=None)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--query-ids", default="", help="Comma-separated query numbers to run, e.g. 44,48,49")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--execution-mode", default="sync")
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument("--output", required=True)
    parser.add_argument("--save-responses-dir", default="")
    return parser.parse_args()


def load_queries(corpus_path: Path) -> Dict[int, str]:
    queries: Dict[int, str] = {}
    for line in corpus_path.read_text(encoding="utf-8").splitlines():
        match = PROMPT_RE.match(line)
        if match:
            queries[int(match.group(1))] = match.group(2).strip()
    return queries


def select_queries(all_queries: Dict[int, str], args: argparse.Namespace) -> Dict[int, str]:
    if args.query_ids:
        selected_ids = [int(part.strip()) for part in args.query_ids.split(",") if part.strip()]
        return {qid: all_queries[qid] for qid in selected_ids if qid in all_queries}
    if args.start is None or args.end is None:
        raise ValueError("Either --query-ids or both --start/--end must be provided.")
    return {qid: text for qid, text in all_queries.items() if args.start <= qid <= args.end}


def _extract_connector(error_text: str) -> str:
    if ":" in error_text:
        return error_text.split(":", 1)[0].strip()
    return "unknown"


def _section_counts(payload: Dict[str, Any]) -> Dict[str, int]:
    literature_kg = payload.get("literature_kg") or {}
    graph = literature_kg if isinstance(literature_kg, dict) and literature_kg.get("nodes") else payload.get("graph") or {}
    traceable_summary = payload.get("traceable_summary") or {}
    llm_contradictions = payload.get("llm_contradictions") or []
    return {
        "literature_rows": len(payload.get("literature_table") or []),
        "filtered_rows": len(payload.get("filtered_literature") or []),
        "llm_contradictions": len(llm_contradictions),
        "llm_verified": sum(1 for item in llm_contradictions if item.get("llm_verified")),
        "supporting_findings": len(traceable_summary.get("supporting_findings") or []),
        "dissenting_findings": len(traceable_summary.get("dissenting_findings") or []),
        "pathways": len(payload.get("pathways") or []),
        "targets": len(payload.get("target_prioritization") or []),
        "kg_nodes": len(graph.get("nodes") or []),
        "kg_edges": len(graph.get("edges") or []),
        "mechanism_clusters": len(payload.get("mechanism_clusters") or []),
    }


def _validation_failures(payload: Dict[str, Any], section_counts: Dict[str, int]) -> List[str]:
    failures: List[str] = []
    guards = payload.get("quality_guards") or {}

    target_guard = guards.get("targets") or {}
    if target_guard.get("minimum_expected", 0) > 0 and target_guard.get("status") != "pass":
        failures.append(f"targets_low:{section_counts['targets']}")

    pathway_guard = guards.get("pathways") or {}
    if pathway_guard.get("minimum_expected", 0) > 0 and pathway_guard.get("status") != "pass":
        failures.append(f"pathways_low:{section_counts['pathways']}")

    contradiction_guard = guards.get("llm_contradictions") or {}
    if section_counts["literature_rows"] > 0 and contradiction_guard.get("status") != "pass" and section_counts["llm_contradictions"] == 0:
        failures.append("empty:llm_contradictions")

    return failures


async def run_query(qnum: int, query: str, args: argparse.Namespace, save_responses_dir: Path | None) -> Dict[str, Any]:
    classification = classify_query(query)
    started = time.monotonic()
    response_status = 200
    try:
        payload = await asyncio.wait_for(
            _run_cockpit_analysis_payload(
                AnalyzeRequest(query=query, limit=args.limit, execution_mode=args.execution_mode),
                run_id=f"batch-q{qnum}",
            ),
            timeout=args.timeout_seconds,
        )
    except Exception as exc:
        payload = {"errors": [str(exc)]}
        response_status = 500
    elapsed = round(time.monotonic() - started, 1)

    section_counts = _section_counts(payload)
    validation_failures = _validation_failures(payload, section_counts)
    errors_in_response = [str(err) for err in (payload.get("errors") or []) if str(err).strip()]

    result = {
        "qnum": qnum,
        "disease": classification.disease,
        "cohort": classification.cohort,
        "query": query,
        "status": "PASS" if response_status == 200 and not validation_failures else "FAIL",
        "elapsed_s": elapsed,
        "http_status": response_status,
        "validation_failures": validation_failures,
        "section_counts": section_counts,
        "errors_in_response": errors_in_response,
        "error_connectors": sorted({_extract_connector(err) for err in errors_in_response}),
        "quality_guards": payload.get("quality_guards") or {},
        "runtime_diagnostics": payload.get("runtime_diagnostics") or {},
    }

    if save_responses_dir is not None:
        save_responses_dir.mkdir(parents=True, exist_ok=True)
        (save_responses_dir / f"q{qnum}_response.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Q{qnum}: {result['status']} ({elapsed:.1f}s)")
    return result


async def async_main(args: argparse.Namespace) -> None:
    all_queries = load_queries(Path(args.corpus))
    selected_queries = select_queries(all_queries, args)
    if not selected_queries:
        raise ValueError("No queries selected from the corpus.")

    save_responses_dir = Path(args.save_responses_dir) if args.save_responses_dir else None

    started_at = datetime.now(timezone.utc)
    results: List[Dict[str, Any]] = []

    for qnum, query in selected_queries.items():
        results.append(await run_query(qnum, query, args, save_responses_dir))

    finished_at = datetime.now(timezone.utc)
    passed = sum(1 for item in results if item["status"] == "PASS")
    failed = len(results) - passed

    report = {
        "start_time": started_at.isoformat(),
        "end_time": finished_at.isoformat(),
        "range": args.query_ids or f"Q{min(selected_queries)}-Q{max(selected_queries)}",
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / len(results), 3),
        "total_seconds": round((finished_at - started_at).total_seconds(), 1),
        "results": results,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote batch report to {output_path}")


def main() -> None:
    args = parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()