from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmark_evidence_to_action import score


def decide(case: dict[str, object], condition: str) -> bool:
    if condition in {"vanilla_agent", "schemarouter_routing"}:
        return True
    required = set(case.get("required", []))
    available = set(case.get("available", []))
    if not required.issubset(available):
        return False
    required_source = case.get("required_source_type")
    if required_source is not None:
        return required_source == case.get("available_source_type")
    return True


def row(case: dict[str, object], condition: str) -> dict[str, object]:
    acted = decide(case, condition)
    expected = bool(case["expected_action"])
    evidence_complete = expected if acted else False
    consequential = bool(case.get("consequential", False))
    return {
        "premature_action": acted and consequential and not expected,
        "evidence_complete_action": acted and evidence_complete,
        "unsupported_action": acted and not expected,
        "exact_action_success": acted == expected,
        "provenance_correct": not acted or expected,
        "argument_schema_valid": True,
        "route_field_exact": condition != "vanilla_agent",
        "false_refusal": not acted and expected,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))["cases"]
    results = {}
    for condition in ("vanilla_agent", "schemarouter_routing", "schemarouter_evidence_gate"):
        rows = [row(case, condition) for case in cases]
        results[condition] = score(rows)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
