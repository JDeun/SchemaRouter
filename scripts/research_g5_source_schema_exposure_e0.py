"""#1560 G5 source-verified original schema cost assay; E0 synthetic only.

No duplicate retrieval/selection: call the existing native indexed fork
lookup and separately verify against the existing source-native exhaustive
oracle. Catalog-size exposure is contextual **bytes**, NOT measured LLM
tokens, and unbounded FULL is NOT an equal-K quality baseline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import resource
import time
from pathlib import Path
from typing import Any

from schemarouter import EndpointSpec, SchemaRouter, ToolSpec
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    ALIASES,
    GROUP,
    LEFT,
    RIGHT,
    ROOT,
    build_fixture,
    exhaustive_source_fork_reference,
)

SCHEMA_VERSION = "native-g5-source-verified-schema-exposure-e0-v1"
SIZES = (500, 5000)
EXPECTED = ((ROOT, LEFT, RIGHT),)
MAX_K = 5


def _visible_original_contract_bytes(
    tool: ToolSpec, endpoint: EndpointSpec,
) -> int:
    """Only a current source-owned scoped endpoint, never hidden fields."""
    if not isinstance(tool, ToolSpec) or not isinstance(endpoint, EndpointSpec):
        raise ValueError("source-native current tool and scoped endpoint required")
    payload = {
        "tool": {
            "name": tool.name,
            "source_type": tool.source_type,
            "license": tool.license,
            "description": tool.description,
        },
        "endpoint": endpoint.model_dump(mode="json", exclude_none=True),
    }
    return len(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8"))


def authorized_source_contract_budget(
    router: SchemaRouter,
) -> tuple[dict[str, int], str]:
    """Return current principal-readable source contracts, not raw source data.

    FULL budget deliberately includes unrelated authorized source routes.
    It is an unbounded reference only. Callers MUST NOT report its relative
    size as a matched-K5 precision/cost superiority.
    """
    if not isinstance(router, SchemaRouter):
        raise ValueError("original router required")
    witness = router._retrieval_authority_witness()
    predicate = router._authorization_predicate(ACTOR)
    if predicate is None:
        raise ValueError("trusted read-only principal source policy required")
    selected: dict[str, int] = {}
    for tool in router.registry.tools():
        for endpoint in tool.endpoints:
            if (
                endpoint.read_only is not True or endpoint.destructive is True
                or not predicate(tool, endpoint)
            ):
                continue
            if router.planner.availability_predicate is not None and not (
                router.planner.availability_predicate(tool, endpoint)
            ):
                continue
            visible = router._data_scope_endpoint_view(ACTOR, tool, endpoint)
            if visible is None:
                continue
            route = f"{tool.key}.{endpoint.name}"
            if route in selected:
                raise ValueError("duplicate source-native model route")
            selected[route] = _visible_original_contract_bytes(tool, visible)
    router._check_retrieval_authority_witness(witness)
    # Digest only current public route identifiers and lengths, no actual
    # source fields/policy contents/raw observations in the research JSON.
    canonical = json.dumps(
        sorted(selected.items()), separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return selected, hashlib.sha256(canonical).hexdigest()


def evaluate_fixture(
    *, registered_routes: int, mixed_scope: bool = False,
) -> dict[str, Any]:
    if registered_routes not in SIZES or type(registered_routes) is not int:
        raise ValueError("G5 schema assay uses only preregistered catalog sizes")
    if type(mixed_scope) is not bool:
        raise ValueError("mixed-scope boolean required")
    router = build_fixture(registered_routes, mixed_scope=mixed_scope)
    witness = router._retrieval_authority_witness()
    started = time.perf_counter_ns()
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    index_build_ms = (time.perf_counter_ns() - started) / 1_000_000
    oracle = exhaustive_source_fork_reference(router)
    if oracle != EXPECTED:
        raise ValueError("original-source fork oracle invalid or changed")
    budget, public_budget_digest = authorized_source_contract_budget(router)
    if len(budget) > registered_routes or len(budget) < MAX_K:
        raise ValueError("unexpected authorized native source view")
    if index.field_index.indexed_route_count != registered_routes:
        raise ValueError("source route count drift")

    oracle_menu = frozenset(route for triple in oracle for route in triple)
    if len(oracle_menu) != 3 or not oracle_menu.issubset(budget):
        raise ValueError("original verified fork lacks current eligible fields")
    oracle_bytes = sum(budget[route] for route in oracle_menu)
    full_bytes = sum(budget.values())
    if oracle_bytes <= 0 or full_bytes < oracle_bytes:
        raise ValueError("invalid original source contract envelope")

    rows: list[dict[str, Any]] = []
    for language, query in zip(("en", "ko", "ja"), ALIASES, strict=True):
        t0 = time.perf_counter_ns()
        selection = index.lookup_shared_root_forks(
            router, query, group=GROUP, principal=ACTOR, k=MAX_K,
        )
        lookup_ms = (time.perf_counter_ns() - t0) / 1_000_000
        found = tuple(
            (candidate.root_route_id, *candidate.branch_route_ids)
            for candidate in selection.candidates
        )
        if (
            selection.status != "complete"
            or selection.requested_k != MAX_K
            or selection.executable_authority
            or selection.independent_quality_evidence
            or selection.qualified_fork_count != 1
            or found != oracle
        ):
            raise ValueError("G5 native output differs from independent source oracle")
        selected = frozenset(route for triple in found for route in triple)
        if (
            selected != oracle_menu
            or len(selected) > MAX_K
            or not selected.issubset(budget)
        ):
            raise ValueError("G5 returned unqualified or out-of-budget native menu")
        graph_bytes = sum(budget[route] for route in selected)
        if graph_bytes != oracle_bytes:
            raise ValueError("G5 menu bytes differ from original-source exact oracle")
        rows.append({
            "language": language,
            "qualified_g5_fork_count": selection.qualified_fork_count,
            "qualified_distinct_native_routes": len(selected),
            "source_oracle_exact_match": True,
            "typed_producer_consumer_binding": True,
            "scope_approved_k5": True,
            "g5_original_source_schema_bytes": graph_bytes,
            "same_success_oracle_schema_bytes": oracle_bytes,
            "unbounded_full_principal_source_schema_bytes": full_bytes,
            "g5_native_lookup_wall_ms": round(lookup_ms, 4),
        })
    router._check_retrieval_authority_witness(witness)
    # Health refusal proves that cached typed source graph doesn't release
    # a stale route if its *original* provider availability changes.
    router.planner.availability_predicate = (
        lambda tool, _endpoint: tool.key != "fork_owner"
    )
    for query in ALIASES:
        denied = index.lookup_shared_root_forks(
            router, query, group=GROUP, principal=ACTOR, k=MAX_K,
        )
        if denied.candidates or denied.status != "no_proven_hit":
            raise ValueError("G5 source authorization/availability drift disclosed")
    router.planner.availability_predicate = None
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_tier": "E0_SYNTHETIC_ORIGINAL_SOURCE_G5_NOT_EXTERNAL",
        "registered_native_routes": registered_routes,
        "principal_authorized_visible_routes": len(budget),
        "mixed_source_scope_and_contract_decoys": mixed_scope,
        "strict_k": MAX_K,
        "supported_language_query_count": len(rows),
        "frozen_original_source_budget_digest": public_budget_digest,
        "index_build_wall_ms": round(index_build_ms, 4),
        "rows": rows,
        "same_snapshot_health_revocation_denied": True,
        "all_model_tokens_measured": False,
        "unbounded_full_is_matched_k5_agent_control": False,
        "independent_e2_qualified": False,
        "release_qualified": False,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "peak_process_rss_kib": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registered-routes", type=int, choices=SIZES, required=True)
    p.add_argument("--mixed-scope", action="store_true")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    record = evaluate_fixture(
        registered_routes=args.registered_routes, mixed_scope=args.mixed_scope,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "registered_native_routes": record["registered_native_routes"],
        "mixed_source_scope_and_contract_decoys": record["mixed_source_scope_and_contract_decoys"],
        "all_g5_routes_source_oracle_qualified": all(
            row["source_oracle_exact_match"] for row in record["rows"]
        ),
        "independent_e2_qualified": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
