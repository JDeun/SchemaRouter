"""Reviewed CPU-only joint pool-width / re-ranking DEV search, stage V2.

Independent of the running V1 artifact chain. The current public
SchemaPlanner retrieves K=24/64/128 from registered synthetic catalogs.
The candidate receives only public candidate metadata and query text;
gold enters the separate scorer *after* candidate ranking. No API calls,
hosted models, product source edits, permission grants or executable tools.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from benchmarks.agent_utility_v5_catalog import (
    CATALOG_SIZES,
    build_registry,
    build_tasks,
)
from research.autoresearch.actions_ranker import BASE, generate, rank, validate
from schemarouter import PlanRequest, SchemaPlanner
from scripts.research_autoresearch_sandbox import candidate_view, decide
from scripts.research_current_main_multilingual_dev import (
    KS,
    encoded,
    score_case,
    select_cases,
)

ROOT = Path(__file__).resolve().parents[1]
POOL_WIDTHS = (24, 64, 128)
MAX_TRIALS = 36
CLAIM_BOUNDARY = {
    "benchmark": "preexposed_v5_generated_DEV_100_250_500",
    "current_API_retrieval_executed": True,
    "new_independently_authored_test": False,
    "principal_authorization_tested": False,
    "required_output_field_gold_tested": False,
    "agent_task_success_tested": False,
    "actual_endpoint_execution": False,
    "may_promote": False,
    "may_release": False,
}


def validated_genome(config: Any) -> dict[str, Any]:
    if not isinstance(config, dict) or set(config) != {"width", "weights"}:
        raise ValueError("only reviewed pool width and rank weights can change")
    width = config["width"]
    if type(width) is not int or width not in POOL_WIDTHS:
        raise ValueError("unregistered pool width")
    return {"width": width, "weights": validate(config["weights"])}


def new_genome(
    rng: random.Random, champion: dict[str, Any] | None,
) -> dict[str, Any]:
    if champion is None or rng.random() < 0.35:
        width = rng.choice(POOL_WIDTHS)
        weights = generate(rng, None, None)
    else:
        width = (
            rng.choice(POOL_WIDTHS)
            if rng.random() < 0.45 else champion["width"]
        )
        weights = generate(rng, champion["weights"], None)
    return validated_genome({"width": width, "weights": weights})


def split_fixture(
    cases_per_group: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if type(cases_per_group) is not int or cases_per_group not in (2, 5):
        raise ValueError("reviewed CPU DEV fit/check choices are 2 or 5")
    tasks = select_cases(build_tasks(), cases_per_group=cases_per_group)
    fit, check = [], []
    counts: dict[tuple[str, str], int] = defaultdict(int)
    boundary = 1 if cases_per_group == 2 else 3
    for case in tasks:
        key = case["language"], case["task_stratum"]
        counts[key] += 1
        (fit if counts[key] <= boundary else check).append(case)
    if len(fit) != 48 * boundary or len(check) != 48 * (cases_per_group - boundary):
        raise ValueError("changed balanced fit/check cohorts")
    if set(x["task_id"] for x in fit) & set(x["task_id"] for x in check):
        raise ValueError("DEV fit/check task identity overlap")
    return fit, check


def preload(
    tasks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Cache real current API outputs for each width; never pass gold to ranker."""
    cases = []
    for size in CATALOG_SIZES:
        registry = build_registry(size)
        routes = {
            f"{tool.key}.{endpoint.name}"
            for tool in registry.tools() for endpoint in tool.endpoints
        }
        if len(routes) != size:
            raise ValueError("registry route count drift")
        planner = SchemaPlanner(registry)
        planner._index()
        for case in tasks:
            if not set(case["required_route_ids"]) <= routes:
                raise ValueError("registered gold missing from typed catalog")
            pools: dict[int, dict[str, Any]] = {}
            for width in POOL_WIDTHS:
                started = time.perf_counter_ns()
                result = planner.retrieve(PlanRequest(query=case["query"]), k=width)
                ms = (time.perf_counter_ns() - started) / 1_000_000
                raw = result.candidates
                names = [candidate.route_id for candidate in raw]
                if (
                    result.registry_version != registry.version
                    or result.requested_k != width
                    or len(names) != len(set(names))
                    or len(names) > width
                    or not set(names) <= routes
                ):
                    raise ValueError("current planner returned bad registered pool")
                pools[width] = {
                    "candidates": raw,
                    "view": candidate_view(raw),
                    "retrieval_ms": ms,
                }
            cases.append({
                "size": size,
                "task": case,
                "registered_route_ids": routes,
                "pools": pools,
            })
    return cases


