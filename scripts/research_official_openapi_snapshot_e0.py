"""Pin and compile one genuine upstream Ollama OpenAPI snapshot (offline E0).

The upstream's MIT notice is retained verbatim. This is a provider-authored
*schema*, not a publisher-reviewed test suite, an authorization grant, or E2.
No network, provider execution, model, agent, or default-routing changes.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from schemarouter import AuthorizationPolicy, SchemaRouter, ToolSpec
from schemarouter.adapters import tool_from_openapi
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex

UPSTREAM_REPOSITORY = "ollama/ollama"
UPSTREAM_COMMIT = "66ab8482e08035a3238dff04a5739c4371c61bfe"
SCHEMA_GIT_BLOB = "3d0f5db4e71f1cb8331170c4d209902a00dfecc0"
LICENSE_GIT_BLOB = "8e3dc978a7ca8c53f56bbedc5b558116140fc02e"
SCHEMA_SHA256 = "e94c8f02969c6807f431b7d0643eb0f8368f1d1baa719a4edaf07989b758f257"
LICENSE_SHA256 = "5934ed2ce0d15154bcdb9c85203210abac0da4314af34081e36df4599f90b226"
SCHEMA_BYTES = 87348
LICENSE_BYTES = 1058
EVIDENCE_TIER = "E0_OFFICIAL_PROVIDER_OPENAPI_SOURCE_ONLY_NOT_E2"
REVIEWED_READS = {
    "/api/tags": ("list", "ListResponse"),
    "/api/ps": ("ps", "PsResponse"),
}
REFERENCED_SCHEMAS = ("ModelSummary", "ListResponse", "Ps", "PsResponse")
FIXTURE_DIR = (
    Path(__file__).resolve().parent.parent
    / "research" / "fixtures" / "provider-snapshots"
)


def _pin(raw: bytes, *, size: int, sha256: str, git_blob: str) -> None:
    """Match source's exact original raw bytes, not reserialized YAML."""
    if type(raw) is not bytes or len(raw) != size:
        raise ValueError("official native source snapshot length mismatch")
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError("official native source snapshot SHA-256 mismatch")
    git = b"blob " + str(len(raw)).encode("ascii") + bytes((0,)) + raw
    if hashlib.sha1(git).hexdigest() != git_blob:
        raise ValueError("official native source snapshot Git blob mismatch")


def parse_pinned_ollama_source(raw_spec: bytes, raw_license: bytes) -> dict[str, Any]:
    """Parse ONLY fully pinned upstream source; never trust mutable GitHub main."""
    _pin(raw_spec, size=SCHEMA_BYTES, sha256=SCHEMA_SHA256, git_blob=SCHEMA_GIT_BLOB)
    _pin(raw_license, size=LICENSE_BYTES, sha256=LICENSE_SHA256, git_blob=LICENSE_GIT_BLOB)
    document = yaml.safe_load(raw_spec.decode("utf-8"))
    if not isinstance(document, dict):
        raise ValueError("official native OpenAPI document invalid")
    info = document.get("info")
    if (
        document.get("openapi") != "3.1.0"
        or not isinstance(info, dict)
        or info.get("title") != "Ollama API"
        or not isinstance(info.get("license"), dict)
        or info["license"].get("name") != "MIT"
        or not isinstance(document.get("paths"), dict)
        or not isinstance(document.get("components"), dict)
    ):
        raise ValueError("official native OpenAPI source contract unexpected")
    return document


def _scoped_original_document(document: dict[str, Any]) -> dict[str, Any]:
    """Exact vendor-owned GET operations, not reauthored endpoint definitions."""
    paths: dict[str, Any] = {}
    for path, (operation_id, response_name) in REVIEWED_READS.items():
        entry = document["paths"].get(path)
        operation = entry.get("get") if isinstance(entry, dict) else None
        if (
            not isinstance(operation, dict)
            or operation.get("operationId") != operation_id
            or not isinstance(operation.get("responses"), dict)
            or not isinstance(operation["responses"].get("200"), dict)
        ):
            raise ValueError("official source GET contract missing")
        paths[path] = {"get": deepcopy(operation)}
        response = operation["responses"]["200"]
        schema = response.get("content", {}).get("application/json", {}).get("schema", {})
        if schema.get("$ref") != f"#/components/schemas/{response_name}":
            raise ValueError("official source response contract drift")
    all_schemas = document["components"].get("schemas")
    if not isinstance(all_schemas, dict) or any(
        not isinstance(all_schemas.get(name), dict) for name in REFERENCED_SCHEMAS
    ):
        raise ValueError("official source schema definitions missing")
    return {
        "openapi": document["openapi"],
        "info": deepcopy(document["info"]),
        "security": deepcopy(document.get("security", [])),
        "paths": paths,
        "components": {
            "schemas": {name: deepcopy(all_schemas[name]) for name in REFERENCED_SCHEMAS},
        },
    }


def compile_official_ollama_snapshot(
    raw_spec: bytes, raw_license: bytes,
) -> ToolSpec:
    """Use the production OpenAPI converter without inventing source permission."""
    doc = _scoped_original_document(parse_pinned_ollama_source(raw_spec, raw_license))
    tool = tool_from_openapi("ollama_official_source_snapshot", doc)
    if (
        len(tool.endpoints) != 2
        or {(e.path, e.method, e.name) for e in tool.endpoints}
        != {(path, "GET", op) for path, (op, _) in REVIEWED_READS.items()}
        or any(e.read_only is not True or e.destructive is True for e in tool.endpoints)
    ):
        raise ValueError("official source converter route mismatch")
    # The actual MIT LICENSE document is not an authorization/semantic grant.
    if tool.source_type or tool.license or any(
        any(field.semantic_id for field in ep.output_fields)
        for ep in tool.endpoints
    ):
        raise ValueError("unreviewed native source gained authority or semantics")
    return tool


def audit_official_ollama_snapshot(
    spec_path: Path | None = None, license_path: Path | None = None,
) -> dict[str, Any]:
    original = FIXTURE_DIR / f"ollama-{UPSTREAM_COMMIT[:8]}"
    raw_spec = (spec_path or Path(str(original) + "-openapi.yaml")).read_bytes()
    raw_license = (license_path or Path(str(original) + "-LICENSE.txt")).read_bytes()
    tool = compile_official_ollama_snapshot(raw_spec, raw_license)
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(default_effect="deny"))
    router.add_tool(tool)
    graph = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    if (
        graph.field_index.indexed_route_count != 2
        or graph.graph.edges
        or graph.native_root_count
        or graph.native_consumer_count
    ):
        raise ValueError("official unreviewed source unexpectedly generated verified graph")
    return {
        "evidence_tier": EVIDENCE_TIER,
        "source_repository": UPSTREAM_REPOSITORY,
        "source_commit": UPSTREAM_COMMIT,
        "source_schema_git_blob": SCHEMA_GIT_BLOB,
        "source_schema_sha256": SCHEMA_SHA256,
        "license_git_blob": LICENSE_GIT_BLOB,
        "source_license_spdx": "MIT",
        "native_source_routes": graph.field_index.indexed_route_count,
        "source_semantic_reviewed": False,
        "provider_live_io": False,
        "publisher_gold_verified": False,
        "independent_e2_qualified": False,
        "execution_authority": False,
        "default_routing_changed": False,
    }


if __name__ == "__main__":
    print(json.dumps(audit_official_ollama_snapshot(), sort_keys=True, allow_nan=False))
