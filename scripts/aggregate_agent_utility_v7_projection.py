"""Aggregate #506 projection shards into one canonical result.

Factual metrics are reported separately and never collapsed into a single score,
following the same rule as #424. The statistical unit is the semantic task; the
two catalog sizes are repeated measures nested inside it, so they are averaged
within a task before any resampling.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_utility_v7_projection import PROJECTION_CONDITIONS  # noqa: E402

BOOTSTRAP_ITERATIONS = 10_000
BOOTSTRAP_SEED = 20260929
CONFIDENCE = 0.95

FACTUAL_METRICS = (
    "required_fact_recall",
    "numeric_value_accuracy",
    "unit_accuracy",
    "provenance_accuracy",
    "unsupported_fact_rate",
    "final_envelope_valid",
    "exact_field_completion",
)
COST_METRICS = ("observation_chars", "input_tokens", "output_tokens", "turns")
COMPARATOR = "RAW-FULL"


def _mean(values: list[float]) -> float | None:
    usable = [value for value in values if value is not None]
    return statistics.fmean(usable) if usable else None


def _per_task(rows: list[dict[str, Any]], metric: str) -> dict[tuple[str, str], float]:
    """Average a metric within (condition, task) across catalog repeats."""
    buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        value = row.get(metric)
        if value is None:
            continue
        buckets[(str(row["condition"]), str(row["semantic_task_id"]))].append(float(value))
    return {key: statistics.fmean(values) for key, values in buckets.items()}


def _paired_delta_interval(
    rows: list[dict[str, Any]],
    metric: str,
    condition: str,
) -> dict[str, Any] | None:
    per_task = _per_task(rows, metric)
    tasks = sorted(
        {task for (cond, task) in per_task if cond == condition}
        & {task for (cond, task) in per_task if cond == COMPARATOR}
    )
    if not tasks:
        return None

    deltas = [per_task[(condition, task)] - per_task[(COMPARATOR, task)] for task in tasks]
    rng = random.Random(BOOTSTRAP_SEED)
    samples: list[float] = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        resampled = [deltas[rng.randrange(len(deltas))] for _ in range(len(deltas))]
        samples.append(statistics.fmean(resampled))
    samples.sort()
    low = samples[int((1 - CONFIDENCE) / 2 * (len(samples) - 1))]
    high = samples[int((1 + CONFIDENCE) / 2 * (len(samples) - 1))]
    return {
        "paired_tasks": len(tasks),
        "mean_delta": statistics.fmean(deltas),
        "ci_low": low,
        "ci_high": high,
    }


def aggregate(shards: list[dict[str, Any]]) -> dict[str, Any]:
    if not shards:
        raise SystemExit("no shards supplied")

    identities = {shard["tasks_sha256"] for shard in shards}
    if len(identities) != 1:
        raise SystemExit(f"shards disagree on corpus identity: {sorted(identities)}")
    runtimes = {shard["runtime"]["runtime"] for shard in shards}
    if len(runtimes) != 1:
        raise SystemExit(f"shards mix runtimes: {sorted(runtimes)}")
    evidence_classes = {shard["runtime"]["evidence_class"] for shard in shards}

    rows: list[dict[str, Any]] = []
    seen: set[tuple[int, str, str]] = set()
    for shard in shards:
        for row in shard["rows"]:
            key = (int(row["catalog_size"]), str(row["semantic_task_id"]), str(row["condition"]))
            if key in seen:
                raise SystemExit(f"duplicate episode across shards: {key}")
            seen.add(key)
            rows.append(row)

    by_condition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_condition[str(row["condition"])].append(row)

    missing = set(PROJECTION_CONDITIONS) - set(by_condition)
    if missing:
        raise SystemExit(f"missing conditions: {sorted(missing)}")

    conditions: dict[str, Any] = {}
    for condition in PROJECTION_CONDITIONS:
        condition_rows = by_condition[condition]
        summary: dict[str, Any] = {
            "episodes": len(condition_rows),
            "task_pass_rate": _mean([float(row["passed"]) for row in condition_rows]),
            "unauthorized_destructive_executions": sum(
                int(row["unauthorized_destructive_executions"]) for row in condition_rows
            ),
            "contradiction_count": sum(
                int(row.get("contradiction_count", 0)) for row in condition_rows
            ),
        }
        for metric in FACTUAL_METRICS + COST_METRICS:
            summary[metric] = _mean(
                [
                    float(row[metric])
                    for row in condition_rows
                    if row.get(metric) is not None
                ]
            )
        if condition != COMPARATOR:
            summary["paired_vs_raw_full"] = {
                metric: _paired_delta_interval(rows, metric, condition)
                for metric in FACTUAL_METRICS + COST_METRICS
            }
        conditions[condition] = summary

    strata: dict[str, Any] = defaultdict(dict)
    for condition in PROJECTION_CONDITIONS:
        for row in by_condition[condition]:
            bucket = strata[str(row["projection_stratum"])].setdefault(condition, [])
            bucket.append(float(row["required_fact_recall"]))
    stratum_report = {
        stratum: {
            condition: _mean(values) for condition, values in per_condition.items()
        }
        for stratum, per_condition in strata.items()
    }

    languages: dict[str, Any] = defaultdict(dict)
    for condition in PROJECTION_CONDITIONS:
        for row in by_condition[condition]:
            languages[str(row["language"])].setdefault(condition, []).append(
                float(row["required_fact_recall"])
            )
    language_report = {
        language: {
            condition: _mean(values) for condition, values in per_condition.items()
        }
        for language, per_condition in languages.items()
    }

    return {
        "schema_version": 1,
        "issue": 506,
        "experiment": shards[0]["experiment"],
        "tasks_sha256": shards[0]["tasks_sha256"],
        "source_identity_sha256": shards[0]["source_identity_sha256"],
        "candidate_condition": shards[0]["candidate_condition"],
        "runtime": sorted(runtimes)[0],
        "evidence_class": sorted(evidence_classes)[0],
        "episodes": len(rows),
        "shards": len(shards),
        "statistics": {
            "cluster_unit": "semantic_task_id",
            "catalog_sizes_nested_within_task": True,
            "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "confidence_interval": CONFIDENCE,
            "comparator": COMPARATOR,
        },
        "conditions": conditions,
        "by_projection_stratum": stratum_report,
        "by_language": language_report,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    shards = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(args.input_dir.rglob("*.json"))
    ]
    result = aggregate(shards)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "episodes": result["episodes"],
                "evidence_class": result["evidence_class"],
                "conditions": {
                    condition: summary["required_fact_recall"]
                    for condition, summary in result["conditions"].items()
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
