"""Offline original OpenAI OpenAPI GET catalog through bounded native projections.

Source-only B1 E0 evidence. Neither a client, permission grant, semantic gold,
model runner, nor replacement for the production OpenAPI complexity guard.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from yaml.nodes import ScalarNode

from schemarouter import AuthorizationPolicy, PrincipalContext, SchemaRouter
from schemarouter.adapters import tool_from_openapi
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.research_cross_provider_openapi_e0 import (
    PIRATE_COMMIT,
    compile_official_pirate_weather_source,
)
from scripts.research_official_openapi_snapshot_e0 import (
    FIXTURE_DIR,
    compile_official_ollama_snapshot,
)
from scripts.research_official_openapi_snapshot_e0 import (
    UPSTREAM_COMMIT as OLLAMA_COMMIT,
)

PUBLISHER_REPO = "openai/openai-openapi"
PUBLISHER_COMMIT = "8243cc8fa6f04430fb1f1a6a2cb926fbeb4f7f26"
ORIGINAL_SPEC_BYTES = 4210167
ORIGINAL_SPEC_SHA256 = "cc2a329f77bb06b451b9eb6c14cacd6c1c36276ae778f2d63940fab1c7bbb6f6"
ORIGINAL_SPEC_BLOB = "8d777683a29adc528382f163a88b0cd62613552d"
ORIGINAL_LICENSE_BYTES = 1083
ORIGINAL_LICENSE_SHA256 = "bcba3de214851cce46ed5af42d6698044616eeace887c3231bc7a20474ab639e"
ORIGINAL_LICENSE_BLOB = "4f14854c3243516f3de1487a60f14882874d7e3a"
COMPRESSED_SPEC_BYTES = 486142
COMPRESSED_SPEC_SHA256 = "703048f660242020c05019b8c776e5f65a87d079ae4e6148fbe7da4b96e10417"
UNSUPPORTED_GET_PATHS = frozenset({
    "/responses/{response_id}?beta=true",
    "/responses/{response_id}/input_items?beta=true",
})
_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options", "trace"})
EVIDENCE_TIER = "E0_GENUINE_OPENAI_GET_SOURCE_NATIVE_CATALOG_NO_E2"


class _SourceStringTimestampLoader(yaml.SafeLoader):
    """Keep publisher YAML date-shaped examples as JSON-compatible strings.

    PyYAML SafeLoader otherwise turns bare OpenAPI schema examples such as
    2024-10-01 into datetime.date; no global YAML loader is modified.
    """


def _literal_yaml_timestamp(loader: yaml.SafeLoader, node: yaml.nodes.Node) -> str:
    if not isinstance(node, ScalarNode):
        raise ValueError("original timestamp literal must be a YAML scalar")
    return loader.construct_scalar(node)


_SourceStringTimestampLoader.add_constructor(
    "tag:yaml.org,2002:timestamp", _literal_yaml_timestamp,
)


def _strict_snapshot(raw: bytes, *, size: int, digest: str, blob: str | None = None) -> None:
    if type(raw) is not bytes or len(raw) != size:
        raise ValueError("pinned provider snapshot length mismatch")
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("pinned provider snapshot SHA-256 mismatch")
    if blob is not None:
        git = b"blob " + str(len(raw)).encode("ascii") + bytes((0,)) + raw
        if hashlib.sha1(git).hexdigest() != blob:
            raise ValueError("pinned provider snapshot original Git blob mismatch")


def parse_pinned_openai_source(compressed: bytes, license_bytes: bytes) -> dict[str, Any]:
    """Decompress only a fixed local blob after independently pinning its container."""
    _strict_snapshot(
        compressed, size=COMPRESSED_SPEC_BYTES, digest=COMPRESSED_SPEC_SHA256,
    )
    _strict_snapshot(
        license_bytes, size=ORIGINAL_LICENSE_BYTES,
        digest=ORIGINAL_LICENSE_SHA256, blob=ORIGINAL_LICENSE_BLOB,
    )
    try:
        raw_spec = gzip.decompress(compressed)
    except (OSError, EOFError) as exc:
        raise ValueError("pinned provider snapshot cannot decompress") from exc
    _strict_snapshot(
        raw_spec, size=ORIGINAL_SPEC_BYTES,
        digest=ORIGINAL_SPEC_SHA256, blob=ORIGINAL_SPEC_BLOB,
    )
    source = yaml.load(raw_spec.decode("utf-8"), Loader=_SourceStringTimestampLoader)
    if not isinstance(source, dict):
        raise ValueError("pinned provider snapshot invalid OpenAPI document")
    info = source.get("info")
    if (
        source.get("openapi") != "3.1.0"
        or not isinstance(info, dict)
        or info.get("title") != "OpenAI API"
        or not isinstance(info.get("license"), dict)
        or info["license"].get("identifier") != "MIT"
        or not isinstance(source.get("paths"), dict)
        or not isinstance(source.get("components"), dict)
    ):
        raise ValueError("pinned provider snapshot OpenAPI metadata drift")
    return source


def scope_original_get_source(document: dict[str, Any], path: str) -> dict[str, Any]:
    """Preserve the established GET-only source projection API."""
    return scope_original_http_operation_source(document, path, "get")


def scope_original_http_operation_source(
    document: dict[str, Any], path: str, method: str,
) -> dict[str, Any]:
    """Copy one original HTTP operation and its transitive local references.

    No string matching to infer schemas and no normalization of invalid paths;
    the production adapter remains the sole native schema converter/validator.
    """
    paths = document.get("paths")
    components = document.get("components")
    if (
        not isinstance(paths, dict) or not isinstance(components, dict)
        or not isinstance(path, str) or "?" in path or method not in _METHODS
        or not isinstance(paths.get(path), dict)
        or not isinstance(paths[path].get(method), dict)
    ):
        raise ValueError("original HTTP operation path/method is unsupported")
    path_item = paths[path]
    selected = {
        key: deepcopy(value) for key, value in path_item.items()
        if key not in _METHODS
    }
    selected[method] = deepcopy(path_item[method])
    original_schemes = components.get("securitySchemes", {})
    if not isinstance(original_schemes, dict):
        raise ValueError("original security component invalid")
    used: dict[str, dict[str, Any]] = {"securitySchemes": deepcopy(original_schemes)}
    found: set[tuple[str, str]] = set()
    pending: list[Any] = [selected]
    while pending:
        node = pending.pop()
        if isinstance(node, list):
            pending.extend(node)
        elif isinstance(node, dict):
            ref = node.get("$ref")
            if ref is not None:
                if not isinstance(ref, str) or not ref.startswith("#/components/"):
                    raise ValueError("original source unsupported local/remote reference")
                parts = ref.split("/")
                if len(parts) < 4 or any(not part for part in parts[2:4]):
                    raise ValueError("original source component reference invalid")
                kind, name = (part.replace("~1", "/").replace("~0", "~")
                              for part in parts[2:4])
                originals = components.get(kind)
                if not isinstance(originals, dict) or name not in originals:
                    raise ValueError("original source component reference missing")
                key = (kind, name)
                if key not in found:
                    found.add(key)
                    if len(found) > 512:
                        raise ValueError("original source component closure unbounded")
                    original = deepcopy(originals[name])
                    used.setdefault(kind, {})[name] = original
                    pending.append(original)
            pending.extend(node.values())
    return {
        "openapi": document["openapi"],
        "info": deepcopy(document["info"]),
        "servers": deepcopy(document.get("servers", [])),
        "security": deepcopy(document.get("security", [])),
        "paths": {path: selected},
        "components": used,
    }


def audit_official_openai_get_catalog_e0() -> dict[str, Any]:
    """Build the original source's supported GET routes with no grants or calls."""
    source_path = FIXTURE_DIR / f"openai-openapi-{PUBLISHER_COMMIT[:8]}"
    document = parse_pinned_openai_source(
        Path(str(source_path) + "-openapi.yaml.gz").read_bytes(),
        Path(str(source_path) + "-LICENSE.txt").read_bytes(),
    )
    if not all(isinstance(item, dict) for item in document["paths"].values()):
        raise ValueError("original source path declarations invalid")
    method_count = sum(
        method in _METHODS
        for path_item in document["paths"].values() for method in path_item
    )
    source_gets = tuple(
        path for path, path_item in document["paths"].items() if "get" in path_item
    )
    if len(document["paths"]) != 237 or method_count != 371 or len(source_gets) != 163:
        raise ValueError("original provider operation inventory drift")
    unsupported = frozenset(path for path in source_gets if "?" in path)
    if unsupported != UNSUPPORTED_GET_PATHS:
        raise ValueError("original unsupported native GET path inventory drift")
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(default_effect="deny"))
    start = time.perf_counter_ns()
    parameterized = protected = 0
    for index, path in enumerate(source_gets):
        if path in unsupported:
            continue  # Existing adapter rejects these literal query-bearing paths.
        projected = scope_original_get_source(document, path)
        native = tool_from_openapi(f"openai_official_get_{index:03d}", projected)
        if len(native.endpoints) != 1:
            raise ValueError("original publisher GET changed supported route count")
        endpoint = native.endpoints[0]
        original_operation = document["paths"][path]["get"]
        if (
            endpoint.path != path or endpoint.method != "GET"
            or endpoint.read_only is not True or endpoint.destructive is True
            or endpoint.name != original_operation.get("operationId")
            or native.source_type or native.license
            or any(field.semantic_id for field in endpoint.output_fields)
        ):
            raise ValueError("original GET source evidence or no-grant boundary changed")
        path_names = set(re.findall(r"\{([^{}]+)\}", path))
        required_path_names = {
            parameter.name for parameter in endpoint.parameters
            if parameter.location == "path" and parameter.required
        }
        if not path_names.issubset(required_path_names):
            raise ValueError("original required provider path input was weakened")
        parameterized += bool(path_names)
        publisher_security = original_operation.get("security", document.get("security"))
        if publisher_security:
            if not endpoint.auth_requirements:
                raise ValueError("original provider security declaration was weakened")
            protected += 1
        router.add_tool(native)
    compile_ms = (time.perf_counter_ns() - start) / 1_000_000
    posting = NativeSchemaPostingIndex.build(router.registry)
    graph = NativeSchemaGraphIndex.build(posting)
    if (
        posting.indexed_route_count != 161 or len(posting.route_locations) != 161
        or posting.postings or graph.graph.edges
        or graph.native_root_count or graph.native_consumer_count
    ):
        raise ValueError("unreviewed provider source gained semantic/index authority")
    # One actual heterogeneous native catalog, not three independent result
    # counters or a copy of the synthetic 500/5000 publisher-like fixture.
    ollama = FIXTURE_DIR / f"ollama-{OLLAMA_COMMIT[:8]}"
    pirate = FIXTURE_DIR / f"pirate-weather-{PIRATE_COMMIT[:8]}"
    router.add_tool(compile_official_ollama_snapshot(
        Path(str(ollama) + "-openapi.yaml").read_bytes(),
        Path(str(ollama) + "-LICENSE.txt").read_bytes(),
    ))
    router.add_tool(compile_official_pirate_weather_source(
        Path(str(pirate) + "-openapi.yaml").read_bytes(),
        Path(str(pirate) + "-LICENSE.txt").read_bytes(),
    ))
    mixed_posting = NativeSchemaPostingIndex.build(router.registry)
    mixed_graph = NativeSchemaGraphIndex.build(mixed_posting)
    if (
        mixed_posting.indexed_route_count != 164
        or len(mixed_posting.route_locations) != 164
        or mixed_posting.postings or mixed_graph.graph.edges
        or mixed_graph.native_root_count or mixed_graph.native_consumer_count
    ):
        raise ValueError("actual mixed-source registry gained unreviewed native semantics")
    principal = PrincipalContext(subject="not-authorized-to-run-provider", roles=())
    allowed = router._authorization_predicate(principal)
    if allowed is None or any(
        allowed(tool, endpoint)
        for tool in router.registry.tools() for endpoint in tool.endpoints
    ):
        raise ValueError("official provider metadata incorrectly granted execution")
    return {
        "evidence_tier": EVIDENCE_TIER,
        "provider_repository": PUBLISHER_REPO,
        "provider_commit": PUBLISHER_COMMIT,
        "original_source_git_blob": ORIGINAL_SPEC_BLOB,
        "source_path_count": len(document["paths"]),
        "source_http_operation_count": method_count,
        "source_get_operation_count": len(source_gets),
        "native_get_route_count": posting.indexed_route_count,
        "mixed_source_registered_routes": mixed_posting.indexed_route_count,
        "mixed_source_provider_count": 3,
        "source_unsupported_get_count": len(unsupported),
        "required_path_input_route_count": parameterized,
        "protected_get_route_count": protected,
        "native_compile_wall_ms": round(compile_ms, 2),
        "untrusted_semantic_postings": len(posting.postings),
        "unauthorized_dependency_edges": len(graph.graph.edges),
        "provider_runtime_calls": 0,
        "execution_authority": False,
        "publisher_gold_verified": False,
        "independent_e2_qualified": False,
        "default_routing_changed": False,
    }


if __name__ == "__main__":
    print(json.dumps(audit_official_openai_get_catalog_e0(), sort_keys=True, allow_nan=False))
