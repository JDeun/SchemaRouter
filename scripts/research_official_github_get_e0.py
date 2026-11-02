"""Offline original GitHub REST 651 GET catalog through the canonical native index.

This is publisher-authored SOURCE E0 only, never an API client, source-owner
semantic approval, permission attestation or independent query gold/E2.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
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
from scripts.research_official_openai_get_e0 import scope_original_http_operation_source
from scripts.research_official_openapi_snapshot_e0 import (
    FIXTURE_DIR,
    compile_official_ollama_snapshot,
)
from scripts.research_official_openapi_snapshot_e0 import (
    UPSTREAM_COMMIT as OLLAMA_COMMIT,
)

PUBLISHER_REPO = "github/rest-api-description"
PUBLISHER_COMMIT = "755ee33b4a81d51f6f07a902cce26cbec3b822f2"
UPSTREAM_SPEC_PATH = "descriptions/api.github.com/api.github.com.2022-11-28.json"
ORIGINAL_SPEC_BYTES = 13429427
ORIGINAL_SPEC_SHA256 = "309e30296b212d220ed143beeba216dbb0df11915daf79ee2ed01e06c6c9a586"
ORIGINAL_SPEC_BLOB = "28c3aec115589c92b6c584579b5572b5d6a2d78b"
COMPRESSED_SPEC_BYTES = 962226
COMPRESSED_SPEC_SHA256 = "f65b4b2db635589e713979e50dbcf019d205044a76cfcd71f57f6b6070acfe4d"
ORIGINAL_LICENSE_BYTES = 1063
ORIGINAL_LICENSE_SHA256 = "3243761cbac07e6d169a5a2f4e7c25cc544da85248e735df74c3672e055cc87b"
ORIGINAL_LICENSE_BLOB = "b50625eb63949013cae604b1cadd42cfa1eaf825"
EVIDENCE_TIER = "E0_GENUINE_GITHUB_651_READS_SOURCE_NATIVE_JOURNAL_NO_E2"


def _pinned_bytes(raw: bytes, *, size: int, digest: str, blob: str | None = None) -> None:
    if type(raw) is not bytes or len(raw) != size:
        raise ValueError("pinned original GitHub REST snapshot length mismatch")
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("pinned original GitHub REST snapshot hash mismatch")
    if blob is not None:
        header = b"blob " + str(len(raw)).encode("ascii") + bytes((0,))
        if hashlib.sha1(header + raw).hexdigest() != blob:
            raise ValueError("original GitHub REST publisher Git blob mismatch")


def parse_pinned_github_rest_source(compressed: bytes, license_bytes: bytes) -> dict[str, Any]:
    """Accept only immutable original JSON/license, without modifying source data."""
    _pinned_bytes(compressed, size=COMPRESSED_SPEC_BYTES, digest=COMPRESSED_SPEC_SHA256)
    _pinned_bytes(
        license_bytes, size=ORIGINAL_LICENSE_BYTES,
        digest=ORIGINAL_LICENSE_SHA256, blob=ORIGINAL_LICENSE_BLOB,
    )
    if not license_bytes.startswith(b"MIT License\n\nCopyright (c) 2020 GitHub"):
        raise ValueError("original GitHub MIT publisher notice changed")
    try:
        raw = gzip.decompress(compressed)
    except (OSError, EOFError) as exc:
        raise ValueError("pinned original GitHub REST archive cannot decompress") from exc
    _pinned_bytes(
        raw, size=ORIGINAL_SPEC_BYTES,
        digest=ORIGINAL_SPEC_SHA256, blob=ORIGINAL_SPEC_BLOB,
    )
    source: Any = json.loads(raw)
    if (
        not isinstance(source, dict) or source.get("openapi") != "3.0.3"
        or not isinstance(source.get("info"), dict)
        or source["info"].get("title") != "GitHub v3 REST API"
        or not isinstance(source.get("paths"), dict)
        or not isinstance(source.get("components"), dict)
        or len(source["paths"]) != 823
        or sum(
            isinstance(entry, dict) and "get" in entry
            for entry in source["paths"].values()
        ) != 651
    ):
        raise ValueError("pinned original GitHub REST source operation inventory drift")
    return source


def _local_snapshot() -> dict[str, Any]:
    base = FIXTURE_DIR / f"github-rest-{PUBLISHER_COMMIT[:8]}"
    return parse_pinned_github_rest_source(
        Path(str(base) + "-api.github.com.2022-11-28.json.gz").read_bytes(),
        Path(str(base) + "-LICENSE.md").read_bytes(),
    )


def compile_official_github_get_bundle_e0(document: dict[str, Any]) -> ToolSpec:
    """Group original GET endpoints by their one publisher; no new engine."""
    source_paths = document.get("paths")
    if not isinstance(source_paths, dict) or len(source_paths) != 823:
        raise ValueError("original GitHub publisher path inventory missing")
    gets = tuple(sorted(
        path for path, entry in source_paths.items()
        if isinstance(entry, dict) and "get" in entry
    ))
    if len(gets) != 651 or any("?" in path for path in gets):
        raise ValueError("original GitHub native GET path inventory unexpected")
    endpoints = []
    seen_ids: set[str] = set()
    for serial, path in enumerate(gets):
        projected = scope_original_http_operation_source(document, path, "get")
        native = tool_from_openapi(f"github_official_get_{serial:03d}", projected)
        original_operation = source_paths[path]["get"]
        if len(native.endpoints) != 1 or not isinstance(original_operation, dict):
            raise ValueError("original GitHub native GET converter cardinality changed")
        endpoint = native.endpoints[0]
        source_operation_id = original_operation.get("operationId")
        if (
            not isinstance(source_operation_id, str)
            or not source_operation_id or source_operation_id in seen_ids
            or endpoint.name != source_operation_id or endpoint.path != path
            or endpoint.method != "GET" or endpoint.read_only is not True
            or endpoint.destructive is True
            or native.source_type or native.license
            or any(field.semantic_id for field in endpoint.output_fields)
        ):
            raise ValueError("original GitHub GET method or source ownership weakened")
        required_path = {
            p.name for p in endpoint.parameters if p.required and p.location == "path"
        }
        if not set(re.findall(r"\{([^{}]+)\}", path)).issubset(required_path):
            raise ValueError("original GitHub GET path input requirement weakened")
        original_security = original_operation.get("security", document.get("security"))
        if original_security and not endpoint.auth_requirements:
            raise ValueError("original GitHub GET declared authentication was discarded")
        seen_ids.add(source_operation_id)
        endpoints.append(endpoint)
    return ToolSpec(
        name="github_rest_original_get_source",
        description="Original GitHub REST GET structural source; no invocation authorization",
        endpoints=endpoints,
        execution_metadata={"adapter": "openapi"},
    )


def _previous_two_providers() -> tuple[ToolSpec, ToolSpec]:
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


def _same_original_source_index(
    router: SchemaRouter,
    index: NativeSchemaGraphIndex,
    original_routes: set[tuple[str, str]],
) -> None:
    rebuilt = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    field, fresh = index.field_index, rebuilt.field_index
    if (
        field.snapshot_id != fresh.snapshot_id
        or field.registry_version != fresh.registry_version
        or field.indexed_route_count != len(original_routes)
        or field.route_locations != fresh.route_locations
        or field.route_fingerprints != fresh.route_fingerprints
        or field.tool_fingerprints != fresh.tool_fingerprints
        or field.postings != fresh.postings
        or set(field.route_locations.values()) != original_routes
        or index.graph != rebuilt.graph
        or index.native_root_count != rebuilt.native_root_count
        or index.native_consumer_count != rebuilt.native_consumer_count
        or field.postings or index.graph.edges
        or index.native_root_count or index.native_consumer_count
    ):
        raise ValueError("original GitHub source journal differs from full native rebuild")


def audit_official_github_get_churn_e0() -> dict[str, Any]:
    """Actual publisher bundle 654→3→654 under one source-owned journal key."""
    document = _local_snapshot()
    github = compile_official_github_get_bundle_e0(document)
    other = _previous_two_providers()
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(default_effect="deny"))
    for tool in (github, *other):
        router.add_tool(tool)
    original_routes = {
        (github.key, entry["get"]["operationId"])
        for entry in document["paths"].values() if "get" in entry
    } | {(t.key, e.name) for t in other for e in t.endpoints}
    github_routes = {(github.key, e.name) for e in github.endpoints}
    if len(original_routes) != 654 or len(github_routes) != 651:
        raise ValueError("original GitHub provider source route manifest collision")
    principal = PrincipalContext(subject="denied-original-publisher-audit", roles=())
    allowed = router._authorization_predicate(principal)
    if allowed is None or any(
        allowed(tool, endpoint)
        for tool in router.registry.tools() for endpoint in tool.endpoints
    ):
        raise ValueError("MIT OpenAPI publisher schema incorrectly granted tool execution")

    probe = "not independently verified publisher capability"
    unproved = NativeDeclaredFieldGroup(
        aliases=(probe,),
        required_fields=(CapabilityFieldContract(
            semantic_id="research.no-original-publisher-approved-semantics",
            json_schema={"type": "string"},
        ),),
    )
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    versions: set[int] = set()
    snapshots: set[str] = set()
    counts: list[int] = []
    stale = 0
    for stage in ("initial", "removed", "restored"):
        if stage != "initial":
            if stage == "removed":
                unregister_if_current(
                    router.registry, github.key,
                    expected_fingerprint=router.registry.get(github.key).fingerprint,
                    expected_version=router.registry.version,
                )
            else:
                router.add_tool(github)
            try:
                index.lookup(router, probe, group=unproved, principal=principal)
            except PolicyViolationError:
                stale += 1
            else:
                raise ValueError("stale original GitHub publisher index accepted")
            index = NativeSchemaGraphIndex.refresh_from_inmemory_journal(
                index, router.registry,
            )
        expected = original_routes - github_routes if stage == "removed" else original_routes
        _same_original_source_index(router, index, expected)
        if index.lookup(
            router, probe, group=unproved, principal=principal,
        ).status != "no_proven_hit":
            raise ValueError("unreviewed original GitHub provider promoted to semantic lookup")
        versions.add(router.registry.version)
        snapshots.add(index.field_index.snapshot_id)
        counts.append(index.field_index.indexed_route_count)

    return {
        "evidence_tier": EVIDENCE_TIER,
        "original_github_repo": PUBLISHER_REPO,
        "original_github_commit": PUBLISHER_COMMIT,
        "original_github_source_blob": ORIGINAL_SPEC_BLOB,
        "original_github_source_paths": len(document["paths"]),
        "original_github_get_routes": len(github.endpoints),
        "mixed_publisher_route_counts": counts,
        "distinct_source_versions": len(versions),
        "distinct_index_snapshots": len(snapshots),
        "stale_index_rejections": stale,
        "journal_matches_full_rebuild": True,
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
    print(json.dumps(audit_official_github_get_churn_e0(), sort_keys=True, allow_nan=False))
