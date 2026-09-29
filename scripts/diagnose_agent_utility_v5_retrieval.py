"""Diagnose #430 large-catalog retrieval misses without changing the scorer."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_v5_catalog import (  # noqa: E402
    CATALOG_SIZES,
    build_registry,
    build_tasks,
)
from scripts.evaluate_agent_utility_phase_a import _rank  # noqa: E402

TOP_K = 10


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _classify_required_route(
    *,
    full_ranking: list[dict[str, Any]],
    route_id: str,
    k: int = TOP_K,
) -> dict[str, Any]:
    positions = {
        str(candidate["route_id"]): index
        for index, candidate in enumerate(full_ranking, start=1)
    }
    if route_id not in positions:
        return {
            "route_id": route_id,
            "rank": None,
            "score": None,
            "cutoff_score": (
                float(full_ranking[k - 1]["score"])
                if len(full_ranking) >= k
                else None
            ),
            "equal_score_candidate_count": 0,
            "strictly_higher_score_candidate_count": 0,
            "miss_class": "missing_from_catalog",
        }

    rank = positions[route_id]
    score = float(full_ranking[rank - 1]["score"])
    cutoff_score = (
        float(full_ranking[k - 1]["score"])
        if len(full_ranking) >= k
        else float(full_ranking[-1]["score"])
    )
    equal_score_count = sum(
        math.isclose(
            float(candidate["score"]),
            score,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        for candidate in full_ranking
    )
    higher_count = sum(
        float(candidate["score"]) > score
        and not math.isclose(
            float(candidate["score"]),
            score,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        for candidate in full_ranking
    )

    if rank <= k:
        miss_class = "covered"
    elif score <= 0.0:
        miss_class = "zero_score"
    elif math.isclose(
        score,
        cutoff_score,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        miss_class = "tie_collision"
    elif score < cutoff_score:
        miss_class = "below_cutoff"
    else:
        miss_class = "ordering_anomaly"

    return {
        "route_id": route_id,
        "rank": rank,
        "score": score,
        "cutoff_score": cutoff_score,
        "equal_score_candidate_count": equal_score_count,
        "strictly_higher_score_candidate_count": higher_count,
        "miss_class": miss_class,
    }


def diagnose() -> dict[str, Any]:
    tasks = build_tasks()
    rows: list[dict[str, Any]] = []

    for catalog_size in CATALOG_SIZES:
        registry = build_registry(catalog_size)
        for task in tasks:
            required = [
                str(route_id)
                for route_id in task["required_route_ids"]
            ]
            if not required:
                continue

            ranking = _rank(registry, str(task["query"]))
            route_diagnostics = [
                _classify_required_route(
                    full_ranking=ranking,
                    route_id=route_id,
                )
                for route_id in required
            ]
            rows.append(
                {
                    "task_id": str(task["task_id"]),
                    "task_stratum": str(task["task_stratum"]),
                    "language": str(task["language"]),
                    "catalog_size": catalog_size,
                    "query": str(task["query"]),
                    "required_route_diagnostics": route_diagnostics,
                    "all_required_top10": all(
                        item["rank"] is not None
                        and int(item["rank"]) <= TOP_K
                        for item in route_diagnostics
                    ),
                }
            )

    miss_classes: Counter[str] = Counter()
    per_catalog: dict[str, Counter[str]] = defaultdict(Counter)
    per_stratum: dict[str, Counter[str]] = defaultdict(Counter)
    per_language: dict[str, Counter[str]] = defaultdict(Counter)
    required_total = 0
    required_hits = 0

    for row in rows:
        catalog_key = str(row["catalog_size"])
        for item in row["required_route_diagnostics"]:
            required_total += 1
            miss_class = str(item["miss_class"])
            miss_classes[miss_class] += 1
            per_catalog[catalog_key][miss_class] += 1
            per_stratum[str(row["task_stratum"])][miss_class] += 1
            per_language[str(row["language"])][miss_class] += 1
            if miss_class == "covered":
                required_hits += 1

    def summarize(counter: Counter[str]) -> dict[str, Any]:
        total = sum(counter.values())
        covered = counter.get("covered", 0)
        return {
            "required_route_count": total,
            "required_route_recall_at_10": _safe_ratio(
                covered,
                total,
            ),
            "miss_classes": dict(sorted(counter.items())),
        }

    return {
        "schema_version": 1,
        "issue": 430,
        "experiment": "adaptive-capability-shortlist-depth-v1",
        "surface": "development",
        "diagnostic_only": True,
        "scorer_changed": False,
        "top_k": TOP_K,
        "row_count": len(rows),
        "required_route_count": required_total,
        "required_route_recall_at_10": _safe_ratio(
            required_hits,
            required_total,
        ),
        "miss_classes": dict(sorted(miss_classes.items())),
        "per_catalog": {
            key: summarize(value)
            for key, value in sorted(
                per_catalog.items(),
                key=lambda item: int(item[0]),
            )
        },
        "per_stratum": {
            key: summarize(value)
            for key, value in sorted(per_stratum.items())
        },
        "per_language": {
            key: summarize(value)
            for key, value in sorted(per_language.items())
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = diagnose()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "required_route_recall_at_10": result[
                    "required_route_recall_at_10"
                ],
                "miss_classes": result["miss_classes"],
                "per_catalog": result["per_catalog"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
