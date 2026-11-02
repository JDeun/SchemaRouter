"""Three native source domains x EN/KO/JA under fair K5: E0 research.

No new graph ranker, model or oracle-injected retrieval. New owner-authored
source fixtures isolate type/field/domain confusion beyond the original CRM
fork. A separate registry scanner supplies the evaluation-only route gold.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from schemarouter import (
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeDeclaredFieldGroup,
    ParameterSpec,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    ALIASES,
    GROUP,
    build_fixture,
    exhaustive_source_fork_reference,
)
from scripts.research_g5_source_schema_exposure_e0 import MAX_K, SIZES
from scripts.research_g5_vs_scoped_lexical_k5_e0 import (
    scoped_source_lexical_k5,
)

SCHEMA_VERSION = "g5-multidomain-matched-k5-e0-v1"
LICENSE = "host-reviewed-synthetic"


@dataclass(frozen=True)
class Domain:
    name: str
    identity: str
    identity_kind: str
    fields: tuple[tuple[str, str], tuple[str, str]]
    aliases: tuple[str, str, str]

    def group(self) -> NativeDeclaredFieldGroup:
        return NativeDeclaredFieldGroup(
            aliases=self.aliases,
            required_fields=tuple(
                CapabilityFieldContract(
                    semantic_id=f"{self.name}.{semantic}",
                    json_schema={"type": "string"},
                )
                for semantic, _ in self.fields
            ),
            source_type=self.name,
            license=LICENSE,
        )


DOMAINS = (
    Domain("lab", "sample_id", "integer", (
        ("assay_state", "assay"), ("purity_band", "purity"),
    ), ("sample assay and purity", "시료 분석상태 및 순도", "試料の分析状態と純度")),
    Domain("inventory", "lot_id", "string", (
        ("temperature_band", "temperature"), ("storage_zone", "zone"),
    ), ("lot temperature and storage", "로트 온도 및 보관 위치", "ロットの温度と保管場所")),
)


def _new_root(domain: Domain) -> ToolSpec:
    identifier = domain.identity
    schema = {"type": domain.identity_kind}
    return ToolSpec(
        name=f"{domain.name}_origin", source_type=domain.name,
        license=LICENSE,
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            output_fields=[FieldSpec(
                name=identifier, semantic_id=f"{domain.name}.{identifier}",
                json_schema=schema, identifier=True,
            )],
            output_schema={
                "type": "object", "properties": {identifier: schema},
                "required": [identifier],
            },
        )],
    )


def _new_leaf(
    domain: Domain, *, idx: int, suffix: str = "",
    wrong_input: bool = False, wrong_source: bool = False,
    wrong_license: bool = False,
) -> ToolSpec:
    semantic, field = domain.fields[idx]
    name = f"{domain.name}_{field}{suffix}"
    kind = (
        ("string" if domain.identity_kind == "integer" else "integer")
        if wrong_input else domain.identity_kind
    )
    schema = {"type": kind}
    return ToolSpec(
        name=name,
        source_type="other_source" if wrong_source else domain.name,
        license="unreviewed" if wrong_license else LICENSE,
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            parameters=[ParameterSpec(
                name=domain.identity, semantic_id=f"{domain.name}.{domain.identity}",
                required=True, json_schema=schema,
            )],
            input_schema={
                "type": "object", "properties": {domain.identity: schema},
                "required": [domain.identity],
            },
            output_fields=[FieldSpec(
                name=field, semantic_id=f"{domain.name}.{semantic}",
                json_schema={"type": "string"},
            )],
        )],
    )


def build_multidomain_source(
    base_routes: int, *, mixed_scope: bool,
) -> SchemaRouter:
    """Make one combined original registry, no model or query-derived tools."""
    if type(base_routes) is not int or base_routes not in SIZES:
        raise ValueError("base route size not preregistered")
    if type(mixed_scope) is not bool:
        raise ValueError("mixed scope flag required")
    router = build_fixture(base_routes, mixed_scope=mixed_scope)
    for domain in DOMAINS:
        router.add_tool(_new_root(domain))
        router.add_tool(_new_leaf(domain, idx=0))
        router.add_tool(_new_leaf(domain, idx=1))
        router.add_tool(_new_leaf(domain, idx=0, suffix="_wrong_id", wrong_input=True))
        router.add_tool(_new_leaf(domain, idx=1, suffix="_unlicensed", wrong_license=True))
        router.add_tool(_new_leaf(domain, idx=1, suffix="_other_source", wrong_source=True))
    return router


def source_scan_oracle(
    router: SchemaRouter, domain: Domain,
) -> tuple[tuple[str, str, str], ...]:
    """Independent *original* registry scan, not G5/lexical candidates.

    Validate matching read-only provider/license, current principal, source
    field visibility, root identifier property and strict consumer input.
    This is evaluation-only and never called inside a selection arm.
    """
    if not isinstance(router, SchemaRouter) or domain not in DOMAINS:
        raise ValueError("unqualified source scanner input")
    witness = router._retrieval_authority_witness()
    allowed = router._authorization_predicate(ACTOR)
    if allowed is None:
        raise ValueError("principal source policy unavailable")
    roots: list[str] = []
    leaves: dict[str, list[str]] = {
        field_id: [] for field_id, _ in domain.fields
    }
    root_field = f"{domain.name}.{domain.identity}"
    root_schema = {"type": domain.identity_kind}
    for tool in router.registry.tools():
        if tool.source_type != domain.name or tool.license != LICENSE:
            continue
        for ep in tool.endpoints:
            if (
                ep.read_only is not True or ep.destructive is True
                or not allowed(tool, ep)
            ):
                continue
            available = router.planner.availability_predicate
            if available is not None and not available(tool, ep):
                continue
            scoped = router._data_scope_endpoint_view(ACTOR, tool, ep)
            if scoped is None:
                continue
            route = f"{tool.key}.{ep.name}"
            if (
                not scoped.parameters
                and scoped.output_schema == {
                    "type": "object",
                    "properties": {domain.identity: root_schema},
                    "required": [domain.identity],
                }
                and sum(
                    f.name == domain.identity
                    and f.semantic_id == root_field
                    and f.identifier is True
                    and f.json_schema == root_schema
                    for f in scoped.output_fields
                ) == 1
            ):
                roots.append(route)
            if len(scoped.parameters) != 1:
                continue
            parameter = scoped.parameters[0]
            if (
                parameter.name != domain.identity
                or parameter.semantic_id != root_field
                or parameter.required is not True
                or parameter.json_schema != root_schema
                or scoped.input_schema != {
                    "type": "object",
                    "properties": {domain.identity: root_schema},
                    "required": [domain.identity],
                }
            ):
                continue
            for semantic, _ in domain.fields:
                if any(
                    f.semantic_id == f"{domain.name}.{semantic}"
                    and f.json_schema == {"type": "string"}
                    for f in scoped.output_fields
                ):
                    leaves[semantic].append(route)
    router._check_retrieval_authority_witness(witness)
    lfield, rfield = (field_id for field_id, _ in domain.fields)
    return tuple(sorted(
        (root, left, right)
        for root in roots
        for left in leaves[lfield]
        for right in leaves[rfield]
        if len({root, left, right}) == 3
    ))


def analyze_multidomain_source(
    *, base_routes: int, mixed_scope: bool,
) -> dict[str, Any]:
    router = build_multidomain_source(base_routes, mixed_scope=mixed_scope)
    actual_size = sum(len(tool.endpoints) for tool in router.registry.tools())
    expected_size = base_routes + 6 * len(DOMAINS)
    if actual_size != expected_size:
        raise ValueError("combined registered native catalog size drift")
    graph = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    if graph.field_index.indexed_route_count != actual_size:
        raise ValueError("native indexed route count drift")

    cases = [(GROUP.source_type, GROUP, ALIASES,
              exhaustive_source_fork_reference(router))]
    for domain in DOMAINS:
        cases.append((
            domain.name, domain.group(), domain.aliases,
            source_scan_oracle(router, domain),
        ))
    rows: list[dict[str, Any]] = []
    for label, group, aliases, oracle in cases:
        if len(oracle) != 1 or len(set(oracle[0])) != 3:
            raise ValueError("independent original source fork ambiguous or absent")
        expected = frozenset(oracle[0])
        for language, query in zip(("en", "ko", "ja"), aliases, strict=True):
            lexical, visible_cost = scoped_source_lexical_k5(
                router, query=query, group=group,
            )
            native = graph.lookup_shared_root_forks(
                router, query, group=group, principal=ACTOR, k=MAX_K,
            )
            g5_paths = tuple(
                (p.root_route_id, *p.branch_route_ids)
                for p in native.candidates
            )
            if (
                native.status != "complete"
                or native.requested_k != MAX_K
                or g5_paths != oracle
                or native.executable_authority
                or native.independent_quality_evidence
            ):
                raise ValueError("G5 cannot prove original source task")
            graph_routes = frozenset(
                route for path in g5_paths for route in path
            )
            if (
                len(graph_routes) > MAX_K
                or len(lexical) > MAX_K
                or not graph_routes.issubset(visible_cost)
                or not set(lexical).issubset(visible_cost)
            ):
                raise ValueError("unscoped or over-K source model exposure")
            g5_hit = expected.issubset(graph_routes)
            lexical_hit = expected.issubset(lexical)
            rows.append({
                "domain": label, "language": language,
                "g5_source_complete": g5_hit,
                "lexical_source_complete": lexical_hit,
                "shared_complete_cost_eligible": g5_hit and lexical_hit,
                "g5_route_count": len(graph_routes),
                "lexical_route_count": len(lexical),
                "g5_schema_bytes": sum(visible_cost[r] for r in graph_routes),
                "lexical_schema_bytes": sum(visible_cost[r] for r in lexical),
                "same_host_scope_k": True,
            })

    # Test live current health independently in EVERY source domain. Neither
    # method may leak a previously indexed but now revoked consumer route.
    for _label, group, aliases, oracle in cases:
        forbidden = oracle[0][2]
        tool_key = forbidden.rsplit(".", 1)[0]
        router.planner.availability_predicate = (
            lambda tool, _ep, excluded=tool_key: tool.key != excluded
        )
        lexical, budget = scoped_source_lexical_k5(
            router, query=aliases[0], group=group,
        )
        g5 = graph.lookup_shared_root_forks(
            router, aliases[0], group=group, principal=ACTOR, k=MAX_K,
        )
        if (
            forbidden in lexical or forbidden in budget
            or g5.candidates or g5.status != "no_proven_hit"
        ):
            raise ValueError("revoked original source still disclosed")
        router.planner.availability_predicate = None

    both = [r for r in rows if r["shared_complete_cost_eligible"]]
    g5_only = sum(r["g5_source_complete"] and not r["lexical_source_complete"] for r in rows)
    lexical_only = sum(not r["g5_source_complete"] and r["lexical_source_complete"] for r in rows)
    neither = sum(not r["g5_source_complete"] and not r["lexical_source_complete"] for r in rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_tier": "E0_MULTIDOMAIN_DEVELOPER_SOURCE_NOT_E2",
        "base_registered_routes": base_routes,
        "actual_registered_native_routes": actual_size,
        "mixed_scope": mixed_scope,
        "strict_k": MAX_K,
        "three_source_domains": [GROUP.source_type, *(d.name for d in DOMAINS)],
        "rows": rows,
        "paired": {
            "both_complete": len(both),
            "g5_only_complete": g5_only,
            "lexical_only_complete": lexical_only,
            "neither_complete": neither,
            "quality_conditioned_g5_schema_bytes": sum(r["g5_schema_bytes"] for r in both),
            "quality_conditioned_lexical_schema_bytes": sum(
                r["lexical_schema_bytes"] for r in both
            ),
        },
        "all_domain_revocations_denied": True,
        "model_token_measurement": False,
        "actual_provider_calls": False,
        "independent_e2_qualified": False,
        "release_qualified": False,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-routes", type=int, choices=SIZES, required=True)
    p.add_argument("--mixed-scope", action="store_true")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    report = analyze_multidomain_source(
        base_routes=args.base_routes, mixed_scope=args.mixed_scope,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False,
    ) + "\n", encoding="utf-8")
    print(json.dumps({
        "actual_registered_native_routes": report["actual_registered_native_routes"],
        "paired": report["paired"],
        "independent_e2_qualified": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
