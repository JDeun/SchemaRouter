"""B1 E0: 500/5000 mixed-source versioned churn and live-scope oracle audit.

Every indexed result is compared to a separate full source registry scan and
an independently rebuilt canonical graph index. Neither path grants execution
authority, learns a ranking, or supplies independently reviewed publisher gold.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import resource
import time
from typing import Any

from schemarouter import PrincipalContext, SchemaRouter
from schemarouter.concept_graph_retrieval import retrieve_authorized_concept_graph
from schemarouter.errors import PolicyViolationError
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_native_heterogeneous_parity_e0 import (
    ACTOR,
    CASES,
    CATALOG,
    SCENARIOS,
    SOURCE_TYPES,
    build_heterogeneous_fixture,
    configure_heterogeneous_scope,
    original_heterogeneous_oracle,
)

EVIDENCE = "E0_SYNTHETIC_HETEROGENEOUS_NATIVE_JOURNAL_CHURN_NOT_E2"
_ANONYMOUS = PrincipalContext(subject="unprivileged-e0", roles=())


def _sample_summary(samples: list[float]) -> dict[str, float]:
    if not samples:
        raise AssertionError("churn audit has no measured queries")
    ordered = sorted(samples)
    return {
        f"p{percentile}": round(
            ordered[max(0, math.ceil(len(ordered) * percentile / 100) - 1)], 4,
        ) for percentile in (50, 95, 99)
    }


def _checked_query(
    router: SchemaRouter,
    query: str,
    principal: PrincipalContext,
    index: NativeSchemaGraphIndex,
    rebuilt: NativeSchemaGraphIndex,
    *,
    concept_id: str,
    wall_samples: list[float],
    cpu_samples: list[float],
    expected_source: tuple[str, ...] | None = None,
) -> None:
    """Compare exact public, nonexecuting receipts against original source."""
    original = original_heterogeneous_oracle(router, concept_id, principal)
    # A source oracle that consumes the same broken policy as the indexed
    # query is not sufficient by itself: this principal MUST have no grants.
    if principal is _ANONYMOUS and original:
        raise AssertionError("churn unprivileged source oracle unexpectedly grants routes")
    if expected_source is not None and original != expected_source:
        raise AssertionError("churn scope violates independently declared fixture conditions")
    wall_start = time.perf_counter_ns()
    cpu_start = time.process_time_ns()
    actual = retrieve_authorized_concept_graph(
        router, query, principal=principal, catalog=CATALOG,
        index=index, experimental_indexed_direct=True,
    )
    cpu_samples.append((time.process_time_ns() - cpu_start) / 1_000_000)
    wall_samples.append((time.perf_counter_ns() - wall_start) / 1_000_000)
    rebuilt_result = retrieve_authorized_concept_graph(
        router, query, principal=principal, catalog=CATALOG,
        index=rebuilt, experimental_indexed_direct=True,
    )
    if (
        actual.route_ids != original
        or actual.status != ("complete" if original else "no_proven_hit")
        or actual.executable_authority
        or actual.independent_quality_evidence
        or actual.calibrated_no_fit
        or tuple(dict.fromkeys(
            route for item in actual.route_sets for route in item.route_ids
        )) != original
    ):
        raise AssertionError("churn indexed result disagrees with original-source oracle")
    if actual != rebuilt_result:
        raise AssertionError("churn journal index disagrees with full graph rebuild")


def _verify_snapshot_equivalence(
    journal: NativeSchemaGraphIndex, rebuilt: NativeSchemaGraphIndex,
) -> None:
    lhs, rhs = journal.field_index, rebuilt.field_index
    if (
        lhs.registry_ref is not rhs.registry_ref
        or lhs.snapshot_id != rhs.snapshot_id
        or lhs.registry_version != rhs.registry_version
        or lhs.indexed_route_count != rhs.indexed_route_count
        or lhs.postings != rhs.postings
        or lhs.route_fingerprints != rhs.route_fingerprints
        or lhs.route_locations != rhs.route_locations
        or lhs.tool_fingerprints != rhs.tool_fingerprints
        or journal.graph != rebuilt.graph
        or journal.native_root_count != rebuilt.native_root_count
        or journal.native_consumer_count != rebuilt.native_consumer_count
        or journal.edge_consumer_routes != rebuilt.edge_consumer_routes
        or journal.approved_host_roots != rebuilt.approved_host_roots
        or journal._source_contracts != rebuilt._source_contracts
    ):
        raise AssertionError("churn journal source snapshot differs from full rebuild")


def _scope_matrix(
    router: SchemaRouter,
    journal: NativeSchemaGraphIndex,
    rebuilt: NativeSchemaGraphIndex,
    *,
    iterations: int,
    wall_samples: list[float],
    cpu_samples: list[float],
) -> int:
    count = 0
    for scenario in SCENARIOS:
        configure_heterogeneous_scope(router, scenario)
        for principal in (ACTOR, _ANONYMOUS):
            for case in CASES:
                source = router.registry.get(case.tool_name)
                is_eligible = (
                    principal is ACTOR
                    and source.source_type == case.source_type
                    and source.license == CATALOG.concepts[CASES.index(case)].license
                    and not (
                        (scenario == "hidden" and case.source_type == "mcp")
                        or (scenario == "denied" and case.source_type == "openapi")
                        or (scenario == "unavailable" and case.source_type == "optimade")
                    )
                )
                fixture_expected = (case.route_id,) if is_eligible else ()
                for alias in case.aliases:
                    for _ in range(iterations):
                        _checked_query(
                            router, alias, principal, journal, rebuilt,
                            concept_id=case.concept_id,
                            wall_samples=wall_samples, cpu_samples=cpu_samples,
                            expected_source=fixture_expected,
                        )
                        count += 1
    return count


def _same_predicate_health_checks(
    router: SchemaRouter,
    journal: NativeSchemaGraphIndex,
    rebuilt: NativeSchemaGraphIndex,
    *,
    wall_samples: list[float],
    cpu_samples: list[float],
) -> int:
    """Host-owned live health state changes while the predicate ID stays put."""
    configure_heterogeneous_scope(router, "visible")
    blocked: set[str] = set()

    def available(tool: Any, _endpoint: Any) -> bool:
        return tool.key not in blocked

    router.planner.availability_predicate = available
    initial_version = router.registry.version
    count = 0
    for case in CASES:
        for denied in (False, True, False):
            if denied:
                blocked.add(case.tool_name)
            else:
                blocked.discard(case.tool_name)
            if router.planner.availability_predicate is not available:
                raise AssertionError("live health predicate identity changed")
            _checked_query(
                router, case.aliases[0], ACTOR, journal, rebuilt,
                concept_id=case.concept_id,
                wall_samples=wall_samples, cpu_samples=cpu_samples,
            )
            # An oracle/index pair that both leaked the blocked route would
            # evade equality alone; require the expected health transition.
            observed = original_heterogeneous_oracle(router, case.concept_id, ACTOR)
            should_exist = not denied and router.registry.get(case.tool_name).license == (
                CATALOG.concepts[CASES.index(case)].license
            )
            if bool(observed) != should_exist:
                raise AssertionError("live health transition violated original-source contract")
            count += 1
    if router.registry.version != initial_version:
        raise AssertionError("live health scenario unexpectedly mutated source")
    return count


def audit_heterogeneous_churn(
    registered_routes: int, *, iterations: int = 1,
) -> dict[str, Any]:
    """Bounded independent-exhaustive-oracle E0 audit over three snapshots."""
    if type(registered_routes) is not int or registered_routes not in (500, 5000):
        raise ValueError("only preregistered 500/5000 source catalogs allowed")
    if type(iterations) is not int or not 1 <= iterations <= 4:
        raise ValueError("iterations must be a bounded integer between 1 and 4")
    router = build_heterogeneous_fixture(registered_routes)
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    wall_samples: list[float] = []
    cpu_samples: list[float] = []
    count = 0
    health_checks = 0
    versions: set[int] = set()
    snapshot_ids: set[str] = set()
    stale_rejections = 0
    initial_tool = router.registry.get(CASES[0].tool_name)
    for stage in ("initial", "revoked", "restored"):
        if stage != "initial":
            changed = router.registry.get(CASES[0].tool_name)
            changed.license = (
                "revoked-host-reviewed-synthetic" if stage == "revoked"
                else initial_tool.license
            )
            router.registry.register(changed, replace=True)
            configure_heterogeneous_scope(router, "visible")
            try:
                retrieve_authorized_concept_graph(
                    router, CASES[0].aliases[0], principal=ACTOR,
                    catalog=CATALOG, index=index,
                    experimental_indexed_direct=True,
                )
            except PolicyViolationError:
                stale_rejections += 1
            else:
                raise AssertionError("churn stale source index did not fail closed")
            index = NativeSchemaGraphIndex.refresh_from_inmemory_journal(
                index, router.registry,
            )
        rebuilt = NativeSchemaGraphIndex.build(
            NativeSchemaPostingIndex.build(router.registry),
        )
        _verify_snapshot_equivalence(index, rebuilt)
        versions.add(router.registry.version)
        snapshot_ids.add(index.field_index.snapshot_id)
        configure_heterogeneous_scope(router, "visible")
        current = original_heterogeneous_oracle(router, CASES[0].concept_id, ACTOR)
        should_find = stage != "revoked"
        if bool(current) != should_find:
            raise AssertionError("churn original-source revocation/restoration drift")
        count += _scope_matrix(
            router, index, rebuilt, iterations=iterations,
            wall_samples=wall_samples, cpu_samples=cpu_samples,
        )
        health_checks += _same_predicate_health_checks(
            router, index, rebuilt,
            wall_samples=wall_samples, cpu_samples=cpu_samples,
        )
    return {
        "evidence_tier": EVIDENCE,
        "independent_e2_qualified": False,
        "source_gold_verified": False,
        "default_routing_changed": False,
        "journal_and_full_rebuild_exact_parity": True,
        "source_authorization_oracle_checked": True,
        "registered_source_routes": registered_routes,
        "source_type_count": len(SOURCE_TYPES),
        "source_snapshot_count": len(snapshot_ids),
        "registry_version_count": len(versions),
        "stale_index_rejections": stale_rejections,
        "revoked_source_excluded": True,
        "restored_source_reincluded": True,
        "policy_and_principal_checks": count,
        "same_predicate_health_flip_checks": health_checks,
        "paired_checks": count,
        "query_wall_ms": _sample_summary(wall_samples),
        "query_process_cpu_ms": _sample_summary(cpu_samples),
        "peak_process_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "python_version": platform.python_version(),
        "limitations": [
            "Developer-authored native-like mixed sources; not provider imports",
            "No independently reviewed publisher source/permission/gold E2",
            "No learned ranking, model tokens, agent or real source I/O",
            "No production schema-byte/tail-latency/churn-throughput claim",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registered-routes", type=int, choices=(500, 5000), required=True)
    parser.add_argument("--iterations", type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(
        audit_heterogeneous_churn(args.registered_routes, iterations=args.iterations),
        ensure_ascii=False, sort_keys=True, allow_nan=False,
    ))


if __name__ == "__main__":
    main()
