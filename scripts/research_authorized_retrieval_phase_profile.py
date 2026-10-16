"""Phase-timed current authorized retrieval (research DEV; no product changes).

This intentionally instruments the SAME production public API. Timings are
wall-clock under Python wrappers, not uninstrumented CPU-cycle measurements.
No external model, network, action, or live third-party provider is invoked.
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
from scripts.research_current_main_multilingual_dev import encoded

ROOT = Path(__file__).resolve().parents[1]
WIDTHS = (24, 56)
LANGUAGES = ("en", "ko", "ja")
ROLES = ("viewer", "editor")
SCOPES = ("field_scope", "route_policy_only")
REPEATS = 2
# Texts are author-visible synthetic DEV, not independently audited labels.
QUERIES = {
    "en": "Read invoice total amount and payment status.",
    "ko": "청구서의 합계 금액과 결제 상태를 조회하세요.",
    "ja": "請求書の合計金額と支払い状況を取得してください。",
}
STAGE_METHODS = (
    (SchemaRouter, "_scoped_analysis_registry", "scoped_registry_rebuild"),
    (SchemaRouter, "_project_retrieval_data_scope", "final_field_projection"),
    (SchemaPlanner, "_analyze_sync", "planner_query_analysis"),
    (SchemaPlanner, "_retrieve_from_intent", "planner_retrieval_total"),
    (SchemaPlanner, "_candidates", "planner_candidate_scoring"),
)
SOURCES = (
    "benchmarks/current_adapter_scaled_authorized_dev_v1.py",
    "benchmarks/current_adapter_field_scope_dev_v1.py",
    "scripts/research_authorized_retrieval_phase_profile.py",
    "src/schemarouter/runtime.py",
    "src/schemarouter/planner.py",
    "src/schemarouter/authorization.py",
)
EXPECTED_ROWS = (
    len(SIZES) * len(WIDTHS) * len(LANGUAGES)
    * len(ROLES) * len(SCOPES) * REPEATS
)


def _percentile(values: list[float], numerator: int) -> float:
    if not values or any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("no valid exact profile elapsed durations")
    return round(sorted(values)[math.ceil(len(values) * numerator / 100) - 1], 5)


def timed_retrieve(
    router: SchemaRouter,
    *,
    query: str,
    role: str,
    width: int,
    mode: str,
) -> dict[str, Any]:
    if role not in ROLES or width not in WIDTHS or mode not in SCOPES:
        raise ValueError("unregistered profile principal, width or policy mode")
    who = principal(role)
    spans: dict[str, list[float]] = defaultdict(list)

    def timed(original: Any, stage: str) -> Any:
        def measure(*args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter_ns()
            try:
                return original(*args, **kwargs)
            finally:
                elapsed = (time.perf_counter_ns() - started) / 1_000_000
                spans[stage].append(elapsed)
        return measure

    with ExitStack() as stack:
        for target, method, stage in STAGE_METHODS:
            stack.enter_context(patch.object(
                target, method, timed(getattr(target, method), stage),
            ))
        started = time.perf_counter_ns()
        retrieval = router.retrieve_authorized(
            PlanRequest(query=query), principal=who, k=width,
        )
        total = (time.perf_counter_ns() - started) / 1_000_000

    if (
        retrieval.requested_k != width
        or len(retrieval.candidates) > width
        or not math.isfinite(total)
        or total < 0
    ):
        raise ValueError("invalid exact current authorized retrieval")
    names = [item.route_id for item in retrieval.candidates]
    if len(set(names)) != len(names):
        raise ValueError("duplicate authorized capability")
    if role == "viewer":
        if set(names).intersection(DENIED_VIEWER):
            raise ValueError("unauthorized mutating viewer capability")
        if mode == "field_scope" and any(
            field.name == "audit_tag"
            for item in retrieval.candidates
            for field in item.output_fields
            if item.tool.startswith("bench")
        ):
            raise ValueError("hidden viewer field leaked into search result")
    if mode == "route_policy_only" and spans.get("scoped_registry_rebuild"):
        raise ValueError("no-field-scope path rebuilt scoped analysis registry")
    if mode == "field_scope" and len(spans.get("scoped_registry_rebuild", [])) != 1:
        raise ValueError("scoped registry phase was bypassed or double invoked")
    if any(len(spans.get(stage, [])) != 1 for stage in (
        "planner_query_analysis", "planner_retrieval_total",
        "planner_candidate_scoring", "final_field_projection",
    )):
        raise ValueError("missing or duplicated stage timing instrumentation")

    phases = {
        stage: round(sum(spans.get(stage, [])), 5)
        for _, _, stage in STAGE_METHODS
    }
    # Nested candidate scoring is a component of planner retrieval time.
    independent_stages = (
        phases["scoped_registry_rebuild"]
        + phases["planner_query_analysis"]
        + phases["planner_retrieval_total"]
        + phases["final_field_projection"]
    )
    if independent_stages > total * 1.01:
        raise ValueError("overlapping or invalid top-level phase accounting")
    phases["other"] = round(total - independent_stages, 5)
    phases["planner_non_candidate"] = round(
        phases["planner_retrieval_total"]
        - phases["planner_candidate_scoring"], 5,
    )
    if phases["planner_non_candidate"] < -0.001:
        raise ValueError("nested scorer timing exceeds encompassing retrieval")
    return {
        "total_ms": round(total, 5),
        "phases_ms": phases,
        "return_count": len(names),
        "ids_sha256": hashlib.sha256(encoded(names)).hexdigest(),
        "schema_bytes": len(encoded([
            item.model_dump(mode="json") for item in retrieval.candidates
        ])),
        "unauthorized_count": 0,
        "principal": role,
        "scope": mode,
        "requested_k": width,
    }


def _groups(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        name = "/".join(str(row[k]) for k in (
            "size", "language", "role", "mode", "width",
        ))
        groups[name].append(row)
    return {
        key: {
            "samples": len(entries),
            "total_p50_ms": _percentile([r["total_ms"] for r in entries], 50),
            "total_p95_ms": _percentile([r["total_ms"] for r in entries], 95),
            "phase_p95_ms": {
                stage: _percentile([
                    r["phases_ms"][stage] for r in entries
                ], 95)
                for _, _, stage in STAGE_METHODS
            },
        }
        for key, entries in sorted(groups.items())
    }


def profile(
    *,
    sizes: tuple[int, ...] = SIZES,
    repeats: int = REPEATS,
    languages: tuple[str, ...] = LANGUAGES,
    widths: tuple[int, ...] = WIDTHS,
) -> dict[str, Any]:
    if (
        not isinstance(sizes, tuple) or not sizes
        or len(set(sizes)) != len(sizes)
        or any(type(x) is not int or x not in SIZES for x in sizes)
        or type(repeats) is not int or not 1 <= repeats <= REPEATS
        or not isinstance(languages, tuple) or not languages
        or len(set(languages)) != len(languages)
        or any(x not in LANGUAGES for x in languages)
        or not isinstance(widths, tuple) or not widths
        or len(set(widths)) != len(widths)
        or any(type(x) is not int or x not in WIDTHS for x in widths)
    ):
        raise ValueError("unregistered phase-profile CPU experiment shape")

    cases: list[dict[str, Any]] = []
    for size in sizes:
        scoped_router, original = build_fixture(size)
        route_only_policy = AuthorizationPolicy(
            rules=original.rules,
            default_effect=original.default_effect,
        )
        route_only_router = SchemaRouter(
            registry=scoped_router.registry,
            authorization_policy=route_only_policy,
        )
        routers = {
            "field_scope": scoped_router,
            "route_policy_only": route_only_router,
        }
        for language in languages:
            for role in ROLES:
                for width in widths:
                    for iteration in range(repeats):
                        for mode in SCOPES:
                            row = timed_retrieve(
                                routers[mode], query=QUERIES[language],
                                role=role, width=width, mode=mode,
                            )
                            row.update({
                                "size": size, "language": language,
                                "role": role, "width": width,
                                "mode": mode, "iteration": iteration,
                                "warmup": iteration == 0,
                            })
                            cases.append(row)

    expected = len(sizes) * len(languages) * len(widths) * len(ROLES) * len(SCOPES) * repeats
    if len(cases) != expected:
        raise ValueError("partial phase-profile paired request matrix")
    source_sha = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in SOURCES
    }
    git = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        text=True, capture_output=True, check=True, timeout=10,
    ).stdout.strip()
    return {
        "schema_version": 1,
        "scope": {
            "author_visible_synthetic_dev": True,
            "end_to_end_agent_or_provider": False,
            "instrumented_wall_clock_not_uninstrumented_slo": True,
            "host_principal_authenticated": False,
            "positive_quality_claim": False,
            "independent_confirmation": False,
            "automatic_product_change": False,
            "may_release": False,
        },
        "source_commit": git,
        "source_file_sha256": source_sha,
        "source_sha256": hashlib.sha256(encoded(source_sha)).hexdigest(),
        "languages": list(languages),
        "sizes": list(sizes),
        "widths": list(widths),
        "repeats": repeats,
        "cases_expected": expected,
        "cases_actual": len(cases),
        "groups": _groups(cases),
        "cases": cases,
        "peak_resident_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "hardware": {
            "os": platform.platform(), "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "actions_run_id": os.environ.get("GITHUB_RUN_ID"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", type=int, default=list(SIZES))
    parser.add_argument("--repeats", type=int, default=REPEATS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = profile(sizes=tuple(args.sizes), repeats=args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "INSTRUMENTED_AUTHORIZED_SYNTHETIC_DEV_ONLY",
        "paired_requests": evidence["cases_actual"],
        "source_sha256": evidence["source_sha256"],
        "independent": False, "may_release": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
