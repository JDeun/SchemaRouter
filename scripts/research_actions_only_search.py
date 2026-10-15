"""GitHub Actions-only adaptive CPU research search; no coding agent or API.

Only typed, reviewed ranking weights change. Uses real current SchemaPlanner
candidate pools on previously exposed synthetic DEV, with disjoint internal
fit/check slices. This is NOT an independent holdout or agent task evaluation.
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
    TASKS_PER_CELL,
    build_registry,
    build_tasks,
)
from research.autoresearch.actions_ranker import BASE, fingerprint, generate, rank, validate
from schemarouter import PlanRequest, SchemaPlanner
from scripts.research_autoresearch_sandbox import candidate_view, decide
from scripts.research_current_main_multilingual_dev import (
    KS,
    encoded,
    score_case,
    select_cases,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "research/autoresearch/actions_ranker.py",
    "scripts/research_actions_only_search.py",
    "scripts/research_actions_continuation.py",
    ".github/workflows/research-actions-only-cpu-search.yml",
    "scripts/research_autoresearch_sandbox.py",
    "scripts/research_current_main_multilingual_dev.py",
    "benchmarks/agent_utility_v5_catalog.py",
    "src/schemarouter/planner.py",
    "src/schemarouter/models.py",
)
SCOPE = "existing-visible-synthetic-DEV-only"
MAX_TRIALS = 64


def source_manifest() -> dict[str, str]:
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in SOURCES
    }


def split_tasks(tasks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Three fit + two internal-check examples per language/stratum.

    The two groups are query-disjoint, but are from the SAME exposed synthetic
    generator. Never call internal-check an external independent holdout.
    """
    selected = select_cases(tasks, cases_per_group=TASKS_PER_CELL)
    count: dict[tuple[str, str], int] = defaultdict(int)
    fit, check = [], []
    for item in selected:
        key = item["language"], item["task_stratum"]
        count[key] += 1
        (fit if count[key] <= 3 else check).append(item)
    if len(fit) != 144 or len(check) != 96:
        raise ValueError("unexpected internal DEV cohort split")
    return fit, check


