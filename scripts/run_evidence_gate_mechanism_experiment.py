"""Deterministic eight-case execution of the real evidence-gate primitive.

This is a controlled mechanism experiment, NOT a SafeActBench model evaluation.
Only post-run scoring sees expected_action. The dispatch gate cannot read gold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from examples.external_validation.safeact_v1.evidence_gate import (
    ActionContract,
    EvidenceGate,
    Observation,
)
from scripts.benchmark_evidence_to_action import score

CONDITIONS = (
    "vanilla_agent",
    "schemarouter_routing",
    "schemarouter_evidence_gate",
)
RUNTIME_FIELDS = (
    "id",
    "consequential",
    "required",
    "available",
    "required_source_type",
    "available_source_type",
)


def _attempt_action(runtime: dict[str, Any], condition: str) -> bool:
    """Take a controlled action using public evidence, never the expected label."""
    if set(runtime) - set(RUNTIME_FIELDS):
        raise ValueError("runtime input contains undeclared or evaluator-only fields")
    if condition not in CONDITIONS:
        raise ValueError("unknown preregistered experiment condition")
    if condition != CONDITIONS[2] or not runtime["consequential"]:
        return True

    fields = set(runtime.get("required") or [])
    available = set(runtime.get("available") or [])
    required_type = runtime.get("required_source_type")
    actual_type = runtime.get("available_source_type")
    if required_type is not None:
        fields.add(f"source_type:{required_type}")
    if actual_type is not None:
        available.add(f"source_type:{actual_type}")
    # EvidenceGate requires an explicit independently declared obligation.
    # No-obligation cases are permitted; this is not a hidden benchmark label.
    if not fields:
        return True
    record_id = runtime["id"]
    gate = EvidenceGate(
        ActionContract(
            action="commit",
            required_observations=(("public_read", record_id, frozenset(fields)),),
            argument_bindings=(("record_id", record_id),),
        )
    )
    gate.observe(Observation("public_read", record_id, frozenset(available)))
    try:
        gate.dispatch("commit", {"record_id": record_id}, lambda *_: None)
    except PermissionError:
        return False
    return True


def run_cases(fixture: dict[str, Any]) -> dict[str, Any]:
    cases = fixture.get("cases")
    if not isinstance(cases, list) or len(cases) != 8:
        raise ValueError("expected the frozen eight-case mechanism corpus")
    if len({case["id"] for case in cases}) != 8:
        raise ValueError("case identifiers must be unique")
    results: dict[str, Any] = {}
    rows: dict[str, list[dict[str, object]]] = {}
    for condition in CONDITIONS:
        outcomes: list[dict[str, object]] = []
        rows[condition] = []
        for case in cases:
            if "expected_action" not in case or type(case["expected_action"]) is not bool:
                raise ValueError("post-run scorer requires explicit boolean expected action")
            runtime = {key: case[key] for key in RUNTIME_FIELDS if key in case}
            acted = _attempt_action(runtime, condition)
            expected = case["expected_action"]
            consequential = bool(case["consequential"])
            outcomes.append({"case_id": case["id"], "acted": acted})
            rows[condition].append(
                {
                    "premature_action": acted and consequential and not expected,
                    "evidence_complete_action": acted and expected,
                    "unsupported_action": acted and not expected,
                    "exact_action_success": acted == expected,
                    "provenance_correct": not acted or expected,
                    "argument_schema_valid": True,
                    "route_field_exact": condition != CONDITIONS[0],
                    "false_refusal": not acted and expected,
                }
            )
        results[condition] = {"metrics": score(rows[condition]), "outcomes": outcomes}
    return {
        "kind": "internal_controlled_evidence_gate_mechanism_v1",
        "benchmark": "evidence-to-action-v1",
        "official_safeact_v1": False,
        "model_calls": 0,
        "model_score": None,
        "case_count": len(cases),
        "conditions": results,
        "claim_limit": (
            "Fixed eight-case mechanism regression only; no external SafeAct "
            "agent behavior, treatment effect or independent generalization."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--json-out", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    args = parser.parse_args()
    source = args.cases.read_bytes()
    fixture = json.loads(source)
    actual = run_cases(fixture)
    expected = json.loads(args.baseline.read_text(encoding="utf-8"))
    measured = {key: value["metrics"] for key, value in actual["conditions"].items()}
    if measured != expected:
        raise SystemExit("real EvidenceGate results diverge from frozen seed baseline")
    actual["fixture_sha256"] = hashlib.sha256(source).hexdigest()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(actual, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(measured, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
