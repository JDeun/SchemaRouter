"""E0 source-owned official OpenAI GET projections, never an execution grant."""
from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest


def _module():
    return import_module("scripts.research_official_openai_get_e0")


def _snapshot() -> tuple[bytes, bytes]:
    mod = _module()
    base = mod.FIXTURE_DIR / "openai-openapi-8243cc8f"
    return (
        Path(str(base) + "-openapi.yaml.gz").read_bytes(),
        Path(str(base) + "-LICENSE.txt").read_bytes(),
    )


def test_pinned_genuine_openai_get_catalog_keeps_existing_safety_limits() -> None:
    mod = _module()
    receipt = mod.audit_official_openai_get_catalog_e0()
    assert receipt["source_path_count"] == 237
    assert receipt["source_http_operation_count"] == 371
    assert receipt["source_get_operation_count"] == 163
    assert receipt["native_get_route_count"] == 161
    assert receipt["source_unsupported_get_count"] == 2
    assert receipt["required_path_input_route_count"] == 116
    assert receipt["protected_get_route_count"] == 161
    assert receipt["mixed_source_registered_routes"] == 164
    assert receipt["mixed_source_provider_count"] == 3
    assert receipt["untrusted_semantic_postings"] == 0
    assert receipt["unauthorized_dependency_edges"] == 0
    assert receipt["provider_runtime_calls"] == 0
    assert receipt["execution_authority"] is False
    assert receipt["publisher_gold_verified"] is False
    assert receipt["independent_e2_qualified"] is False
    assert receipt["default_routing_changed"] is False


@pytest.mark.parametrize("which", ("compressed", "license"))
@pytest.mark.parametrize("mutation", ("flip", "append", "truncate"))
def test_genuine_openai_source_and_original_notice_fail_closed_on_change(
    which: str, mutation: str,
) -> None:
    mod = _module()
    source, notice = _snapshot()
    altered = bytearray(source if which == "compressed" else notice)
    if mutation == "flip":
        altered[len(altered) // 2] ^= 1
    elif mutation == "append":
        altered.append(32)
    else:
        altered.pop()
    with pytest.raises(ValueError, match="pinned|snapshot"):
        mod.parse_pinned_openai_source(
            bytes(altered) if which == "compressed" else source,
            bytes(altered) if which == "license" else notice,
        )


def test_original_get_projection_refuses_missing_component_instead_of_guessing() -> None:
    mod = _module()
    source = {
        "openapi": "3.1.0", "info": {"title": "OpenAI API"},
        "paths": {"/models": {"get": {
            "operationId": "listModels", "responses": {
                "200": {"$ref": "#/components/responses/NotPresent"},
            },
        }}},
        "components": {"schemas": {}, "responses": {}, "securitySchemes": {}},
    }
    with pytest.raises(ValueError, match="component|reference"):
        mod.scope_original_get_source(source, "/models")


def test_original_get_projection_keeps_owner_operation_and_authentication() -> None:
    mod = _module()
    compressed, notice = _snapshot()
    document = mod.parse_pinned_openai_source(compressed, notice)
    scoped = mod.scope_original_get_source(document, "/models")
    assert scoped["paths"]["/models"]["get"] == document["paths"]["/models"]["get"]
    assert scoped["security"] == document["security"]
    assert scoped["components"]["securitySchemes"] == document["components"][
        "securitySchemes"
    ]
    assert scoped["components"]["schemas"]
    assert "listModels" == scoped["paths"]["/models"]["get"]["operationId"]