def preload(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fetch full current-library registered pools ONCE per task/size."""
    cases = []
    for size in CATALOG_SIZES:
        registry = build_registry(size)
        all_routes = {
            f"{tool.key}.{endpoint.name}"
            for tool in registry.tools() for endpoint in tool.endpoints
        }
        if len(all_routes) != size:
            raise ValueError("unregistered corpus/catalog identity")
        planner = SchemaPlanner(registry)
        planner._index()
        for item in tasks:
            if not set(item["required_route_ids"]) <= all_routes:
                raise ValueError("missing declared gold route in registry")
            result = planner.retrieve(PlanRequest(query=item["query"]), k=24)
            candidate_ids = [c.route_id for c in result.candidates]
            if len(candidate_ids) != len(set(candidate_ids)):
                raise ValueError("duplicated input candidate identity")
            if not set(candidate_ids) <= all_routes:
                raise ValueError("unregistered input candidate identity")
            cases.append({
                "size": size,
                "task": item,
                "candidates": result.candidates,
                "views": candidate_view(result.candidates),
                "all_routes": all_routes,
            })
    return cases


def metric_rows(
    inputs: list[dict[str, Any]], config: dict[str, float],
) -> tuple[list[dict[str, Any]], float]:
    config = validate(config)
    rows = []
    latencies: list[float] = []
    for item in inputs:
        started = time.perf_counter_ns()
        ranked_ids = rank(item["task"]["query"], item["views"], config)
        elapsed = (time.perf_counter_ns() - started) / 1_000_000
        original = item["candidates"]
        original_ids = [candidate.route_id for candidate in original]
        if (
            len(ranked_ids) != len(original_ids)
            or len(set(ranked_ids)) != len(ranked_ids)
            or set(ranked_ids) != set(original_ids)
        ):
            raise ValueError("ranker fabricated or omitted candidate ID")
        indexed = {candidate.route_id: candidate for candidate in original}
        reordered = [indexed[route_id] for route_id in ranked_ids]
        latencies.append(elapsed)
        for k in KS:
            row = score_case(
                item["task"], candidates=reordered, k=k,
                latency_ms=elapsed, all_routes=item["all_routes"],
            )
            row["catalog_size"] = item["size"]
            rows.append(row)
    if not latencies or any(not math.isfinite(x) or x < 0 for x in latencies):
        raise ValueError("invalid ranker timing samples")
    ordered = sorted(latencies)
    return rows, ordered[math.ceil(0.95 * len(ordered)) - 1]


def utility(reference: list[dict[str, Any]], observed: list[dict[str, Any]]) -> float:
    """Fit-only heuristic with explicit penalties; never a release score."""
    base5 = [row for row in reference if row["k"] == 5]
    new5 = [row for row in observed if row["k"] == 5]
    route_gain = sum(x["found_required_count"] for x in new5) - sum(
        x["found_required_count"] for x in base5
    )
    coverage_gain = sum(x["full_coverage"] for x in new5) - sum(
        x["full_coverage"] for x in base5
    )
    penalty = 0
    grouped: dict[tuple[int, str, int], list[int]] = defaultdict(lambda: [0, 0])
    for before, after in zip(reference, observed, strict=True):
        if (
            before["task_id"], before["catalog_size"], before["k"]
        ) != (
            after["task_id"], after["catalog_size"], after["k"]
        ):
            raise ValueError("unpaired train/dev rows")
        key = before["catalog_size"], before["language"], before["k"]
        grouped[key][0] += before["found_required_count"]
        grouped[key][1] += after["found_required_count"]
    penalty = sum(max(0, a - b) for a, b in grouped.values())
    return float(route_gain * 4 + coverage_gain * 2 - penalty * 8)


def contract_hash() -> str:
    return hashlib.sha256(encoded({
        "sources": source_manifest(), "split": "three-fit-two-check",
        "catalog_sizes": list(CATALOG_SIZES), "K": list(KS), "scope": SCOPE,
    })).hexdigest()


def load_previous(path: Path | None, expected_hash: str) -> dict[str, Any]:
    initial = {
        "schema_version": 1, "contract_sha256": expected_hash,
        "epoch": 0, "total_trials": 0, "seen": [],
        "anchor": BASE.copy(), "champion": None,
    }
    if path is None or not path.is_file():
        return initial
    saved = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(saved, dict) or set(saved) != set(initial):
        raise ValueError("unrecognized previous Actions state")
    if saved["schema_version"] != 1 or saved["contract_sha256"] != expected_hash:
        raise ValueError("stale source, corpus or protocol contract in prior artifact")
    if (
        type(saved["epoch"]) is not int or not 0 <= saved["epoch"] <= 100000
        or type(saved["total_trials"]) is not int or saved["total_trials"] < 0
        or not isinstance(saved["seen"], list) or len(saved["seen"]) > 512
        or any(type(s) is not str or len(s) != 64 for s in saved["seen"])
    ):
        raise ValueError("invalid bounded trial state")
    saved["anchor"] = validate(saved["anchor"])
    if saved["champion"] is not None:
        saved["champion"] = validate(saved["champion"])
    return saved


def search(
    *, trials: int, seed: int, previous: dict[str, Any],
    seconds: int = 900,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if (
        type(trials) is not int or not 1 <= trials <= MAX_TRIALS
        or type(seconds) is not int or not 1 <= seconds <= 1200
    ):
        raise ValueError("unbounded CPU search requested")
    tasks = build_tasks()
    fit_tasks, check_tasks = split_tasks(tasks)
    dataset_sha = hashlib.sha256(encoded(tasks)).hexdigest()
    fit_input, check_input = preload(fit_tasks), preload(check_tasks)
    base_fit, _ = metric_rows(fit_input, BASE)
    base_check, _ = metric_rows(check_input, BASE)
    initial_hash = contract_hash()
    if previous["contract_sha256"] != initial_hash:
        raise ValueError("source/experiment identity drift")
    rng = random.Random(seed + previous["epoch"] * 1009)
    tested = set(previous["seen"])
    anchor = validate(previous["anchor"])
    champion = previous["champion"]
    if champion is not None:
        champion = validate(champion)
    best_utility = utility(base_fit, metric_rows(fit_input, anchor)[0])
    log: list[dict[str, Any]] = []
    end_at = time.monotonic() + seconds
    for index in range(trials):
        if time.monotonic() >= end_at:
            break
        parent = anchor if index % 4 else champion
        config = generate(rng, parent, champion if index % 3 == 0 else None)
        identifier = fingerprint(config)
        if identifier in tested:
            continue
        tested.add(identifier)
        rows, p95 = metric_rows(fit_input, config)
        score = utility(base_fit, rows)
        train_gate = decide(base_fit, rows, candidate_p95_ms=p95)
        record = {
            "config_sha256": identifier, "genome": config,
            "fit_utility": score, "fit_p95_ms": round(p95, 5),
            "fit_decision": train_gate["decision"],
            "checked": False, "qualified_on_internal_dev": False,
        }
        if score > best_utility:
            anchor, best_utility = config, score
        if train_gate["decision"] == "KEEP_RESEARCH_CANDIDATE":
            checked_rows, check_p95 = metric_rows(check_input, config)
            check_gate = decide(base_check, checked_rows, candidate_p95_ms=check_p95)
            record["checked"] = True
            record["internal_dev_gain"] = check_gate["top5_required_route_gain"]
            record["qualified_on_internal_dev"] = (
                check_gate["decision"] == "KEEP_RESEARCH_CANDIDATE"
            )
            if record["qualified_on_internal_dev"]:
                if champion is None:
                    champion = config
                else:
                    old_rows, _ = metric_rows(check_input, champion)
                    if utility(base_check, checked_rows) > utility(base_check, old_rows):
                        champion = config
        log.append(record)
    new_state = {
        "schema_version": 1,
        "contract_sha256": initial_hash,
        "epoch": previous["epoch"] + 1,
        "total_trials": previous["total_trials"] + len(log),
        "seen": sorted(tested)[-512:],
        "anchor": anchor,
        "champion": champion,
    }
    git_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
        text=True, check=True, timeout=10,
    ).stdout.strip()
    report = {
        "schema_version": 1, "status": "ACTIONS_CPU_RESEARCH_ONLY",
        "source_commit": git_sha,
        "contract_sha256": initial_hash, "dataset_sha256": dataset_sha,
        "fit_tasks_per_catalog": len(fit_tasks),
        "internal_check_tasks_per_catalog": len(check_tasks),
        "catalogs": list(CATALOG_SIZES), "total_new_trials": len(log),
        "previous_epoch": previous["epoch"], "new_epoch": new_state["epoch"],
        "history": log, "champion": champion,
        "champion_available": champion is not None,
        "search_space": "continuous_safe_weights_not_generated_code",
        "compute": {
            "platform": platform.platform(), "cpu_count": os.cpu_count(),
            "python": platform.python_version(), "actions_run_id": os.getenv("GITHUB_RUN_ID"),
        },
        "limitations": [
            "EXPOSED_SYNTHETIC_DEV_ONLY",
            "FIT_AND_CHECK_SHARE_GENERATOR_NOT_INDEPENDENT",
            "CURRENT_REGISTERED_TOP24_CANNOT_RECOVER_MISSING_ROUTE",
            "NO_LLM_OR_AUTONOMOUS_SOURCE_EDITS",
            "NO_FIELD_GOLD_OR_AGENT_TASK_SUCCESS",
            "NO_EXECUTION_AUTHORIZATION_TESTED",
            "NO_PRODUCTION_RELEASE_OR_MERGE",
        ],
        "may_promote_to_product": False, "independent_validation": False,
    }
    return report, new_state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=16)
    parser.add_argument("--seed", type=int, default=1412)
    parser.add_argument("--seconds", type=int, default=900)
    parser.add_argument("--previous-state", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    previous = load_previous(args.previous_state, contract_hash())
    report, state = search(
        trials=args.trials, seed=args.seed, previous=previous, seconds=args.seconds,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in (("report.json", report), ("state.json", state)):
        (args.output_dir / name).write_text(
            json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "status": report["status"],
        "new_trials": report["total_new_trials"],
        "epoch": report["new_epoch"],
        "champion_found": report["champion_available"],
        "independent": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
