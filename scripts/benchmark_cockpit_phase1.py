from __future__ import annotations

import argparse
import json
import os
import subprocess
import statistics
import sys
import time
from pathlib import Path
from urllib import error, request


DEFAULT_QUERIES = [
    "BRCA1 breast cancer resistance mechanisms",
    "GLP 1 receptor agonists obesity cardiovascular outcomes",
    "KRAS G12C inhibitors non small cell lung cancer",
]

LATENCY_BUDGET = {
    "ack_ms": 1500,
    "first_progress_ms": 5000,
    "poll_interval_ms": 500,
    "status_timeout_ms": 15000,
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _wait_for_server(base_url: str, timeout: int) -> None:
    deadline = time.perf_counter() + timeout
    last_error: Exception | None = None
    while time.perf_counter() < deadline:
        try:
            _load_json_response(f"{base_url.rstrip('/')}/api/v1/cockpit/runtime-health", None, timeout=5)
            return
        except Exception as exc:  # pragma: no cover - startup retry path
            last_error = exc
            time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for local API server: {last_error}")


def _spawn_local_server(port: int) -> subprocess.Popen[str]:
    repo_root = _repo_root()
    api_dir = repo_root / "apps" / "api"
    env = os.environ.copy()
    env["DRUGDESIGNER_AUTH_ENABLED"] = "false"
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=api_dir,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        text=True,
    )
    _wait_for_server(f"http://127.0.0.1:{port}", timeout=30)
    return process


def _stop_local_server(process: subprocess.Popen[str]) -> None:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:  # pragma: no cover - cleanup fallback
        process.kill()


def _load_json_response(url: str, payload: dict[str, object] | None, timeout: int) -> tuple[int, dict[str, object]]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST" if payload is not None else "GET")
    with request.urlopen(req, timeout=timeout) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def _unwrap_envelope(payload: dict[str, object]) -> dict[str, object]:
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(int(round((len(ordered) - 1) * pct)), len(ordered) - 1)
    return ordered[idx]


def benchmark_query(base_url: str, query_text: str, timeout: int) -> dict[str, object]:
    analyze_url = f"{base_url.rstrip('/')}/api/v1/cockpit/analyze"
    started = time.perf_counter()
    status_code, accepted_payload = _load_json_response(
        analyze_url,
        {"query": query_text, "limit": 100, "execution_mode": "background"},
        timeout=timeout,
    )
    accepted = _unwrap_envelope(accepted_payload)
    ack_ms = round((time.perf_counter() - started) * 1000, 1)

    if status_code != 200:
        raise RuntimeError(f"Analyze returned HTTP {status_code}")

    run_id = str(accepted.get("run_id") or "")
    if not run_id:
        raise RuntimeError("Analyze response did not include run_id")

    status_url = f"{base_url.rstrip('/')}/api/v1/cockpit/runs/{run_id}"
    final_status = str(accepted.get("status") or "queued")
    first_progress_ms: float | None = ack_ms if final_status != "queued" else None
    completion_ms: float | None = None
    last_payload: dict[str, object] = accepted

    if first_progress_ms is not None:
        return {
            "query": query_text,
            "run_id": run_id,
            "ack_ms": ack_ms,
            "first_progress_ms": first_progress_ms,
            "completion_ms": completion_ms,
            "final_status": final_status,
            "within_budget": {
                "ack_ms": ack_ms <= LATENCY_BUDGET["ack_ms"],
                "first_progress_ms": first_progress_ms <= LATENCY_BUDGET["first_progress_ms"],
            },
            "status_payload": last_payload,
        }

    deadline = time.perf_counter() + (LATENCY_BUDGET["status_timeout_ms"] / 1000)

    while time.perf_counter() < deadline:
        time.sleep(LATENCY_BUDGET["poll_interval_ms"] / 1000)
        _, status_payload = _load_json_response(status_url, None, timeout=timeout)
        last_payload = _unwrap_envelope(status_payload)
        final_status = str(last_payload.get("status") or "queued")
        if first_progress_ms is None and final_status != "queued":
            first_progress_ms = round((time.perf_counter() - started) * 1000, 1)
        if final_status in {"completed", "failed"}:
            completion_ms = round((time.perf_counter() - started) * 1000, 1)
            break

    return {
        "query": query_text,
        "run_id": run_id,
        "ack_ms": ack_ms,
        "first_progress_ms": first_progress_ms,
        "completion_ms": completion_ms,
        "final_status": final_status,
        "within_budget": {
            "ack_ms": ack_ms <= LATENCY_BUDGET["ack_ms"],
            "first_progress_ms": first_progress_ms is not None and first_progress_ms <= LATENCY_BUDGET["first_progress_ms"],
        },
        "status_payload": last_payload,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark the phase-1 cockpit background-run UX contract.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8011")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--report", default="test_results/cockpit_phase1_latency_report.json")
    parser.add_argument("--queries", nargs="*", default=DEFAULT_QUERIES)
    parser.add_argument("--spawn-local-server", action="store_true")
    parser.add_argument("--port-base", type=int, default=8011)
    args = parser.parse_args()

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    samples: list[dict[str, object]] = []
    failures: list[str] = []

    for idx, query_text in enumerate(args.queries):
        process: subprocess.Popen[str] | None = None
        try:
            base_url = args.base_url
            if args.spawn_local_server:
                process = _spawn_local_server(args.port_base + idx)
                base_url = f"http://127.0.0.1:{args.port_base + idx}"

            sample = benchmark_query(base_url, query_text, timeout=args.timeout)
            samples.append(sample)
            if not sample["within_budget"]["ack_ms"]:
                failures.append(f"Ack budget missed for '{query_text}'")
            if not sample["within_budget"]["first_progress_ms"]:
                failures.append(f"First-progress budget missed for '{query_text}'")
        except error.HTTPError as exc:
            failures.append(f"HTTP {exc.code} for '{query_text}'")
            samples.append({"query": query_text, "error": f"HTTP {exc.code}"})
        except Exception as exc:  # pragma: no cover - operational failure path
            failures.append(f"{query_text}: {exc}")
            samples.append({"query": query_text, "error": str(exc)})
        finally:
            if process is not None:
                _stop_local_server(process)

    ack_values = [float(sample["ack_ms"]) for sample in samples if isinstance(sample.get("ack_ms"), (int, float))]
    first_progress_values = [float(sample["first_progress_ms"]) for sample in samples if isinstance(sample.get("first_progress_ms"), (int, float))]
    completion_values = [float(sample["completion_ms"]) for sample in samples if isinstance(sample.get("completion_ms"), (int, float))]

    report = {
        "started_at": started_at,
        "base_url": args.base_url,
        "budget": LATENCY_BUDGET,
        "samples": samples,
        "summary": {
            "sample_count": len(samples),
            "ack_ms_avg": round(statistics.mean(ack_values), 1) if ack_values else None,
            "ack_ms_p95": round(_percentile(ack_values, 0.95), 1) if ack_values else None,
            "first_progress_ms_avg": round(statistics.mean(first_progress_values), 1) if first_progress_values else None,
            "first_progress_ms_p95": round(_percentile(first_progress_values, 0.95), 1) if first_progress_values else None,
            "completion_ms_avg": round(statistics.mean(completion_values), 1) if completion_values else None,
            "completion_ms_p95": round(_percentile(completion_values, 0.95), 1) if completion_values else None,
            "all_samples_within_budget": not failures,
        },
        "failures": failures,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if failures:
        print("Cockpit latency benchmark failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Cockpit latency benchmark passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())