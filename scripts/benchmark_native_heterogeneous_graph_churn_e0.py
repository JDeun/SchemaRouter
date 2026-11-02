"""B1 E0 mixed-source *nonempty* G5 1/2-hop journal churn experiment.

Uses the production canonical graph and posting index, source-owned changed-key
receipts, and live policy/health scopes. All witnesses are synthetic, host
declared and nonexecuting: this is not independent provider/publisher E2 gold.
"""

from __future__ import annotations

import argparse
import json
import platform
import resource
import time
from typing import Any

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.errors import PolicyViolationError
from schemarouter.field_group_retrieval import NativeDeclaredFieldGroup
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_native_heterogeneous_churn_e0 import (
    _sample_summary,
    _verify_snapshot_equivalence,
)
from scripts.benchmark_native_heterogeneous_parity_e0 import (
    ACTOR,
    SOURCE_TYPES,
    build_heterogeneous_fixture,
)

EVIDENCE = "E0_SYNTHETIC_MIXED_SOURCE_NONEMPTY_G5_JOURNAL_CHURN_NOT_E2"
ROOT, MIDDLE, TARGET, DIRECT = (
    f"unrelated_{i:05d}.read" for i in range(4)
)
ANONYMOUS = PrincipalContext(subject="no-grant-e0", roles=())
ALIASES = ("linked account status", "연결된 계정 상태", "連携アカウント状態")
DIRECT_ALIASES = ("account display status", "계정 표시 상태", "アカウント表示状態")
TWO_HOP_GROUP = NativeDeclaredFieldGroup(
    aliases=ALIASES,
    required_fields=(CapabilityFieldContract(
        semantic_id="bench.linked_status", json_schema={"type": "string"},
    ),),
    source_type="optimade", license="host-reviewed-synthetic",
)
ONE_HOP_GROUP = NativeDeclaredFieldGroup(
    aliases=DIRECT_ALIASES,
    required_fields=(CapabilityFieldContract(
        semantic_id="bench.direct_status", json_schema={"type": "string"},
    ),),
    source_type="custom", license="host-reviewed-synthetic",
)
EXPECTED_EDGES = (
    (ROOT, MIDDLE), (ROOT, DIRECT), (MIDDLE, TARGET),
)
STAGES = (
    "initial", "middle_unbound", "middle_restored", "root_unbound", "root_restored",
)
STAGE_EDGES: dict[str, tuple[tuple[str, str], ...]] = {
    "initial": EXPECTED_EDGES,
    "middle_unbound": EXPECTED_EDGES[:2],
    "middle_restored": EXPECTED_EDGES,
    "root_unbound": EXPECTED_EDGES[2:],
    "root_restored": EXPECTED_EDGES,
}
SCOPES = (
    "visible", "hidden_root", "hidden_middle", "denied_middle",
    "denied_direct", "unavailable_root",
)


def _native_tool(
    key: str, source_type: str, *,
    output_name: str, output_semantic: str, identifier: bool,
    input_name: str | None = None, input_semantic: str | None = None,
) -> ToolSpec:
    parameters = ([ParameterSpec(
        name=input_name, required=True, semantic_id=input_semantic,
        json_schema={"type": "string"},
    )] if input_name is not None else [])
    return ToolSpec(
        name=key, source_type=source_type, license="host-reviewed-synthetic",
        endpoints=[EndpointSpec(
            name="read", read_only=True, parameters=parameters,
            input_schema=({
                "type": "object", "properties": {input_name: {"type": "string"}},
                "required": [input_name], "additionalProperties": False,
            } if input_name is not None else {}),
            output_fields=[FieldSpec(
                name=output_name, semantic_id=output_semantic,
                identifier=identifier, json_schema={"type": "string"},
            )],
        )],
    )


