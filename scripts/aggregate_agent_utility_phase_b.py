"""Aggregate sharded #420 B1 agent-utility results."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_v1_catalog import TASKS  # noqa: E402
from scripts.evaluate_agent_utility_phase_b_qwen import (  # noqa: E402
    _bootstrap_delta,
    _summary,
)

DEPLOYABLE = ("SR-3", "SR-5", "SR-10", "SR-PROGRESSIVE")
RETRIEVAL_ELIGIBLE = {
    "SR-3": False,
    "SR-5": True,
    "SR-10": True,
    "SR-PROGRESSIVE": True,
}


def aggregate(paths: list[Path]) -> dict[str, Any]:
    if not paths:
        raise ValueError("no B1 shard results supplied")

    loaded = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    models = {
        (
            row["model"]["name"],
            row["model"]["revision"],
            row["model"]["dtype"],
            row["model"]["device"],
            row["model"]["context_limit"],
        )
        for row in loaded
    }
    if len(models) != 1:
        raise ValueError(f"model identity drift across shards: {models}")

    rows = [
        episode
        for result in loaded
        for episode in result["rows"]
    ]
    expected_task_ids = {task.task_id for task in TASKS}
    expected_conditions = {
        "FULL",
        "SR-3",
        "SR-5",
        "SR-10",
        "SR-PROGRESSIVE",
        "ORACLE",
    }
    episode_keys = [
        (
            int(row["catalog_size"]),
            str(row["task_id"]),
            str(row["condition"]),
        )
        for row in rows
    ]
    if len(set(episode_keys)) != len(episode_keys):
        raise ValueError("duplicate B1 episode key detected")

    actual_task_ids = {str(row["task_id"]) for row in rows}
    unknown_task_ids = sorted(actual_task_ids.difference(expected_task_ids))
    if unknown_task_ids:
        raise ValueError(
            "unknown B1 task id(s): " + ", ".join(unknown_task_ids)
        )

    actual_conditions = {str(row["condition"]) for row in rows}
    if actual_conditions != expected_conditions:
        raise ValueError(
            "condition set drift: "
            f"expected={sorted(expected_conditions)} "
            f"actual={sorted(actual_conditions)}"
        )

    expected_sizes = {20, 50, 100, 250}
    actual_sizes = {int(row["catalog_size"]) for row in rows}
    if actual_sizes != expected_sizes:
        raise ValueError(
            f"catalog shards incomplete: expected={expected_sizes} actual={actual_sizes}"
        )

    conditions = ("FULL", "SR-3", "SR-5", "SR-10", "SR-PROGRESSIVE", "ORACLE")
    summary_by_catalog: dict[str, Any] = {}
    for size in sorted(expected_sizes):
        summary_by_catalog[str(size)] = {}
        for condition in conditions:
            subset = [
                row
                for row in rows
                if int(row["catalog_size"]) == size
                and row["condition"] == condition
            ]
            subset_task_ids = {str(row["task_id"]) for row in subset}
            if subset_task_ids != expected_task_ids:
                missing = sorted(expected_task_ids.difference(subset_task_ids))
                unexpected = sorted(subset_task_ids.difference(expected_task_ids))
                raise ValueError(
                    f"{size}/{condition} frozen task set mismatch: "
                    f"missing={missing} unexpected={unexpected}"
                )
            if len(subset) != len(expected_task_ids):
                raise ValueError(
                    f"{size}/{condition} expected {len(expected_task_ids)} rows, "
                    f"got {len(subset)}"
                )
            summary_by_catalog[str(size)][condition] = _summary(subset)

    overall = {
        condition: _summary(
            [row for row in rows if row["condition"] == condition]
        )
        for condition in conditions
    }

    full_rows = [row for row in rows if row["condition"] == "FULL"]
    paired = {
        condition: _bootstrap_delta(
            full_rows,
            [row for row in rows if row["condition"] == condition],
        )
        for condition in DEPLOYABLE
    }

    full = overall["FULL"]
    utility_gates: dict[str, Any] = {}
    for condition in DEPLOYABLE:
        current = overall[condition]
        full_schema = float(full["mean_tool_schema_tokens"])
        current_schema = float(current["mean_tool_schema_tokens"])
        schema_ratio = (
            current_schema / full_schema if full_schema > 0 else None
        )
        pass_delta = (
            float(current["task_pass_rate"]) - float(full["task_pass_rate"])
        )
        gates = {
            "retrieval_eligible": RETRIEVAL_ELIGIBLE[condition],
            "task_pass_noninferior_minus_2pp": pass_delta >= -0.02,
            "tool_schema_tokens_at_most_40pct_full": (
                schema_ratio is not None and schema_ratio <= 0.40
            ),
            "total_input_tokens_less_than_full": (
                float(current["mean_input_tokens"])
                < float(full["mean_input_tokens"])
            ),
            "unauthorized_destructive_executions_zero": (
                int(current["unauthorized_destructive_executions"]) == 0
            ),
        }
        utility_gates[condition] = {
            "pass_delta_vs_full": pass_delta,
            "paired_bootstrap": paired[condition],
            "tool_schema_token_ratio_vs_full": schema_ratio,
            "gates": gates,
            "passes_all": all(gates.values()),
        }

    progressive_rows = [
        row for row in rows if row["condition"] == "SR-PROGRESSIVE"
    ]
    initial_misses = [
        row
        for row in progressive_rows
        if not set(row["required_routes"]).issubset(
            set(row["candidate_history"][0])
        )
    ]
    recovered = [row for row in initial_misses if row["passed"]]

    return {
        "experiment": "0.14-agent-utility-phase-b1-qwen3-0.6b",
        "issue": 420,
        "interpretation": "sanity_and_reproducibility_baseline_only",
        "model": loaded[0]["model"],
        "episode_count": len(rows),
        "expected_episode_count": 23 * 4 * 6,
        "summary_by_catalog": summary_by_catalog,
        "overall": overall,
        "paired_task_pass_delta_vs_full": paired,
        "utility_gates": utility_gates,
        "progressive_recovery": {
            "initial_required_set_miss_count": len(initial_misses),
            "recovered_count": len(recovered),
            "recovery_rate": (
                len(recovered) / len(initial_misses)
                if initial_misses
                else None
            ),
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    paths = sorted(args.input_dir.rglob("phase-b1-*.json"))
    result = aggregate(paths)
    if result["episode_count"] != result["expected_episode_count"]:
        raise SystemExit(
            "incomplete B1 result set: "
            f"{result['episode_count']} != {result['expected_episode_count']}"
        )

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
                "utility_gates": result["utility_gates"],
                "progressive_recovery": result["progressive_recovery"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
