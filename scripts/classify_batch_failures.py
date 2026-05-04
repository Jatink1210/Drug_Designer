from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify autonomous batch failures by connector, module, and symptom.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def _extract_connector(error_text: str) -> str:
    if ":" in error_text:
        return error_text.split(":", 1)[0].strip()
    return "unknown"


def _extract_symptom(validation_failure: str) -> str:
    if ":" in validation_failure:
        return validation_failure.split(":", 1)[0].strip()
    return validation_failure.strip()


def _module_for_symptom(symptom: str) -> str:
    if symptom.startswith("targets_low") or symptom.startswith("pathways_low"):
        return "quality_guards"
    if symptom.startswith("empty"):
        return "literature_analysis"
    return "unknown"


def build_classification(report: Dict[str, Any]) -> Dict[str, Any]:
    by_connector: Counter[str] = Counter()
    by_symptom: Counter[str] = Counter()
    by_module: Counter[str] = Counter()
    failed_queries: List[Dict[str, Any]] = []
    pass_rate = report.get("pass_rate")
    if pass_rate is None and report.get("total"):
        pass_rate = round((report.get("passed", 0) / report.get("total", 1)), 3)

    for item in report.get("results", []):
        connectors = sorted({_extract_connector(err) for err in item.get("errors_in_response", [])})
        symptoms = [_extract_symptom(failure) for failure in item.get("validation_failures", [])]
        modules = sorted({_module_for_symptom(symptom) for symptom in symptoms})

        for connector in connectors:
            by_connector[connector] += 1
        for symptom in symptoms:
            by_symptom[symptom] += 1
            by_module[_module_for_symptom(symptom)] += 1

        if item.get("status") == "FAIL" or connectors or symptoms:
            failed_queries.append({
                "qnum": item.get("qnum"),
                "status": item.get("status"),
                "connectors": connectors,
                "modules": modules,
                "symptoms": symptoms,
                "validation_failures": item.get("validation_failures", []),
                "errors_in_response": item.get("errors_in_response", []),
            })

    return {
        "source_report": report.get("range"),
        "summary": {
            "total": report.get("total", 0),
            "passed": report.get("passed", 0),
            "failed": report.get("failed", 0),
            "pass_rate": pass_rate,
        },
        "by_connector": dict(sorted(by_connector.items())),
        "by_module": dict(sorted(by_module.items())),
        "by_symptom": dict(sorted(by_symptom.items())),
        "failed_queries": failed_queries,
    }


def main() -> None:
    args = parse_args()
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    classification = build_classification(report)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(classification, indent=2), encoding="utf-8")
    print(f"Wrote classification report to {output_path}")


if __name__ == "__main__":
    main()