def evaluate_genome(
    inputs: list[dict[str, Any]], config: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], float, float]:
    """Paired outcome and timed end-to-end retrieval + optional rerank."""
    if not inputs:
        raise ValueError("no registered DEV requests")
    selected = validated_genome(config) if config is not None else None
    rows, rank_times, end_to_end = [], [], []
    for item in inputs:
        width = selected["width"] if selected else 24
        pool = item["pools"][width]
        raw = pool["candidates"]
        ranking_ms = 0.0
        if selected is not None:
            started = time.perf_counter_ns()
            ordered = rank(item["task"]["query"], pool["view"], selected["weights"])
            ranking_ms = (time.perf_counter_ns() - started) / 1_000_000
            names = [c.route_id for c in raw]
            if (
                len(ordered) != len(names)
                or len(ordered) != len(set(ordered))
                or set(ordered) != set(names)
            ):
                raise ValueError("optimizer forged, omitted or duplicated route")
            registered = {candidate.route_id: candidate for candidate in raw}
            raw = [registered[name] for name in ordered]
        latency = pool["retrieval_ms"] + ranking_ms
        if not math.isfinite(latency) or latency < 0:
            raise ValueError("nonfinite candidate runtime")
        rank_times.append(ranking_ms)
        end_to_end.append(latency)
        for k in KS:
            scored = score_case(
                item["task"], candidates=raw, k=k,
                latency_ms=latency, all_routes=item["registered_route_ids"],
            )
            scored["catalog_size"] = item["size"]
            rows.append(scored)
    index = max(0, math.ceil(len(rank_times) * 0.95) - 1)
    return (
        rows,
        sorted(rank_times)[index],
        sorted(end_to_end)[index],
    )


