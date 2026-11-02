"""One authentic four-publisher OpenAPI catalog, without execution/gold E2.

All four provider documents come from immutable existing upstream source
fixtures. This research-only E0 script never invokes publisher endpoints.
"""
from __future__ import annotations

import re
from collections import Counter
from time import perf_counter
from typing import Any

from schemarouter import AuthorizationPolicy, PrincipalContext, SchemaRouter, ToolSpec
from schemarouter.adapters import tool_from_openapi
from schemarouter.capability_contracts import CapabilityFieldContract
from schemarouter.errors import PolicyViolationError
from schemarouter.field_group_retrieval import NativeDeclaredFieldGroup
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from schemarouter.registry import unregister_if_current
from scripts.research_official_github_get_e0 import (
    _local_snapshot,
    compile_official_github_get_bundle_e0,
)
from scripts.research_official_openai_get_e0 import scope_original_http_operation_source
from scripts.research_official_openai_operations_e0 import (
    _HTTP_METHODS,
    _UNSUPPORTED_PATHS,
    _other_providers,
    _source_document,
)
from scripts.research_official_openapi_snapshot_e0 import REVIEWED_READS

EVIDENCE_TIER = "E0_FOUR_ORIGINAL_PUBLISHERS_1009_NATIVE_OPERATIONS_NO_E2"


def _compile_original_openai_http_publisher_e0(document: dict[str, Any]) -> ToolSpec:
    """Bundle independently source-verified OpenAI operations by publisher."""
    paths = document.get("paths")
    if not isinstance(paths, dict) or not all(
        isinstance(item, dict) for item in paths.values()
    ):
        raise ValueError("original OpenAI HTTP paths missing")
    operations = [
        (path, method, item[method])
        for path, item in sorted(paths.items())
        for method in sorted(_HTTP_METHODS & item.keys())
    ]
    if len(operations) != 371 or Counter(m.upper() for _, m, _ in operations) != {
        "GET": 163, "POST": 155, "DELETE": 53,
    }:
        raise ValueError("original OpenAI method inventory drift")
    if {p for p, _, _ in operations if "?" in p} != _UNSUPPORTED_PATHS:
        raise ValueError("original OpenAI literal query exclusions changed")

    unsupported_media = {
        (path, method)
        for path, method, operation in operations if "?" not in path
        and isinstance(operation, dict)
        and isinstance((body := operation.get("requestBody")), dict)
        and isinstance((content := body.get("content")), dict)
        and bool(content) and "application/json" not in content
    }
    if len(unsupported_media) != 9 or any(
        method != "post" for _, method in unsupported_media
    ):
        raise ValueError("original OpenAI non-JSON operation exclusions changed")

    endpoints = []
    source_ids: set[str] = set()
    method_counts: Counter[str] = Counter()
    for serial, (path, method, original) in enumerate(operations):
        if "?" in path or (path, method) in unsupported_media:
            continue
        scoped = scope_original_http_operation_source(document, path, method)
        converted = tool_from_openapi(f"openai_original_http_{serial:03d}", scoped)
        if len(converted.endpoints) != 1 or not isinstance(original, dict):
            raise ValueError("original OpenAI operation conversion cardinality changed")
        endpoint = converted.endpoints[0]
        operation_id = original.get("operationId")
        if (
            not isinstance(operation_id, str) or not operation_id
            or operation_id in source_ids
            or endpoint.name != operation_id or endpoint.path != path
            or endpoint.method != method.upper()
            or endpoint.read_only is not (method == "get")
            or endpoint.destructive is not (method == "delete")
            or converted.source_type or converted.license
            or any(field.semantic_id for field in endpoint.output_fields)
        ):
            raise ValueError("original OpenAI HTTP source identity or safety weakened")
        required_path = {
            parameter.name for parameter in endpoint.parameters
            if parameter.required and parameter.location == "path"
        }
        if not set(re.findall(r"\{([^{}]+)\}", path)).issubset(required_path):
            raise ValueError("original OpenAI required path argument was discarded")
        if original.get("security", document.get("security")) and not endpoint.auth_requirements:
            raise ValueError("original OpenAI declared authentication was discarded")
        body = original.get("requestBody")
        if (
            isinstance(body, dict) and body.get("required") is True
            and isinstance(body.get("content"), dict)
            and "application/json" in body["content"]
            and endpoint.execution_metadata.get("request_body_required") is not True
        ):
            raise ValueError("original OpenAI mandatory JSON body was discarded")
        endpoints.append(endpoint)
        source_ids.add(operation_id)
        method_counts[method.upper()] += 1

    if len(source_ids) != 355 or method_counts != {"GET": 161, "POST": 142, "DELETE": 52}:
        raise ValueError("original OpenAI supported operation inventory drift")
    return ToolSpec(
        name="openai_original_http_source",
        description="Original OpenAI HTTP structural source; no invocation authorization",
        endpoints=endpoints,
        execution_metadata={"adapter": "openapi"},
    )


