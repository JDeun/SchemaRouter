"""#1560 E0 paired direct posting K5 probe; synthetic query-encoded routes only.

This demonstrates a real DecisionBackend invocation, the source-index K5
boundary and per-stage process CPU. The query includes the expected route
name, so measured exposure is NOT relevance quality or independent E2.
"""
from __future__ import annotations

import argparse
import json
import platform
import resource
import time
from typing import Any

from schemarouter.concept_retrieval import resolve_native_concepts
from schemarouter.decisions import CallableDecisionBackend
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_indexed_concept_direct_parity_e0 import (
    ACTOR,
    ALIASES,
    CATALOG,
    DIRECT_ROUTES,
    _metrics,
    build_fixture,
    configure_scope,
    original_source_direct_oracle,
)
from scripts.research_indexed_decision_backend_ranker_e0 import (
    ResearchAuthorizedIndexedDecisionRanker,
)

EVIDENCE_TIER = "E0_QUERY_CONTAINS_GOLD_ROUTE_SYNTHETIC_NOT_INDEPENDENT_E2"


def benchmark(*, registered_routes: int, iterations: int = 3) -> dict[str, Any]:
    if type(registered_routes) is not int or registered_routes not in (500, 5000):
        raise ValueError("only original preregistered 500/5000 catalogs allowed")
    if type(iterations) is not int or not 3 <= iterations <= 12:
        raise ValueError("benchmark requires bounded 3-12 paired iterations")
    router = build_fixture(registered_routes)
    started = time.perf_counter_ns()
    index = NativeSchemaPostingIndex.build(router.registry)
    build_wall_ms = (time.perf_counter_ns() - started) / 1_000_000
    assert index.indexed_route_count == registered_routes

    def direct_lookup(query, *, research_ranker=None):
        # The independent source oracle checks INPUT-FREE endpoints; a raw
        # semantic posting hit may be a consumer requiring unavailable args.
        # Filter before K5, never by trimming an already disclosed menu.
        group = resolve_native_concepts(query, catalog=CATALOG).field_group
        return index.lookup(
            router, query, principal=ACTOR, group=group,
            input_free_only=True, _research_ranker=research_ranker,
        )

    configure_scope(router, "six")
    authorized = original_source_direct_oracle(router)
    assert authorized == DIRECT_ROUTES

    request_bytes: list[int] = []
    model_calls = 0

    def deterministic_query_route_decision(request):
        nonlocal model_calls
        model_calls += 1
        request_bytes.append(len(request.model_dump_json().encode("utf-8")))
        # The baseline deliberately names the target route in the input query.
        # This is a functional K5-overflow demonstration, NOT a learned model.
        target = request.query.rsplit(" ", 1)[-1] + ".read"
        matches = [o for o in request.options if o.label == target]
        if len(matches) != 1:
            return {"abstained": True}
        ordered = matches + [o for o in request.options if o.label != target]
        return {"selections": [
            {"option_id": option.id} for option in ordered[:5]
        ]}

    ranker = ResearchAuthorizedIndexedDecisionRanker(
        CallableDecisionBackend(deterministic_query_route_decision),
    )
    default_wall, default_cpu = [], []
    ranked_wall, ranked_cpu = [], []
    default_hits = 0
    fixed_first5_hits = 0
    ranked_hits = 0
    cases = []
    # Fixed preregistered matrix, not optimized or derived from measured scores.
    for alias in ALIASES:
        for expected in DIRECT_ROUTES:
            query = f"{alias} {expected.split('.')[0]}"
            before = direct_lookup(query)
            after = direct_lookup(query, research_ranker=ranker)
            if (
                before.status != "over_k_unranked"
                or before.candidates or before.qualified_count != 6
                or after.status != "ranked_unverified"
                or after.qualified_count != 6
                or len(after.candidates) != 5
            ):
                raise AssertionError("direct source index ranking contract changed")
            chosen = tuple(item.route_id for item in after.candidates)
            if len(set(chosen)) != 5 or not set(chosen) <= set(authorized):
                raise AssertionError("research backend exposed invalid route")
            default_hits += int(expected in (c.route_id for c in before.candidates))
            fixed_first5_hits += int(expected in authorized[:5])
            ranked_hits += int(expected in chosen)
            cases.append({
                "language_query": alias,
                "synthetic_target": expected,
                "default_status": before.status,
                "ranked_status": after.status,
                "ranked_target_position": (
                    chosen.index(expected) + 1 if expected in chosen else None
                ),
            })
            # Same index, same source scope, same query and principal in each
            # timed pair; no full registry scan or invented agent execution.
            for _ in range(iterations):
                start_wall = time.perf_counter_ns()
                start_cpu = time.process_time_ns()
                a = direct_lookup(query)
                default_cpu.append(
                    (time.process_time_ns() - start_cpu) / 1_000_000
                )
                default_wall.append(
                    (time.perf_counter_ns() - start_wall) / 1_000_000
                )
                start_wall = time.perf_counter_ns()
                start_cpu = time.process_time_ns()
                b = direct_lookup(query, research_ranker=ranker)
                ranked_cpu.append(
                    (time.process_time_ns() - start_cpu) / 1_000_000
                )
                ranked_wall.append(
                    (time.perf_counter_ns() - start_wall) / 1_000_000
                )
                if a != before or b != after:
                    raise AssertionError("paired lookup changed during measurement")

    # Policy/scope/availability test cohorts: no model inference when <=K.
    safety = {}
    for scenario, count in (("one", 1), ("none", 0), ("hidden", 0), ("health", 1)):
        configure_scope(router, scenario)
        assert len(original_source_direct_oracle(router)) == count
        calls_before = model_calls
        status = direct_lookup(ALIASES[0], research_ranker=ranker)
        if (
            status.qualified_count != count
            or len(status.candidates) != count
            or status.experimental_ranked
            or model_calls != calls_before
        ):
            raise AssertionError("ranker called for unauthorized/incomplete source")
        safety[scenario] = status.status

    if ranked_hits != len(cases) or fixed_first5_hits >= ranked_hits:
        raise AssertionError("synthetic query-encoded expected exposure changed")
    return {
        "evidence_tier": EVIDENCE_TIER,
        "independent_quality_evidence": False,
        "independent_e2_qualified": False,
        "real_model_or_provider_called": False,
        "query_encodes_expected_route": True,
        "new_default_routing": False,
        "registered_source_routes": registered_routes,
        "index_snapshot_sha256": index.snapshot_id,
        "strict_k": 5,
        "ranker_candidate_cap": 32,
        "index_build_wall_ms": round(build_wall_ms, 4),
        "queries": len(cases),
        "iterations_per_query": iterations,
        "source_scoped_ranker_calls": model_calls,
        "max_model_input_bytes": max(request_bytes),
        "synthetic_target_exposure": {
            "default_abstain_hits": default_hits,
            "fixed_first5_hits": fixed_first5_hits,
            "decision_ranker_hits": ranked_hits,
            "denominator": len(cases),
        },
        "default": _metrics(default_wall, default_cpu),
        "decision_ranker": _metrics(ranked_wall, ranked_cpu),
        "safety_statuses": safety,
        "python": platform.python_version(),
        "peak_process_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "limitations": (
            "Target route appears literally in each synthetic query; no model "
            "generalization or independent ground truth, live provider, "
            "agent completion or released performance SLO."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registered-routes", type=int, required=True, choices=(500, 5000),
    )
    parser.add_argument("--iterations", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(
        benchmark(
            registered_routes=args.registered_routes,
            iterations=args.iterations,
        ),
        ensure_ascii=False, sort_keys=True, allow_nan=False,
    ))


if __name__ == "__main__":
    main()
