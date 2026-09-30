"""Evaluate retrieval-only metrics for the frozen #432 held-out surface."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from benchmarks.agent_utility_b2_catalog import route_ids
from scripts.agent_utility_generated_common import (
    EXTENDED_CATALOG_SIZES,
    build_extended_registry,
    static_ranked_routes,
    structural_routes,
)


def _rr(ranking: list[str], required: set[str]) -> float:
    if not required:
        return 0.0
    return sum(
        1.0 / (ranking.index(route) + 1) if route in ranking else 0.0
        for route in required
    ) / len(required)


def _ndcg(ranking: list[str], required: set[str], k: int) -> float:
    if not required:
        return 0.0
    dcg = sum(
        1.0 / math.log2(index + 2)
        for index, route in enumerate(ranking[:k])
        if route in required
    )
    ideal = sum(
        1.0 / math.log2(index + 2)
        for index in range(min(len(required), k))
    )
    return dcg / ideal if ideal else 0.0


def evaluate(corpus: dict[str, Any]) -> dict[str, Any]:
    conditions = list(corpus["condition_manifest"]["conditions"])
    rows: list[dict[str, Any]] = []

    for catalog_size in EXTENDED_CATALOG_SIZES:
        registry = build_extended_registry(catalog_size)
        full = sorted(route_ids(registry))
        for task in corpus["tasks"]:
            query = str(task["query"])
            required = {str(route) for route in task["required_routes"]}
            ranked = static_ranked_routes(registry, query)
            structural = (
                structural_routes(registry, query, k=3)
                if "STRUCT-FIXED-3" in conditions
                else []
            )
            for condition in conditions:
                if condition == "FULL":
                    candidates = full
                    ranking = full
                elif condition == "ORACLE":
                    candidates = sorted(required)
                    ranking = candidates
                elif condition == "SR-5":
                    candidates = sorted(ranked[:5])
                    ranking = ranked
                elif condition == "SR-10":
                    candidates = sorted(ranked[:10])
                    ranking = ranked
                elif condition == "SR-PROGRESSIVE":
                    candidates = sorted(ranked[:10])
                    ranking = ranked
                elif condition == "SR-5-STATE-AWARE":
                    candidates = sorted(ranked[:5])
                    ranking = ranked
                elif condition == "STRUCT-FIXED-3":
                    candidates = structural
                    ranking = structural
                else:
                    raise ValueError(condition)

                hits = len(required.intersection(candidates))
                rows.append(
                    {
                        "semantic_task_id": task["semantic_task_id"],
                        "task_stratum": task["task_stratum"],
                        "language": task["language"],
                        "supported": task["supported"],
                        "catalog_size": catalog_size,
                        "condition": condition,
                        "required_count": len(required),
                        "required_hits": hits,
                        "all_required_covered": (
                            hits == len(required) if required else None
                        ),
                        "candidate_count": len(candidates),
                        "mrr_required": _rr(ranking, required),
                        "ndcg_at_10": _ndcg(ranking, required, 10),
                    }
                )

    summary: dict[str, Any] = {}
    for catalog_size in EXTENDED_CATALOG_SIZES:
        summary[str(catalog_size)] = {}
        for condition in conditions:
            subset = [
                row
                for row in rows
                if row["catalog_size"] == catalog_size
                and row["condition"] == condition
            ]
            supported = [row for row in subset if row["required_count"] > 0]
            required_total = sum(int(row["required_count"]) for row in supported)
            hit_total = sum(int(row["required_hits"]) for row in supported)
            summary[str(catalog_size)][condition] = {
                "rows": len(subset),
                "required_route_recall": (
                    hit_total / required_total if required_total else None
                ),
                "all_required_full_coverage": (
                    sum(bool(row["all_required_covered"]) for row in supported)
                    / len(supported)
                    if supported
                    else None
                ),
                "mean_mrr_required": (
                    sum(float(row["mrr_required"]) for row in supported)
                    / len(supported)
                    if supported
                    else None
                ),
                "mean_ndcg_at_10": (
                    sum(float(row["ndcg_at_10"]) for row in supported)
                    / len(supported)
                    if supported
                    else None
                ),
            }

    return {
        "schema_version": 1,
        "issue": 432,
        "benchmark": corpus["benchmark"],
        "tasks_sha256": corpus["tasks_sha256"],
        "conditions": conditions,
        "catalog_sizes": list(EXTENDED_CATALOG_SIZES),
        "rows": rows,
        "summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    result = evaluate(corpus)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