def compile_four_original_provider_tools_e0() -> tuple[ToolSpec, ToolSpec, ToolSpec, ToolSpec]:
    """Build four actual original-publisher tools, not two summed receipts."""
    openai = _compile_original_openai_http_publisher_e0(_source_document())
    github = compile_official_github_get_bundle_e0(_local_snapshot())
    ollama, pirate = _other_providers()
    tools = (openai, github, ollama, pirate)
    if (
        len({tool.key for tool in tools}) != 4
        or [len(tool.endpoints) for tool in tools] != [355, 651, 2, 1]
    ):
        raise ValueError("four original publishers have duplicate identities")
    return tools


def _source_route_manifest(
    openai_source: dict[str, Any],
    github_source: dict[str, Any],
    tools: tuple[ToolSpec, ToolSpec, ToolSpec, ToolSpec],
) -> set[tuple[str, str]]:
    """Independent publisher path→operationId oracle, not converted endpoints."""
    openai, github, ollama, pirate = tools
    original_openai = {
        (openai.key, operation["operationId"])
        for path, item in openai_source["paths"].items()
        for method, operation in item.items() if method in _HTTP_METHODS
        and "?" not in path and not (
            isinstance((body := operation.get("requestBody")), dict)
            and isinstance((content := body.get("content")), dict)
            and bool(content) and "application/json" not in content
        )
    }
    original_github = {
        (github.key, item["get"]["operationId"])
        for item in github_source["paths"].values() if "get" in item
    }
    # These two source converters already validate these exact raw/pinned
    # publisher IDs against their immutable original OpenAPI documents.
    original_smaller = {
        *((ollama.key, operation_id) for operation_id, _ in REVIEWED_READS.values()),
        (pirate.key, "Weather"),
    }
    manifest = original_openai | original_github | original_smaller
    if (
        len(original_openai) != 355 or len(original_github) != 651
        or len(original_smaller) != 3 or len(manifest) != 1009
    ):
        raise ValueError("independent original four-publisher route inventory drift")
    return manifest


def _verify_catalog_stage(
    router: SchemaRouter,
    index: NativeSchemaGraphIndex,
    expected_manifest: set[tuple[str, str]],
) -> float:
    start = perf_counter()
    full = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    build_ms = (perf_counter() - start) * 1000
    lhs, rhs = index.field_index, full.field_index
    if (
        lhs.registry_version != rhs.registry_version
        or lhs.snapshot_id != rhs.snapshot_id
        or lhs.indexed_route_count != len(expected_manifest)
        or lhs.route_locations != rhs.route_locations
        or lhs.route_fingerprints != rhs.route_fingerprints
        or lhs.tool_fingerprints != rhs.tool_fingerprints
        or lhs.postings != rhs.postings
        or set(lhs.route_locations.values()) != expected_manifest
        or index.graph != full.graph
        or index.native_root_count != full.native_root_count
        or index.native_consumer_count != full.native_consumer_count
        or lhs.postings or index.graph.edges
        or index.native_root_count or index.native_consumer_count
    ):
        raise ValueError("four-provider source journal / full rebuild / manifest mismatch")
    return build_ms


