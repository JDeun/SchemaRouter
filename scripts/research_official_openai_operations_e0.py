"""Real OpenAI GET/POST/DELETE OpenAPI operations through the existing native journal.

Source-only offline #1560 E0 audit: no network, provider execution, semantic
attestation, host permissions, external gold or model/agent result.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from schemarouter import AuthorizationPolicy, PrincipalContext, SchemaRouter, ToolSpec
from schemarouter.adapters import tool_from_openapi
from schemarouter.capability_contracts import CapabilityFieldContract
from schemarouter.errors import PolicyViolationError
from schemarouter.field_group_retrieval import NativeDeclaredFieldGroup
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from schemarouter.registry import unregister_if_current
from scripts.research_cross_provider_openapi_e0 import (
    PIRATE_COMMIT,
    compile_official_pirate_weather_source,
)
from scripts.research_official_openai_get_e0 import (
    PUBLISHER_COMMIT,
    parse_pinned_openai_source,
    scope_original_http_operation_source,
)
from scripts.research_official_openapi_snapshot_e0 import (
    FIXTURE_DIR,
    compile_official_ollama_snapshot,
)
from scripts.research_official_openapi_snapshot_e0 import (
    UPSTREAM_COMMIT as OLLAMA_COMMIT,
)

_HTTP_METHODS = frozenset({"get", "post", "delete"})
_UNSUPPORTED_PATHS = frozenset({
    "/responses?beta=true",
    "/responses/{response_id}?beta=true",
    "/responses/{response_id}/cancel?beta=true",
    "/responses/compact?beta=true",
    "/responses/{response_id}/input_items?beta=true",
    "/responses/input_tokens?beta=true",
})
EVIDENCE_TIER = "E0_ORIGINAL_THREE_PROVIDER_ALL_NATIVE_HTTP_SOURCE_JOURNAL_NO_E2"


def _source_document() -> dict[str, Any]:
    base = FIXTURE_DIR / f"openai-openapi-{PUBLISHER_COMMIT[:8]}"
    return parse_pinned_openai_source(
        Path(str(base) + "-openapi.yaml.gz").read_bytes(),
        Path(str(base) + "-LICENSE.txt").read_bytes(),
    )


def _other_providers() -> tuple[ToolSpec, ToolSpec]:
    ollama = FIXTURE_DIR / f"ollama-{OLLAMA_COMMIT[:8]}"
    pirate = FIXTURE_DIR / f"pirate-weather-{PIRATE_COMMIT[:8]}"
    return (
        compile_official_ollama_snapshot(
            Path(str(ollama) + "-openapi.yaml").read_bytes(),
            Path(str(ollama) + "-LICENSE.txt").read_bytes(),
        ),
        compile_official_pirate_weather_source(
            Path(str(pirate) + "-openapi.yaml").read_bytes(),
            Path(str(pirate) + "-LICENSE.txt").read_bytes(),
        ),
    )


def _verify_current_source_index(
    router: SchemaRouter,
    index: NativeSchemaGraphIndex,
    expected_routes: set[tuple[str, str]],
) -> None:
    """Prove current journal against fresh native rebuild AND original manifest."""
    rebuilt = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    lhs, rhs = index.field_index, rebuilt.field_index
    if (
        lhs.registry_version != rhs.registry_version
        or lhs.snapshot_id != rhs.snapshot_id
        or lhs.indexed_route_count != len(expected_routes)
        or lhs.route_locations != rhs.route_locations
        or lhs.route_fingerprints != rhs.route_fingerprints
        or lhs.tool_fingerprints != rhs.tool_fingerprints
        or lhs.postings != rhs.postings
        or set(lhs.route_locations.values()) != expected_routes
        or index.graph != rebuilt.graph
        or index.native_root_count != rebuilt.native_root_count
        or index.native_consumer_count != rebuilt.native_consumer_count
        or lhs.postings or index.graph.edges
        or index.native_root_count or index.native_consumer_count
    ):
        raise ValueError("original HTTP source journal, registry or full-build mismatch")


def audit_official_openai_operations_churn_e0() -> dict[str, Any]:
    """355 represented original operations and one real DELETE removal/restore.

    This audits only native schema registration; no model, tool or provider
    invocation can be reached through this diagnostic.
    """
    document = _source_document()
    paths = document["paths"]
    if not all(isinstance(entry, dict) for entry in paths.values()):
        raise ValueError("original HTTP method source declarations invalid")
    operations = [
        (path, method, entry[method])
        for path, entry in sorted(paths.items())
        for method in sorted(_HTTP_METHODS & entry.keys())
    ]
    original_counts = Counter(method.upper() for _, method, _ in operations)
    if original_counts != {"GET": 163, "POST": 155, "DELETE": 53}:
        raise ValueError("original HTTP operation inventory changed")
    unsupported_paths = frozenset(path for path, _, _ in operations if "?" in path)
    if unsupported_paths != _UNSUPPORTED_PATHS:
        raise ValueError("original query-bearing operation inventory changed")
    skipped = sum("?" in path for path, _, _ in operations)
    if len(operations) != 371 or skipped != 7:
        raise ValueError("original HTTP source operation inventory drift")
    # The existing native OpenAPI converter represents JSON bodies only.
    # Never count multipart/SDP-only operations as usable source contracts:
    # some require a file and would silently lose that mandatory input.
    unsupported_bodies = {
        (path, method)
        for path, method, operation in operations if "?" not in path
        and isinstance(operation, dict)
        and isinstance((body := operation.get("requestBody")), dict)
        and isinstance((content := body.get("content")), dict)
        and bool(content) and "application/json" not in content
    }
    if len(unsupported_bodies) != 9 or any(
        method != "post" for _, method in unsupported_bodies
    ):
        raise ValueError("original unsupported HTTP media-type inventory drift")

    router = SchemaRouter(authorization_policy=AuthorizationPolicy(default_effect="deny"))
    native_counts: Counter[str] = Counter()
    expected_openai_routes: set[tuple[str, str]] = set()
    write_to_churn: ToolSpec | None = None
    for serial, (path, method, original) in enumerate(operations):
        if "?" in path or (path, method) in unsupported_bodies:
            continue  # Invalid literal paths or non-JSON-only request bodies.
        projected = scope_original_http_operation_source(document, path, method)
        native = tool_from_openapi(f"openai_official_http_{serial:03d}", projected)
        if len(native.endpoints) != 1 or not isinstance(original, dict):
            raise ValueError("original HTTP operation changed converter cardinality")
        endpoint = native.endpoints[0]
        if (
            endpoint.name != original.get("operationId")
            or endpoint.method != method.upper() or endpoint.path != path
            or endpoint.read_only is not (method == "get")
            or endpoint.destructive is not (method == "delete")
            or native.source_type or native.license
            or any(field.semantic_id for field in endpoint.output_fields)
        ):
            raise ValueError("original HTTP method/source or no-grant boundary changed")
        required_path = {
            parameter.name for parameter in endpoint.parameters
            if parameter.location == "path" and parameter.required
        }
        if not set(re.findall(r"\{([^{}]+)\}", path)).issubset(required_path):
            raise ValueError("original HTTP required path input was weakened")
        source_security = original.get("security", document.get("security"))
        if source_security and not endpoint.auth_requirements:
            raise ValueError("original HTTP owner authentication was weakened")
        body = original.get("requestBody")
        if (
            isinstance(body, dict) and body.get("required") is True
            and isinstance(body.get("content"), dict)
            and "application/json" in body["content"]
            and endpoint.execution_metadata.get("request_body_required") is not True
        ):
            raise ValueError("original required JSON request body was discarded")
        router.add_tool(native)
        expected_openai_routes.add((native.key, original["operationId"]))
        native_counts[method.upper()] += 1
        if path == "/models/{model}" and method == "delete":
            write_to_churn = native
    if (
        native_counts != {"GET": 161, "POST": 142, "DELETE": 52}
        or write_to_churn is None or len(expected_openai_routes) != 355
    ):
        raise ValueError("original HTTP native method coverage drift")

    other = _other_providers()
    for tool in other:
        router.add_tool(tool)
    expected = expected_openai_routes | {
        (tool.key, endpoint.name) for tool in other for endpoint in tool.endpoints
    }
    if len(expected) != 358:
        raise ValueError("source publisher native manifest collision")
    principal = PrincipalContext(subject="unauthorized-original-provider-audit", roles=())
    authorize = router._authorization_predicate(principal)
    if authorize is None or any(
        authorize(tool, endpoint)
        for tool in router.registry.tools() for endpoint in tool.endpoints
    ):
        raise ValueError("OpenAPI HTTP metadata incorrectly granted tool execution")

    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    unproved_group = NativeDeclaredFieldGroup(
        aliases=("original publisher operation audit",),
        required_fields=(CapabilityFieldContract(
            semantic_id="research.no-independent-provider-semantic-gold",
            json_schema={"type": "string"},
        ),),
    )
    route_counts: list[int] = []
    versions: set[int] = set()
    snapshot_ids: set[str] = set()
    stale_count = 0
    for stage in ("initial", "removed", "restored"):
        if stage != "initial":
            if stage == "removed":
                unregister_if_current(
                    router.registry, write_to_churn.key,
                    expected_fingerprint=router.registry.get(write_to_churn.key).fingerprint,
                    expected_version=router.registry.version,
                )
            else:
                router.add_tool(write_to_churn)
            try:
                index.lookup(
                    router, "original publisher operation audit",
                    group=unproved_group, principal=principal,
                )
            except PolicyViolationError:
                stale_count += 1
            else:
                raise ValueError("stale original HTTP operation index was accepted")
            index = NativeSchemaGraphIndex.refresh_from_inmemory_journal(
                index, router.registry,
            )
        stage_expected = expected - {
            (write_to_churn.key, write_to_churn.endpoints[0].name),
        } if stage == "removed" else expected
        _verify_current_source_index(router, index, stage_expected)
        if index.lookup(
            router, "original publisher operation audit",
            group=unproved_group, principal=principal,
        ).status != "no_proven_hit":
            raise ValueError("unreviewed original publisher method promoted to retrieval")
        versions.add(router.registry.version)
        snapshot_ids.add(index.field_index.snapshot_id)
        route_counts.append(index.field_index.indexed_route_count)

    return {
        "evidence_tier": EVIDENCE_TIER,
        "source_revision": PUBLISHER_COMMIT,
        "original_source_operation_count": len(operations),
        "unsupported_literal_query_operation_count": skipped,
        "unsupported_non_json_body_operation_count": len(unsupported_bodies),
        "native_method_counts": dict(native_counts),
        "native_original_operations": len(expected_openai_routes),
        "mixed_provider_route_counts": route_counts,
        "distinct_registry_versions": len(versions),
        "distinct_index_snapshots": len(snapshot_ids),
        "stale_index_rejections": stale_count,
        "required_path_inputs_preserved": True,
        "original_authentication_preserved": True,
        "required_json_bodies_preserved": True,
        "write_methods_never_read_only": True,
        "source_methods_and_operation_ids_preserved": True,
        "journal_rebuild_matches": True,
        "original_source_manifest_matches": True,
        "untrusted_semantic_postings": len(index.field_index.postings),
        "unauthorized_dependency_edges": len(index.graph.edges),
        "provider_runtime_calls": 0,
        "execution_authority": False,
        "publisher_gold_verified": False,
        "independent_e2_qualified": False,
        "default_routing_changed": False,
    }


if __name__ == "__main__":
    print(json.dumps(audit_official_openai_operations_churn_e0(), sort_keys=True))
