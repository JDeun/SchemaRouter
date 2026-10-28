"""Reproducible E0 *public* Algorithm 1 planning profile at 500/5,000 routes.

Measures the prepared-session and source-pinned Graph Rank route all the way
through public sync Understand and async model-Understand APIs. A deterministic
local callback stands in for the *model response*, NOT for an LLM timing
measurement or independent semantic-quality oracle. NO provider/tool execution.
Existing source-native graph and router indexes are reused, not reimplemented.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
from math import ceil
from statistics import median
from time import perf_counter_ns, process_time_ns
from typing import Any

from schemarouter import (
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    ParameterSpec,
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperNativeRankPolicy,
    PrincipalContext,
    ToolSpec,
)
from schemarouter.paper_understood_direct_plan import PaperUnderstanding
from scripts.benchmark_indexed_native_graph_g5_cpu_e0 import _synthetic_router

EVIDENCE_TIER = "E0_SYNTHETIC_PUBLIC_PLAN_ONLY_NOT_INDEPENDENT_E2"
ACTOR = PrincipalContext(subject="paper-public-e0", roles=("reader",))
LICENSE = "host-reviewed-synthetic"


def _typed_consumer(
    name: str, input_name: str, input_semantic: str,
    output_name: str, output_semantic: str, *, identifier: bool = False,
) -> ToolSpec:
    return ToolSpec(
        name=name, source_type="crm", license=LICENSE,
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            parameters=[ParameterSpec(
                name=input_name, semantic_id=input_semantic, required=True,
                json_schema={"type": "string"},
            )],
            input_schema={
                "type": "object", "properties": {
                    input_name: {"type": "string"},
                }, "required": [input_name],
            },
            output_fields=[FieldSpec(
                name=output_name, semantic_id=output_semantic,
                json_schema={"type": "string"}, identifier=identifier,
            )],
        )],
    )


def build_synthetic_public_case(routes: int, hops: int) -> tuple[Any, Any, Any, tuple[str, ...]]:
    """Exact registered route count; independently fixed expected typed DAG."""
    if type(routes) is not int or routes not in (500, 5000):
        raise ValueError("synthetic registered route count must be 500 or 5000")
    if type(hops) is not int or hops not in (1, 2):
        raise ValueError("synthetic G5 path must have 1 or 2 edges")

    extra = 2 if hops == 2 else 0
    # The existing source-native factory already registers the contact root,
    # a typed one-hop case service and heterogeneous unrelated source tools.
    router = _synthetic_router(routes - 2 - extra)
    if hops == 2:
        router.add_tool(_typed_consumer(
            "case_middle", "customer_id", "crm.customer_id",
            "case_id", "crm.case_id", identifier=True,
        ))
        router.add_tool(_typed_consumer(
            "case_followup", "case_id", "crm.case_id",
            "resolution", "crm.resolution",
        ))
    semantic = "crm.status" if hops == 1 else "crm.resolution"
    phrase = "case status" if hops == 1 else "case resolution"
    target = "case_service.read" if hops == 1 else "case_followup.read"
    expected = (
        ("contact_directory.read", "case_service.read") if hops == 1
        else ("contact_directory.read", "case_middle.read", "case_followup.read")
    )
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id=semantic, aliases=(phrase,),
        source_type="crm", license=LICENSE,
        required_fields=(CapabilityFieldContract(
            semantic_id=semantic, json_schema={"type": "string"},
        ),),
    ),))
    intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id="case.lookup", required_concept_ids=(semantic,),
        domains=("case",),
    ),))
    return router, catalog, intents, expected


def _percentiles(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    return {
        key: round(ordered[max(0, ceil(len(ordered) * fraction) - 1)], 4)
        for key, fraction in (("p50", 0.50), ("p95", 0.95), ("p99", 0.99))
    }


def _assert_plan(plan: Any, expected: tuple[str, ...]) -> int:
    routes = tuple(call.route_id for call in plan.calls)
    if (
        plan.status != "requires_observation"
        or routes != expected
        or len(plan.bindings) != len(expected) - 1
        or plan.executable_authority is not False
        or plan.ranked_unverified is not True
    ):
        raise AssertionError("public Algorithm 1 plan disagreed with source fixture")
    return len(plan.model_dump_json().encode("utf-8"))


def _measure_sync(session: Any, understanding: Any, intents: Any, policy: Any,
                  expected: tuple[str, ...], warmup: int, repeats: int) -> dict[str, Any]:
    def one_call() -> Any:
        return session.compile_understood(
            understanding, principal=ACTOR, intent_registry=intents,
            rank_policy=policy, allow_unnamed_graph_discovery=True,
        )

    for _ in range(warmup):
        _assert_plan(one_call(), expected)
    wall: list[float] = []
    cpu: list[float] = []
    byte_count = 0
    for _ in range(repeats):
        w0, c0 = perf_counter_ns(), process_time_ns()
        plan = one_call()
        wall.append((perf_counter_ns() - w0) / 1_000_000)
        cpu.append((process_time_ns() - c0) / 1_000_000)
        byte_count = _assert_plan(plan, expected)
    return {
        "warmup_calls": warmup, "measured_calls": repeats,
        "wall_ms": _percentiles(wall), "process_cpu_ms": _percentiles(cpu),
        "median_wall_ms": round(median(wall), 4),
        "receipt_bytes": byte_count, "exact_route_oracle": True,
    }


async def _measure_async(session: Any, semantic: str, intents: Any, policy: Any,
                         expected: tuple[str, ...], warmup: int,
                         repeats: int) -> dict[str, Any]:
    model_calls = 0
    model_payload_max_bytes = 0

    async def deterministic_model(payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal model_calls, model_payload_max_bytes
        model_calls += 1
        if payload.get("offered_tool_keys") != []:
            raise AssertionError("unnamed source target identities leaked to model")
        model_payload_max_bytes = max(
            model_payload_max_bytes,
            len(json.dumps(payload, sort_keys=True).encode("utf-8")),
        )
        return {
            "intent_id": "case.lookup",
            "concept_ids": [semantic],
            "named_tools": [],
        }

    async def one_call() -> Any:
        return await session.acompile_query(
            "Who handles this case?", principal=ACTOR,
            model=deterministic_model, intent_registry=intents,
            model_visible_intent_ids=("case.lookup",),
            model_visible_concept_ids=(semantic,),
            model_visible_tool_keys=(), rank_policy=policy,
            allow_unnamed_graph_discovery=True,
        )

    for _ in range(warmup):
        _assert_plan(await one_call(), expected)
    wall: list[float] = []
    cpu: list[float] = []
    byte_count = 0
    for _ in range(repeats):
        w0, c0 = perf_counter_ns(), process_time_ns()
        plan = await one_call()
        wall.append((perf_counter_ns() - w0) / 1_000_000)
        cpu.append((process_time_ns() - c0) / 1_000_000)
        byte_count = _assert_plan(plan, expected)
    if model_calls != warmup + repeats:
        raise AssertionError("unexpected model stub call count")
    return {
        "warmup_calls": warmup, "measured_calls": repeats,
        "wall_ms": _percentiles(wall), "process_cpu_ms": _percentiles(cpu),
        "median_wall_ms": round(median(wall), 4),
        "receipt_bytes": byte_count,
        "exact_route_oracle": True,
        "model_stub_calls": model_calls,
        "model_stub_payload_max_bytes": model_payload_max_bytes,
        "real_model_calls": 0, "provider_calls": 0,
    }


def benchmark(routes: int, *, hops: int = 1, repeats: int = 3,
              warmup: int = 1) -> dict[str, Any]:
    if (
        type(repeats) is not int or not 1 <= repeats <= 20
        or type(warmup) is not int or not 0 <= warmup <= 3
    ):
        raise ValueError("E0 bounded benchmark accepts 1-20 runs and 0-3 warmups")
    router, catalog, intents, expected = build_synthetic_public_case(routes, hops)
    build_w0, build_c0 = perf_counter_ns(), process_time_ns()
    session = router.prepare_field_routing(catalog=catalog)
    build_wall_ms = (perf_counter_ns() - build_w0) / 1_000_000
    build_cpu_ms = (process_time_ns() - build_c0) / 1_000_000
    if session._index.field_index.indexed_route_count != routes:
        raise AssertionError("synthetic benchmark registered route count drift")
    policy = PaperNativeRankPolicy(
        snapshot_id=session.snapshot_id,
        route_domains={expected[-1]: ("case",)},
        route_priorities={expected[-1]: 90},
    )
    semantic = "crm.status" if hops == 1 else "crm.resolution"
    hint = PaperUnderstanding(intent_id="case.lookup", named_tools=())
    sync = _measure_sync(
        session, hint, intents, policy, expected, warmup, repeats,
    )
    async_metrics = asyncio.run(_measure_async(
        session, semantic, intents, policy, expected, warmup, repeats,
    ))
    return {
        "schema_version": 1,
        "evidence_tier": EVIDENCE_TIER,
        "independent_e2_qualified": False,
        "model_latency_measured": False,
        "provider_execution_performed": False,
        "registered_routes": routes,
        "expected_hops": hops,
        "strict_k": 5,
        "expected_route_ids": list(expected),
        "source_snapshot_id": session.snapshot_id,
        "prepared_build_wall_ms": round(build_wall_ms, 4),
        "prepared_build_process_cpu_ms": round(build_cpu_ms, 4),
        "prepared_sync": sync,
        "prepared_async_model_stub": async_metrics,
        "python": platform.python_version(),
        "limitations": [
            "Synthetic known-source CRM path plus unrelated source noise",
            "Deterministic local model response has no LLM inference cost",
            "No network, provider calls, external gold or independent E2",
            "Process CPU and wall numbers are machine-specific DEV baselines",
            "No default router or release qualification",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routes", type=int, choices=(500, 5000), default=500)
    parser.add_argument("--hops", type=int, choices=(1, 2), default=1)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(
        benchmark(args.routes, hops=args.hops, repeats=args.repeats,
                  warmup=args.warmup),
        sort_keys=True, ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
