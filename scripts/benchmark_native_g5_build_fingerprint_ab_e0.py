"""Paired per-endpoint vs per-detached-tool G5 source hash scans at 5k routes.

Only the ORIGINAL native ToolSpec hash repetition is compared. A separate
real field-posting + canonical graph build is measured but NOT the counter-
factual baseline. Synthetic developer source only: no model, agent, API or SLA.
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import resource
import statistics
import subprocess
import time
from pathlib import Path

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeDeclaredFieldGroup,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex

TOOLS = 100
ENDPOINTS_PER_TOOL = 50
ROUTES = TOOLS * ENDPOINTS_PER_TOOL
QUERY = "case status"
PRINCIPAL = PrincipalContext(subject="synthetic-reader", roles=("reader",))
GROUP = NativeDeclaredFieldGroup(
    aliases=(QUERY,),
    required_fields=(CapabilityFieldContract(
        semantic_id="crm.status", json_schema={"type": "string"},
    ),),
    source_type="crm", license="synthetic-reviewed",
)
ROOT = Path(__file__).resolve().parents[1]


def _synthetic_router() -> SchemaRouter:
    """100 multi-endpoint native ToolSpecs; 5000 exact source routes."""
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.*", roles_any=("reader",),
        ),),
    ))
    for tool_idx in range(TOOLS):
        endpoints: list[EndpointSpec] = []
        for endpoint_idx in range(ENDPOINTS_PER_TOOL):
            if (tool_idx, endpoint_idx) == (0, 0):
                endpoint = EndpointSpec(
                    name="read_0", read_only=True,
                    output_fields=[FieldSpec(
                        name="customer_id", semantic_id="crm.customer_id",
                        identifier=True, json_schema={"type": "string"},
                    )],
                )
            elif (tool_idx, endpoint_idx) == (1, 0):
                endpoint = EndpointSpec(
                    name="read_0", read_only=True,
                    parameters=[{
                        "name": "customer_id", "required": True,
                        "location": "argument", "semantic_id": "crm.customer_id",
                        "json_schema": {"type": "string"},
                    }],
                    input_schema={
                        "type": "object",
                        "properties": {"customer_id": {"type": "string"}},
                        "required": ["customer_id"],
                    },
                    output_fields=[FieldSpec(
                        name="status", semantic_id="crm.status",
                        json_schema={"type": "string"},
                    )],
                )
            else:
                endpoint = EndpointSpec(
                    name=f"read_{endpoint_idx}",
                    description=("English / 한국어 / 日本語" if endpoint_idx % 3 == 0
                                 else "unrelated source-native endpoint"),
                    read_only=True,
                    output_fields=[FieldSpec(
                        name="label",
                        semantic_id=f"noise_{tool_idx:03d}.label",
                        json_schema={"type": "string"},
                    )],
                )
            endpoints.append(endpoint)
        router.add_tool(ToolSpec(
            name=f"tool_{tool_idx:03d}",
            source_type="crm" if tool_idx < 2 else f"domain_{tool_idx % 6}",
            license="synthetic-reviewed",
            endpoints=endpoints,
        ))
    return router


def _original_scan(router: SchemaRouter) -> dict[str, tuple[str, str]]:
    """Exact historical per-endpoint full ToolSpec fingerprint behavior."""
    routes: dict[str, tuple[str, str]] = {}
    for tool in router.registry.tools():
        for endpoint in tool.endpoints:
            route = f"{tool.key}.{endpoint.name}"
            if route in routes:
                raise ValueError("duplicate original native route")
            routes[route] = (tool.fingerprint, endpoint.fingerprint)
    return routes


def _optimized_scan(router: SchemaRouter) -> dict[str, tuple[str, str]]:
    """New per-detached-tool full ToolSpec hash, all endpoint hashes intact."""
    routes: dict[str, tuple[str, str]] = {}
    for tool in router.registry.tools():
        tool_fingerprint = tool.fingerprint
        tool_key = tool.key
        for endpoint in tool.endpoints:
            route = f"{tool_key}.{endpoint.name}"
            if route in routes:
                raise ValueError("duplicate optimized native route")
            routes[route] = (tool_fingerprint, endpoint.fingerprint)
    return routes


def run(*, pairs: int = 4) -> dict:
    if type(pairs) is not int or not 2 <= pairs <= 8:
        raise ValueError("bounded E0 paired 5k scan count required")
    router = _synthetic_router()
    before_version = router.registry.version
    sizes: dict[str, list[float]] = {
        "original_per_endpoint": [], "once_per_detached_tool": [],
    }
    deltas: list[float] = []
    for pair in range(pairs):
        if router.registry.version != before_version:
            raise ValueError("G5 source revision changed before paired scan")
        variants = (
            ("original_per_endpoint", "once_per_detached_tool")
            if pair % 2 == 0
            else ("once_per_detached_tool", "original_per_endpoint")
        )
        results = {}
        for label in variants:
            start = time.perf_counter_ns()
            results[label] = (
                _original_scan(router) if label == "original_per_endpoint"
                else _optimized_scan(router)
            )
            elapsed = (time.perf_counter_ns() - start) / 1e6
            if not math.isfinite(elapsed) or elapsed < 0:
                raise ValueError("invalid G5 measured scan latency")
            sizes[label].append(elapsed)
        if (
            results["original_per_endpoint"]
            != results["once_per_detached_tool"]
            or len(results["original_per_endpoint"]) != ROUTES
            or router.registry.version != before_version
        ):
            raise ValueError("G5 paired source fingerprint mismatch")
        deltas.append(
            sizes["once_per_detached_tool"][-1]
            - sizes["original_per_endpoint"][-1]
        )
    start = time.perf_counter_ns()
    field_index = NativeSchemaPostingIndex.build(router.registry)
    graph = NativeSchemaGraphIndex.build(field_index)
    build_wall_ms = (time.perf_counter_ns() - start) / 1e6
    if (
        len(field_index.route_fingerprints) != ROUTES
        or dict(field_index.route_fingerprints)
        != results["original_per_endpoint"]
        or router.registry.version != before_version
    ):
        raise ValueError("G5 built index changed exact original source identity")
    lookup = graph.lookup(router, QUERY, group=GROUP, principal=PRINCIPAL)
    if (
        lookup.status != "complete"
        or lookup.qualified_path_count != 1
        or lookup.candidates[0].producer_route_id != "tool_000.read_0"
        or lookup.candidates[0].consumer_route_id != "tool_001.read_0"
        or lookup.executable_authority or lookup.independent_quality_evidence
        or lookup.calibrated_no_fit
    ):
        raise ValueError("G5 live scoped native graph evidence drift")
    git_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True,
        text=True, timeout=10, cwd=ROOT,
    ).stdout.strip()
    if len(git_sha) != 40 or any(c not in "0123456789abcdef" for c in git_sha):
        raise ValueError("unverifiable checkout revision")
    return {
        "evidence_tier": "E0_SYNTHETIC_5000_MULTIENTPOINT_G5_BUILD_DEV_ONLY",
        "source_revision": git_sha,
        "independent_e2_qualified": False,
        "real_native_provider_execution": False,
        "model_inference_executed": False,
        "registered_source_tools": TOOLS,
        "registered_source_routes": ROUTES,
        "endpoints_per_tool": ENDPOINTS_PER_TOOL,
        "paired_scans_per_arm": pairs,
        "all_original_vs_optimized_native_fingerprints_identical": True,
        "scan_wall_ms": {
            key: {
                "median": statistics.median(values),
                "min": min(values),
                "max": max(values),
            }
            for key, values in sizes.items()
        },
        "paired_scan_delta_ms": {
            "median_optimized_minus_original": statistics.median(deltas),
            "optimized_faster_pairs": sum(x < 0 for x in deltas),
        },
        "optimized_real_posting_plus_graph_build_wall_ms": build_wall_ms,
        "verified_permission_scoped_typed_one_hop_paths": lookup.qualified_path_count,
        "peak_process_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "python": platform.python_version(),
        "limitations": (
            "Paired original/optimized costs are source fingerprint scan-only. "
            "Full G5 build timing has no paired original full-build baseline. "
            "100 generated 50-endpoint synthetic tools, not 5000 independent "
            "real providers; no language retrieval, external agent, E2 or SLA."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=int, default=4)
    args = parser.parse_args()
    report = run(pairs=args.pairs)
    print(json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()