def full_result(
    *, trials: int = 6, cases_per_group: int = 2, seed: int = 1412,
) -> dict[str, Any]:
    if type(trials) is not int or not 3 <= trials <= MAX_TRIALS:
        raise ValueError("bounded V2 search requires 3..36 variants")
    if type(seed) is not int or seed < 0:
        raise ValueError("randomized research reproducibility seed must be >= 0")
    fit, check = split_fixture(cases_per_group)
    fit_inputs, check_inputs = preload(fit), preload(check)
    base_fit, _, baseline_p95 = evaluate_genome(fit_inputs, None)
    base_check, _, _ = evaluate_genome(check_inputs, None)
    rng = random.Random(seed)
    history = []
    champion: dict[str, Any] | None = None
    best_internal = -math.inf
    configurations: set[str] = set()
    for index in range(trials):
        # Three mandatory controls prove breadth options, then adaptive search.
        genome = (
            validated_genome({"width": POOL_WIDTHS[index], "weights": BASE})
            if index < len(POOL_WIDTHS)
            else new_genome(rng, champion)
        )
        config_id = hashlib.sha256(encoded(genome)).hexdigest()
        if config_id in configurations:
            continue
        configurations.add(config_id)
        fit_rows, rank_p95, total_p95 = evaluate_genome(fit_inputs, genome)
        gate = decide(base_fit, fit_rows, candidate_p95_ms=rank_p95)
        # Cost is the actual separately timed registered-width retrieval
        # plus ranker, not a synthetic k=128 slice used as K=24 timing.
        cost_ok = total_p95 <= 150.0
        item: dict[str, Any] = {
            "genome": genome,
            "config_sha256": config_id,
            "actual_fit_top5_gain": gate["top5_required_route_gain"],
            "fit_regressions": gate["regressions"],
            "actual_rank_p95_ms": round(rank_p95, 4),
            "actual_retrieval_plus_rank_p95_ms": round(total_p95, 4),
            "fit_guard_pass": gate["decision"] == "KEEP_RESEARCH_CANDIDATE"
                and cost_ok,
            "internal_dev_checked": False,
            "internal_dev_keep": False,
        }
        if item["fit_guard_pass"]:
            tested_rows, tested_rank_p95, tested_total_p95 = evaluate_genome(
                check_inputs, genome,
            )
            checked = decide(base_check, tested_rows, candidate_p95_ms=tested_rank_p95)
            item["internal_dev_checked"] = True
            item["internal_dev_gain"] = checked["top5_required_route_gain"]
            item["internal_dev_keep"] = (
                checked["decision"] == "KEEP_RESEARCH_CANDIDATE"
                and tested_total_p95 <= 150.0
            )
            if item["internal_dev_keep"]:
                # Research-only selection against the current K24 baseline.
                utility = sum(
                    row["found_required_count"] for row in tested_rows if row["k"] == 5
                )
                if utility > best_internal:
                    best_internal, champion = utility, genome
        history.append(item)
    git_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    files = (
        "research/autoresearch/actions_ranker.py",
        "scripts/research_actions_width_search_dev.py",
        "scripts/research_autoresearch_sandbox.py",
        "benchmarks/agent_utility_v5_catalog.py",
        "src/schemarouter/planner.py",
    )
    return {
        "schema_version": 1,
        "id": "actions-only-adaptive-pool-width-reranking-v2-dev",
        "source_commit": git_sha,
        "source_file_sha256": {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in files
        },
        "data_sha256": hashlib.sha256(encoded(build_tasks())).hexdigest(),
        "scope": CLAIM_BOUNDARY.copy(),
        "reviewed_pool_widths": list(POOL_WIDTHS),
        "reviewed_candidate_weights": list(BASE),
        "fit_cases_per_catalog": len(fit),
        "internal_check_cases_per_catalog": len(check),
        "actual_current_planner_retrieval_calls": (
            len(CATALOG_SIZES) * (len(fit) + len(check)) * len(POOL_WIDTHS)
        ),
        "baseline_fit_actual_total_p95_ms": round(baseline_p95, 4),
        "attempts": history,
        "champion": champion,
        "champion_is_only_internal_exposed_DEV": True,
        "hardware": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "actions_run_id": os.environ.get("GITHUB_RUN_ID"),
        },
        "notes": (
            "Candidate search is parameter exploration only, not model code "
            "generation or global optimization. Fit and internal check share an "
            "already exposed synthetic fixture. No actual agent, field, policy "
            "execution or independent test was performed."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=6)
    ap.add_argument("--cases-per-group", type=int, choices=(2, 5), default=2)
    ap.add_argument("--seed", type=int, default=1412)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    report = full_result(
        trials=args.trials,
        cases_per_group=args.cases_per_group,
        seed=args.seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    for attempt in report["attempts"]:
        print(json.dumps({
            "width": attempt["genome"]["width"],
            "fit_gain": attempt["actual_fit_top5_gain"],
            "checked": attempt["internal_dev_checked"],
            "internal_keep": attempt["internal_dev_keep"],
            "runtime_p95_ms": attempt["actual_retrieval_plus_rank_p95_ms"],
        }))
    print(json.dumps({
        "status": "REAL_CPU_WEIGHT_AND_WIDTH_DEV_SEARCH",
        "attempts": len(report["attempts"]),
        "champion_found": report["champion"] is not None,
        "independent": False, "product_promoted": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
