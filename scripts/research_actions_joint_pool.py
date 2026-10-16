"""CPU-only adaptive joint optimization of registered pool width and reranking.

No LLM, code-edit agent, network model, live tool execution, hidden holdout or
production promotion. Existing visible #430 generated DEV is diagnostic only.
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
from pathlib import Path
from typing import Any

from benchmarks.agent_utility_v5_catalog import (
    CATALOG_SIZES,
    build_registry,
    build_tasks,
)
from research.autoresearch.actions_ranker import BASE, generate, rank, validate
from schemarouter import PlanRequest, SchemaPlanner
from scripts.research_actions_only_search import split_tasks, utility
from scripts.research_autoresearch_sandbox import candidate_view, decide
from scripts.research_candidate_pool_ceiling_dev import POOL_SIZES
from scripts.research_current_main_multilingual_dev import KS, encoded, percentile, score_case

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "scripts/research_actions_joint_pool.py",
    ".github/workflows/research-actions-joint-pool-search.yml",
    "research/autoresearch/actions_ranker.py",
    "scripts/research_actions_only_search.py",
    "scripts/research_autoresearch_sandbox.py",
    "scripts/research_candidate_pool_ceiling_dev.py",
    "benchmarks/agent_utility_v5_catalog.py",
    "src/schemarouter/planner.py",
    "src/schemarouter/models.py",
)
MAX_TRIALS = 32
MAX_BATCHES = 8
CANDIDATE_TIME_MAX_MS = 20.0
MAX_RETRIEVAL_P95_MS = 250.0
MAX_RETRIEVAL_RATIO = 3.0
SEARCH_CLASS = "reviewed_joint_pool_width_and_rank_weights_DEV"


def validate_genome(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"pool_width", "weights"}:
        raise ValueError("unregistered pool/weights genome")
    if type(value["pool_width"]) is not int or value["pool_width"] not in POOL_SIZES:
        raise ValueError("unregistered candidate pool width")
    return {
        "pool_width": value["pool_width"],
        "weights": validate(value["weights"]),
    }


def genome_id(value: dict[str, Any]) -> str:
    return hashlib.sha256(encoded(validate_genome(value))).hexdigest()


def mutate(
    rng: random.Random, anchor: dict[str, Any] | None,
    champion: dict[str, Any] | None,
) -> dict[str, Any]:
    parent = validate_genome(anchor) if anchor is not None else None
    other = validate_genome(champion) if champion is not None else None
    weights = generate(
        rng,
        parent["weights"] if parent else None,
        other["weights"] if other else None,
    )
    if parent and rng.random() < 0.70:
        width = parent["pool_width"]
        if rng.random() < 0.35:
            width = rng.choice([w for w in POOL_SIZES if w != width])
    else:
        width = rng.choice(POOL_SIZES)
    return validate_genome({"pool_width": width, "weights": weights})


def manifest() -> dict[str, str]:
    return {
        filename: hashlib.sha256((ROOT / filename).read_bytes()).hexdigest()
        for filename in FILES
    }


def contract() -> str:
    return hashlib.sha256(encoded({
        "source": manifest(), "sizes": list(CATALOG_SIZES),
        "widths": list(POOL_SIZES), "k": list(KS),
        "split": "prior-visible-DEV-three-fit-two-check",
        "ranking": SEARCH_CLASS,
        "safety_limits": {
            "rerank_p95_ms": CANDIDATE_TIME_MAX_MS,
            "retrieval_p95_ms": MAX_RETRIEVAL_P95_MS,
            "relative_retrieval_p95": MAX_RETRIEVAL_RATIO,
        },
    })).hexdigest()


def blank_state() -> dict[str, Any]:
    return {
        "schema_version": 1, "contract_sha256": contract(),
        "epoch": 0, "total_trials": 0, "seen": [],
        "anchor": {"pool_width": 24, "weights": BASE.copy()},
        "champion": None,
    }


def load_state(path: Path | None) -> dict[str, Any]:
    result = blank_state()
    if path is None:
        return result
    if not path.is_file():
        raise ValueError("explicit predecessor artifact is missing")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or set(obj) != set(result):
        raise ValueError("untrusted previous research state shape")
    if obj["schema_version"] != 1 or obj["contract_sha256"] != result["contract_sha256"]:
        raise ValueError("previous state uses different source, dataset or search contract")
    epoch, count, seen = obj["epoch"], obj["total_trials"], obj["seen"]
    if (
        type(epoch) is not int or not 0 <= epoch < MAX_BATCHES
        or type(count) is not int or not 0 <= count <= MAX_BATCHES * MAX_TRIALS
        or not isinstance(seen, list) or len(seen) > MAX_BATCHES * MAX_TRIALS
        or len(seen) != len(set(seen))
        or any(
            type(item) is not str
            or len(item) != 64
            or any(c not in "0123456789abcdef" for c in item)
            for item in seen
        )
    ):
        raise ValueError("invalid or excessive previous trial state")
    if count != len(seen):
        raise ValueError("trial count and candidate IDs diverged")
    obj["anchor"] = validate_genome(obj["anchor"])
    if obj["champion"] is not None:
        obj["champion"] = validate_genome(obj["champion"])
        if genome_id(obj["champion"]) not in seen:
            raise ValueError("champion has no observed trial identity")
    return obj


def preload() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Cache actual current registered retrievals: each width is requested.

    The gold task labels remain outside candidate_view and rank().
    """
    tasks = build_tasks()
    fit, check = split_tasks(tasks)
    fit_ids = {t["task_id"] for t in fit}
    check_ids = {t["task_id"] for t in check}
    if fit_ids & check_ids or len(fit_ids) != 144 or len(check_ids) != 96:
        raise ValueError("synthetic DEV split is not case disjoint")
    entries: list[dict[str, Any]] = []
    for size in CATALOG_SIZES:
        registry = build_registry(size)
        registered = {
            f"{tool.key}.{endpoint.name}"
            for tool in registry.tools() for endpoint in tool.endpoints
        }
        if len(registered) != size:
            raise ValueError("synthetic current registry count changed")
        planner = SchemaPlanner(registry)
        planner._index()
        for task in tasks:
            if not set(task["required_route_ids"]) <= registered:
                raise ValueError("gold route absent from synthetic typed registry")
            candidates: dict[int, dict[str, Any]] = {}
            for width in POOL_SIZES:
                started = time.perf_counter_ns()
                retrieval = planner.retrieve(PlanRequest(query=task["query"]), k=width)
                elapsed = (time.perf_counter_ns() - started) / 1_000_000
                if retrieval.registry_version != registry.version or retrieval.requested_k != width:
                    raise ValueError("current typed registry snapshot differs")
                original = retrieval.candidates
                ids = [c.route_id for c in original]
                if len(ids) != len(set(ids)) or not set(ids) <= registered:
                    raise ValueError("unknown or duplicated registered route IDs")
                candidates[width] = {
                    "objects": original, "view": candidate_view(original),
                    "elapsed_ms": elapsed,
                }
            entries.append({
                "size": size, "task": task, "registered": registered,
                "candidates": candidates,
            })
    inputs_fit = [entry for entry in entries if entry["task"]["task_id"] in fit_ids]
    inputs_check = [entry for entry in entries if entry["task"]["task_id"] in check_ids]
    if len(inputs_fit) != 432 or len(inputs_check) != 288:
        raise ValueError("unexpected full mixed-catalog evaluation coverage")
    return inputs_fit, inputs_check, {
        "dataset_sha256": hashlib.sha256(encoded(tasks)).hexdigest(),
        "actual_current_planner_retrieval_calls": len(entries) * len(POOL_SIZES),
    }


