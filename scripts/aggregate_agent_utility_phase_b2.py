"""Aggregate sharded #420 B1 agent-utility results."""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_b2_catalog import TASKS  # noqa: E402
from scripts.evaluate_agent_utility_phase_b_smollm3 import _summary  # noqa: E402

DEPLOYABLE = ("SR-5", "SR-10", "SR-PROGRESSIVE")


def _cluster_bootstrap_delta(
    full_rows: list[dict[str, Any]],
    condition_rows: list[dict[str, Any]],
    *,
    iterations: int = 5000,
    seed: int = 20260929,
) -> dict[str, Any]:
    """Bootstrap paired pass-rate deltas by semantic task, not repeated catalog row."""

    full = {
        (str(row["task_id"]), int(row["catalog_size"])): bool(row["passed"])
        for row in full_rows
    }
    condition = {
        (str(row["task_id"]), int(row["catalog_size"])): bool(row["passed"])
        for row in condition_rows
    }
    if set(full) != set(condition):
        raise ValueError("paired condition keys do not match FULL")

    task_ids = sorted({task_id for task_id, _ in full})
    if not task_ids:
        raise ValueError("no paired tasks for bootstrap")

    task_deltas: dict[str, float] = {}
    for task_id in task_ids:
        keys = sorted(key for key in full if key[0] == task_id)
        task_deltas[task_id] = statistics.fmean(
            int(condition[key]) - int(full[key])
            for key in keys
        )

    delta = statistics.fmean(task_deltas.values())
    rng = random.Random(seed)
    samples = sorted(
        statistics.fmean(
            task_deltas[task_ids[rng.randrange(len(task_ids))]]
            for _ in range(len(task_ids))
        )
        for _ in range(iterations)
    )

    def quantile(probability: float) -> float:
        position = probability * (len(samples) - 1)
        low = math.floor(position)
        high = math.ceil(position)
        if low == high:
            return samples[low]
        weight = position - low
        return samples[low] * (1.0 - weight) + samples[high] * weight

    return {
        "delta": delta,
        "ci_low": quantile(0.025),
        "ci_high": quantile(0.975),
        "cluster_unit": "task_id",
        "unique_task_count": len(task_ids),
        "catalog_repeats_per_task": len(full) // len(task_ids),
        "iterations": iterations,
    }


def _retrieval_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Measure coverage from the candidate sets actually exposed to the agent."""

    if not rows:
        raise ValueError("no rows for retrieval coverage")

    def metrics(subset: list[dict[str, Any]]) -> dict[str, float | int]:
        required_total = 0
        required_hits = 0
        fully_covered = 0
        candidate_counts: list[int] = []

        for row in subset:
            history = row.get("candidate_history")
            if not isinstance(history, list) or not history:
                raise ValueError("missing candidate_history in B2 episode")
            final_candidates = set(history[-1])
            required = set(row["required_routes"])
            required_total += len(required)
            required_hits += len(required.intersection(final_candidates))
            fully_covered += int(required.issubset(final_candidates))
            candidate_counts.append(len(final_candidates))

        return {
            "episodes": len(subset),
            "required_route_instances": required_total,
            "required_route_recall": (
                required_hits / required_total if required_total else 1.0
            ),
            "all_required_task_coverage": fully_covered / len(subset),
            "mean_final_candidate_count": statistics.fmean(candidate_counts),
        }

    catalog_sizes = sorted({int(row["catalog_size"]) for row in rows})
    by_catalog = {
        str(size): metrics(
            [row for row in rows if int(row["catalog_size"]) == size]
        )
        for size in catalog_sizes
    }
    overall = metrics(rows)
    overall["minimum_required_route_recall_by_catalog"] = min(
        float(bucket["required_route_recall"])
        for bucket in by_catalog.values()
    )
    overall["by_catalog"] = by_catalog
    return overall


def aggregate(paths: list[Path]) -> dict[str, Any]:
    if not paths:
        raise ValueError("no B2 shard results supplied")

    loaded = [json.loads(path.read_text(encoding="utf-8")) for path in paths]

    experiments = {str(result.get("experiment")) for result in loaded}
    if experiments != {"0.14-agent-utility-phase-b2-smollm3-3b"}:
        raise ValueError(
            f"experiment identity drift across shards: {sorted(experiments)}"
        )

    issues = {result.get("issue") for result in loaded}
    if issues != {423}:
        raise ValueError(f"issue identity drift across shards: {issues}")

    model_identities = {
        json.dumps(result["model"], sort_keys=True, separators=(",", ":"))
        for result in loaded
    }
    if len(model_identities) != 1:
        raise ValueError("model configuration drift across shards")

    runtime_identities = {
        json.dumps(result["runtime"], sort_keys=True, separators=(",", ":"))
        for result in loaded
    }
    if len(runtime_identities) != 1:
        raise ValueError("runtime identity drift across shards")

    policy_identities = {
        json.dumps(result["policy"], sort_keys=True, separators=(",", ":"))
        for result in loaded
    }
    if len(policy_identities) != 1:
        raise ValueError("B2 policy drift across shards")

    rows = [
        episode
        for result in loaded
        for episode in result["rows"]
    ]
    expected_task_ids = {task.task_id for task in TASKS}
    expected_conditions = {
        "FULL",
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
        raise ValueError("duplicate B2 episode key detected")

    actual_task_ids = {str(row["task_id"]) for row in rows}
    unknown_task_ids = sorted(actual_task_ids.difference(expected_task_ids))
    if unknown_task_ids:
        raise ValueError(
            "unknown B2 task id(s): " + ", ".join(unknown_task_ids)
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

    conditions = ("FULL", "SR-5", "SR-10", "SR-PROGRESSIVE", "ORACLE")
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

    retrieval_coverage = {
        condition: _retrieval_coverage(
            [row for row in rows if row["condition"] == condition]
        )
        for condition in conditions
    }

    full_rows = [row for row in rows if row["condition"] == "FULL"]
    paired = {
        condition: _cluster_bootstrap_delta(
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
            "retrieval_eligible": (
                float(
                    retrieval_coverage[condition][
                        "minimum_required_route_recall_by_catalog"
                    ]
                )
                >= 0.97
            ),
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
            "execution_policy_integrity_100pct": (
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
        "experiment": "0.14-agent-utility-phase-b2-smollm3-3b",
        "issue": 423,
        "interpretation": "strong_agent_replication_controlled_surface",
        "statistical_scope": {
            "unique_semantic_task_count": len({str(row["task_id"]) for row in rows}),
            "catalog_repeats_per_task": 4,
            "bootstrap_unit": "task_id_cluster",
            "minus_2pp_gate": (
                "controlled_replication_gate_not_population_noninferiority_claim"
            ),
        },
        "model": loaded[0]["model"],
        "runtime": loaded[0]["runtime"],
        "episode_count": len(rows),
        "expected_episode_count": 23 * 4 * 5,
        "summary_by_catalog": summary_by_catalog,
        "overall": overall,
        "paired_task_pass_delta_vs_full": paired,
        "retrieval_coverage": retrieval_coverage,
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
                "retrieval_coverage": result["retrieval_coverage"],
                "utility_gates": result["utility_gates"],
                "progressive_recovery": result["progressive_recovery"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