def _graph_source_fixture(registered_routes: int) -> SchemaRouter:
    """Replace four existing routes, maintaining exactly 500/5000 mixed tools."""
    router = build_heterogeneous_fixture(registered_routes)
    nodes = (
        _native_tool("unrelated_00000", "openapi", output_name="contact_id",
                     output_semantic="bench.contact_id", identifier=True),
        _native_tool("unrelated_00001", "mcp", output_name="case_id",
                     output_semantic="bench.case_id", identifier=True,
                     input_name="contact_id", input_semantic="bench.contact_id"),
        _native_tool("unrelated_00002", "optimade", output_name="status",
                     output_semantic="bench.linked_status", identifier=False,
                     input_name="case_id", input_semantic="bench.case_id"),
        _native_tool("unrelated_00003", "custom", output_name="status",
                     output_semantic="bench.direct_status", identifier=False,
                     input_name="contact_id", input_semantic="bench.contact_id"),
    )
    for tool in nodes:
        router.registry.register(tool, replace=True)
    if len(router.registry.tools()) != registered_routes:
        raise AssertionError("G5 synthetic native source route count drift")
    return router


def _structural_witness(router: SchemaRouter) -> tuple[tuple[str, str], ...]:
    """Independent four-tool source check, without graph builder/edge updater.

    These deliberately bounded expectations are *not* independent publisher
    gold. They catch the graph index and the full rebuild sharing a bad edge.
    """
    pairs: list[tuple[str, str]] = []
    for producer, consumer in EXPECTED_EDGES:
        producer_tool = router.registry.get(producer.split(".")[0])
        consumer_tool = router.registry.get(consumer.split(".")[0])
        source = producer_tool.endpoint("read")
        target = consumer_tool.endpoint("read")
        if not (
            producer_tool.source_type and producer_tool.license
            and consumer_tool.source_type and consumer_tool.license
            and source.read_only is True and target.read_only is True
            and not source.destructive and not target.destructive
            and len(target.parameters) == 1
            and target.parameters[0].required is True
            and target.input_schema.get("additionalProperties") is False
            and target.input_schema.get("required") == [target.parameters[0].name]
        ):
            continue
        param = target.parameters[0]
        matching = [field for field in source.output_fields if (
            field.identifier is True and field.semantic_id == param.semantic_id
            and field.json_schema == param.json_schema == {"type": "string"}
        )]
        if len(matching) == 1:
            pairs.append((producer, consumer))
    return tuple(pairs)


def _scope(router: SchemaRouter, scenario: str) -> None:
    if scenario not in SCOPES:
        raise ValueError("unknown G5 source scope")
    deny = {
        "denied_middle": MIDDLE,
        "denied_direct": DIRECT,
    }.get(scenario)
    hide = {
        "hidden_root": (ROOT, "contact_id"),
        "hidden_middle": (MIDDLE, "case_id"),
    }.get(scenario)
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny",
        rules=tuple([AuthorizationRule(
            effect="deny", operation=deny, roles_any=("reader",),
        )] if deny else []) + (AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
        data_rules=(DataScopeRule(
            operation=hide[0], hidden_fields=(hide[1],),
            roles_any=("reader",),
        ),) if hide else (),
    )
    router.planner.availability_predicate = (
        (lambda tool, _ep: tool.key != ROOT.split(".")[0])
        if scenario == "unavailable_root" else None
    )


