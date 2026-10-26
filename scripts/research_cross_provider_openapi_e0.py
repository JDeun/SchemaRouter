"""Cross-provider native OpenAPI source preflight: Ollama + Pirate Weather (E0).

Both documents are genuine publisher-authored, exact-commit-pinned bytes.
No network operations, synthetic parameter values, host execution grants,
semantic joins, independent gold, or model calls are allowed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from schemarouter import AuthorizationPolicy, PrincipalContext, SchemaRouter, ToolSpec
from schemarouter.adapters import tool_from_openapi
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.research_official_openapi_snapshot_e0 import (
    FIXTURE_DIR,
    compile_official_ollama_snapshot,
)
from scripts.research_official_openapi_snapshot_e0 import (
    UPSTREAM_COMMIT as OLLAMA_COMMIT,
)

PIRATE_COMMIT = "6c3b4b0d9890d19b2199f8315488e8669c6951c3"
PIRATE_SPEC_SHA256 = "ad8bb15117a01902a0a598c7d02a65ec6a30852e160e6cc3a828da0f855c7db3"
PIRATE_LICENSE_SHA256 = "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"
PIRATE_SPEC_BLOB = "1b417160dc385c8d10897d88ec37fa4793d50816"
PIRATE_LICENSE_BLOB = "261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64"
PIRATE_SPEC_BYTES = 73096
PIRATE_LICENSE_BYTES = 11357
FORECAST_PATH = "/forecast/{api_key}/{lat_and_long_or_time}"
EVIDENCE_TIER = "E0_TWO_GENUINE_PROVIDER_OPENAPI_SNAPSHOTS_NO_E2"


def _strict_source(raw: bytes, *, size: int, digest: str, blob: str) -> None:
    if type(raw) is not bytes or len(raw) != size:
        raise ValueError("publisher raw snapshot length mismatch")
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("publisher raw snapshot SHA-256 mismatch")
    header = b"blob " + str(len(raw)).encode("ascii") + bytes((0,))
    if hashlib.sha1(header + raw).hexdigest() != blob:
        raise ValueError("publisher original Git blob mismatch")


def compile_official_pirate_weather_source(raw_spec: bytes, raw_license: bytes) -> ToolSpec:
    _strict_source(
        raw_spec, size=PIRATE_SPEC_BYTES, digest=PIRATE_SPEC_SHA256,
        blob=PIRATE_SPEC_BLOB,
    )
    _strict_source(
        raw_license, size=PIRATE_LICENSE_BYTES, digest=PIRATE_LICENSE_SHA256,
        blob=PIRATE_LICENSE_BLOB,
    )
    source: Any = yaml.safe_load(raw_spec.decode("utf-8"))
    if not isinstance(source, dict):
        raise ValueError("publisher source OpenAPI document is invalid")
    info = source.get("info")
    paths = source.get("paths")
    if (
        source.get("openapi") != "3.1.0"
        or not isinstance(info, dict)
        or info.get("title") != "Pirate Weather API"
        or not isinstance(info.get("license"), dict)
        or info["license"].get("name") != "Apache License 2.0"
        or not isinstance(paths, dict) or set(paths) != {FORECAST_PATH}
    ):
        raise ValueError("publisher original OpenAPI contract unexpected")
    path = paths[FORECAST_PATH]
    method = path.get("get") if isinstance(path, dict) else None
    if not isinstance(method, dict) or method.get("operationId") != "Weather":
        raise ValueError("publisher original operation unexpected")
    declared = method.get("parameters")
    if not isinstance(declared, list) or any(
        not isinstance(item, dict) for item in declared
    ):
        raise ValueError("publisher source declared inputs unexpected")
    mandatory = {
        (item.get("name"), item.get("in")) for item in declared
        if item.get("required") is True
    }
    if not {
        ("api_key", "path"), ("lat_and_long_or_time", "path"),
    }.issubset(mandatory):
        raise ValueError("publisher API credentials or required location lost")
    tool = tool_from_openapi("pirate_weather_official_source", source)
    if len(tool.endpoints) != 1:
        raise ValueError("publisher native tool-route count unexpected")
    ep = tool.endpoints[0]
    if (
        ep.name != "Weather" or ep.path != FORECAST_PATH or ep.method != "GET"
        or ep.read_only is not True or ep.destructive is True
        or not {"api_key", "lat_and_long_or_time"}.issubset(
            {param.name for param in ep.parameters if param.required}
        )
    ):
        raise ValueError("publisher required API parameter was weakened")
    if tool.source_type or tool.license or any(
        field.semantic_id for field in ep.output_fields
    ):
        raise ValueError("unreviewed publisher native source gained semantic authority")
    return tool


def audit_cross_provider_source() -> dict[str, Any]:
    ollama = FIXTURE_DIR / f"ollama-{OLLAMA_COMMIT[:8]}"
    pirate = FIXTURE_DIR / f"pirate-weather-{PIRATE_COMMIT[:8]}"
    first = compile_official_ollama_snapshot(
        Path(str(ollama) + "-openapi.yaml").read_bytes(),
        Path(str(ollama) + "-LICENSE.txt").read_bytes(),
    )
    second = compile_official_pirate_weather_source(
        Path(str(pirate) + "-openapi.yaml").read_bytes(),
        Path(str(pirate) + "-LICENSE.txt").read_bytes(),
    )
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(default_effect="deny"))
    router.add_tool(first)
    router.add_tool(second)
    posting = NativeSchemaPostingIndex.build(router.registry)
    graph = NativeSchemaGraphIndex.build(posting)
    if (
        posting.indexed_route_count != 3 or len(posting.route_locations) != 3
        or posting.postings or graph.graph.edges
        or graph.native_root_count or graph.native_consumer_count
    ):
        raise ValueError("unreviewed cross-provider semantic graph was promoted")
    # The public role cannot gain permission from publisher license strings.
    principal = PrincipalContext(subject="non-authorized-source-audit", roles=())
    policy = router._authorization_predicate(principal)
    if policy is None or any(
        policy(tool, endpoint)
        for tool in router.registry.tools()
        for endpoint in tool.endpoints
    ):
        raise ValueError("publisher metadata incorrectly granted tool invocation")
    return {
        "evidence_tier": EVIDENCE_TIER,
        "provider_repositories": ["ollama/ollama", "Pirate-Weather/pirateweather"],
        "provider_commits": [OLLAMA_COMMIT, PIRATE_COMMIT],
        "provider_git_blobs": [
            "3d0f5db4e71f1cb8331170c4d209902a00dfecc0",
            PIRATE_SPEC_BLOB,
        ],
        "registered_native_routes": posting.indexed_route_count,
        "unauthorized_cross_provider_edges": len(graph.graph.edges),
        "provider_runtime_calls": 0,
        "independent_e2_qualified": False,
        "publisher_gold_verified": False,
        "model_quality_verified": False,
        "execution_authority": False,
        "default_routing_changed": False,
    }


if __name__ == "__main__":
    print(json.dumps(audit_cross_provider_source(), sort_keys=True, allow_nan=False))
