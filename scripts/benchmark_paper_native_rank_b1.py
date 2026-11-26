"""Original-paper native Rank K5 at 500/5000 heterogeneous source routes.

E0 synthetic CPU/byte evidence only: no provider calls, task gold, E2 claims,
model ranking or promotion to the default public retrieval path.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from dataclasses import asdict
from math import ceil
from statistics import median
from time import perf_counter_ns, process_time_ns
from typing import Any

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeDeclaredFieldGroup,
    NativeSchemaPostingIndex,
    PaperNativeRankPolicy,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)

ACTOR = PrincipalContext(subject="paper-rank-b1-synthetic", roles=("reader",))
SOURCES = ("crm", "mcp", "web", "custom")
GROUP = NativeDeclaredFieldGroup(
    aliases=("case status and priority",),
    required_fields=(
        CapabilityFieldContract(
            semantic_id="crm.status", json_schema={"type": "string"},
        ),
        CapabilityFieldContract(
            semantic_id="crm.priority", json_schema={"type": "string"},
        ),
    ),
    source_type="crm", license="owner-reviewed-synthetic",
)


def build_rank_fixture(routes: int) -> tuple[
    SchemaRouter, tuple[str, ...], dict[str, int], str,
]:
    """Source-owned independent expected eligible routes, incl. decoys."""
    if type(routes) is not int or routes not in (500, 5000):
        raise ValueError("only 500 or 5000 declared synthetic routes")
    denied = "native_00000.read"
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(
            AuthorizationRule(effect="deny", operation=denied,
                              roles_any=("reader",)),
            AuthorizationRule(effect="allow", operation="*.read",
                              roles_any=("reader",)),
        ),
    ))
    eligible: list[str] = []
    for i in range(routes):
        name = f"native_{i:05d}"
        source = SOURCES[i % len(SOURCES)]
        fields = [FieldSpec(
            name="status", semantic_id="crm.status",
            json_schema={"type": "string"},
        )] if source == "crm" else [FieldSpec(
            name="payload", semantic_id=f"{source}.payload",
            json_schema={"type": "string"},
        )]
        complete = source == "crm" and i % 29 != 0
        if complete:
            fields.append(FieldSpec(
                name="priority", semantic_id="crm.priority",
                json_schema={"type": "string"},
            ))
        router.add_tool(ToolSpec(
            name=name, source_type=source, license="owner-reviewed-synthetic",
            endpoints=[EndpointSpec(
                name="read", read_only=True, output_fields=fields,
            )],
        ))
        if complete and f"{name}.read" != denied:
            eligible.append(f"{name}.read")
    priorities = {route: index + 1
                  for index, route in enumerate(eligible[-5:])}
    priorities[denied] = 100  # Owner rank must never elevate a denied route.
    return router, tuple(eligible), priorities, denied


def benchmark_paper_rank(
    routes: int, *, repeats: int = 3,
) -> dict[str, Any]:
    if type(repeats) is not int or not 1 <= repeats <= 10:
        raise ValueError("1-10 repetitions required")
    router, eligible, priorities, denied = build_rank_fixture(routes)
    index = NativeSchemaPostingIndex.build(router.registry)
    policy = PaperNativeRankPolicy(
        snapshot_id=index.snapshot_id, route_priorities=priorities,
    )
    expected = tuple(sorted(eligible, key=lambda r: (-priorities.get(r, 0), r))[:5])
    wall_ms: list[float] = []
    cpu_ms: list[float] = []
    response_bytes: list[int] = []
    for _ in range(repeats):
        start_wall = perf_counter_ns()
        start_cpu = process_time_ns()
        result = index.lookup(
            router, GROUP.aliases[0], principal=ACTOR, group=GROUP,
            _paper_rank_policy=policy,
            _paper_rank_aliases=(("case status",), ("case priority",)),
        )
        cpu_ms.append((process_time_ns() - start_cpu) / 1_000_000)
        wall_ms.append((perf_counter_ns() - start_wall) / 1_000_000)
        got = tuple(candidate.route_id for candidate in result.candidates)
        if (
            result.status != "ranked_unverified"
            or not result.deterministic_paper_ranked
            or result.qualified_count != len(eligible)
            or got != expected or denied in got
        ):
            raise RuntimeError("original authorized Rank disagrees with fixture oracle")
        response_bytes.append(len(json.dumps(
            asdict(result), ensure_ascii=False, sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")))

    def percentiles(samples: list[float]) -> dict[str, float]:
        ordered = sorted(samples)
        return {
            name: round(ordered[ceil(len(ordered) * fraction) - 1], 3)
            for name, fraction in (("p50", 0.5), ("p95", 0.95), ("p99", 0.99))
        }

    return {
        "provenance": "SOURCE_OWNED_SYNTHETIC_ALGORITHM1_RANK_B1_DEV",
        "evidence_tier": "E0_SYNTHETIC_NOT_PUBLISHER_E2",
        "source_snapshot": index.snapshot_id,
        "registered_routes": index.indexed_route_count,
        "qualified_routes": len(eligible),
        "ranked_k": len(expected),
        "oracle_top_k": list(expected),
        "repeats": repeats,
        "median_lookup_wall_ms": round(median(wall_ms), 3),
        "median_lookup_cpu_ms": round(median(cpu_ms), 3),
        "max_lookup_wall_ms": round(max(wall_ms), 3),
        "lookup_wall_ms": percentiles(wall_ms),
        "lookup_cpu_ms": percentiles(cpu_ms),
        "serialized_receipt_bytes": max(response_bytes),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routes", type=int, choices=(500, 5000), default=500)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    report = benchmark_paper_rank(args.routes, repeats=args.repeats)
    print(json.dumps({
        **report,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
