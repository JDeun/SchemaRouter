"""Same-K native G5 vs original-source scoped schema lexical E0.

Both arms only see host-authorized visible original source contracts. The
lexical ranking uses the SAME host-declared FieldGroup as typed G5 but no
graph traversal, source join gold, route-ID oracle or execution rights.
Synthetic E0, not model tokens, diverse source E2 or agent success.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from schemarouter import SchemaRouter
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    ALIASES,
    GROUP,
    build_fixture,
    exhaustive_source_fork_reference,
)
from scripts.research_g5_source_schema_exposure_e0 import (
    MAX_K,
    SIZES,
    _visible_original_contract_bytes,
)
from scripts.research_g5_source_schema_exposure_e0 import (
    SCHEMA_VERSION as PARENT_SCHEMA_VERSION,
)

SCHEMA_VERSION = "g5-vs-scoped-lexical-k5-e0-v1"
TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def _tokens(text: str) -> frozenset[str]:
    return frozenset(TOKEN_RE.findall(text.casefold()))


def scoped_source_lexical_k5(
    router: SchemaRouter, *, query: str,
) -> tuple[tuple[str, ...], dict[str, int]]:
    """Rank only currently visible original source contracts, strict K5.

    No knowledge of gold route IDs, edges, joins, or executable authority.
    Source/FieldGroup constraints, as well as both output and input schema
    keywords, are disclosed equally to G5 and this comparator.
    """
    if not isinstance(router, SchemaRouter) or query not in ALIASES:
        raise ValueError("bounded approved source lexical query required")
    witness = router._retrieval_authority_witness()
    policy = router.authorization_policy
    if policy is None:
        raise ValueError("explicit original-source policy required")
    original_policy = (policy.default_effect, repr(policy.rules), repr(policy.data_rules))
    permitted = router._authorization_predicate(ACTOR)
    if permitted is None:
        raise ValueError("trusted reader predicate required")
    wanted = _tokens(" ".join(field.semantic_id for field in GROUP.required_fields))
    demand_semantics = {field.semantic_id for field in GROUP.required_fields}
    query_tokens = _tokens(query)
    scored: list[tuple[int, str]] = []
    costs: dict[str, int] = {}
    for tool in router.registry.tools():
        if tool.source_type != GROUP.source_type or tool.license != GROUP.license:
            continue
        for ep in tool.endpoints:
            if ep.read_only is not True or ep.destructive is True:
                continue
            if not permitted(tool, ep):
                continue
            available = router.planner.availability_predicate
            if available is not None and not available(tool, ep):
                continue
            scoped = router._data_scope_endpoint_view(ACTOR, tool, ep)
            if scoped is None:
                continue
            route_id = f"{tool.key}.{ep.name}"
            if route_id in costs:
                raise ValueError("duplicate original source route")
            costs[route_id] = _visible_original_contract_bytes(tool, scoped)
            output = _tokens(" ".join(
                f"{field.name} {field.semantic_id or ''} "
                + " ".join(field.aliases)
                for field in scoped.output_fields
            ))
            parameter = _tokens(" ".join(
                f"{p.name} {p.semantic_id or ''}" for p in scoped.parameters
            ))
            label = _tokens(" ".join((
                tool.name, tool.description, ep.name, ep.description,
            )))
            exact = sum(
                f.semantic_id in demand_semantics for f in scoped.output_fields
            )
            score = (
                20 * exact
                + 3 * len(wanted & output)
                + 2 * len(query_tokens & (label | output))
                + len(wanted & (parameter | label))
            )
            if score > 0:
                scored.append((score, route_id))
    router._check_retrieval_authority_witness(witness)
    current = router.authorization_policy
    if (
        current is None
        or (current.default_effect, repr(current.rules), repr(current.data_rules))
        != original_policy
    ):
        raise ValueError("source authorization changed during lexical ranking")
    scored.sort(key=lambda row: (-row[0], row[1]))
    selected = tuple(route for _, route in scored[:MAX_K])
    if len(selected) != len(set(selected)) or not set(selected).issubset(costs):
        raise ValueError("source-scoped lexical K5 selection escaped source view")
    return selected, costs


def compare_source_pair(
    *, registered_routes: int, mixed_scope: bool,
) -> dict[str, Any]:
    if type(registered_routes) is not int or registered_routes not in SIZES:
        raise ValueError("predeclared native catalog required")
    if type(mixed_scope) is not bool:
        raise ValueError("mixed scope boolean required")
    router = build_fixture(registered_routes, mixed_scope=mixed_scope)
    oracle = exhaustive_source_fork_reference(router)
    if len(oracle) != 1 or len(set(oracle[0])) != 3:
        raise ValueError("unqualified source topology")
    expected = frozenset(oracle[0])
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    if index.field_index.indexed_route_count != registered_routes:
        raise ValueError("source route count mismatch")

    rows: list[dict[str, Any]] = []
    for lang, query in zip(("en", "ko", "ja"), ALIASES, strict=True):
        selected, budget = scoped_source_lexical_k5(router, query=query)
        g5 = index.lookup_shared_root_forks(
            router, query, group=GROUP, principal=ACTOR, k=MAX_K,
        )
        actual_paths = tuple(
            (c.root_route_id, *c.branch_route_ids) for c in g5.candidates
        )
        if (
            g5.status != "complete" or g5.requested_k != MAX_K
            or g5.qualified_fork_count != 1 or actual_paths != oracle
            or g5.executable_authority or g5.independent_quality_evidence
        ):
            raise ValueError("G5 source scope / original oracle mismatch")
        g5_routes = frozenset(route for path in actual_paths for route in path)
        if not g5_routes.issubset(budget):
            raise ValueError("G5 route omitted in lexical source view")
        if not set(selected).issubset(budget):
            raise ValueError("lexical selected unauthorized original route")
        lexical_set = frozenset(selected)
        lex_complete = expected.issubset(lexical_set)
        g5_complete = expected.issubset(g5_routes)
        if not g5_complete:
            raise ValueError("G5 lost original graph required route")
        rows.append({
            "language": lang,
            "required_original_routes": len(expected),
            "g5_route_count": len(g5_routes),
            "lexical_route_count": len(selected),
            "g5_source_oracle_complete": g5_complete,
            "lexical_source_oracle_complete": lex_complete,
            "g5_schema_bytes": sum(budget[r] for r in g5_routes),
            "lexical_schema_bytes": sum(budget[r] for r in lexical_set),
            "shared_complete_cost_eligible": lex_complete and g5_complete,
            "both_arms_same_scope_and_k": True,
            "both_arms_executable_authority": False,
        })

    # The same original source health revocation must affect BOTH discovery
    # arms: absent original producer/consumer => no provable complete path.
    router.planner.availability_predicate = (
        lambda tool, _ep: tool.key != "fork_owner"
    )
    refused = index.lookup_shared_root_forks(
        router, ALIASES[0], group=GROUP, principal=ACTOR, k=MAX_K,
    )
    lexical_denied, denied_budget = scoped_source_lexical_k5(
        router, query=ALIASES[0],
    )
    if (
        refused.candidates or refused.status != "no_proven_hit"
        or "fork_owner.read" in lexical_denied
        or "fork_owner.read" in denied_budget
    ):
        raise ValueError("stale original source route survived provider revocation")
    return {
        "schema_version": SCHEMA_VERSION,
        "parent_source_exposure_schema": PARENT_SCHEMA_VERSION,
        "evidence_tier": "E0_DEVELOPER_SYNTHETIC_MATCHED_K5",
        "registered_native_routes": registered_routes,
        "mixed_scope": mixed_scope,
        "strict_k": MAX_K,
        "rows": rows,
        "same_snapshot_source_health_denied": True,
        "independent_e2_qualified": False,
        "all_model_tokens_measured": False,
        "actual_agent_final_task_measured": False,
        "release_qualified": False,
        "limitations": [
            "Same owner-authored one-root/two-consumer topology, repeated aliases",
            "Lexical scorer is declared schema-aware, not optimized external SOTA",
            "No model token counts, original callbacks or independent external E2",
            "A 3-route oracle is used only for evaluation, not in either selector",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registered-routes", type=int, choices=SIZES, required=True)
    parser.add_argument("--mixed-scope", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = compare_source_pair(
        registered_routes=args.registered_routes, mixed_scope=args.mixed_scope,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        report, sort_keys=True, indent=2, allow_nan=False,
    ) + "\n", encoding="utf-8")
    print(json.dumps({
        "catalog": report["registered_native_routes"],
        "mixed": report["mixed_scope"],
        "shared_complete": sum(
            row["shared_complete_cost_eligible"] for row in report["rows"]
        ),
        "independent_e2_qualified": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
