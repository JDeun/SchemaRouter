"""Paired current authorized typed retrieval/field CPU DEV at 100/250/500 routes.

Research-only. Not real provider, authenticated identity, execution, agent
task success, independent holdout, or a release qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import resource
import subprocess
import time
from pathlib import Path
from typing import Any

from benchmarks.current_adapter_field_scope_dev_v1 import (
    authored_tasks as prior_tasks,
    principal,
)
from benchmarks.current_adapter_scaled_authorized_dev_v1 import (
    DENIED_VIEWER,
    SIZES,
    WIDTHS,
    authored_tasks,
    build_fixture,
)
from research.autoresearch.actions_ranker import rank
from schemarouter import PlanRequest
from scripts.research_autoresearch_sandbox import candidate_view
from scripts.research_current_adapter_field_scope_dev import validate_gold
from scripts.research_current_main_multilingual_dev import encoded
from scripts.research_v1_v2_paired_cpu_dev import frozen_genomes
from scripts.research_v3_width_pareto_cpu_dev import p95

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "benchmarks/current_adapter_scaled_authorized_dev_v1.py",
    "benchmarks/current_adapter_field_scope_dev_v1.py",
    "benchmarks/autoresearch-v1-v2-frozen-incumbents.json",
    "scripts/research_current_adapter_scaled_authorized_dev.py",
    "scripts/research_current_adapter_field_scope_dev.py",
    "scripts/research_v1_v2_paired_cpu_dev.py",
    "scripts/research_autoresearch_sandbox.py",
    "research/autoresearch/actions_ranker.py",
    "src/schemarouter/planner.py",
    "src/schemarouter/runtime.py",
    "src/schemarouter/authorization.py",
    "src/schemarouter/adapters/openapi.py",
    "src/schemarouter/adapters/mcp.py",
)
MAX_CASES = 27
MAX_CALLS = len(SIZES) * MAX_CASES * (1 + len(WIDTHS))


def _tasks() -> list[dict[str, Any]]:
    tasks = authored_tasks()
    old_queries = {t["query"].casefold() for t in prior_tasks()}
    if (
        len(tasks) != MAX_CASES
        or len({t["id"] for t in tasks}) != MAX_CASES
        or len({t["query"] for t in tasks}) != MAX_CASES
        or set(t["query"].casefold() for t in tasks) & old_queries
        or {t["language"] for t in tasks} != {"en", "ko", "ja"}
    ):
        raise ValueError("new DEV authoring identity or exact-query isolation failed")
    return tasks


def _validate_retrieval(
    candidates: list[Any], allowed: set[str], width: int,
    role: str,
) -> None:
    ids = [item.route_id for item in candidates]
    if (
        len(ids) > width or len(ids) != len(set(ids))
        or not set(ids) <= allowed
    ):
        raise ValueError("unauthorized, missing-scope, duplicate or overwide shortlist")
    if role == "viewer":
        if any(route in DENIED_VIEWER for route in ids):
            raise ValueError("viewer-only authorization bypass")
        for candidate in candidates:
            if candidate.route_id.startswith("bench") and any(
                field.name == "audit_tag" for field in candidate.output_fields
            ):
                raise ValueError("viewer-only field projection leak")


def _measure(
    router: Any, query: str, who: Any, allowed: set[str],
    *, width: int, weights: dict[str, float],
) -> dict[str, Any]:
    start = time.perf_counter_ns()
    retrieved = router.retrieve_authorized(
        PlanRequest(query=query), principal=who, k=width,
    )
    raw = retrieved.candidates
    _validate_retrieval(raw, allowed, width, who.roles[0])
    ranked = rank(query, candidate_view(raw), weights)
    raw_ids = [item.route_id for item in raw]
    if len(ranked) != len(raw_ids) or set(ranked) != set(raw_ids):
        raise ValueError("ranker inserted, duplicated or omitted authorized endpoints")
    by_id = {item.route_id: item for item in raw}
    output = [by_id[route] for route in ranked[:5]]
    elapsed = (time.perf_counter_ns() - start) / 1_000_000
    if not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError("invalid measured retrieval/ranking latency")
    size_bytes = len(encoded([item.model_dump(mode="json") for item in output]))
    return {
        "top5": output, "elapsed_ms": elapsed, "schema_bytes": size_bytes,
        "all_candidate_ids": raw_ids,
    }


def _scored(
    task: dict[str, Any], measured: dict[str, Any],
    allowed: set[str],
) -> dict[str, Any]:
    gold = task["gold_route"]
    selected = measured["top5"]
    matched = next((item for item in selected if item.route_id == gold), None)
    gold_fields = set(task["gold_fields"])
    visible = {field.name for field in matched.output_fields} if matched else set()
    if gold is not None and gold not in allowed:
        raise ValueError("supported DEV gold illegally outside principal scope")
    return {
        "route_found": bool(gold is not None and matched),
        "required_field_count": len(gold_fields),
        "required_fields_found": sorted(gold_fields & visible),
        "all_required_fields_found": bool(gold is not None and gold_fields <= visible),
        "unsupported_nonempty_shortlist": bool(gold is None and selected),
        "top5_ids": [item.route_id for item in selected],
        "schema_bytes": measured["schema_bytes"],
        "retrieval_rerank_ms": round(measured["elapsed_ms"], 5),
        "unauthorized_count": sum(item.route_id not in allowed for item in selected),
    }


def _summary(cases: list[dict[str, Any]], name: str) -> dict[str, Any]:
    supported = [item for item in cases if item["required_route"] is not None]
    condition = [item["conditions"][name] for item in cases]
    eligible = [item["conditions"][name] for item in supported]
    required_total = sum(value["required_field_count"] for value in eligible)
    return {
        "cases": len(cases),
        "supported": len(supported),
        "required_routes_found": sum(x["route_found"] for x in eligible),
        "required_fields_found": sum(
            len(x["required_fields_found"]) for x in eligible
        ),
        "required_fields_total": required_total,
        "full_field_coverage": sum(
            x["all_required_fields_found"] for x in eligible
        ),
        "unsupported_nonempty_shortlist": sum(
            x["unsupported_nonempty_shortlist"] for x in condition
        ),
        "unauthorized_candidate_count": sum(
            x["unauthorized_count"] for x in condition
        ),
        "p95_retrieval_rerank_ms": round(p95([
            x["retrieval_rerank_ms"] for x in condition
        ]), 5),
        "mean_top5_schema_bytes": round(
            sum(x["schema_bytes"] for x in condition) / len(condition), 2
        ),
    }


def assess(*, sizes: tuple[int, ...] = SIZES) -> dict[str, Any]:
    if (
        not isinstance(sizes, tuple) or not sizes
        or len(set(sizes)) != len(sizes)
        or any(type(x) is not int or x not in SIZES for x in sizes)
    ):
        raise ValueError("unreviewed DEV catalog subset")
    v1, v2, manifest = frozen_genomes()
    if v1["width"] != 24 or v2["width"] != 64:
        raise ValueError("frozen research comparison dimensions changed")
    tasks = _tasks()
    source = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in SOURCES
    }
    cases: list[dict[str, Any]] = []
    for size in sizes:
        router, policy = build_fixture(size)
        catalog = {
            f"{tool.key}.{endpoint.name}": (tool, endpoint)
            for tool in router.registry.tools() for endpoint in tool.endpoints
        }
        if len(catalog) != size:
            raise ValueError("incomplete actual adapter-parsed scaled catalog")
        for task in tasks:
            validate_gold(task, catalog, policy)
            who = principal(task["role"])
            allowed = {
                route for route, (tool, endpoint) in catalog.items()
                if policy.visible(who, tool, endpoint)
            }
            if not allowed or (task["role"] == "viewer" and any(
                route in allowed for route in DENIED_VIEWER
            )):
                raise ValueError("authorization contract drift")
            full_oracle = bool(task["gold_route"] in allowed)
            conditions: dict[str, dict[str, Any]] = {}
            variants = (
                ("v1_k24", 24, v1["weights"]),
                *(
                    (f"v3_k{width}", width, v2["weights"])
                    for width in WIDTHS
                ),
            )
            for name, width, weights in variants:
                condition = _measure(
                    router, task["query"], who, allowed,
                    width=width, weights=weights,
                )
                conditions[name] = _scored(task, condition, allowed)
            cases.append({
                "case_id": task["id"], "language": task["language"],
                "scenario": task["scenario"], "role": task["role"],
                "catalog_size": size, "required_route": task["gold_route"],
                "required_fields": task["gold_fields"],
                "authorized_full_contains_required_route": full_oracle,
                "eligible_candidate_count": len(allowed),
                "conditions": conditions,
            })
    names = ("v1_k24", *(f"v3_k{w}" for w in WIDTHS))
    by_condition = {name: _summary(cases, name) for name in names}
    by_scale_language_role = {
        f"{size}/{lang}/{role}": {
            name: _summary(group, name) for name in names
        }
        for size in sizes
        for lang in ("en", "ko", "ja")
        for role in ("viewer", "editor")
        if (group := [
            c for c in cases
            if c["catalog_size"] == size
            and c["language"] == lang and c["role"] == role
        ])
    }
    source_sha = hashlib.sha256(encoded(source)).hexdigest()
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    return {
        "schema_version": 1,
        "id": "author_visible_scaled_current_adapter_principal_field_dev",
        "source_commit": commit,
        "source_sha256": source_sha,
        "source_file_sha256": source,
        "task_manifest_sha256": hashlib.sha256(encoded(tasks)).hexdigest(),
        "v1_champion_sha256": manifest["v1"]["content_sha256"],
        "v2_research_sha256": manifest["v2"]["content_sha256"],
        "registered_sizes": list(sizes),
        "candidate_widths": list(WIDTHS),
        "actual_authorized_router_calls": len(cases) * len(names),
        "required_router_calls_expected": len(sizes) * MAX_CASES * len(names),
        "overall": by_condition,
        "by_scale_language_role": by_scale_language_role,
        "cases": cases,
        "max_resident_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "scope": {
            "locally_authored_and_synthetic_dev_only": True,
            "new_queries_but_not_independently_blind": True,
            "actual_current_openapi_mcp_typed_parsers": True,
            "actual_current_principal_and_data_scope": True,
            "real_host_identity_authentication": False,
            "model_or_external_tools_executed": False,
            "actual_agent_task_success": False,
            "independent_confirmation": False,
            "automatic_product_promotion": False,
            "may_release": False,
        },
        "hardware": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "actions_run_id": os.environ.get("GITHUB_RUN_ID"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", type=int, default=list(SIZES))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = assess(sizes=tuple(args.sizes))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "SCALED_AUTHORIZED_CURRENT_ADAPTER_SYNTHETIC_DEV_ONLY",
        "cases": len(result["cases"]),
        "real_authorized_calls": result["actual_authorized_router_calls"],
        "unauthorized_candidates": sum(
            item["unauthorized_candidate_count"]
            for item in result["overall"].values()
        ),
        "independent": False, "may_release": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
