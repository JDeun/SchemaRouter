"""Paired, no-model source-fingerprint scan optimization DEV (#1339/#1477).

The baseline is the original per-endpoint ToolSpec fingerprint implementation.
Both arms resnapshot the same protected registry each time, compare every
route+fingerprint, and never suppress before/after authorization checks.
Measured speed is a scan-level CPU result, NOT model or agent E2 latency.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from scripts.evaluate_authorized_e5_hybrid_cpu_dev import CORPUS, PRINCIPAL
from scripts.evaluate_authorized_e5_scale_500_cpu_dev import (
    SIZES,
    build_scaled_authorized_router,
)
from scripts.evaluate_multilingual_embedding_cpu_dev import (
    load_development_corpus,
    percentile,
)
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_authorized_fixed5_decision_bridge import (
    _visible_fingerprints,
)

ROOT = Path(__file__).resolve().parents[1]
PAIRS_PER_SCALE = 24


def _original_visible_fingerprints(view: Any) -> dict[str, tuple[str, str]]:
    """Unchanged earlier research source scan (reference baseline only)."""
    source: dict[str, tuple[str, str]] = {}
    for tool in view.router.registry.tools():
        for endpoint in tool.endpoints:
            route = f"{tool.key}.{endpoint.name}"
            if route in source:
                raise ValueError("duplicate native source route")
            if route in view.visible_route_ids:
                source[route] = (tool.fingerprint, endpoint.fingerprint)
    if set(source) != set(view.visible_route_ids):
        raise ValueError("baseline native source fingerprints incomplete")
    return source


def run_fingerprint_scan_ab() -> dict[str, Any]:
    corpus, digest = load_development_corpus(CORPUS)
    case = corpus["cases"][0]  # One pinned source request, no model/agent.
    scales: dict[str, Any] = {}
    for size in SIZES:
        router, native_sha = build_scaled_authorized_router(corpus, size)
        view = capture_authorized_agent_tool_surface(
            router, case["query"], principal=PRINCIPAL,
        )
        if len(view.visible_route_ids) != size:
            raise ValueError("incomplete scoped source catalog")
        timings = {"original_full_per_endpoint": [], "once_per_detached_tool": []}
        deltas: list[float] = []
        for pair in range(PAIRS_PER_SCALE):
            view.assert_source_unchanged()
            order = (
                ("original_full_per_endpoint", "once_per_detached_tool")
                if pair % 2 == 0 else
                ("once_per_detached_tool", "original_full_per_endpoint")
            )
            comparisons: dict[str, dict[str, tuple[str, str]]] = {}
            for arm in order:
                start = time.perf_counter_ns()
                comparisons[arm] = (
                    _original_visible_fingerprints(view)
                    if arm == "original_full_per_endpoint"
                    else _visible_fingerprints(view)
                )
                elapsed = (time.perf_counter_ns() - start) / 1e6
                if elapsed < 0:
                    raise ValueError("invalid source fingerprint CPU timing")
                timings[arm].append(elapsed)
            view.assert_source_unchanged()
            if (
                comparisons["original_full_per_endpoint"]
                != comparisons["once_per_detached_tool"]
                or set(comparisons["once_per_detached_tool"])
                != set(view.visible_route_ids)
            ):
                raise ValueError("paired source fingerprint mismatch")
            deltas.append(
                timings["once_per_detached_tool"][-1]
                - timings["original_full_per_endpoint"][-1]
            )
        scales[str(size)] = {
            "registered_native_routes": size,
            "source_catalog_sha256": native_sha,
            "paired_source_fingerprint_checks": PAIRS_PER_SCALE,
            "all_paired_fingerprints_exact": True,
            "scans": {
                arm: {
                    "p50_ms": percentile(values, 50),
                    "p95_ms": percentile(values, 95),
                }
                for arm, values in timings.items()
            },
            "paired_delta_new_minus_original": {
                "median_ms": percentile(deltas, 50),
                "optimized_faster_count": sum(delta < 0 for delta in deltas),
            },
        }

    source_revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        capture_output=True, text=True, check=True, timeout=10,
    ).stdout.strip()
    if len(source_revision) != 40 or any(c not in "0123456789abcdef" for c in source_revision):
        raise ValueError("invalid paired scan source revision")
    return {
        "source_revision": source_revision,
        "source_corpus_sha256": digest,
        "surface": "SYNTHETIC_NATIVE_FINGERPRINT_SCAN_E0_DEV_ONLY",
        "independent_agent_e2": False,
        "model_inference_executed": False,
        "exact_source_and_permission_guard_preserved": True,
        "catalog_sizes": list(SIZES),
        "pairs_per_size": PAIRS_PER_SCALE,
        "scales": scales,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = run_fingerprint_scan_ab()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
