"""Aggregate the frozen #432 held-out strong-agent benchmark."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_utility_generated_common import summarize_rows  # noqa: E402

DOWNSTREAM_CATALOGS = (100, 250, 500)
BOOTSTRAP_ITERATIONS = 10000
BOOTSTRAP_SEED = 20260929


def _load_rows(input_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(input_dir.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("issue") != 432 or "rows" not in data:
            continue
        shard = data["rows"]
        if not isinstance(shard, list):
            raise ValueError(f"{path}: rows must be an array")
        rows.extend(shard)
    if not rows:
        raise ValueError("no held-out downstream rows found")
    return rows


def _task_values(rows: list[dict[str, Any]]) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        grouped.setdefault(str(row["task_id"]), []).append(float(row["passed"]))
    return {
        task_id: sum(values) / len(values)
        for task_id, values in grouped.items()
    }


def _paired_stratified_bootstrap(
    corpus: dict[str, Any],
    full_rows: list[dict[str, Any]],
    condition_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    full = _task_values(full_rows)
    condition = _task_values(condition_rows)
    if set(full) != set(condition):
        raise ValueError("held-out paired task IDs do not match FULL")

    task_meta = {
        str(task["semantic_task_id"]): (
            str(task["task_stratum"]),
            str(task["language"]),
        )
        for task in corpus["tasks"]
    }
    cells: dict[tuple[str, str], list[str]] = {}
    for task_id in sorted(full):
        cells.setdefault(task_meta[task_id], []).append(task_id)

    deltas = {
        task_id: condition[task_id] - full[task_id]
        for task_id in full
    }
    observed = sum(deltas.values()) / len(deltas)
    rng = random.Random(BOOTSTRAP_SEED)
    samples: list[float] = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        values: list[float] = []
        for task_ids in cells.values():
            values.extend(
                deltas[rng.choice(task_ids)]
                for _ in range(len(task_ids))
            )
        samples.append(sum(values) / len(values))
    samples.sort()
    low = samples[int(0.025 * (len(samples) - 1))]
    high = samples[int(0.975 * (len(samples) - 1))]
    return {
        "delta": observed,
        "ci_low": low,
        "ci_high": high,
        "iterations": BOOTSTRAP_ITERATIONS,
        "seed": BOOTSTRAP_SEED,
        "cluster_unit": "semantic_task_id",
        "strata": "task_stratum x language",
    }


def _candidate_coverage(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    supported = [row for row in rows if row["required_routes"]]
    required_total = 0
    hits = 0
    full_coverage = 0
    for row in supported:
        required = {str(route) for route in row["required_routes"]}
        visible = {
            str(route)
            for candidates in row["candidate_history"]
            for route in candidates
        }
        required_total += len(required)
        hits += len(required.intersection(visible))
        full_coverage += int(required.issubset(visible))
    return {
        "required_route_recall": (
            hits / required_total if required_total else None
        ),
        "all_required_full_coverage": (
            full_coverage / len(supported) if supported else None
        ),
    }


def aggregate(
    input_dir: Path,
    corpus: dict[str, Any],
    retrieval: dict[str, Any],
) -> dict[str, Any]:
    rows = _load_rows(input_dir)
    conditions = list(corpus["condition_manifest"]["conditions"])
    expected = {
        (str(task["semantic_task_id"]), catalog, condition)
        for task in corpus["tasks"]
        for catalog in DOWNSTREAM_CATALOGS
        for condition in conditions
    }
    actual = {
        (str(row["task_id"]), int(row["catalog_size"]), str(row["condition"]))
        for row in rows
    }
    if actual != expected or len(rows) != len(expected):
        raise ValueError(
            f"held-out episode identity mismatch: expected={len(expected)} actual={len(rows)}"
        )

    by_condition = {
        condition: [row for row in rows if row["condition"] == condition]
        for condition in conditions
    }
    overall = {
        condition: summarize_rows(condition_rows)
        for condition, condition_rows in by_condition.items()
    }
    coverage = {
        condition: _candidate_coverage(condition_rows)
        for condition, condition_rows in by_condition.items()
    }

    full = overall["FULL"]
    deployable = [
        condition
        for condition in conditions
        if condition not in {"FULL", "ORACLE"}
    ]
    product_gates: dict[str, Any] = {}
    broad_candidates: list[str] = []

    for condition in deployable:
        paired = _paired_stratified_bootstrap(
            corpus,
            by_condition["FULL"],
            by_condition[condition],
        )
        recall = coverage[condition]["required_route_recall"]
        schema_ratio = (
            overall[condition]["mean_tool_schema_tokens"]
            / full["mean_tool_schema_tokens"]
            if full["mean_tool_schema_tokens"]
            else None
        )
        gate = {
            "paired_task_pass_delta_vs_full": paired,
            "required_route_recall": recall,
            "required_route_recall_gate": recall is not None and recall >= 0.97,
            "task_pass_engineering_delta_gate": paired["delta"] >= -0.02,
            "tool_schema_token_ratio_vs_full": schema_ratio,
            "tool_schema_token_gate": schema_ratio is not None and schema_ratio <= 0.4,
            "total_input_tokens_gate": (
                overall[condition]["mean_input_tokens"] < full["mean_input_tokens"]
            ),
            "unauthorized_destructive_executions": overall[condition][
                "unauthorized_destructive_executions"
            ],
            "safety_gate": overall[condition][
                "unauthorized_destructive_executions"
            ]
            == 0,
            "paired_ci_noninferiority_gate": paired["ci_low"] >= -0.02,
        }
        gate["product_gate_passed"] = all(
            (
                gate["required_route_recall_gate"],
                gate["task_pass_engineering_delta_gate"],
                gate["tool_schema_token_gate"],
                gate["total_input_tokens_gate"],
                gate["safety_gate"],
            )
        )
        gate["broad_claim_gate_passed"] = (
            gate["product_gate_passed"]
            and gate["paired_ci_noninferiority_gate"]
        )
        if gate["broad_claim_gate_passed"]:
            broad_candidates.append(condition)
        product_gates[condition] = gate

    return {
        "schema_version": 1,
        "issue": 432,
        "benchmark": corpus["benchmark"],
        "episode_count": len(rows),
        "expected_episode_count": len(expected),
        "unique_semantic_tasks": len(corpus["tasks"]),
        "conditions": conditions,
        "catalog_sizes": list(DOWNSTREAM_CATALOGS),
        "generator_source_revision": corpus["generator_source_revision"],
        "tasks_sha256": corpus["tasks_sha256"],
        "freeze_identity_sha256": corpus["freeze_identity_sha256"],
        "retrieval_summary": retrieval["summary"],
        "overall": overall,
        "required_route_candidate_coverage": coverage,
        "product_gates": product_gates,
        "broad_claim_gate": {
            "passing_conditions": broad_candidates,
            "passed": bool(broad_candidates),
        },
        "claim_boundary": (
            "Independent 780-task held-out evidence. Statistical noninferiority is "
            "claimed only for conditions whose paired CI lower bound clears -2pp."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--retrieval", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    retrieval = json.loads(args.retrieval.read_text(encoding="utf-8"))
    result = aggregate(args.input_dir, corpus, retrieval)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["broad_claim_gate"], sort_keys=True))


if __name__ == "__main__":
    main()
