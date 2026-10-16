"""Locate fingerprint serialization cost on the current authorized public API.

Read-only same-author synthetic DEV. Inclusive wrappers overlap. Only a
temporary class property replacement is made inside each serialized request;
it is restored before the next request, with no production instrumentation.
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
from schemarouter import AuthorizationPolicy, PlanRequest, SchemaRouter, ToolSpec
from schemarouter.executor import RegistryExecutor
from schemarouter.planner import SchemaPlanner
from scripts.research_authorized_retrieval_phase_profile import QUERIES
from scripts.research_current_main_multilingual_dev import encoded

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("en", "ko", "ja")
ROLES = ("viewer", "editor")
MODES = ("field_scope", "route_policy_only")
STAGES = (
    (SchemaPlanner, "_snapshot_tool_fingerprint", "tool_fingerprint_resolve"),
    (RegistryExecutor, "is_access_available_for_contract", "cooldown_lookup"),
    (SchemaPlanner, "_semantic_recall_catalog", "semantic_catalog"),
)
SOURCES = (
    "scripts/research_availability_fingerprint_attribution.py",
    "src/schemarouter/runtime.py",
    "src/schemarouter/planner.py",
    "src/schemarouter/executor.py",
    "src/schemarouter/models.py",
    "benchmarks/current_adapter_scaled_authorized_dev_v1.py",
)


def _p95(numbers: list[float]) -> float:
    if not numbers or any(not math.isfinite(v) or v < 0 for v in numbers):
        raise ValueError("missing or nonfinite CPU sample")
    return round(sorted(numbers)[math.ceil(len(numbers) * 0.95) - 1], 5)


def sample(
    router: SchemaRouter,
    *,
    language: str,
    role: str,
    mode: str,
) -> dict[str, Any]:
    if language not in LANGUAGES or role not in ROLES or mode not in MODES:
        raise ValueError("unapproved author-visible fingerprint probe")
    measured: dict[str, list[float]] = defaultdict(list)
    original_fingerprint = ToolSpec.fingerprint.fget
    if original_fingerprint is None:
        raise ValueError("ToolSpec.fingerprint is not the expected property")

    def wrap_method(original: Any, name: str) -> Any:
        def tracked(*args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter_ns()
            try:
                return original(*args, **kwargs)
            finally:
                measured[name].append(
                    (time.perf_counter_ns() - started) / 1_000_000
                )
        return tracked

    def track_fingerprint(tool: ToolSpec) -> str:
        started = time.perf_counter_ns()
        try:
            return original_fingerprint(tool)
        finally:
            measured["tool_fingerprint_property"].append(
                (time.perf_counter_ns() - started) / 1_000_000
            )

    # These class-level wrappers are deliberately limited to one synchronous
    # Actions CPU sample. Never use this diagnostic concurrently in a host.
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(ToolSpec, "fingerprint", property(track_fingerprint))
        )
        for target, method, stage in STAGES:
            stack.enter_context(patch.object(
                target, method,
                wrap_method(getattr(target, method), stage),
            ))
        # The planner captured the bound availability callback at router
        # construction. Replacing the SchemaRouter class descriptor later
        # does not replace that captured callback. Wrap the stored callback.
        callback = router.planner.availability_predicate
        if callback is None:
            raise ValueError("missing current availability predicate")
        stack.enter_context(patch.object(
            router.planner, "availability_predicate",
            wrap_method(callback, "access_predicate"),
        ))
        started = time.perf_counter_ns()
        result = router.retrieve_authorized(
            PlanRequest(query=QUERIES[language]),
            principal=principal(role),
            k=24,
        )
        elapsed = (time.perf_counter_ns() - started) / 1_000_000

    ids = [item.route_id for item in result.candidates]
    if (
        result.requested_k != 24 or len(ids) > 24 or len(ids) != len(set(ids))
        or not math.isfinite(elapsed) or elapsed <= 0
        or any(not math.isfinite(v) or v < 0
               for group in measured.values() for v in group)
    ):
        raise ValueError("invalid real current public authorized retrieval")
    if role == "viewer":
        if set(ids) & set(DENIED_VIEWER):
            raise ValueError("viewer unauthorized write capability leaked")
        if mode == "field_scope" and any(
            field.name == "audit_tag"
            for item in result.candidates if item.tool.startswith("bench")
            for field in item.output_fields
        ):
            raise ValueError("viewer hidden output field leaked")
    # Under the old eager contract every available endpoint triggered
    # a full ToolSpec fingerprint. After the lazy optimization, a catalog
    # without matching cooldowns MUST have zero fingerprint resolutions.
    # Missing availability or semantic-catalog calls still mean bad tracing.
    for key in ("access_predicate", "semantic_catalog"):
        if not measured[key]:
            raise ValueError(f"missing current availability instrument: {key}")
    if len(measured["cooldown_lookup"]) > len(
        measured["tool_fingerprint_resolve"]
    ):
        raise ValueError("cooldown check without a contract fingerprint")
    if len(measured["semantic_catalog"]) != 1:
        raise ValueError("semantic scorer unexpectedly reentered")
    return {
        "total_ms": round(elapsed, 5),
        "stages": {
            stage: {
                "calls": len(measured[stage]),
                "inclusive_total_ms": round(sum(measured[stage]), 5),
            }
            for stage in (
                "tool_fingerprint_property",
                "access_predicate",
                *(label for _, _, label in STAGES),
            )
        },
        "scope": mode,
        "language": language,
        "role": role,
        "candidate_count": len(ids),
        "visible_ids_sha256": hashlib.sha256(encoded(ids)).hexdigest(),
        "unauthorized_count": 0,
    }


def evaluate(
    *,
    sizes: tuple[int, ...] = SIZES,
    repeats: int = 2,
    languages: tuple[str, ...] = LANGUAGES,
) -> dict[str, Any]:
    if (
        type(sizes) is not tuple or not sizes
        or len(set(sizes)) != len(sizes)
        or any(type(v) is not int or v not in SIZES for v in sizes)
        or type(repeats) is not int or not 1 <= repeats <= 2
        or type(languages) is not tuple or not languages
        or len(set(languages)) != len(languages)
        or any(lang not in LANGUAGES for lang in languages)
    ):
        raise ValueError("unbounded or unregistered fingerprint CPU probe")
    rows: list[dict[str, Any]] = []
    for size in sizes:
        scoped, policy = build_fixture(size)
        router_no_scope = SchemaRouter(
            registry=scoped.registry,
            authorization_policy=AuthorizationPolicy(
                rules=policy.rules, default_effect=policy.default_effect,
            ),
        )
        for lang in languages:
            for role in ROLES:
                for iteration in range(repeats):
                    for mode in MODES:
                        router = (
                            scoped if mode == "field_scope" else router_no_scope
                        )
                        row = sample(
                            router, language=lang, role=role, mode=mode,
                        )
                        rows.append({
                            "size": size, "iteration": iteration, **row,
                        })
    expected = len(sizes) * len(languages) * len(ROLES) * len(MODES) * repeats
    if len(rows) != expected:
        raise ValueError("missing paired fingerprint-attribution samples")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[f"{row['size']}/{row['scope']}"].append(row)
    summary = {
        key: {
            "samples": len(group),
            "total_p95_ms": _p95([r["total_ms"] for r in group]),
            "stages": {
                stage: {
                    "calls": sum(x["stages"][stage]["calls"] for x in group),
                    "mean_inclusive_ms": round(
                        sum(x["stages"][stage]["inclusive_total_ms"]
                            for x in group) / len(group), 5,
                    ),
                    "p95_inclusive_ms": _p95([
                        x["stages"][stage]["inclusive_total_ms"] for x in group
                    ]),
                }
                for stage in rows[0]["stages"]
            },
        }
        for key, group in sorted(grouped.items())
    }
    source_files = {
        key: hashlib.sha256((ROOT / key).read_bytes()).hexdigest()
        for key in SOURCES
    }
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        check=True, capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    return {
        "schema_version": 1,
        "id": "source_frozen_nested_tool_fingerprint_cpu_dev",
        "source_commit": sha,
        "source_file_sha256": source_files,
        "source_sha256": hashlib.sha256(encoded(source_files)).hexdigest(),
        "expected": expected,
        "actual": len(rows),
        "sizes": list(sizes),
        "languages": list(languages),
        "repeats": repeats,
        "nested_times_overlap_do_not_sum": True,
        "groups": summary,
        "cases": rows,
        "peak_resident_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "hardware": {
            "os": platform.platform(),
            "cpu_count": os.cpu_count(),
            "python": platform.python_version(),
            "actions_run_id": os.environ.get("GITHUB_RUN_ID"),
        },
        "scope": {
            "synthetic_dev": True,
            "independent_confirmation": False,
            "real_agents_or_external_providers": False,
            "automatic_product_promotion": False,
            "may_release": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", type=int, default=list(SIZES))
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = evaluate(sizes=tuple(args.sizes), repeats=args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": report["id"], "cases": report["actual"],
        "independent": False, "may_release": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
