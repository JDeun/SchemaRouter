"""Evaluate the frozen lightweight candidate on an independent fresh surface."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

import analyze_lightweight_negative_gte_executable_v4 as frozen

MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "operation-routing-v4-lightweight-negative-gte-executable.json"
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _fresh_gate(summary: dict[str, Any], manifest: dict[str, Any]) -> bool:
    gate = manifest["gate"]
    latency_p95 = summary["total_latency_ms"]["p95"]
    return (
        summary["supported_exact_route_accuracy"]
        >= float(gate["supported_exact_route_accuracy_min"])
        and summary["near_domain_unsupported_rejection"]
        >= float(gate["near_domain_unsupported_rejection_min"])
        and summary["out_of_domain_rejection"]
        == float(gate["out_of_domain_rejection"])
        and summary["false_route_rate"]
        <= float(gate["false_route_rate_max"])
        and summary["authority_violations"]
        <= int(gate["authority_violations_max"])
        and summary["execution_errors"]
        <= int(gate["execution_errors_max"])
        and latency_p95 is not None
        and float(latency_p95) <= float(gate["p95_ms_max"])
    )


def evaluate_fresh(
    cases: list[dict[str, Any]],
    *,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    # The frozen evaluator requires a DEV parity reference. For fresh confirmation,
    # provide a neutral same-ID reference so the exact frozen scoring/decision code
    # runs unchanged. DEV-reference parity fields are diagnostics only and are not
    # part of the fresh gate.
    neutral = {
        "rows": [
            {
                "case_id": str(case["id"]),
                "final_route": None,
            }
            for case in cases
        ]
    }
    with tempfile.TemporaryDirectory() as tmp:
        reference_path = Path(tmp) / "neutral-reference.json"
        reference_path.write_text(
            json.dumps(neutral, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result = frozen.evaluate(
            cases,
            manifest=manifest,
            reference_path=reference_path,
        )

    summary = result["summary"]
    summary["fresh_confirmation_gate_pass"] = _fresh_gate(summary, manifest)
    result["dataset_role"] = "fresh_surface_development_confirmation"
    result["policy"]["dev_reference_parity_is_not_a_fresh_gate"] = True
    result["policy"]["semantic_retuning_after_freeze"] = False
    result["policy"]["fresh_surface_used_for_tuning"] = False
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cases = _load_json(args.corpus)
    if not isinstance(cases, list) or any(not isinstance(row, dict) for row in cases):
        raise ValueError("corpus must be a list of objects")
    if len(cases) != 1800:
        raise ValueError(f"fresh corpus must contain 1800 rows, got {len(cases)}")

    manifest = _load_json(args.manifest)
    result = evaluate_fresh(cases, manifest=manifest)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