def audit_original_four_provider_native_churn_e0() -> dict[str, Any]:
    """Prove 1,009→358→1,009→654→1,009 on one actual native registry."""
    openai_source = _source_document()
    github_source = _local_snapshot()
    tools = (
        _compile_original_openai_http_publisher_e0(openai_source),
        compile_official_github_get_bundle_e0(github_source),
        *_other_providers(),
    )
    openai, github, _, _ = tools
    manifest = _source_route_manifest(openai_source, github_source, tools)
    github_routes = {(github.key, e.name) for e in github.endpoints}
    openai_routes = {(openai.key, e.name) for e in openai.endpoints}
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(default_effect="deny"))
    for tool in tools:
        router.add_tool(tool)
    if len(tuple(router.registry.tools())) != 4:
        raise ValueError("original four-provider registry cardinality changed")

    principal = PrincipalContext(subject="no-original-publisher-grants", roles=())
    denied = router._authorization_predicate(principal)
    if denied is None or any(denied(t, e) for t in tools for e in t.endpoints):
        raise ValueError("source-owner metadata incorrectly granted tool execution")
    query = "never independent publisher semantic authority"
    group = NativeDeclaredFieldGroup(
        aliases=(query,),
        required_fields=(CapabilityFieldContract(
            semantic_id="research.unreviewed-original-four-publisher-semantic",
            json_schema={"type": "string"},
        ),),
    )
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    route_counts: list[int] = []
    versions: set[int] = set()
    snapshots: set[str] = set()
    full_build_ms: list[float] = []
    journal_refresh_ms: list[float] = []
    stale_rejections = 0
    for action in ("initial", "remove_github", "restore_github", "remove_openai", "restore_openai"):
        if action != "initial":
            provider = github if "github" in action else openai
            if action.startswith("remove_"):
                unregister_if_current(
                    router.registry, provider.key,
                    expected_fingerprint=router.registry.get(provider.key).fingerprint,
                    expected_version=router.registry.version,
                )
            else:
                router.add_tool(provider)
            try:
                index.lookup(router, query, group=group, principal=principal)
            except PolicyViolationError:
                stale_rejections += 1
            else:
                raise ValueError("stale four-provider source index was accepted")
            refresh_start = perf_counter()
            index = NativeSchemaGraphIndex.refresh_from_inmemory_journal(index, router.registry)
            journal_refresh_ms.append((perf_counter() - refresh_start) * 1000)

        expected = manifest
        if action == "remove_github":
            expected = manifest - github_routes
        elif action == "remove_openai":
            expected = manifest - openai_routes
        full_build_ms.append(_verify_catalog_stage(router, index, expected))
        if index.lookup(router, query, group=group, principal=principal).status != "no_proven_hit":
            raise ValueError("unreviewed four-provider semantics unexpectedly promoted")
        route_counts.append(index.field_index.indexed_route_count)
        versions.add(router.registry.version)
        snapshots.add(index.field_index.snapshot_id)

    if route_counts != [1009, 358, 1009, 654, 1009] or stale_rejections != 4:
        raise ValueError("four-provider source churn stage counts changed")
    try:
        import resource

        peak_rss: int | None = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except ImportError:  # Platform without POSIX resource accounting.
        peak_rss = None
    return {
        "evidence_tier": EVIDENCE_TIER,
        "original_publisher_count": len(tools),
        "original_source_route_counts": [len(t.endpoints) for t in tools],
        "original_methods": dict(Counter(e.method for t in tools for e in t.endpoints)),
        "mixed_native_route_counts": route_counts,
        "registry_versions": len(versions),
        "index_snapshots": len(snapshots),
        "stale_index_rejections": stale_rejections,
        "journal_matches_full_rebuild": True,
        "original_source_manifest_matches": True,
        "untrusted_semantic_postings": len(index.field_index.postings),
        "unreviewed_typed_graph_edges": len(index.graph.edges),
        "performance_observed_not_sla": {
            "full_rebuild_ms": full_build_ms,
            "journal_refresh_ms": journal_refresh_ms,
            "process_peak_rss_raw": peak_rss,
        },
        "provider_runtime_calls": 0,
        "execution_authority": False,
        "publisher_gold_verified": False,
        "independent_e2_qualified": False,
        "default_routing_changed": False,
    }
