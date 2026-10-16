"""CPU-only retrospective width Pareto sweep against the *final V1* champion.

Evaluate K24/K32/K40/K48/K56/K64 on the same registered current
SchemaPlanner corpus, reranking each with frozen V2 weights and comparing to
frozen V1-at-24. Output is exposed synthetic DEV research only. This sweep
uses no agent, independent gold, model API, product updates or tool calls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

from benchmarks.agent_utility_v5_catalog import (
    CATALOG_SIZES,
    LANGUAGES,
    TASKS_PER_CELL,
    build_registry,
    build_tasks,
)
from research.autoresearch.actions_ranker import rank, validate
from schemarouter import PlanRequest, SchemaPlanner
from scripts.research_autoresearch_sandbox import candidate_view, decide
from scripts.research_current_main_multilingual_dev import (
    KS,
    score_case,
    select_cases,
)
from scripts.research_v1_v2_paired_cpu_dev import compare_pairs, frozen_genomes

ROOT = Path(__file__).resolve().parents[1]
WIDTHS = (24, 32, 40, 48, 56, 64)
MAX_TOTAL_P95_MS = 150.0
MAX_V1_P95_MULTIPLIER = 1.5
SOURCES = (
    "benchmarks/autoresearch-v1-v2-frozen-incumbents.json",
    "scripts/research_v1_v2_paired_cpu_dev.py",
    "scripts/research_v3_width_pareto_cpu_dev.py",
    "research/autoresearch/actions_ranker.py",
    "scripts/research_autoresearch_sandbox.py",
    "benchmarks/agent_utility_v5_catalog.py",
    "src/schemarouter/planner.py",
)


def p95(values: list[float]) -> float:
    if not values or any(not math.isfinite(x) or x < 0 for x in values):
        raise ValueError("missing or invalid independently measured CPU timings")
    return sorted(values)[math.ceil(len(values) * 0.95) - 1]


def preload(*, cases_per_group: int) -> list[dict[str, Any]]:
    if (
        type(cases_per_group) is not int
        or not 1 <= cases_per_group <= TASKS_PER_CELL
    ):
        raise ValueError("unregistered exposed DEV cohort budget")
    tasks = select_cases(build_tasks(), cases_per_group=cases_per_group)
    rows = []
    for size in CATALOG_SIZES:
        registry = build_registry(size)
        routes = {
            f"{tool.key}.{endpoint.name}"
            for tool in registry.tools() for endpoint in tool.endpoints
        }
        if len(routes) != size:
            raise ValueError("registered route identity drift")
        planner = SchemaPlanner(registry)
        planner._index()
        for case in tasks:
            if not set(case["required_route_ids"]) <= routes:
                raise ValueError("required route absent from current registry")
            pools = {}
            for width in WIDTHS:
                started = time.perf_counter_ns()
                result = planner.retrieve(PlanRequest(query=case["query"]), k=width)
                elapsed = (time.perf_counter_ns() - started) / 1_000_000
                candidates = result.candidates
                names = [item.route_id for item in candidates]
                if (
                    result.registry_version != registry.version
                    or result.requested_k != width
                    or len(names) > width
                    or len(names) != len(set(names))
                    or not set(names) <= routes
                    or not math.isfinite(elapsed)
                    or elapsed < 0
                ):
                    raise ValueError("stale, nonregistered, or duplicate current pool")
                pools[width] = {
                    "candidates": candidates,
                    "view": candidate_view(candidates),
                    "retrieval_ms": elapsed,
                }
            rows.append({
                "case": case, "catalog_size": size,
                "registered_route_ids": routes, "pools": pools,
            })
    return rows


def evaluate_width(
    inputs: list[dict[str, Any]],
    *, width: int, weights: dict[str, float],
) -> tuple[list[dict[str, Any]], float, float]:
    if type(width) is not int or width not in WIDTHS or not inputs:
        raise ValueError("unreviewed pool width or missing current registered tasks")
    config = validate(weights)
    rows, rank_times, total_times = [], [], []
    for sample in inputs:
        pool = sample["pools"][width]
        original = pool["candidates"]
        started = time.perf_counter_ns()
        ordered = rank(sample["case"]["query"], pool["view"], config)
        rank_ms = (time.perf_counter_ns() - started) / 1_000_000
        names = [candidate.route_id for candidate in original]
        if (
            len(ordered) != len(names)
            or len(ordered) != len(set(ordered))
            or set(ordered) != set(names)
        ):
            raise ValueError("ranker attempted to widen authorization/registry")
        by_id = {candidate.route_id: candidate for candidate in original}
        candidates = [by_id[name] for name in ordered]
        total = pool["retrieval_ms"] + rank_ms
        if not math.isfinite(total) or total < 0:
            raise ValueError("invalid candidate end-to-end CPU time")
        rank_times.append(rank_ms)
        total_times.append(total)
        for k in KS:
            score = score_case(
                sample["case"], candidates=candidates, k=k,
                latency_ms=total,
                all_routes=sample["registered_route_ids"],
            )
            score["catalog_size"] = sample["catalog_size"]
            rows.append(score)
    return rows, p95(rank_times), p95(total_times)


def assess(*, cases_per_group: int = TASKS_PER_CELL) -> dict[str, Any]:
    incumbent, challenger, manifest = frozen_genomes()
    inputs = preload(cases_per_group=cases_per_group)
    incumbent_rows, v1_rank_p95, v1_total_p95 = evaluate_width(
        inputs, width=incumbent["width"], weights=incumbent["weights"],
    )
    attempts = []
    for width in WIDTHS:
        candidate_rows, rank_time, total_time = evaluate_width(
            inputs, width=width, weights=challenger["weights"],
        )
        difference = compare_pairs(incumbent_rows, candidate_rows)
        guard = decide(
            incumbent_rows, candidate_rows,
            candidate_p95_ms=rank_time,
        )
        # Strict absolute and relative CPU budgets: no papering over
        # regressions with a quality-weighted objective function.
        speed_ok = (
            total_time <= MAX_TOTAL_P95_MS
            and total_time <= v1_total_p95 * MAX_V1_P95_MULTIPLIER
        )
        eligible = (
            guard["decision"] == "KEEP_RESEARCH_CANDIDATE"
            and speed_ok
            and not difference["any_language_size_k_regression"]
        )
        attempts.append({
            "pool_width": width,
            "uses_frozen_v2_weights": True,
            "top5_route_recall": difference["v2_top5"]["route_recall"],
            "top5_found_required": difference["v2_top5"]["found_total"],
            "top5_full_coverage": difference["v2_top5"]["full_coverage"],
            "top5_gain_vs_frozen_v1": (
                difference["v2_top5"]["found_total"]
                - difference["v1_top5"]["found_total"]
            ),
            "measured_ranking_p95_ms": round(rank_time, 5),
            "measured_retrieval_plus_ranking_p95_ms": round(total_time, 5),
            "relative_p95_vs_v1": round(total_time / v1_total_p95, 5),
            "strict_pairing_guard": guard,
            "absolute_and_relative_cpu_budget_pass": speed_ok,
            "no_group_recall_or_full_coverage_regression": not difference[
                "any_language_size_k_regression"
            ],
            "passes_all_retrospective_dev_guards": eligible,
            "cohorts": difference["cohorts"],
            "top5_case_disagreements": difference["case_disagreements_top5"],
        })
    approved = [row for row in attempts if row["passes_all_retrospective_dev_guards"]]
    approved.sort(
        key=lambda row: (
            -row["top5_found_required"],
            row["measured_retrieval_plus_ranking_p95_ms"],
            row["pool_width"],
        )
    )
    sources = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in SOURCES
    }
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        capture_output=True, text=True, check=True, timeout=10,
    ).stdout.strip()
    return {
        "schema_version": 1,
        "id": "frozen_V1_V2_intermediate_width_retrospective_DEV",
        "source_commit": commit,
        "source_sha256": sources,
        "existing_fixture_sha256": manifest["source_corpus_sha256"],
        "frozen_incumbent_provenance": {
            "v1": {
                "run_id": manifest["v1"]["run_id"],
                "artifact_file_sha256": manifest["v1"]["content_sha256"],
            },
            "v2": {
                "run_id": manifest["v2"]["run_id"],
                "artifact_file_sha256": manifest["v2"]["content_sha256"],
            },
        },
        "catalog_sizes": list(CATALOG_SIZES),
        "languages": list(LANGUAGES),
        "ks": list(KS),
        "registered_pool_widths": list(WIDTHS),
        "cases_per_language_stratum": cases_per_group,
        "cases_per_candidate": len(inputs),
        "actual_current_planner_retrieval_calls": len(inputs) * len(WIDTHS),
        "v1_baseline": {
            "width": incumbent["width"],
            "rank_p95_ms": round(v1_rank_p95, 5),
            "retrieval_plus_rank_p95_ms": round(v1_total_p95, 5),
            "top5_found_required": sum(
                x["found_required_count"] for x in incumbent_rows if x["k"] == 5
            ),
        },
        "attempts": attempts,
        "best_retrospective_DEV_candidate": (
            {"pool_width": approved[0]["pool_width"],
             "top5_found_required": approved[0]["top5_found_required"],
             "measured_total_p95_ms": approved[0][
                 "measured_retrieval_plus_ranking_p95_ms"
             ]}
            if approved else None
        ),
        "source_scope": {
            "exposed_synthetic_DEV_only": True,
            "both_genomes_previously_tuned_on_same_generator": True,
            "independent_confirmation": False,
            "real_live_provider_validation": False,
            "auth_or_output_field_gold": False,
            "actual_agent_task_success": False,
            "automatic_product_change": False,
            "may_release": False,
        },
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "github_actions_run_id": os.environ.get("GITHUB_RUN_ID"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-per-group", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = assess(cases_per_group=args.cases_per_group)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    for row in report["attempts"]:
        print(json.dumps({
            "width": row["pool_width"],
            "required_route_gain": row["top5_gain_vs_frozen_v1"],
            "total_p95_ms": row["measured_retrieval_plus_ranking_p95_ms"],
            "p95_ratio": row["relative_p95_vs_v1"],
            "no_group_regression": row[
                "no_group_recall_or_full_coverage_regression"
            ],
            "passes_all": row["passes_all_retrospective_dev_guards"],
        }))
    print(json.dumps({
        "status": "PARETO_EXPOSED_DEV_ONLY",
        "configurations": len(report["attempts"]),
        "winner_width": (
            report["best_retrospective_DEV_candidate"]["pool_width"]
            if report["best_retrospective_DEV_candidate"] else None
        ),
        "independent": False,
        "may_release": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
