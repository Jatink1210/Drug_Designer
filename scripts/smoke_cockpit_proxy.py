from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib import error, request


def _post_json(url: str, payload: dict[str, object], timeout: int) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a long Cockpit request through the local nginx proxy and fail on 504.")
    parser.add_argument("--url", default="http://localhost:3000/api/v1/cockpit/analyze")
    parser.add_argument("--query", default="KRAS G12C inhibitor resistance mechanisms in non small cell lung cancer")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--report", default="test_results/cockpit_proxy_smoke.json")
    args = parser.parse_args()

    started = time.perf_counter()
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report: dict[str, object] = {
        "url": args.url,
        "query": args.query,
        "limit": args.limit,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    try:
        status_code, body = _post_json(
            args.url,
            {"query": args.query, "limit": args.limit},
            timeout=args.timeout,
        )
    except error.HTTPError as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        report.update({
            "elapsed_ms": elapsed_ms,
            "status_code": exc.code,
            "ok": False,
            "error": exc.read().decode("utf-8", errors="replace")[:1000],
        })
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if exc.code == 504:
            print(f"Proxy smoke failed: nginx returned 504 after {elapsed_ms}ms")
        else:
            print(f"Proxy smoke failed: HTTP {exc.code} after {elapsed_ms}ms")
        return 1
    except Exception as exc:  # pragma: no cover - operational failure path
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        report.update({
            "elapsed_ms": elapsed_ms,
            "ok": False,
            "error": str(exc),
        })
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Proxy smoke failed: {exc}")
        return 1

    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    parsed_body: object
    try:
        parsed_body = json.loads(body)
    except json.JSONDecodeError:
        parsed_body = body[:1000]

    report.update({
        "elapsed_ms": elapsed_ms,
        "status_code": status_code,
        "ok": status_code == 200,
        "response": parsed_body,
    })
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if status_code != 200:
        print(f"Proxy smoke failed: HTTP {status_code} after {elapsed_ms}ms")
        return 1

    print(f"Proxy smoke passed: HTTP 200 after {elapsed_ms}ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())