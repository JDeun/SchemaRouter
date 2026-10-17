"""True paired, same-run CPU DEV latency probe: legacy reread vs scoped reuse.

Never a release/SLA/E2 qualification. The measured source is synthetic
and 84 previously disclosed tasks; no native host invocation is performed.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any

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
from scripts.research_authorized_fixed5_decision_bridge import (
    AuthorizedFixed5DecisionSelector,
)

REQUIRED_NATIVE_ROUTES = 500
PAIR = ("legacy_authorized_reread", "request_local_authorized_reuse")


def paired_source_reuse_dev(
    corpus: dict[str, Any],
    digest: str,
    backend: Any,
    *,
    case_limit: int | None = None,
) -> dict[str, Any]:
    """Pair true unchanged fixed-K5 selectors on identical scoped source.

    Alternating the A/B order limits one-sided warm-cache advantages. It
    cannot remove runner scheduling noise or establish a production SLA.
    """
    trusted, trusted_digest = load_development_corpus(CORPUS)
    if corpus != trusted or digest != trusted_digest:
        raise ValueError("frozen public synthetic DEV source hash/contents drift")
    if case_limit is not None and (
        type(case_limit) is not int or not 1 <= case_limit <= 84
    ):
        raise ValueError("invalid paired smoke task bound")
    router, catalog_sha = build_scaled_authorized_router(
        corpus, REQUIRED_NATIVE_ROUTES,
    )
    elapsed: dict[str, list[float]] = {arm: [] for arm in PAIR}
    paired_deltas: list[float] = []
    for index, case in enumerate(corpus["cases"][:case_limit]):
        view = capture_authorized_agent_tool_surface(
            router, case["query"], principal=PRINCIPAL,
        )
        if len(view.visible_route_ids) != REQUIRED_NATIVE_ROUTES:
            raise ValueError("incomplete authorized native 500 source capture")
        selectors = {
            "legacy_authorized_reread": AuthorizedFixed5DecisionSelector(
                view, backend,
                max_model_input_bytes=STRESS_MODEL_INPUT_BUDGET_BYTES,
                reuse_authorized_source=False,
            ),
            "request_local_authorized_reuse": AuthorizedFixed5DecisionSelector(
                view, backend,
                max_model_input_bytes=STRESS_MODEL_INPUT_BUDGET_BYTES,
                reuse_authorized_source=True,
            ),
        }
        # Consistent alternating A/B ordering. Both still perform live model
        # decisions on the same query; no task gold enters the selector.
        order = PAIR if index % 2 == 0 else PAIR[::-1]
        choices: dict[str, tuple[str, ...]] = {}
        for arm in order:
            selector = selectors[arm]
            started = time.perf_counter_ns()
            ranked = selector(view.original_query, view.visible_route_ids)
            elapsed_ms = (time.perf_counter_ns() - started) / 1e6
            if (
                type(elapsed_ms) is not float
                or not math.isfinite(elapsed_ms) or elapsed_ms < 0
                or len(ranked) != 5 or len(set(ranked)) != 5
                or not set(ranked).issubset(view.visible_route_ids)
            ):
                raise ValueError("invalid or unauthorized paired K5 selection")
            elapsed[arm].append(elapsed_ms)
            choices[arm] = tuple(ranked)
        if (
            choices[PAIR[0]] != choices[PAIR[1]]
            or selectors[PAIR[0]].last_status != selectors[PAIR[1]].last_status
            or selectors[PAIR[0]].last_model_input_bytes
            != selectors[PAIR[1]].last_model_input_bytes
        ):
            raise ValueError("legacy/reuse source retrieval decision drift")
        view.assert_source_unchanged()
        paired_deltas.append(elapsed[PAIR[1]][-1] - elapsed[PAIR[0]][-1])

    summaries = {
        arm: {
            "p50_ms": percentile(samples, 50),
            "p95_ms": percentile(samples, 95),
            "p99_ms": percentile(samples, 99),
            "mean_ms": statistics.fmean(samples),
        }
        for arm, samples in elapsed.items()
    }
    delta = {
        "median_reuse_minus_legacy_ms": statistics.median(paired_deltas),
        "mean_reuse_minus_legacy_ms": statistics.fmean(paired_deltas),
        "reuse_faster_count": sum(value < 0 for value in paired_deltas),
        "equal_count": sum(value == 0 for value in paired_deltas),
        "legacy_faster_count": sum(value > 0 for value in paired_deltas),
    }
    return {
        "schema_version": 1,
        "issue": 1477,
        "evidence_tier": "UNATTESTED_BACKEND_PAIRED_LATENCY_DEV_ONLY",
        "real_model_routing_measured": False,
        "independent_e2_qualified": False,
        "agent_task_success_measured": False,
        "calibrated_no_fit": False,
        "publication_gate_passed": False,
        "product_default_promoted": False,
        "source_corpus_sha256": digest,
        "source_catalog_sha256": catalog_sha,
        "catalog_size": REQUIRED_NATIVE_ROUTES,
        "fixed_k": 5,
        "all_paired_decisions_identical": True,
        "full_84_case_evaluation": case_limit is None,
        "case_count": len(paired_deltas),
        "arms": list(PAIR),
        "latency_summary": summaries if case_limit is None else None,
        "paired_delta_summary": delta if case_limit is None else None,
        "limitations": (
            "Warm model passage cache is shared across alternating-order arms. "
            "No raw queries/gold or principal data exported. The p95s are "
            "descriptive on one Actions runner; source capture excluded. "
            "Templated synthetic catalog is not 500 native external providers."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    corpus, digest = load_development_corpus(CORPUS)
    backend, runtime = real_cpu_backend()
    report = paired_source_reuse_dev(corpus, digest, backend)
    if not report["full_84_case_evaluation"] or not report["all_paired_decisions_identical"]:
        raise ValueError("cannot publish incomplete paired source A/B")
    report["evidence_tier"] = "REAL_E5_CPU_PAIRED_LATENCY_DEV_ONLY"
    report["real_model_routing_measured"] = True
    report["model_runtime"] = runtime
    report["source_revision"] = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        check=True, capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    if len(report["source_revision"]) != 40:
        raise ValueError("unable to pin run source revision")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "evidence_tier": report["evidence_tier"],
        "source_revision": report["source_revision"],
        "latency_summary": report["latency_summary"],
        "paired_delta_summary": report["paired_delta_summary"],
    }, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
