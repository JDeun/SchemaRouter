"""Mixed original ToolSpec source types: offline oracle vs opt-in index (E0).

Only the independent audit scans the full registered source inventory. No
product request path, agent, provider transport, or new index is introduced.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import resource
import time
from dataclasses import dataclass
from typing import Any

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.concept_graph_retrieval import retrieve_authorized_concept_graph
from schemarouter.field_group_retrieval import _complete_fields, _root_envelope_empty
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex


@dataclass(frozen=True, slots=True)
class SourceCase:
    concept_id: str
    source_type: str
    tool_name: str
    field_name: str
    semantic_id: str
    json_type: str
    aliases: tuple[str, str, str]

    @property
    def route_id(self) -> str:
        return f"{self.tool_name}.read"


CASES = (
    SourceCase(
        "openapi.temperature", "openapi", "openapi_weather", "temperature",
        "weather.temperature", "number", ("air temperature", "기온", "気温"),
    ),
    SourceCase(
        "mcp.document", "mcp", "mcp_documents", "title", "docs.title",
        "string", ("document title", "문서 제목", "文書タイトル"),
    ),
    SourceCase(
        "optimade.formula", "optimade", "optimade_materials", "formula",
        "materials.formula", "string", ("material formula", "화학식", "組成式"),
    ),
    SourceCase(
        "custom.sku", "custom", "custom_inventory", "sku",
        "inventory.sku", "string", ("product sku", "상품 코드", "商品コード"),
    ),
)
ACTOR = PrincipalContext(subject="source-native-e0-auditor", roles=("reader",))
LICENSE = "host-reviewed-synthetic"
SOURCE_TYPES = tuple(case.source_type for case in CASES)
SCENARIOS = ("visible", "hidden", "denied", "unavailable")
EVIDENCE = "E0_SYNTHETIC_HETEROGENEOUS_NATIVE_SOURCE_PARITY_NOT_E2"
CATALOG = NativeConceptCatalog(concepts=tuple(
    NativeDeclaredConcept(
        concept_id=case.concept_id, aliases=case.aliases,
        required_fields=(CapabilityFieldContract(
            semantic_id=case.semantic_id,
            json_schema={"type": case.json_type},
        ),),
        source_type=case.source_type, license=LICENSE,
    ) for case in CASES
))


def _tool(
    name: str, source_type: str, semantic_id: str, json_type: str,
    *, field_name: str, license_name: str = LICENSE,
) -> ToolSpec:
    return ToolSpec(
        name=name, source_type=source_type, license=license_name,
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            output_fields=[FieldSpec(
                name=field_name, semantic_id=semantic_id,
                json_schema={"type": json_type},
            )],
        )],
    )


def build_heterogeneous_fixture(registered_routes: int) -> SchemaRouter:
    """Exactly 500/5000 author-created mixed native-like source endpoints."""
    if type(registered_routes) is not int or registered_routes not in (500, 5000):
        raise ValueError("only preregistered 500/5000 source catalogs allowed")
    router = SchemaRouter()
    for case in CASES:
        router.add_tool(_tool(
            case.tool_name, case.source_type, case.semantic_id,
            case.json_type, field_name=case.field_name,
        ))
        # Near-matches carry the same semantic ID but violate different
        # ORIGINAL native source declarations; the index may not promote them.
        router.add_tool(_tool(
            f"bad_license_{case.tool_name}", case.source_type,
            case.semantic_id, case.json_type, field_name=case.field_name,
            license_name="unreviewed-synthetic",
        ))
        router.add_tool(_tool(
            f"bad_type_{case.tool_name}", case.source_type,
            case.semantic_id, "integer" if case.json_type == "string" else "string",
            field_name=case.field_name,
        ))
        # Same semantic ID, JSON type, and license; only the native source
        # family is wrong. Source-type omission must fail exact parity.
        other_type = SOURCE_TYPES[(SOURCE_TYPES.index(case.source_type) + 1) % len(SOURCE_TYPES)]
        router.add_tool(_tool(
            f"bad_source_{case.tool_name}", other_type,
            case.semantic_id, case.json_type, field_name=case.field_name,
        ))
    for i in range(registered_routes - 4 * len(CASES)):
        router.add_tool(_tool(
            f"unrelated_{i:05d}", SOURCE_TYPES[i % len(SOURCE_TYPES)],
            f"noise.signal_{i % 19}", "string" if i % 2 else "integer",
            field_name=f"signal_{i % 7}",
        ))
    if len(router.registry.tools()) != registered_routes:
        raise AssertionError("synthetic registered source cardinality drift")
    return router


def configure_heterogeneous_scope(router: SchemaRouter, scenario: str) -> None:
    """Exercise actual authorization/scope/availability, not oracle filters."""
    if scenario not in SCENARIOS:
        raise ValueError("unknown heterogeneous source scenario")
    rules: tuple[AuthorizationRule, ...] = (
        (AuthorizationRule(
            effect="deny", operation="openapi_weather.read",
            roles_any=("reader",),
        ),) if scenario == "denied" else ()
    ) + (AuthorizationRule(
        effect="allow", operation="*.read", roles_any=("reader",),
    ),)
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny", rules=rules,
        data_rules=(DataScopeRule(
            operation="mcp_documents.read", roles_any=("reader",),
            hidden_fields=("title",),
        ),) if scenario == "hidden" else (),
    )
    router.planner.availability_predicate = (
        lambda tool, endpoint: tool.key != "optimade_materials"
    ) if scenario == "unavailable" else None


def original_heterogeneous_oracle(
    router: SchemaRouter, concept_id: str, principal: PrincipalContext,
) -> tuple[str, ...]:
    """Offline exhaustive ORIGINAL registry/source scan, never a query path."""
    matches = tuple(c for c in CATALOG.concepts if c.concept_id == concept_id)
    if len(matches) != 1:
        raise ValueError("unknown original source concept")
    concept = matches[0]
    permitted = router._authorization_predicate(principal)
    if permitted is None:
        return ()
    found: list[str] = []
    for tool in router.registry.tools():
        if tool.source_type != concept.source_type or tool.license != concept.license:
            continue
        for endpoint in tool.endpoints:
            if (
                not endpoint.read_only or endpoint.destructive
                or not _root_envelope_empty(endpoint)
                or not permitted(tool, endpoint)
            ):
                continue
            health = router.planner.availability_predicate
            if health is not None and not health(tool, endpoint):
                continue
            visible = router._data_scope_endpoint_view(principal, tool, endpoint)
            if visible is not None and _complete_fields(
                visible.output_fields, concept.required_fields,
            ):
                found.append(f"{tool.key}.{endpoint.name}")
    return tuple(sorted(found))


def _summary(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    return {
        f"p{percentile}": round(
            ordered[max(0, math.ceil(len(ordered) * percentile / 100) - 1)], 4,
        ) for percentile in (50, 95, 99)
    }


def audit_heterogeneous(
    registered_routes: int, *, iterations: int = 2,
) -> dict[str, Any]:
    """Compare current indexed result to separate exhaustive ground truth."""
    if type(iterations) is not int or not 1 <= iterations <= 10:
        raise ValueError("bounded 1-10 actual query samples required")
    router = build_heterogeneous_fixture(registered_routes)
    start = time.perf_counter_ns()
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    build_ms = round((time.perf_counter_ns() - start) / 1_000_000, 4)
    walls: list[float] = []
    cpu: list[float] = []
    pairs = 0
    for scenario in SCENARIOS:
        configure_heterogeneous_scope(router, scenario)
        for case in CASES:
            # Exhaustive source scan is outside timed retrieval and only
            # determines the offline expected native route set.
            expected = original_heterogeneous_oracle(router, case.concept_id, ACTOR)
            correct = () if (
                (scenario == "hidden" and case.source_type == "mcp")
                or (scenario == "denied" and case.source_type == "openapi")
                or (scenario == "unavailable" and case.source_type == "optimade")
            ) else (case.route_id,)
            if expected != correct:
                raise AssertionError("original source fixture oracle cardinality drift")
            for query in case.aliases:
                for _ in range(iterations):
                    wall_start = time.perf_counter_ns()
                    cpu_start = time.process_time_ns()
                    result = retrieve_authorized_concept_graph(
                        router, query, principal=ACTOR, catalog=CATALOG,
                        index=index, experimental_indexed_direct=True,
                    )
                    cpu.append((time.process_time_ns() - cpu_start) / 1_000_000)
                    walls.append((time.perf_counter_ns() - wall_start) / 1_000_000)
                    if (
                        result.route_ids != expected
                        or result.status != ("complete" if expected else "no_proven_hit")
                        or result.executable_authority
                        or result.independent_quality_evidence
                    ):
                        raise AssertionError("indexed route disagrees with original source")
                    pairs += 1
    return {
        "evidence_tier": EVIDENCE,
        "independent_e2_qualified": False,
        "source_gold_verified": False,
        "default_routing_changed": False,
        "all_exact_parity": True,
        "registered_source_routes": registered_routes,
        "source_type_count": len(SOURCE_TYPES),
        "source_snapshot_id": index.field_index.snapshot_id,
        "scenarios": list(SCENARIOS),
        "languages": ["en", "ko", "ja"],
        "paired_checks": pairs,
        "index_build_wall_ms": build_ms,
        "query_wall_ms": _summary(walls),
        "query_process_cpu_ms": _summary(cpu),
        "peak_process_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "python_version": platform.python_version(),
        "limitations": [
            "Developer-authored E0 source types and concepts; not provider imports",
            "No publisher-authored independent route/field/license gold or E2",
            "No actual models, agent responses, transport or 5000-real-API SLA",
            "No live schema churn throughput or production ranking/no-fit claim",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registered-routes", type=int, choices=(500, 5000), required=True)
    parser.add_argument("--iterations", type=int, default=2)
    args = parser.parse_args()
    print(json.dumps(
        audit_heterogeneous(args.registered_routes, iterations=args.iterations),
        ensure_ascii=False, sort_keys=True, allow_nan=False,
    ))


if __name__ == "__main__":
    main()