def measure(
    cases: list[dict[str, Any]], genome: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    requested = validate_genome(genome)
    rows: list[dict[str, Any]] = []
    ranking_times: list[float] = []
    backend_times: list[float] = []
    pool_bytes: list[int] = []
    for item in cases:
        source = item["candidates"][requested["pool_width"]]
        original = source["objects"]
        views = source["view"]
        before = time.perf_counter_ns()
        ids = rank(item["task"]["query"], views, requested["weights"])
        rerank_ms = (time.perf_counter_ns() - before) / 1_000_000
        input_ids = [c.route_id for c in original]
        if len(ids) != len(input_ids) or len(set(ids)) != len(ids) or set(ids) != set(input_ids):
            raise ValueError("ranker manufactured or removed a registered route")
        lookup = {c.route_id: c for c in original}
        ordered = [lookup[route] for route in ids]
        ranking_times.append(rerank_ms)
        backend_times.append(source["elapsed_ms"])
        pool_bytes.append(len(encoded(views)))
        for k in KS:
            row = score_case(
                item["task"], candidates=ordered, k=k,
                latency_ms=source["elapsed_ms"] + rerank_ms,
                all_routes=item["registered"],
            )
            row["catalog_size"] = item["size"]
            rows.append(row)
    return rows, {
        "rerank_p95_ms": percentile(ranking_times, 0.95),
        "retrieval_p95_ms": percentile(backend_times, 0.95),
        "combined_p95_ms": percentile(
            [a + b for a, b in zip(backend_times, ranking_times, strict=True)],
            0.95,
        ),
        "average_candidate_pool_json_bytes": round(sum(pool_bytes) / len(pool_bytes), 2),
        "queries": len(cases),
    }


def gate(
    base_rows: list[dict[str, Any]], proposal_rows: list[dict[str, Any]],
    base_timing: dict[str, Any], proposal_timing: dict[str, Any],
) -> dict[str, Any]:
    result = decide(
        base_rows, proposal_rows,
        candidate_p95_ms=proposal_timing["rerank_p95_ms"],
    )
    base_p95 = base_timing["retrieval_p95_ms"]
    elapsed = proposal_timing["retrieval_p95_ms"]
    allowed = (
        math.isfinite(elapsed) and elapsed <= MAX_RETRIEVAL_P95_MS
        and elapsed <= MAX_RETRIEVAL_RATIO * max(base_p95, 0.001)
    )
    result["guard_results"]["width_backend_cpu_budget"] = allowed
    if not allowed:
        result["decision"] = "DISCARD_OR_REVISE"
    result["retrieval_p95_relative"] = round(elapsed / base_p95, 4) if base_p95 else None
    result["may_promote_product"] = False
    return result


def continue_chain(report: Any, state: Any, remaining: int) -> tuple[bool, int]:
    if type(remaining) is not int or not 1 <= remaining <= MAX_BATCHES:
        raise ValueError("illegal continuation budget")
    if not isinstance(report, dict) or not isinstance(state, dict):
        raise ValueError("invalid research receipt")
    if (
        report.get("status") != "JOINT_POOL_SYNTHETIC_DEV_ONLY"
        or report.get("contract_sha256") != state.get("contract_sha256")
        or state.get("contract_sha256") != contract()
        or report.get("may_promote_product") is not False
        or report.get("independent_confirmation") is not False
        or report.get("next_epoch") != state.get("epoch")
        or report.get("new_trial_count") != len(report.get("history", []))
        or report.get("champion") != state.get("champion")
        or type(state.get("epoch")) is not int
        or state["epoch"] + remaining - 1 != MAX_BATCHES
    ):
        raise ValueError("untrusted or divergent joint CPU search completion")
    more = remaining > 1 and report["new_trial_count"] > 0
    return more, remaining - 1 if more else 0


def search(
    *, trials: int, seconds: int, seed: int, previous: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if (
        type(trials) is not int or not 1 <= trials <= MAX_TRIALS
        or type(seconds) is not int or not 30 <= seconds <= 1200
        or type(seed) is not int or seed < 0
        or previous.get("contract_sha256") != contract()
        or previous["epoch"] >= MAX_BATCHES
    ):
        raise ValueError("invalid finite research request or stale prior state")
    source_at_start = manifest()
    fit, check, data_identity = preload()
    control = validate_genome({"pool_width": 24, "weights": BASE.copy()})
    train_base, train_base_timing = measure(fit, control)
    check_base, check_base_timing = measure(check, control)
    rng = random.Random(seed + previous["epoch"] * 1009)
    seen = set(previous["seen"])
    champion = previous["champion"]
    anchor = previous["anchor"]
    anchor_quality = utility(train_base, measure(fit, anchor)[0])
    history: list[dict[str, Any]] = []
    deadline = time.monotonic() + seconds
    for _ in range(trials):
        if time.monotonic() >= deadline:
            break
        genome = mutate(rng, anchor, champion)
        candidate_sha = genome_id(genome)
        if candidate_sha in seen:
            continue
        seen.add(candidate_sha)
        observed, timing = measure(fit, genome)
        decision = gate(train_base, observed, train_base_timing, timing)
        score = utility(train_base, observed)
        trial: dict[str, Any] = {
            "candidate_sha256": candidate_sha,
            "pool_width": genome["pool_width"],
            "weights": genome["weights"],
            "fit_score": score,
            "fit_top5_gain": decision["top5_required_route_gain"],
            "fit_decision": decision["decision"],
            "fit_timing": timing,
            "fit_guards": decision["guard_results"],
            "check_executed": False,
            "research_champion": False,
        }
        if score > anchor_quality and decision["guard_results"]["width_backend_cpu_budget"]:
            anchor, anchor_quality = genome, score
        if decision["decision"] == "KEEP_RESEARCH_CANDIDATE":
            check_rows, check_timing = measure(check, genome)
            checked = gate(check_base, check_rows, check_base_timing, check_timing)
            trial["check_executed"] = True
            trial["check_top5_gain"] = checked["top5_required_route_gain"]
            trial["check_decision"] = checked["decision"]
            trial["check_guards"] = checked["guard_results"]
            if checked["decision"] == "KEEP_RESEARCH_CANDIDATE":
                old_score = (
                    utility(check_base, measure(check, champion)[0])
                    if champion is not None else 0.0
                )
                if utility(check_base, check_rows) > old_score:
                    champion = genome
                    trial["research_champion"] = True
        history.append(trial)
    if manifest() != source_at_start:
        raise ValueError("registered research/product code changed mid-experiment")
    new_state = {
        "schema_version": 1, "contract_sha256": contract(),
        "epoch": previous["epoch"] + 1,
        "total_trials": previous["total_trials"] + len(history),
        "seen": sorted(seen),
        "anchor": anchor, "champion": champion,
    }
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        text=True, capture_output=True, check=True, timeout=10,
    ).stdout.strip()
    return {
        "schema_version": 1, "status": "JOINT_POOL_SYNTHETIC_DEV_ONLY",
        "source_commit": head, "source_sha256": source_at_start,
        "contract_sha256": contract(), **data_identity,
        "fit_requests": len(fit), "internal_check_requests": len(check),
        "pool_widths": list(POOL_SIZES), "scored_k": list(KS),
        "current_planner_control": {
            "pool_width": 24, "weights": BASE.copy(),
            "train_cpu": train_base_timing, "check_cpu": check_base_timing,
        },
        "history": history, "new_trial_count": len(history),
        "previous_epoch": previous["epoch"], "next_epoch": new_state["epoch"],
        "champion": champion,
        "execution": {
            "platform": platform.platform(), "python": platform.python_version(),
            "cpu_count": os.cpu_count(), "github_run": os.getenv("GITHUB_RUN_ID"),
        },
        "limitations": [
            "Previously exposed, single-generator synthetic multilingual DEV",
            "Internal check reused adaptively, NOT an independent holdout",
            "No actual principal-specific authorization, field-gold, or agent task success",
            "No LLM, code-writing agent, execution, or product changes",
        ],
        "may_promote_product": False, "independent_confirmation": False,
    }, new_state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=12)
    parser.add_argument("--seconds", type=int, default=900)
    parser.add_argument("--seed", type=int, default=1412)
    parser.add_argument("--previous-state", type=Path)
    parser.add_argument("--remaining", type=int, default=MAX_BATCHES)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    state = load_state(args.previous_state)
    report, next_state = search(
        trials=args.trials, seconds=args.seconds, seed=args.seed, previous=state,
    )
    follow, next_remaining = continue_chain(report, next_state, args.remaining)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, contents in (("report.json", report), ("state.json", next_state)):
        (args.output_dir / filename).write_text(
            json.dumps(contents, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "status": report["status"], "trials": report["new_trial_count"],
        "champion": next_state["champion"] is not None,
        "new_epoch": next_state["epoch"],
        "continue_next": follow, "remaining_next": next_remaining,
        "independent": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
