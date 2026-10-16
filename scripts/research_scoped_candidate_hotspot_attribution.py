"""Nested cost attribution of real authorized typed retrieval on Actions CPU.

All authority and scores come from the actual public SchemaRouter API. Only
class methods are temporarily instrumented in a single-threaded local study;
no global production hooks or persistent cache are installed.
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
from collections import defaultdict
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import patch

from benchmarks.current_adapter_field_scope_dev_v1 import principal
from benchmarks.current_adapter_scaled_authorized_dev_v1 import (
    DENIED_VIEWER,
    SIZES,
    build_fixture,
)
from schemarouter import AuthorizationPolicy, PlanRequest, SchemaRouter
from schemarouter.planner import SchemaPlanner
from scripts.research_authorized_retrieval_phase_profile import QUERIES
from scripts.research_current_main_multilingual_dev import encoded

ROOT = Path(__file__).resolve().parents[1]
MODES = ("scoped", "route_policy_only")
ROLES = ("viewer", "editor")
LANGUAGES = ("en", "ko", "ja")
REPEATS = 2
WIDTH = 24
# Phase wall-clock durations are inclusive and overlap when a nested
# method invokes another instrumented method. NEVER add these totals.
STAGES: tuple[tuple[type, str, str], ...] = (
    (SchemaRouter, "_scoped_analysis_registry", "analysis_registry"),
    (SchemaRouter, "_data_scope_endpoint_view", "field_schema_projection"),
    (SchemaRouter, "_project_retrieval_data_scope", "final_projection"),
    (AuthorizationPolicy, "visible", "route_authorization"),
    (AuthorizationPolicy, "data_scope", "data_scope_decision"),
    (SchemaPlanner, "_analyze_sync", "query_analysis"),
    (SchemaPlanner, "_retrieve_from_intent", "candidate_pipeline"),
    (SchemaPlanner, "_semantic_recall_catalog", "semantic_catalog"),
    (SchemaPlanner, "_score_endpoint", "endpoint_scoring"),
    (SchemaPlanner, "_sort_candidates", "candidate_sort"),
)
SOURCES = (
    "scripts/research_scoped_candidate_hotspot_attribution.py",
    "benchmarks/current_adapter_scaled_authorized_dev_v1.py",
    "scripts/research_authorized_retrieval_phase_profile.py",
    "src/schemarouter/runtime.py",
    "src/schemarouter/planner.py",
    "src/schemarouter/authorization.py",
)


def percentile(values: list[float], pct: int) -> float:
    if not values or any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("missing nonnegative measured CPU wall durations")
    return round(sorted(values)[math.ceil(len(values) * pct / 100) - 1], 5)


def timed_current_retrieval(
    router: SchemaRouter,
    *,
    query: str,
    role: str,
    mode: str,
) -> dict[str, Any]:
    if type(query) is not str or not query or role not in ROLES or mode not in MODES:
        raise ValueError("unregistered synthetic principal/mode/query")
    spans: dict[str, list[float]] = defaultdict(list)

    def wrapped(original: Any, stage: str) -> Any:
        def measure(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter_ns()
            try:
                return original(*args, **kwargs)
            finally:
                spans[stage].append(
                    (time.perf_counter_ns() - start) / 1_000_000,
                )
        return measure

    with ExitStack() as stack:
        for target, method, label in STAGES:
            stack.enter_context(patch.object(
                target, method, wrapped(getattr(target, method), label),
            ))
        start = time.perf_counter_ns()
        result = router.retrieve_authorized(
            PlanRequest(query=query), principal=principal(role), k=WIDTH,
        )
        elapsed = (time.perf_counter_ns() - start) / 1_000_000

    ids = [c.route_id for c in result.candidates]
    if (
        not math.isfinite(elapsed) or elapsed <= 0
        or result.requested_k != WIDTH
        or len(ids) > WIDTH or len(ids) != len(set(ids))
    ):
        raise ValueError("invalid exact authorized runtime output")
    if role == "viewer":
        if set(ids) & set(DENIED_VIEWER):
            raise ValueError("viewer obtained unauthorized write capability")
        if mode == "scoped" and any(
            f.name == "audit_tag"
            for c in result.candidates if c.tool.startswith("bench")
            for f in c.output_fields
        ):
            raise ValueError("hidden viewer field leaked through candidate search")
    if mode == "scoped":
        if (
            len(spans["analysis_registry"]) != 1
            or len(spans["semantic_catalog"]) != 1
            or len(spans["query_analysis"]) != 1
            or len(spans["candidate_pipeline"]) != 1
            or len(spans["final_projection"]) != 1
        ):
            raise ValueError("instrumentation missed scoped public API stages")
    else:
        if spans["analysis_registry"] or spans["field_schema_projection"]:
            raise ValueError("route-policy-only control entered field-scope mode")
    return {
        "elapsed_ms": round(elapsed, 5),
        "stages": {
            label: {
                "calls": len(spans[label]),
                "inclusive_total_ms": round(sum(spans[label]), 5),
            }
            for _, _, label in STAGES
        },
        "authorized_route_ids_sha256": hashlib.sha256(
            encoded(ids)
        ).hexdigest(),
        "output_schema_bytes": len(encoded([
            c.model_dump(mode="json") for c in result.candidates
        ])),
        "candidate_count": len(ids),
        "unauthorized_candidates": 0,
    }


def study(
    *,
    sizes: tuple[int, ...] = SIZES,
    repeats: int = REPEATS,
    languages: tuple[str, ...] = LANGUAGES,
) -> dict[str, Any]:
    if (
        type(sizes) is not tuple or not sizes
        or len(set(sizes)) != len(sizes)
        or any(type(v) is not int or v not in SIZES for v in sizes)
        or type(repeats) is not int or not (1 <= repeats <= REPEATS)
        or type(languages) is not tuple or not languages
        or len(set(languages)) != len(languages)
        or any(lang not in LANGUAGES for lang in languages)
    ):
        raise ValueError("unregistered bounded synthetic CPU attribution cohort")
    rows: list[dict[str, Any]] = []
    for size in sizes:
        current, original_policy = build_fixture(size)
        no_scope = SchemaRouter(
            registry=current.registry,
            authorization_policy=AuthorizationPolicy(
                rules=original_policy.rules,
                default_effect=original_policy.default_effect,
            ),
        )
        for language in languages:
            for role in ROLES:
                for iteration in range(repeats):
                    for mode in MODES:
                        router = current if mode == "scoped" else no_scope
                        observed = timed_current_retrieval(
                            router, query=QUERIES[language],
                            role=role, mode=mode,
                        )
                        rows.append({
                            "size": size, "language": language,
                            "role": role, "mode": mode,
                            "iteration": iteration,
                            "initial_iteration": iteration == 0,
                            **observed,
                        })
    expected = len(sizes) * len(languages) * len(ROLES) * len(MODES) * repeats
    if len(rows) != expected:
        raise ValueError("partial real authorized CPU attribution experiment")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[f"{row['size']}/{row['mode']}"].append(row)
    summaries = {
        key: {
            "calls": len(group),
            "whole_request_p50_ms": percentile([
                x["elapsed_ms"] for x in group
            ], 50),
            "whole_request_p95_ms": percentile([
                x["elapsed_ms"] for x in group
            ], 95),
            "stages": {
                name: {
                    "total_calls": sum(x["stages"][name]["calls"] for x in group),
                    "mean_inclusive_total_ms": round(sum(
                        x["stages"][name]["inclusive_total_ms"] for x in group
                    ) / len(group), 5),
                    "p95_inclusive_total_ms": percentile([
                        x["stages"][name]["inclusive_total_ms"] for x in group
                    ], 95),
                }
                for _, _, name in STAGES
            },
        }
        for key, group in sorted(groups.items())
    }
    source_files = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in SOURCES
    }
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, timeout=10,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return {
        "schema_version": 1,
        "id": "inclusive_nested_scoped_candidate_cost_synthetic_dev",
        "source_commit": sha,
        "source_file_sha256": source_files,
        "source_sha256": hashlib.sha256(encoded(source_files)).hexdigest(),
        "sizes": list(sizes), "languages": list(languages),
        "repeats": repeats, "width": WIDTH,
        "expected_calls": expected, "actual_calls": len(rows),
        "inclusive_spans_are_overlapping": True,
        "samples": rows, "groups": summaries,
        "peak_resident_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "hardware": {
            "os": platform.platform(), "cpu_count": os.cpu_count(),
            "python": platform.python_version(),
            "actions_run_id": os.environ.get("GITHUB_RUN_ID"),
        },
        "scope": {
            "same_author_synthetic_dev": True,
            "independent_confirmation": False,
            "real_provider_or_agent": False,
            "policy_removed_in_product": False,
            "may_release": False,
            "automatic_product_promotion": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="+", default=list(SIZES))
    parser.add_argument("--repeats", type=int, default=REPEATS)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    out = study(sizes=tuple(args.sizes), repeats=args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(out, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": out["id"],
        "sampled_calls": out["actual_calls"],
        "overlapping_spans": True,
        "may_release": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
