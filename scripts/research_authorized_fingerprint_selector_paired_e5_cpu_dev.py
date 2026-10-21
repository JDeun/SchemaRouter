"""Same-run actual E5 CPU DEV: original vs optimized native fingerprint selector.

Research-only patching of a private validation helper in one local synchronous
evaluation worker. No production knobs, model decisions, or source gold changes.
Captures source once, then compares identical scoped candidate decisions.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any
from unittest.mock import patch

from schemarouter.decisions import DecisionBackend
from scripts import research_authorized_fixed5_decision_bridge as bridge
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import (
    CORPUS,
    PRINCIPAL,
    real_cpu_backend,
)
from scripts.evaluate_authorized_e5_scale_500_cpu_dev import (
    ROOT,
    STRESS_MODEL_INPUT_BUDGET_BYTES,
    build_scaled_authorized_router,
)
from scripts.evaluate_multilingual_embedding_cpu_dev import (
    load_development_corpus,
    percentile,
)
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_authorized_fingerprint_scan_ab_cpu_dev import (
    _original_visible_fingerprints,
)

ROUTES = 500
ARMS = ("original_per_endpoint", "optimized_once_per_detached_tool")


def paired_fingerprint_selector_dev(
    corpus: dict[str, Any],
    digest: str,
    backend: DecisionBackend,
    *,
    case_limit: int | None = None,
) -> dict[str, Any]:
    source, source_sha = load_development_corpus(CORPUS)
    if corpus != source or digest != source_sha:
        raise ValueError("unverified frozen synthetic DEV source")
    if case_limit is not None and (
        type(case_limit) is not int or not 1 <= case_limit <= 84
    ):
        raise ValueError("invalid non-scored A/B smoke limit")
    router, catalog_sha = build_scaled_authorized_router(corpus, ROUTES)
    elapsed: dict[str, list[float]] = {name: [] for name in ARMS}
    shared_capture_elapsed: list[float] = []
    capture_plus_selector: dict[str, list[float]] = {
        name: [] for name in ARMS
    }
    paired_deltas: list[float] = []
    for ordinal, case in enumerate(corpus["cases"][:case_limit]):
        started_capture = time.perf_counter_ns()
        view = capture_authorized_agent_tool_surface(
            router, case["query"], principal=PRINCIPAL,
        )
        if len(view.visible_route_ids) != ROUTES:
            raise ValueError("invalid authorized source scope in paired A/B")
        capture_ms = (time.perf_counter_ns() - started_capture) / 1e6
        if not math.isfinite(capture_ms) or capture_ms < 0:
            raise ValueError("invalid shared source capture CPU latency")
        shared_capture_elapsed.append(capture_ms)

        decisions: dict[str, tuple[tuple[str, ...], str | None, int | None]] = {}
        order = ARMS if ordinal % 2 == 0 else ARMS[::-1]
        for arm in order:
            # Single-threaded DEV only. The original implementation is used
            # verbatim for the baseline; no production switch/override exists.
            scope = (
                patch.object(
                    bridge, "_visible_fingerprints",
                    _original_visible_fingerprints,
                )
                if arm == ARMS[0] else nullcontext()
            )
            with scope:
                started = time.perf_counter_ns()
                selector = bridge.AuthorizedFixed5DecisionSelector(
                    view,
                    backend,
                    max_model_input_bytes=STRESS_MODEL_INPUT_BUDGET_BYTES,
                )
                picked = selector(view.original_query, view.visible_route_ids)
                latency = (time.perf_counter_ns() - started) / 1e6
            if (
                type(latency) is not float
                or not math.isfinite(latency) or latency < 0
                or len(picked) != 5 or len(set(picked)) != 5
                or not set(picked).issubset(view.visible_route_ids)
                or selector.last_status != "unverified_full_k_model_ranking"
                or type(selector.last_model_input_bytes) is not int
                or selector.calibrated_no_fit or selector.executable_authority
                or selector.independent_quality_evidence
            ):
                raise ValueError("unverified paired A/B candidate result")
            elapsed[arm].append(latency)
            # Same authenticated source capture for both counterfactual arms.
            # Sum matched per-query durations BEFORE percentile aggregation.
            capture_plus_selector[arm].append(capture_ms + latency)
            decisions[arm] = (
                tuple(picked), selector.last_status, selector.last_model_input_bytes,
            )
        # The two real model decisions must agree in exact order/status/bytes.
        # Never use the task label or expected route to alter the selector.
        if decisions[ARMS[0]] != decisions[ARMS[1]]:
            raise ValueError("original/optimized E5 model ranking drift")
        view.assert_source_unchanged()
        paired_deltas.append(elapsed[ARMS[1]][-1] - elapsed[ARMS[0]][-1])

    complete = case_limit is None

    def _latency_summary(values: list[float]) -> dict[str, float]:
        if len(values) != 84 or any(
            type(value) is not float or not math.isfinite(value) or value < 0
            for value in values
        ):
            raise ValueError("invalid full-cohort measured latency observations")
        return {
            "p50_ms": percentile(values, 50),
            "p95_ms": percentile(values, 95),
            "p99_ms": percentile(values, 99),
            "mean_ms": statistics.fmean(values),
        }

    stats = (
        {arm: _latency_summary(elapsed[arm]) for arm in ARMS}
        if complete else None
    )
    capture_stats = (
        _latency_summary(shared_capture_elapsed) if complete else None
    )
    combined_stats = (
        {arm: _latency_summary(capture_plus_selector[arm]) for arm in ARMS}
        if complete else None
    )
    delta = (
        {
            "median_new_minus_original_ms": statistics.median(paired_deltas),
            "mean_new_minus_original_ms": statistics.fmean(paired_deltas),
            "optimized_faster_count": sum(d < 0 for d in paired_deltas),
            "original_faster_count": sum(d > 0 for d in paired_deltas),
            "equal_count": sum(d == 0 for d in paired_deltas),
        }
        if complete else None
    )
    return {
        "schema_version": 1,
        "evidence_tier": "UNATTESTED_BACKEND_PAIRED_FINGERPRINT_SELECTOR_DEV_ONLY",
        "real_model_routing_measured": False,
        "independent_e2_qualified": False,
        "agent_task_success_measured": False,
        "calibrated_no_fit": False,
        "product_default_promoted": False,
        "source_corpus_sha256": digest,
        "source_catalog_sha256": catalog_sha,
        "fixed_k": 5,
        "registered_native_routes": ROUTES,
        "full_84_case_evaluation": complete,
        "case_count": len(paired_deltas),
        "all_exact_order_status_bytes_identical": True,
        "arms": list(ARMS),
        "selector_including_constructor_latency_ms": stats,
        "shared_authorized_source_capture_latency_ms": capture_stats,
        "shared_capture_plus_selector_latency_ms": combined_stats,
        "paired_delta_summary": delta,
        "limitations": (
            "Same-run paired synthetic DEV only: selection plus constructor. "
            "Shared source capture is measured once per original query and "
            "added to each counterfactual selector duration before per-arm "
            "percentiles (not a sum of independent percentile values). "
            "This constructed source+selector interval is not a native "
            "provider, host agent E2, SLA or calibrated no-fit. "
            "Original helper substituted only in single-threaded research replay; "
            "no production behavior or permissions altered. "
            "Real CPU model and shared warm passage cache; order counterbalanced. "
            "No raw query, gold, source fields or per-case output is published."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    corpus, digest = load_development_corpus(CORPUS)
    backend, runtime = real_cpu_backend()
    report = paired_fingerprint_selector_dev(corpus, digest, backend)
    if (
        not report["full_84_case_evaluation"]
        or not report["all_exact_order_status_bytes_identical"]
    ):
        raise ValueError("cannot publish incomplete paired E5 selection")
    report["evidence_tier"] = "REAL_E5_CPU_PAIRED_FINGERPRINT_SELECTOR_DEV_ONLY"
    report["real_model_routing_measured"] = True
    report["model_runtime"] = runtime
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        capture_output=True, text=True, check=True, timeout=10,
    ).stdout.strip()
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("unattested paired A/B source revision")
    report["source_revision"] = sha
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "source_revision": sha,
        "evidence_tier": report["evidence_tier"],
        "all_exact_order_status_bytes_identical": True,
        "selector_including_constructor_latency_ms": report[
            "selector_including_constructor_latency_ms"
        ],
        "shared_authorized_source_capture_latency_ms": report[
            "shared_authorized_source_capture_latency_ms"
        ],
        "shared_capture_plus_selector_latency_ms": report[
            "shared_capture_plus_selector_latency_ms"
        ],
        "paired_delta_summary": report["paired_delta_summary"],
    }, allow_nan=False))


if __name__ == "__main__":
    main()
