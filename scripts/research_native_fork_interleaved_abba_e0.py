"""Same-index, alternating-order G5 fork CPU A/B research: synthetic E0 ONLY.

Compare the previous bounded native fork collector with index-only pre-shard
scheduling. Both modes use exactly the same source registry, graph, principal,
current policy, health callback and original authorization implementation.
No benchmark gold participates in lookups; no raw path identities are logged.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from statistics import fmean
from typing import Any
from unittest.mock import patch

from schemarouter import native_fork_index
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    ALIASES,
    GROUP,
    _decoy_leaf,
    build_fixture,
    percentile,
)

STUDY = "G5_NATIVE_DENSE_SAME_INDEX_ABBA_CPU_E0_NOT_E2"
PREFIX = "abba_fork_status_"


def run_interleaved_abba(
    *, registered_routes: int, extra_status: int, rounds: int = 10,
) -> dict[str, Any]:
    """ABBA/BAAB balanced ordering; twice each mode per round and condition."""
    if type(registered_routes) is not int or registered_routes not in (500, 5000):
        raise ValueError("bounded native source catalog must be 500/5000")
    if type(extra_status) is not int or extra_status not in (33, 64):
        raise ValueError("bounded same-root status fanout must be 33/64")
    if type(rounds) is not int or not 4 <= rounds <= 20:
        raise ValueError("bounded balanced ABBA rounds must be 4..20")

    router = build_fixture(registered_routes)
    for n in range(extra_status):
        router.add_tool(_decoy_leaf(
            f"{PREFIX}{n}", "crm.fork_status", "status",
        ))
    graph = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    if graph.field_index.indexed_route_count != registered_routes + extra_status:
        raise AssertionError("original source-native catalog registration drift")

    def lookup(alias: str, optimized: bool) -> Any:
        # The constant ONLY schedules already-indexed private targets. All
        # source permissions, types, current health and twice-rechecked
        # completed arms are computed by the unchanged native fork path.
        with patch.object(
            native_fork_index, "MAX_FORK_PREFORK_TARGETS",
            128 if optimized else 0,
        ):
            return graph.lookup_shared_root_forks(
                router, alias, group=GROUP, principal=ACTOR,
            )

    def verify(condition: str) -> None:
        expected = (
            ("over_k_unranked", extra_status + 1, 0)
            if condition == "dense"
            else ("complete", 1, 1)
        )
        for alias in ALIASES:
            original = lookup(alias, False)
            current = lookup(alias, True)
            if (
                original != current
                or (original.status, original.qualified_fork_count,
                    len(original.candidates)) != expected
                or original.requested_k != 5
                or original.executable_authority
                or original.independent_quality_evidence
            ):
                raise AssertionError("native source K5/authorization A-B mismatch")

    def measured(condition: str) -> dict[str, Any]:
        verify(condition)
        # Identical warmup budget on one pinned source graph.
        for _ in range(2):
            lookup(ALIASES[0], False)
            lookup(ALIASES[0], True)
        observations: dict[str, dict[str, list[float]]] = {
            name: {"wall_ms": [], "cpu_ms": []}
            for name in ("baseline", "indexed_preshard")
        }
        for iteration in range(rounds):
            # ABBA on even rounds, BAAB on odd rounds mitigates monotonic
            # CPU temperature/runner load drift; not a randomized trial.
            order = (
                (False, True, True, False)
                if iteration % 2 == 0
                else (True, False, False, True)
            )
            for optimized in order:
                wall_start = time.perf_counter_ns()
                cpu_start = time.process_time_ns()
                observed = lookup(ALIASES[0], optimized)
                cpu_ms = (time.process_time_ns() - cpu_start) / 1_000_000
                wall_ms = (time.perf_counter_ns() - wall_start) / 1_000_000
                if (
                    observed.status != (
                        "over_k_unranked" if condition == "dense" else "complete"
                    )
                    or observed.qualified_fork_count != (
                        extra_status + 1 if condition == "dense" else 1
                    )
                    or (
                        observed.candidates != ()
                        if condition == "dense"
                        else len(observed.candidates) != 1
                    )
                ):
                    raise AssertionError("source-native observed output drift during A-B")
                label = "indexed_preshard" if optimized else "baseline"
                observations[label]["cpu_ms"].append(cpu_ms)
                observations[label]["wall_ms"].append(wall_ms)

        def summarize(nums: list[float]) -> dict[str, float]:
            if len(nums) != 2 * rounds:
                raise AssertionError("unbalanced ABBA sample count")
            return {
                "p50": round(percentile(nums, 50), 4),
                "p95": round(percentile(nums, 95), 4),
                "p99": round(percentile(nums, 99), 4),
                "mean": round(fmean(nums), 4),
            }

        summarized = {
            name: {
                metric: summarize(observations[name][metric])
                for metric in ("wall_ms", "cpu_ms")
            }
            for name in ("baseline", "indexed_preshard")
        }
        return {
            "condition": condition,
            "expected_qualified_forks": extra_status + 1
            if condition == "dense" else 1,
            "samples_per_mode": rounds * 2,
            "order": "ALTERNATING_ABBA_BAAB",
            "baseline": summarized["baseline"],
            "indexed_preshard": summarized["indexed_preshard"],
            "wall_p95_optimized_to_baseline_ratio": round(
                summarized["indexed_preshard"]["wall_ms"]["p95"]
                / max(summarized["baseline"]["wall_ms"]["p95"], 1e-9),
                4,
            ),
        }

    dense = measured("dense")
    router.planner.availability_predicate = (
        lambda tool, _endpoint: not tool.key.startswith(PREFIX)
    )
    revoked = measured("revoked")
    return {
        "study": STUDY,
        "evidence_tier": "E0_DEVELOPER_SOURCE_NATIVE_ONLY",
        "native_registered_routes": graph.field_index.indexed_route_count,
        "base_registered_routes": registered_routes,
        "extra_same_source_status_consumers": extra_status,
        "strict_public_k": 5,
        "same_graph_same_principal_same_policy": True,
        "source_authorization_still_checked_each_query": True,
        "en_ko_ja_exact_alias_parity": True,
        "public_over_k_reveals_no_candidates": True,
        "rounds": rounds,
        "dense": dense,
        "revoked_same_index": revoked,
        "no_product_code_changed": True,
        "no_source_http_or_agent_execution": True,
        "independent_publisher_gold": False,
        "independent_agent_e2": False,
        "production_slo_qualified": False,
        "limitations": [
            "ABBA/BAAB reduces run-order confounding but is not randomized",
            "Developer-authored flat scalar native source contracts only",
            "One ephemeral GitHub runner per job; no controlled hardware or SLO",
            "Same index and principal but synthetic health updates only between arms",
            "No learned Top5 ranker, independent publisher gold or external agent E2",
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--registered-routes", type=int, required=True)
    p.add_argument("--extra-status", type=int, required=True)
    p.add_argument("--rounds", type=int, default=10)
    p.add_argument("--out", type=Path, required=True)
    options = p.parse_args()
    report = run_interleaved_abba(
        registered_routes=options.registered_routes,
        extra_status=options.extra_status,
        rounds=options.rounds,
    )
    options.out.parent.mkdir(parents=True, exist_ok=True)
    options.out.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "study": report["study"],
        "native_registered_routes": report["native_registered_routes"],
        "dense_baseline_p95": report["dense"]["baseline"]["wall_ms"]["p95"],
        "dense_indexed_preshard_p95":
            report["dense"]["indexed_preshard"]["wall_ms"]["p95"],
        "revoked_baseline_p95":
            report["revoked_same_index"]["baseline"]["wall_ms"]["p95"],
        "revoked_indexed_preshard_p95":
            report["revoked_same_index"]["indexed_preshard"]["wall_ms"]["p95"],
        "production_slo_qualified": False,
    }, allow_nan=False))


if __name__ == "__main__":
    main()
