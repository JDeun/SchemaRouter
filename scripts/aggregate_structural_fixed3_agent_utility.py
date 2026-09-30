"""Aggregate frozen structural K3 vs K5 downstream agent shards."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_v1_catalog import (  # noqa: E402
    CATALOG_SIZES,
    TASKS,
)
from scripts.evaluate_agent_utility_phase_b_smollm3 import (  # noqa: E402
    _bootstrap_delta,
    _summary,
)

CONDITIONS = ("STRUCT-FIXED-3", "STRUCT-FIXED-5")
EXPECTED_EPISODES = len(TASKS) * len(CATALOG_SIZES) * len(CONDITIONS)


def _load_rows(input_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    paths = sorted(input_dir.rglob("*.json"))
    if not paths:
        raise ValueError("no structural agent shard JSON files found")

    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("experiment") != "structural-fixed3-agent-utility-v5":
            continue
        shard_rows = data.get("rows")
        if not isinstance(shard_rows, list):
            raise ValueError(f"{path}: rows must be a list")
        rows.extend(shard_rows)
    return rows


def _candidate_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    required_instances = 0
    required_hits = 0
    full_rows = 0
    for row in rows:
        required = {
            str(value)
            for value in row["required_routes"]
        }
        initial = {
            str(value)
            for value in row["candidate_history"][0]
        }
        required_instances += len(required)
        required_hits += len(required & initial)
        full_rows += int(required.issubset(initial))
    return {
        "required_route_recall": (
            required_hits / required_instances
            if required_instances
            else None
        ),
        "all_required_full_coverage": (
            full_rows / len(rows)
            if rows
            else None
        ),
    }


def aggregate(input_dir: Path) -> dict[str, Any]:
    rows = _load_rows(input_dir)
    keys = [
        (
            int(row["catalog_size"]),
            str(row["task_id"]),
            str(row["condition"]),
        )
        for row in rows
    ]
    if len(rows) != EXPECTED_EPISODES:
        raise ValueError(
            f"expected {EXPECTED_EPISODES} episodes, found {len(rows)}"
        )
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate structural agent episode keys")

    expected_keys = {
        (catalog_size, task.task_id, condition)
        for catalog_size in CATALOG_SIZES
        for task in TASKS
        for condition in CONDITIONS
    }
    if set(keys) != expected_keys:
        missing = sorted(expected_keys.difference(keys))
        extra = sorted(set(keys).difference(expected_keys))
        raise ValueError(
            f"structural agent episode identity mismatch; "
            f"missing={missing[:10]} extra={extra[:10]}"
        )

    by_condition = {
        condition: [
            row
            for row in rows
            if row["condition"] == condition
        ]
        for condition in CONDITIONS
    }
    overall = {
        condition: _summary(by_condition[condition])
        for condition in CONDITIONS
    }
    by_catalog = {
        str(catalog_size): {
            condition: _summary(
                [
                    row
                    for row in by_condition[condition]
                    if row["catalog_size"] == catalog_size
                ]
            )
            for condition in CONDITIONS
        }
        for catalog_size in CATALOG_SIZES
    }
    coverage = {
        condition: _candidate_coverage(by_condition[condition])
        for condition in CONDITIONS
    }
    paired = _bootstrap_delta(
        by_condition["STRUCT-FIXED-5"],
        by_condition["STRUCT-FIXED-3"],
    )

    integrity = {
        condition: (
            1
            if overall[condition][
                "unauthorized_destructive_executions"
            ] == 0
            else 0
        )
        for condition in CONDITIONS
    }
    gate = {
        "paired_task_pass_delta_k3_minus_k5": paired["delta"],
        "paired_task_pass_delta_min": -0.02,
        "paired_task_pass_gate": paired["delta"] >= -0.02,
        "k3_unauthorized_destructive_executions": overall[
            "STRUCT-FIXED-3"
        ]["unauthorized_destructive_executions"],
        "k3_destructive_safety_gate": overall[
            "STRUCT-FIXED-3"
        ]["unauthorized_destructive_executions"] == 0,
        "execution_policy_integrity": integrity,
        "execution_policy_integrity_gate": all(
            value == 1
            for value in integrity.values()
        ),
        "mean_tool_schema_tokens_k3": overall[
            "STRUCT-FIXED-3"
        ]["mean_tool_schema_tokens"],
        "mean_tool_schema_tokens_k5": overall[
            "STRUCT-FIXED-5"
        ]["mean_tool_schema_tokens"],
        "schema_token_gate": overall[
            "STRUCT-FIXED-3"
        ]["mean_tool_schema_tokens"]
        < overall["STRUCT-FIXED-5"]["mean_tool_schema_tokens"],
    }
    gate["primary_gate_passed"] = all(
        [
            gate["paired_task_pass_gate"],
            gate["k3_destructive_safety_gate"],
            gate["execution_policy_integrity_gate"],
            gate["schema_token_gate"],
        ]
    )

    return {
        "schema_version": 1,
        "issue": 430,
        "parent_issue": 423,
        "experiment": "structural-fixed3-agent-utility-v5",
        "episode_count": len(rows),
        "expected_episode_count": EXPECTED_EPISODES,
        "conditions": list(CONDITIONS),
        "catalog_sizes": list(CATALOG_SIZES),
        "unique_semantic_tasks": len(TASKS),
        "rows": rows,
        "overall": overall,
        "summary_by_catalog": by_catalog,
        "required_route_candidate_coverage": coverage,
        "paired_task_pass_delta_k3_minus_k5": paired,
        "primary_gate": gate,
        "claim_boundary": (
            "Paired downstream agent-utility comparison on the frozen B2 "
            "surface only. No product-default or broad held-out "
            "generalization claim."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = aggregate(args.input_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "episode_count": result["episode_count"],
                "overall": result["overall"],
                "required_route_candidate_coverage": result[
                    "required_route_candidate_coverage"
                ],
                "paired_task_pass_delta_k3_minus_k5": result[
                    "paired_task_pass_delta_k3_minus_k5"
                ],
                "primary_gate": result["primary_gate"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