def _source_path_oracle(
    router: SchemaRouter, principal: PrincipalContext,
    stage: str, scenario: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Author-owned fixed path matrix, additionally pinned to source-only edges."""
    if _structural_witness(router) != STAGE_EDGES[stage]:
        raise AssertionError("G5 source-native structural contract drift")
    if principal is ANONYMOUS:
        return (), ()
    direct = (ROOT, DIRECT) if (
        (ROOT, DIRECT) in STAGE_EDGES[stage]
        and scenario not in ("hidden_root", "denied_direct", "unavailable_root")
    ) else ()
    two = (ROOT, MIDDLE, TARGET) if (
        (ROOT, MIDDLE) in STAGE_EDGES[stage]
        and (MIDDLE, TARGET) in STAGE_EDGES[stage]
        and scenario not in (
            "hidden_root", "hidden_middle", "denied_middle", "unavailable_root",
        )
    ) else ()
    return direct, two


def _assert_paths(
    router: SchemaRouter, index: NativeSchemaGraphIndex,
    rebuilt: NativeSchemaGraphIndex, *, principal: PrincipalContext,
    stage: str, scenario: str, alias_no: int,
    wall_samples: list[float], cpu_samples: list[float],
) -> None:
    expected_one, expected_two = _source_path_oracle(router, principal, stage, scenario)
    for is_two, aliases, group, expected in (
        (False, DIRECT_ALIASES, ONE_HOP_GROUP, expected_one),
        (True, ALIASES, TWO_HOP_GROUP, expected_two),
    ):
        query = aliases[alias_no]
        start_wall, start_cpu = time.perf_counter_ns(), time.process_time_ns()
        if is_two:
            actual = index.lookup_two_hop(
                router, query, group=group, principal=principal,
            )
            wall_samples.append((time.perf_counter_ns() - start_wall) / 1_000_000)
            cpu_samples.append((time.process_time_ns() - start_cpu) / 1_000_000)
            full = rebuilt.lookup_two_hop(
                router, query, group=group, principal=principal,
            )
            observed = actual.candidates[0].route_ids if actual.candidates else ()
            if expected and (
                actual.candidates[0].root_to_intermediate
                != (("contact_id", "contact_id"),)
                or actual.candidates[0].intermediate_to_target
                != (("case_id", "case_id"),)
            ):
                raise AssertionError("G5 2-hop original source argument binding drift")
        else:
            actual = index.lookup(
                router, query, group=group, principal=principal,
            )
            wall_samples.append((time.perf_counter_ns() - start_wall) / 1_000_000)
            cpu_samples.append((time.process_time_ns() - start_cpu) / 1_000_000)
            full = rebuilt.lookup(
                router, query, group=group, principal=principal,
            )
            observed = (
                (actual.candidates[0].producer_route_id,
                 actual.candidates[0].consumer_route_id)
                if actual.candidates else ()
            )
            if expected and (
                actual.candidates[0].parameter_bindings
                != (("contact_id", "contact_id"),)
                or actual.candidates[0].consumer_output_fields != ("status",)
            ):
                raise AssertionError("G5 1-hop original source argument binding drift")
        if (
            observed != expected
            or actual != full
            or actual.status != ("complete" if expected else "no_proven_hit")
            or actual.qualified_path_count != int(bool(expected))
            or actual.executable_authority or actual.independent_quality_evidence
            or actual.calibrated_no_fit
        ):
            raise AssertionError("G5 original-source oracle/index/full-rebuild path mismatch")


def audit_heterogeneous_graph_churn(registered_routes: int) -> dict[str, Any]:
    if type(registered_routes) is not int or registered_routes not in (500, 5000):
        raise ValueError("only preregistered 500/5000 native source catalogs allowed")
    router = _graph_source_fixture(registered_routes)
    graph = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    wall_samples: list[float] = []
    cpu_samples: list[float] = []
    versions: set[int] = set()
    snapshots: set[str] = set()
    edges_per_stage: list[int] = []
    stale_rejections = 0
    one_checks = two_checks = health_checks = 0
    for stage in STAGES:
        if stage != "initial":
            changed_key = ("unrelated_00001" if "middle" in stage else "unrelated_00000")
            changed = router.registry.get(changed_key)
            changed.endpoint("read").output_fields[0].semantic_id = (
                "bench.moved_case" if stage == "middle_unbound"
                else "bench.moved_contact" if stage == "root_unbound"
                else "bench.case_id" if "middle" in stage else "bench.contact_id"
            )
            router.registry.register(changed, replace=True)
            _scope(router, "visible")
            try:
                graph.lookup_two_hop(
                    router, ALIASES[0], group=TWO_HOP_GROUP, principal=ACTOR,
                )
            except PolicyViolationError:
                stale_rejections += 1
            else:
                raise AssertionError("G5 stale graph did not fail closed")
            graph = NativeSchemaGraphIndex.refresh_from_inmemory_journal(
                graph, router.registry,
            )
        rebuilt = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
        _verify_snapshot_equivalence(graph, rebuilt)
        witness = _structural_witness(router)
        actual_edges = tuple(sorted(
            (edge.producer_id, edge.consumer_id) for edge in graph.graph.edges
        ))
        if (
            witness != STAGE_EDGES[stage] or actual_edges != tuple(sorted(witness))
            or graph.native_root_count != 1 or graph.native_consumer_count != 3
        ):
            raise AssertionError("G5 nonempty original-source edge oracle mismatch")
        edges_per_stage.append(len(actual_edges))
        versions.add(router.registry.version)
        snapshots.add(graph.field_index.snapshot_id)
        for scenario in SCOPES:
            _scope(router, scenario)
            for principal in (ACTOR, ANONYMOUS):
                for alias_no in range(3):
                    _assert_paths(
                        router, graph, rebuilt, principal=principal,
                        stage=stage, scenario=scenario, alias_no=alias_no,
                        wall_samples=wall_samples, cpu_samples=cpu_samples,
                    )
                    one_checks += 1
                    two_checks += 1
        if stage == "initial":
            # Reuse a SINGLE predicate instance while state changes. Index
            # freshness/version must not conceal live provider health flips.
            blocked: set[str] = set()

            def health(
                tool: ToolSpec, _ep: EndpointSpec, *,
                _blocked: set[str] = blocked,
            ) -> bool:
                return tool.key not in _blocked

            _scope(router, "visible")
            router.planner.availability_predicate = health
            pinned_version = router.registry.version
            for key in ("unrelated_00000", "unrelated_00001"):
                for blocked_now in (True, False):
                    if blocked_now:
                        blocked.add(key)
                    else:
                        blocked.discard(key)
                    # Root suppression affects both; intermediate affects only 2-hop.
                    expected = (((), ()) if key == "unrelated_00000" and blocked_now
                                else ((ROOT, DIRECT), ()) if blocked_now
                                else ((ROOT, DIRECT), (ROOT, MIDDLE, TARGET)))
                    one = graph.lookup(
                        router, DIRECT_ALIASES[0], group=ONE_HOP_GROUP, principal=ACTOR,
                    )
                    two = graph.lookup_two_hop(
                        router, ALIASES[0], group=TWO_HOP_GROUP, principal=ACTOR,
                    )
                    observed = (
                        (one.candidates[0].producer_route_id,
                         one.candidates[0].consumer_route_id) if one.candidates else (),
                        two.candidates[0].route_ids if two.candidates else (),
                    )
                    if (
                        observed != expected
                        or one.qualified_path_count != int(bool(expected[0]))
                        or two.qualified_path_count != int(bool(expected[1]))
                        or one.status != ("complete" if expected[0] else "no_proven_hit")
                        or two.status != ("complete" if expected[1] else "no_proven_hit")
                        or len(one.candidates) != int(bool(expected[0]))
                        or len(two.candidates) != int(bool(expected[1]))
                        or one.executable_authority or two.executable_authority
                        or router.planner.availability_predicate is not health
                    ):
                        raise AssertionError("G5 live same-predicate health transition drift")
                    health_checks += 1
            if router.registry.version != pinned_version:
                raise AssertionError("G5 health-only state unexpectedly changed source")
            router.planner.availability_predicate = None
    return {
        "evidence_tier": EVIDENCE,
        "independent_e2_qualified": False,
        "source_gold_verified": False,
        "default_routing_changed": False,
        "registered_source_routes": registered_routes,
        "source_type_count": len(SOURCE_TYPES),
        "source_snapshot_count": len(snapshots),
        "registry_version_count": len(versions),
        "graph_edge_counts": edges_per_stage,
        "stale_index_rejections": stale_rejections,
        "journal_and_full_rebuild_exact_parity": True,
        "independent_edge_oracle_checked": True,
        "authorized_path_oracle_checked": True,
        "one_hop_checks": one_checks,
        "two_hop_checks": two_checks,
        "same_predicate_health_flip_checks": health_checks,
        "languages": ["en", "ko", "ja"],
        "query_wall_ms": _sample_summary(wall_samples),
        "query_process_cpu_ms": _sample_summary(cpu_samples),
        "peak_process_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "python_version": platform.python_version(),
        "limitations": [
            "Host-synthetic mixed ToolSpec graph, not imported publisher schemas",
            "Source-only host fixture witness is not independent publisher E2 gold",
            "No execution, agent calls, model tokens or real provider I/O",
            "No claimed production churn SLA or calibrated no-fit performance",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registered-routes", type=int, choices=(500, 5000), required=True)
    args = parser.parse_args()
    print(json.dumps(
        audit_heterogeneous_graph_churn(args.registered_routes),
        ensure_ascii=False, sort_keys=True, allow_nan=False,
    ))


if __name__ == "__main__":
    main()
