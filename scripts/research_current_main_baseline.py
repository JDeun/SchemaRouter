"""Current-code, development-only SchemaRouter baseline orchestration (#1412).

Runs two pre-existing benchmarks on the checked-out source: synthetic catalog
break-even plus the Gearlynx E1 retrieval hot path. It does not execute tools,
invoke an LLM, create a holdout, optimize thresholds, or certify agent success.
It deliberately does not run/fork frozen 0.14 held-out evaluation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "scripts/benchmark_realistic_break_even.py",
    "scripts/benchmark_retrieval_hot_path.py",
    "scripts/external_validation_gearlynx.py",
    "src/schemarouter/planner.py",
    "src/schemarouter/models.py",
    "src/schemarouter/runtime.py",
    "src/schemarouter/authorization.py",
    "src/schemarouter/executor.py",
)
SIZES = (20, 50, 100, 250, 500)
AMBIGUITIES = ("low", "medium", "high")
METHODS = (
    "lexical_baseline",
    "schema_lexical_baseline",
    "schemarouter_full",
    "schemarouter_auto",
)
INDICATORS = (
    "required_tool_recall",
    "unsupported_rejection",
    "false_route_rate",
    "mean_selected_contract_bytes",
    "p50_ms",
    "p95_ms",
)
# The original benchmark calls the presence of an unsupported shortlist
# "false_route". It is NOT evidence of an unauthorized tool dispatch.
LIMITS = {
    "source_class": "previously_visible_synthetic_and_gearlynx_dev",
    "independent_validation": False,
    "agent_task_success_measured": False,
    "authorization_or_execution_measured": False,
    "may_promote": False,
    "may_release": False,
}


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _strict_number(value: Any, *, rate: bool = False) -> float:
    if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        raise ValueError("negative/nonfinite/non-numeric baseline metric")
    if rate and value > 1:
        raise ValueError("baseline rate exceeds 1")
    return float(value)


def validate_break_even(report: dict[str, Any]) -> list[dict[str, Any]]:
    if (
        not isinstance(report, dict)
        or report.get("schema_version") != 1
        or report.get("benchmark") != "realistic-catalog-break-even"
        or report.get("sizes") != list(SIZES)
        or report.get("ambiguities") != list(AMBIGUITIES)
    ):
        raise ValueError("unexpected baseline benchmark schema")
    cells = report.get("matrix")
    if not isinstance(cells, list) or len(cells) != 15:
        raise ValueError("incomplete catalog/ambiguity matrix")
    seen: set[tuple[int, str]] = set()
    comparisons = []
    for cell in cells:
        if not isinstance(cell, dict):
            raise ValueError("invalid matrix cell")
        size, ambiguity = cell.get("catalog_size"), cell.get("ambiguity")
        if type(size) is not int or size not in SIZES or ambiguity not in AMBIGUITIES:
            raise ValueError("unregistered matrix cell")
        key = (size, ambiguity)
        if key in seen:
            raise ValueError("duplicate matrix cell")
        seen.add(key)
        if (
            type(cell.get("auto_full_selection_mismatches")) is not int
            or cell["auto_full_selection_mismatches"] != 0
        ):
            raise ValueError("indexed/exhaustive candidate disagreement")
        if (
            type(cell.get("supported_cases")) is not int
            or cell["supported_cases"] < 1
            or type(cell.get("unsupported_cases")) is not int
            or cell["unsupported_cases"] < 1
        ):
            raise ValueError("invalid supported/unsupported denominator")
        methods = cell.get("methods")
        if not isinstance(methods, dict) or set(methods) != set(METHODS):
            raise ValueError("missing comparison method")
        for metrics in methods.values():
            if not isinstance(metrics, dict):
                raise ValueError("invalid metric envelope")
            for indicator in INDICATORS:
                _strict_number(
                    metrics.get(indicator),
                    rate=indicator in (
                        "required_tool_recall", "unsupported_rejection", "false_route_rate"
                    ),
                )
            if not math.isclose(
                metrics["unsupported_rejection"] + metrics["false_route_rate"],
                1.0, rel_tol=0, abs_tol=1e-8,
            ):
                raise ValueError("unsupported cohort rates do not sum to one")
        auto = methods["schemarouter_auto"]
        exhaustive = methods["schemarouter_full"]
        for name in (
            "required_tool_recall",
            "unsupported_rejection",
            "false_route_rate",
            "mean_selected_contract_bytes",
        ):
            if not math.isclose(auto[name], exhaustive[name], rel_tol=0, abs_tol=1e-10):
                raise ValueError(f"indexed/exhaustive outcome drift: {name}")
        comparisons.append({
            "catalog_size": size,
            "ambiguity": ambiguity,
            "supported_cases": cell["supported_cases"],
            "unsupported_cases": cell["unsupported_cases"],
            "sr_top3_supported_tool_recall": auto["required_tool_recall"],
            "sr_unsupported_nonempty_shortlist_rate": auto["false_route_rate"],
            "sr_mean_selected_contract_bytes": auto["mean_selected_contract_bytes"],
            "sr_request_p95_ms": auto["p95_ms"],
            "schema_lexical_supported_tool_recall":
                methods["schema_lexical_baseline"]["required_tool_recall"],
            "schema_lexical_unsupported_nonempty_shortlist_rate":
                methods["schema_lexical_baseline"]["false_route_rate"],
        })
    if seen != {(s, a) for s in SIZES for a in AMBIGUITIES}:
        raise ValueError("missing matrix cell")
    return sorted(comparisons, key=lambda c: (c["catalog_size"], c["ambiguity"]))


def validate_hot_path(report: dict[str, Any]) -> dict[str, Any]:
    if (
        not isinstance(report, dict)
        or report.get("schema_version") != 2
        or report.get("benchmark") != "retrieval-hot-path-gearlynx-e1"
        or report.get("semantic_mismatches") != []
        or report.get("lightweight_semantic_mismatches") != []
    ):
        raise ValueError("hot-path source or indexed result drift")
    count = report.get("case_count")
    if type(count) is not int or count < 1:
        raise ValueError("empty Gearlynx case count")
    for name in (
        "optimized_typed",
        "optimized_route_refs",
        "legacy_typed_snapshot_copy",
        "legacy_route_refs_snapshot_copy",
    ):
        row = report.get(name)
        if not isinstance(row, dict):
            raise ValueError("missing hot-path condition")
        for metric in ("median_ms", "p95_ms", "mean_ms"):
            _strict_number(row.get(metric))
        if type(row.get("sample_count")) is not int or row["sample_count"] < count:
            raise ValueError("missing request-level timing samples")
    return {
        "case_count": count,
        "typed_p95_ms": report["optimized_typed"]["p95_ms"],
        "route_ref_p95_ms": report["optimized_route_refs"]["p95_ms"],
        "legacy_typed_p95_ms": report["legacy_typed_snapshot_copy"]["p95_ms"],
        "semantic_mismatches": 0,
        "lightweight_semantic_mismatches": 0,
    }


def source_identity() -> dict[str, Any]:
    git = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
        text=True, check=True, timeout=10,
    ).stdout.strip()
    if len(git) != 40 or any(c not in "0123456789abcdef" for c in git):
        raise ValueError("invalid checked-out git commit")
    files = {
        path: sha256((ROOT / path).read_bytes())
        for path in SOURCES
    }
    return {
        "git_commit": git,
        "tracked_file_sha256": files,
        "source_manifest_sha256": sha256(canonical(files)),
        "python": platform.python_version(),
        "os": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "workflow_run_id": os.getenv("GITHUB_RUN_ID"),
        "measurement_hardware": "current_runner_not_cross_host_comparable",
    }


def build_report(
    break_even: dict[str, Any], hot_path: dict[str, Any], identity: dict[str, Any],
) -> dict[str, Any]:
    rows = validate_break_even(break_even)
    gearlynx = validate_hot_path(hot_path)
    if not isinstance(identity, dict) or len(str(identity.get("git_commit", ""))) != 40:
        raise ValueError("missing baseline source identity")
    return {
        "schema_version": 1,
        "id": "current-main-research-baseline-v1",
        "identity": identity,
        "scope": LIMITS.copy(),
        "comparison": rows,
        "gearlynx_hot_path": gearlynx,
        "unmeasured_requirements": [
            "independent_agent_task_success_full_sr_k_progressive_oracle",
            "required_tool_set_full_coverage_and_required_field_recall",
            "end_to_end_latency_and_prompt_tokens",
            "real_100_250_500_heterogeneous_catalogs_across_en_ko_ja",
            "host_principal_policy_execution_and_destructive_action_trace",
            "novel_query_disjoint_confirmation",
        ],
        "raw_sha256": {
            "realistic_break_even": sha256(canonical(break_even)),
            "gearlynx_hot_path": sha256(canonical(hot_path)),
        },
    }


def _registered_runner(path: str, output: Path, iterations: int) -> None:
    if iterations < 1 or iterations > 10:
        raise ValueError("offline budget permits 1..10 iterations per case")
    if path not in SOURCES[:2]:
        raise ValueError("unregistered research benchmark executable")
    # No shell, no arbitrary workflow/executor names. The workflow token is read-only.
    subprocess.run(
        [sys.executable, path, "--iterations", str(iterations), "--json-out", str(output)],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=900,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/current-main-baseline")
    )
    args = parser.parse_args()
    if args.iterations < 1 or args.iterations > 10:
        parser.error("--iterations must be in [1,10]")
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    identity = source_identity()
    raw_paths = {
        "realistic": root / "realistic-break-even.json",
        "gearlynx": root / "gearlynx-hot-path.json",
    }
    _registered_runner(SOURCES[0], raw_paths["realistic"], args.iterations)
    _registered_runner(SOURCES[1], raw_paths["gearlynx"], args.iterations)
    raw = {
        name: json.loads(path.read_text(encoding="utf-8"))
        for name, path in raw_paths.items()
    }
    result = build_report(raw["realistic"], raw["gearlynx"], identity)
    (root / "baseline.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "CURRENT_CODE_DEV_ONLY",
        "source": identity["git_commit"],
        "matrix_cells": len(result["comparison"]),
        "gearlynx_cases": result["gearlynx_hot_path"]["case_count"],
        "independent": False,
        "agent_success": "NOT_MEASURED",
        "output": str(root / "baseline.json"),
    }))
    for row in result["comparison"]:
        print(json.dumps({
            "catalog": row["catalog_size"],
            "ambiguity": row["ambiguity"],
            "sr_top3_recall": row["sr_top3_supported_tool_recall"],
            "schema_lexical_top3_recall": row["schema_lexical_supported_tool_recall"],
            "unsupported_nonempty": row["sr_unsupported_nonempty_shortlist_rate"],
        }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
