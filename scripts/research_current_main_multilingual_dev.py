"""Observe current SchemaRouter typed Top-K on existing multilingual DEV (#1412).

The 240-task / 100-250-500 catalog from #430 is previously exposed DEV,
not a new corpus, independent confirmation or real heterogeneous integration.
This evaluator uses the current SchemaPlanner API. It NEVER invokes endpoints
or an LLM, and never treats nonempty unsupported retrieval as unauthorized
execution. Frozen historical independent experiments remain unopened.
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
from collections import defaultdict
from pathlib import Path
from typing import Any

from benchmarks.agent_utility_v5_catalog import (
    CATALOG_SIZES,
    LANGUAGES,
    STRATA,
    TASKS_PER_CELL,
    build_registry,
    build_tasks,
)
from schemarouter import PlanRequest, SchemaPlanner

ROOT = Path(__file__).resolve().parents[1]
KS = (3, 5, 10)
CORPUS_PATH = ROOT / "benchmarks/agent_utility_v5_catalog.py"
FIXTURE_CLASS = "previously_exposed_synthetic_multilingual_DEV"
REPORT_SCOPE = {
    "independent_confirmation": False,
    "newly_authored_cases": False,
    "host_authorization_tested": False,
    "tool_execution_tested": False,
    "agent_task_success_tested": False,
    "required_output_field_gold_available": False,
    "may_promote": False,
    "may_release": False,
}


def encoded(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def percentile(values: list[float], rank: float) -> float:
    if not values or any(not math.isfinite(x) or x < 0 for x in values):
        raise ValueError("no finite nonnegative timing samples")
    ordered = sorted(values)
    position = (len(ordered) - 1) * rank
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def validate_tasks(tasks: list[dict[str, Any]]) -> None:
    if len(tasks) != len(LANGUAGES) * len(STRATA) * TASKS_PER_CELL:
        raise ValueError("historical DEV surface changed: expected 240 cases")
    ids: set[str] = set()
    queries: set[str] = set()
    cohort: dict[tuple[str, str], int] = defaultdict(int)
    for case in tasks:
        if not isinstance(case, dict) or set(case) != {
            "task_id", "task_stratum", "language", "query",
            "required_route_ids",
        }:
            raise ValueError("malformed DEV task")
        case_id, query = case["task_id"], case["query"]
        language, stratum = case["language"], case["task_stratum"]
        gold = case["required_route_ids"]
        if (
            type(case_id) is not str or not case_id.strip() or case_id in ids
            or type(query) is not str or not query.strip() or query in queries
            or language not in LANGUAGES or stratum not in STRATA
            or type(gold) is not list
            or any(type(route) is not str or "." not in route for route in gold)
            or len(gold) != len(set(gold))
        ):
            raise ValueError("duplicate, malformed, or out-of-scope task")
        if (stratum in ("near_domain_unsupported", "out_of_domain")) != (not gold):
            raise ValueError("unexpected supported/unsupported stratum membership")
        ids.add(case_id)
        queries.add(query)
        cohort[language, stratum] += 1
    if any(
        cohort[language, stratum] != TASKS_PER_CELL
        for language in LANGUAGES for stratum in STRATA
    ):
        raise ValueError("language/stratum coverage drift")


def select_cases(
    tasks: list[dict[str, Any]], *, cases_per_group: int,
) -> list[dict[str, Any]]:
    if type(cases_per_group) is not int or not 1 <= cases_per_group <= TASKS_PER_CELL:
        raise ValueError("invalid bounded DEV cohort size")
    validate_tasks(tasks)
    chosen: list[dict[str, Any]] = []
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for case in tasks:
        key = (case["language"], case["task_stratum"])
        if counts[key] < cases_per_group:
            chosen.append(case)
            counts[key] += 1
    if len(chosen) != len(LANGUAGES) * len(STRATA) * cases_per_group:
        raise ValueError("selected DEV cohort count drift")
    return chosen


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("cannot summarize an empty evaluation group")
    supported = [r for r in rows if r["required_route_count"] > 0]
    unsupported = [r for r in rows if r["required_route_count"] == 0]
    total_required = sum(r["required_route_count"] for r in supported)
    found_required = sum(r["found_required_count"] for r in supported)
    return {
        "cases": len(rows),
        "supported_cases": len(supported),
        "unsupported_cases": len(unsupported),
        "required_route_count": total_required,
        "required_route_recall": (
            found_required / total_required if total_required else None
        ),
        "all_required_coverage": (
            sum(r["full_coverage"] for r in supported) / len(supported)
            if supported else None
        ),
        "unsupported_nonempty_shortlist_rate": (
            sum(bool(r["selected_route_ids"]) for r in unsupported) / len(unsupported)
            if unsupported else None
        ),
        "mean_selected_candidate_json_bytes": round(
            sum(r["candidate_json_bytes"] for r in rows) / len(rows), 2,
        ),
        "request_latency_p50_ms": round(
            percentile([r["retrieval_latency_ms"] for r in rows], 0.5), 3,
        ),
        "request_latency_p95_ms": round(
            percentile([r["retrieval_latency_ms"] for r in rows], 0.95), 3,
        ),
        "missing_required_examples": [
            {"task_id": r["task_id"], "missing": r["missing_required_route_ids"]}
            for r in rows if r["missing_required_route_ids"]
        ][:12],
    }


def score_case(
    case: dict[str, Any], *, candidates: list[Any], k: int,
    latency_ms: float, all_routes: set[str],
) -> dict[str, Any]:
    if k not in KS:
        raise ValueError("unapproved K for development assessment")
    if not math.isfinite(latency_ms) or latency_ms < 0:
        raise ValueError("bad measured request latency")
    selected = candidates[:k]
    route_ids = [item.route_id for item in selected]
    if (
        len(route_ids) != len(set(route_ids))
        or any(type(route) is not str or route not in all_routes for route in route_ids)
    ):
        raise ValueError("unregistered or duplicate candidate leaked")
    gold = case["required_route_ids"]
    if not set(gold) <= all_routes:
        raise ValueError("task gold missing from declared registry")
    missing = sorted(set(gold) - set(route_ids))
    selected_bytes = len(encoded([item.model_dump(mode="json") for item in selected]))
    return {
        "task_id": case["task_id"],
        "language": case["language"],
        "stratum": case["task_stratum"],
        "k": k,
        "required_route_count": len(gold),
        "found_required_count": len(gold) - len(missing),
        "full_coverage": int(bool(gold) and not missing),
        "missing_required_route_ids": missing,
        "selected_route_ids": route_ids,
        "candidate_json_bytes": selected_bytes,
        # Retrieval measured once at max-K per task. This is shared across
        # derived K slices; it is NOT independently timed K=3 or K=5.
        "retrieval_latency_ms": round(latency_ms, 3),
    }


def source_identity() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        capture_output=True, text=True, check=True, timeout=10,
    ).stdout.strip()
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise ValueError("invalid exact source checkout")
    paths = (
        "benchmarks/agent_utility_v5_catalog.py",
        "scripts/research_current_main_multilingual_dev.py",
        "src/schemarouter/planner.py",
        "src/schemarouter/models.py",
    )
    digests = {path: sha256((ROOT / path).read_bytes()) for path in paths}
    return {
        "source_commit": commit,
        "source_file_sha256": digests,
        "manifest_sha256": sha256(encoded(digests)),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "actions_run_id": os.getenv("GITHUB_RUN_ID"),
    }


def evaluate(
    *,
    sizes: tuple[int, ...] = CATALOG_SIZES,
    cases_per_group: int = TASKS_PER_CELL,
) -> dict[str, Any]:
    if not sizes or len(sizes) != len(set(sizes)) or any(s not in CATALOG_SIZES for s in sizes):
        raise ValueError("not a registered current API DEV catalog size")
    tasks = build_tasks()
    selected_tasks = select_cases(tasks, cases_per_group=cases_per_group)
    rows: list[dict[str, Any]] = []
    catalog_summaries: list[dict[str, Any]] = []
    for size in sizes:
        registry = build_registry(size)
        tools = registry.tools()
        all_routes = {
            f"{tool.key}.{endpoint.name}"
            for tool in tools for endpoint in tool.endpoints
        }
        if len(all_routes) != size:
            raise ValueError("catalog endpoint identities drift")
        if not all(set(case["required_route_ids"]) <= all_routes for case in selected_tasks):
            raise ValueError("historical required capability missing from catalog")
        planner = SchemaPlanner(registry)
        # Warm only the index; do not prime a benchmark case and count it as data.
        planner._index()
        for case in selected_tasks:
            start = time.perf_counter_ns()
            retrieval = planner.retrieve(PlanRequest(query=case["query"]), k=max(KS))
            latency_ms = (time.perf_counter_ns() - start) / 1_000_000
            if retrieval.registry_version != registry.version:
                raise ValueError("stale registry snapshot in development retrieval")
            if retrieval.requested_k != max(KS):
                raise ValueError("bad registered candidate envelope")
            for k in KS:
                row = score_case(
                    case, candidates=retrieval.candidates,
                    k=k, latency_ms=latency_ms, all_routes=all_routes,
                )
                row["catalog_size"] = size
                rows.append(row)
        catalog_summaries.append({
            "catalog_size": size,
            "total_registered_route_ids": len(all_routes),
            "source_type": "synthetic_typed_registry_not_live_protocol_adapters",
            "per_k": [
                {"k": k, **summarize([
                    r for r in rows if r["catalog_size"] == size and r["k"] == k
                ])}
                for k in KS
            ],
        })
    return {
        "schema_version": 1,
        "benchmark": "current-code-multilingual-typed-retrieval-dev",
        "scope": REPORT_SCOPE.copy(),
        "corpus_class": FIXTURE_CLASS,
        "data_manifest_sha256": sha256(encoded(tasks)),
        "language_cohorts": list(LANGUAGES),
        "task_strata": list(STRATA),
        "catalog_sizes": list(sizes),
        "ks": list(KS),
        "cases_per_language_stratum": cases_per_group,
        "cases_per_catalog": len(selected_tasks),
        "catalogs": catalog_summaries,
        "cohorts": [
            {
                "catalog_size": size,
                "k": k,
                "language": lang,
                **summarize([
                    r for r in rows
                    if r["catalog_size"] == size
                    and r["k"] == k and r["language"] == lang
                ]),
            }
            for size in sizes for k in KS for lang in LANGUAGES
        ],
        "strata": [
            {
                "catalog_size": size,
                "k": k,
                "stratum": stratum,
                **summarize([
                    r for r in rows
                    if r["catalog_size"] == size
                    and r["k"] == k and r["stratum"] == stratum
                ]),
            }
            for size in sizes for k in KS for stratum in STRATA
        ],
        "case_rows": rows,
        "claim_boundary": (
            "Previously exposed synthetic multilingual DEV only: candidates"
            " are scored with the current public planner, never executed."
            " Required output-field gold, live provider adapters, true host"
            " authorization, agent task success and independent qualification"
            " are not measured. K3/K5 timings are inherited from K10 retrieval."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, choices=CATALOG_SIZES, nargs="+",
                    default=list(CATALOG_SIZES))
    ap.add_argument("--cases-per-group", type=int, default=TASKS_PER_CELL)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.cases_per_group not in range(1, TASKS_PER_CELL + 1):
        ap.error("cases-per-group must be within the registered DEV cohort")
    result = evaluate(
        sizes=tuple(args.sizes),
        cases_per_group=args.cases_per_group,
    )
    result["identity"] = source_identity()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    for row in result["cohorts"]:
        if row["k"] == 5:
            print(json.dumps({
                "size": row["catalog_size"], "language": row["language"],
                "k": row["k"], "recall": row["required_route_recall"],
                "full_coverage": row["all_required_coverage"],
                "unsupported_nonempty": row["unsupported_nonempty_shortlist_rate"],
            }))
    print(json.dumps({
        "status": "EXPOSED_SYNTHETIC_DEV_ONLY",
        "commit": result["identity"]["source_commit"],
        "case_count_per_catalog": result["cases_per_catalog"],
        "catalog_count": len(result["catalogs"]),
        "independent_confirmation": False,
        "agent_task_success": "NOT_MEASURED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
