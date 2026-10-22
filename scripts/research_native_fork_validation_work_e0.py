"""Count repeated native fork validation work; synthetic E0 diagnostic only.

Wrap functions during a single query, never short-circuit them or modify the
source-typed graph, live authorization, availability, field scope or K5.
Counters expose ONLY aggregate code-path events, not private route IDs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from schemarouter import native_fork_index, native_graph_index
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    ALIASES,
    GROUP,
    _decoy_leaf,
    build_fixture,
)

STUDY = "G5_DENSE_VALIDATION_WORK_E0_NOT_E2"
PREFIX = "dense_fork_status_"


def count_once(
    graph: NativeSchemaGraphIndex,
    router: Any,
    *,
    wanted_status: str,
    wanted_forks: int,
) -> dict[str, Any]:
    counters = {
        "private_arm_query_invocations": 0,
        "private_arm_over_cap_responses": 0,
        "graph_required_input_inspections": 0,
        "pair_required_input_inspections": 0,
        "pair_root_flat_contract_inspections": 0,
    }
    orig_lookup = NativeSchemaGraphIndex._lookup_native_paths
    orig_graph_inputs = native_graph_index._native_required_inputs
    orig_pair_inputs = native_fork_index._native_required_inputs
    orig_pair_flat = native_fork_index._flat_same_record_source_contract

    def lookup_count(self: NativeSchemaGraphIndex, *args: Any, **kwargs: Any) -> Any:
        if kwargs.get("_fork_arm_internal") is True:
            counters["private_arm_query_invocations"] += 1
        result = orig_lookup(self, *args, **kwargs)
        if kwargs.get("_fork_arm_internal") is True and result.status == "over_k_unranked":
            counters["private_arm_over_cap_responses"] += 1
        return result

    def graph_inputs_count(*args: Any, **kwargs: Any) -> Any:
        counters["graph_required_input_inspections"] += 1
        return orig_graph_inputs(*args, **kwargs)

    def pair_inputs_count(*args: Any, **kwargs: Any) -> Any:
        counters["pair_required_input_inspections"] += 1
        return orig_pair_inputs(*args, **kwargs)

    def pair_flat_count(*args: Any, **kwargs: Any) -> Any:
        counters["pair_root_flat_contract_inspections"] += 1
        return orig_pair_flat(*args, **kwargs)

    with (
        patch.object(NativeSchemaGraphIndex, "_lookup_native_paths", lookup_count),
        patch.object(native_graph_index, "_native_required_inputs", graph_inputs_count),
        patch.object(native_fork_index, "_native_required_inputs", pair_inputs_count),
        patch.object(native_fork_index, "_flat_same_record_source_contract", pair_flat_count),
    ):
        observed = graph.lookup_shared_root_forks(
            router, ALIASES[0], group=GROUP, principal=ACTOR,
        )
    if (
        observed.status != wanted_status
        or observed.qualified_fork_count != wanted_forks
        or observed.requested_k != 5
        or observed.executable_authority
        or observed.independent_quality_evidence
        or (observed.candidates != () if wanted_status == "over_k_unranked"
            else len(observed.candidates) != 1)
    ):
        raise AssertionError("original source fork safety changed during instrumentation")
    return {
        "status": observed.status,
        "qualified_forks": observed.qualified_fork_count,
        "aggregate_validation_events": counters,
    }


def profile(*, registered_routes: int, extra_status: int) -> dict[str, Any]:
    if type(registered_routes) is not int or registered_routes not in (500, 5000):
        raise ValueError("fixed native source registry size required")
    if type(extra_status) is not int or extra_status not in (33, 64):
        raise ValueError("fixed dense consumer cohort required")
    router = build_fixture(registered_routes)
    for i in range(extra_status):
        router.add_tool(_decoy_leaf(
            f"{PREFIX}{i}", "crm.fork_status", "status",
        ))
    graph = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    if graph.field_index.indexed_route_count != registered_routes + extra_status:
        raise AssertionError("original native registry drift")
    dense = count_once(
        graph, router,
        wanted_status="over_k_unranked", wanted_forks=extra_status + 1,
    )
    router.planner.availability_predicate = (
        lambda tool, _ep: not tool.key.startswith(PREFIX)
    )
    revoked = count_once(
        graph, router, wanted_status="complete", wanted_forks=1,
    )
    for alias in ALIASES:
        result = graph.lookup_shared_root_forks(
            router, alias, group=GROUP, principal=ACTOR,
        )
        if (result.status != "complete" or result.qualified_fork_count != 1
                or len(result.candidates) != 1):
            raise AssertionError("same-index live-health/source authorization changed")
    return {
        "study": STUDY,
        "evidence_tier": "E0_DEVELOPER_SOURCE_NATIVE_ONLY",
        "registered_native_routes": graph.field_index.indexed_route_count,
        "extra_same_key_status_consumers": extra_status,
        "strict_public_k": 5,
        "dense": dense,
        "extras_unavailable": revoked,
        "same_index_live_health_revalidated": True,
        "en_ko_ja_host_alias_parity": True,
        "source_registry_oracle_not_in_query": True,
        "model_selected_tools": False,
        "provider_http_calls": 0,
        "independent_agent_e2": False,
        "product_changed": False,
        "production_latency_qualified": False,
        "limitations": [
            "Function-count instrumentation increases CPU work; NOT latency benchmark",
            "Developer-authored single-source one-hop flat scalar fixture only",
            "Only aggregate invocation counts; no consumer, source, ID or principal logs",
            "These counters do not prove which operation dominates elapsed latency",
            "No independent publisher gold, execution, agent E2 or production SLO",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registered-routes", type=int, required=True)
    parser.add_argument("--extra-status", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    options = parser.parse_args()
    report = profile(
        registered_routes=options.registered_routes,
        extra_status=options.extra_status,
    )
    options.out.parent.mkdir(parents=True, exist_ok=True)
    options.out.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "study": report["study"],
        "registered_native_routes": report["registered_native_routes"],
        "extra_same_key_status_consumers": report["extra_same_key_status_consumers"],
        "dense_aggregate": report["dense"]["aggregate_validation_events"],
        "revoked_aggregate": report["extras_unavailable"]["aggregate_validation_events"],
        "independent_agent_e2": False,
    }, allow_nan=False))


if __name__ == "__main__":
    main()
