from __future__ import annotations

import hashlib
import json

import httpx
import pytest

from schemarouter import (
    AuthRequirementSet,
    AuthSchemeRequirement,
    EndpointSpec,
    NonRetryableInvocationError,
    compare_endpoint_specs,
)
from schemarouter.adapters.openapi import OpenAPIRemoteInvoker, tool_from_openapi
from schemarouter.inspection import inspect_tool_spec


def _document(
    scheme: dict | None = None,
    *,
    security: list[dict] | None = None,
    operation_security: list[dict] | None | object = ...,
) -> dict:
    document: dict = {
        "openapi": "3.1.0",
        "info": {"title": "Auth API", "version": "1.0.0"},
        "servers": [{"url": "https://api.example.test"}],
        "paths": {
            "/items": {
                "get": {
                    "operationId": "list_items",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"}
                                }
                            },
                        }
                    },
                }
            }
        },
    }
    if scheme is not None:
        document["components"] = {"securitySchemes": {"PrimaryAuth": scheme}}
    if security is not None:
        document["security"] = security
    if operation_security is not ...:
        document["paths"]["/items"]["get"]["security"] = operation_security
    return document


@pytest.mark.parametrize(
    ("scheme", "kind", "location", "http_scheme"),
    [
        (
            {"type": "apiKey", "in": "header", "name": "X-API-Key"},
            "api_key",
            "header",
            None,
        ),
        (
            {"type": "apiKey", "in": "query", "name": "api_key"},
            "api_key",
            "query",
            None,
        ),
        (
            {"type": "apiKey", "in": "cookie", "name": "session_key"},
            "api_key",
            "cookie",
            None,
        ),
        (
            {"type": "http", "scheme": "bearer"},
            "http",
            None,
            "bearer",
        ),
        (
            {"type": "http", "scheme": "basic"},
            "http",
            None,
            "basic",
        ),
        (
            {
                "type": "oauth2",
                "flows": {
                    "clientCredentials": {
                        "tokenUrl": "https://auth.example.test/token",
                        "scopes": {"items:read": "Read items"},
                    }
                },
            },
            "oauth2",
            None,
            None,
        ),
        (
            {
                "type": "openIdConnect",
                "openIdConnectUrl": "https://auth.example.test/.well-known/openid-configuration",
            },
            "openid_connect",
            None,
            None,
        ),
    ],
)
def test_openapi_normalizes_common_auth_schemes(
    scheme: dict,
    kind: str,
    location: str | None,
    http_scheme: str | None,
) -> None:
    tool = tool_from_openapi(
        "auth_api",
        _document(
            scheme,
            security=[
                {
                    "PrimaryAuth": (
                        ["items:read"]
                        if kind in {"oauth2", "openid_connect"}
                        else []
                    )
                }
            ],
        ),
    )

    endpoint = tool.endpoint("list_items")
    assert endpoint.auth_required is True
    assert len(endpoint.auth_requirements) == 1
    requirement = endpoint.auth_requirements[0].schemes[0]
    assert requirement.name == "PrimaryAuth"
    assert requirement.kind == kind
    assert requirement.location == location
    assert requirement.http_scheme == http_scheme
    if kind in {"oauth2", "openid_connect"}:
        assert requirement.scopes == ["items:read"]


def test_operation_security_overrides_root_security_with_public_access() -> None:
    tool = tool_from_openapi(
        "auth_api",
        _document(
            {"type": "apiKey", "in": "header", "name": "X-API-Key"},
            security=[{"PrimaryAuth": []}],
            operation_security=[],
        ),
    )

    endpoint = tool.endpoint("list_items")
    assert endpoint.auth_required is False
    assert endpoint.auth_requirements == []
    assert endpoint.metadata["security"] == []


def test_empty_security_alternative_keeps_operation_public() -> None:
    tool = tool_from_openapi(
        "auth_api",
        _document(
            {"type": "http", "scheme": "bearer"},
            security=[{"PrimaryAuth": []}, {}],
        ),
    )

    endpoint = tool.endpoint("list_items")
    assert endpoint.auth_required is False
    assert any(not alternative.schemes for alternative in endpoint.auth_requirements)



def test_explicit_null_security_fails_closed_as_unsupported() -> None:
    tool = tool_from_openapi(
        "auth_api",
        _document(
            {"type": "http", "scheme": "bearer"},
            operation_security=None,
        ),
    )

    endpoint = tool.endpoint("list_items")
    assert endpoint.auth_required is True
    requirement = endpoint.auth_requirements[0].schemes[0]
    assert requirement.kind == "unsupported"
    assert requirement.declared_type == "invalid"


def test_security_alternatives_preserve_or_semantics() -> None:
    document = _document(
        {"type": "apiKey", "in": "header", "name": "X-API-Key"},
        security=[{"PrimaryAuth": []}],
    )
    document["components"]["securitySchemes"]["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
    }
    document["security"] = [{"PrimaryAuth": []}, {"BearerAuth": []}]

    endpoint = tool_from_openapi("auth_api", document).endpoint("list_items")

    assert endpoint.auth_required is True
    assert len(endpoint.auth_requirements) == 2
    names = [
        {scheme.name for scheme in alternative.schemes}
        for alternative in endpoint.auth_requirements
    ]
    assert {"PrimaryAuth"} in names
    assert {"BearerAuth"} in names


@pytest.mark.asyncio
async def test_multiple_schemes_in_one_alternative_require_all_credentials() -> None:
    document = _document(
        {"type": "apiKey", "in": "header", "name": "X-API-Key"},
        security=[{"PrimaryAuth": [], "BearerAuth": []}],
    )
    document["components"]["securitySchemes"]["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
    }
    tool = tool_from_openapi("auth_api", document)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"ok": True}, request=request)
        )
    ) as client:
        missing_one = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.test",
            trusted_headers={"X-API-Key": "runtime-key"},
            http_client=client,
        )
        with pytest.raises(
            NonRetryableInvocationError,
            match="authentication requirements",
        ):
            await missing_one("list_items", {})

        complete = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.test",
            trusted_headers={
                "X-API-Key": "runtime-key",
                "Authorization": "Bearer runtime-token",
            },
            http_client=client,
        )
        assert await complete("list_items", {}) == {"ok": True}


def test_public_endpoint_and_tool_keep_pre_auth_contract_fingerprints() -> None:
    tool = tool_from_openapi("auth_api", _document())
    endpoint = tool.endpoint("list_items")

    endpoint_payload = endpoint.model_dump(
        mode="json",
        exclude={"metadata", "auth_requirements"},
    )
    endpoint_canonical = json.dumps(
        endpoint_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    historical_endpoint_fingerprint = hashlib.sha256(
        endpoint_canonical.encode("utf-8")
    ).hexdigest()

    tool_payload = tool.model_dump(
        mode="json",
        exclude={"metadata", "endpoints"},
    )
    tool_payload["endpoints"] = [
        item.model_dump(
            mode="json",
            exclude={"metadata", "auth_requirements"},
        )
        for item in tool.endpoints
    ]
    tool_canonical = json.dumps(
        tool_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    historical_tool_fingerprint = hashlib.sha256(
        tool_canonical.encode("utf-8")
    ).hexdigest()

    assert endpoint.fingerprint == historical_endpoint_fingerprint
    assert tool.fingerprint == historical_tool_fingerprint


def test_public_to_authenticated_change_is_fingerprinted_security_drift() -> None:
    public = tool_from_openapi("auth_api", _document()).endpoint("list_items")
    secured = tool_from_openapi(
        "auth_api",
        _document(
            {"type": "apiKey", "in": "header", "name": "X-API-Key"},
            security=[{"PrimaryAuth": []}],
        ),
    ).endpoint("list_items")

    report = compare_endpoint_specs(public, secured)

    assert public.fingerprint != secured.fingerprint
    assert report.compatibility == "security_review"
    assert any(
        change.kind == "authentication_requirements_changed"
        and change.severity == "security"
        for change in report.changes
    )


def test_auth_scheme_location_change_is_security_drift() -> None:
    header = tool_from_openapi(
        "auth_api",
        _document(
            {"type": "apiKey", "in": "header", "name": "X-API-Key"},
            security=[{"PrimaryAuth": []}],
        ),
    ).endpoint("list_items")
    query = tool_from_openapi(
        "auth_api",
        _document(
            {"type": "apiKey", "in": "query", "name": "api_key"},
            security=[{"PrimaryAuth": []}],
        ),
    ).endpoint("list_items")

    report = compare_endpoint_specs(header, query)

    assert header.fingerprint != query.fingerprint
    assert report.compatibility == "security_review"
    assert any(
        change.path == "auth_requirements" and change.severity == "security"
        for change in report.changes
    )


def test_inspection_exposes_auth_without_credential_values() -> None:
    secret_value = "runtime-credential-value"
    tool = tool_from_openapi(
        "auth_api",
        _document(
            {"type": "apiKey", "in": "header", "name": "X-API-Key"},
            security=[{"PrimaryAuth": []}],
        ),
    )
    OpenAPIRemoteInvoker(
        tool,
        "https://api.example.test",
        trusted_headers={"X-API-Key": secret_value},
    )

    inspection = inspect_tool_spec(tool)
    endpoint = inspection.endpoints[0]

    assert endpoint.auth_required is True
    assert endpoint.auth_kinds == ["api_key"]
    assert endpoint.auth_scheme_names == ["PrimaryAuth"]
    assert secret_value not in tool.model_dump_json()
    assert secret_value not in inspection.model_dump_json()
    assert secret_value not in tool.fingerprint
    assert secret_value not in tool.endpoints[0].fingerprint


@pytest.mark.asyncio
async def test_runtime_fails_closed_when_required_header_api_key_is_missing() -> None:
    tool = tool_from_openapi(
        "auth_api",
        _document(
            {"type": "apiKey", "in": "header", "name": "X-API-Key"},
            security=[{"PrimaryAuth": []}],
        ),
    )
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"ok": True}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.test",
            http_client=client,
        )
        with pytest.raises(
            NonRetryableInvocationError,
            match="authentication requirements",
        ):
            await invoker("list_items", {})

    assert called is False


@pytest.mark.asyncio
async def test_runtime_uses_trusted_header_api_key_without_serializing_it() -> None:
    tool = tool_from_openapi(
        "auth_api",
        _document(
            {"type": "apiKey", "in": "header", "name": "X-API-Key"},
            security=[{"PrimaryAuth": []}],
        ),
    )
    seen_header: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_header
        seen_header = request.headers.get("X-API-Key")
        return httpx.Response(200, json={"ok": True}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.test",
            trusted_headers={"X-API-Key": "runtime-only"},
            http_client=client,
        )
        result = await invoker("list_items", {})

    assert result == {"ok": True}
    assert seen_header == "runtime-only"
    assert "runtime-only" not in json.dumps(tool.model_dump(mode="json"))


@pytest.mark.asyncio
async def test_query_api_key_fails_closed_without_trusted_query_channel() -> None:
    tool = tool_from_openapi(
        "auth_api",
        _document(
            {"type": "apiKey", "in": "query", "name": "api_key"},
            security=[{"PrimaryAuth": []}],
        ),
    )

    invoker = OpenAPIRemoteInvoker(
        tool,
        "https://api.example.test",
        trusted_headers={"X-API-Key": "not-the-query-key"},
    )

    with pytest.raises(
        NonRetryableInvocationError,
        match="authentication requirements",
    ):
        await invoker("list_items", {})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scheme", "header"),
    [
        ({"type": "http", "scheme": "bearer"}, "Bearer runtime-token"),
        ({"type": "http", "scheme": "basic"}, "Basic encoded-runtime-value"),
        (
            {
                "type": "oauth2",
                "flows": {
                    "clientCredentials": {
                        "tokenUrl": "https://auth.example.test/token",
                        "scopes": {},
                    }
                },
            },
            "Bearer runtime-token",
        ),
        (
            {
                "type": "openIdConnect",
                "openIdConnectUrl": "https://auth.example.test/.well-known/openid-configuration",
            },
            "Bearer runtime-token",
        ),
    ],
)
async def test_runtime_accepts_supported_authorization_header_schemes(
    scheme: dict,
    header: str,
) -> None:
    tool = tool_from_openapi(
        "auth_api",
        _document(scheme, security=[{"PrimaryAuth": []}]),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == header
        return httpx.Response(200, json={"ok": True}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.test",
            trusted_headers={"Authorization": header},
            http_client=client,
        )
        assert await invoker("list_items", {}) == {"ok": True}


@pytest.mark.asyncio
async def test_cookie_api_key_can_come_only_from_trusted_cookie_header() -> None:
    tool = tool_from_openapi(
        "auth_api",
        _document(
            {"type": "apiKey", "in": "cookie", "name": "session_key"},
            security=[{"PrimaryAuth": []}],
        ),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert "session_key=runtime-value" in request.headers["Cookie"]
        return httpx.Response(200, json={"ok": True}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.test",
            trusted_headers={"Cookie": "session_key=runtime-value"},
            http_client=client,
        )
        assert await invoker("list_items", {}) == {"ok": True}


@pytest.mark.asyncio
async def test_unsupported_security_scheme_fails_closed() -> None:
    tool = tool_from_openapi(
        "auth_api",
        _document(
            {"type": "mutualTLS"},
            security=[{"PrimaryAuth": []}],
        ),
    )
    requirement = tool.endpoint("list_items").auth_requirements[0].schemes[0]
    assert requirement.kind == "unsupported"
    assert requirement.declared_type == "mutualTLS"

    invoker = OpenAPIRemoteInvoker(
        tool,
        "https://api.example.test",
        trusted_headers={"Authorization": "Bearer unrelated"},
    )
    with pytest.raises(
        NonRetryableInvocationError,
        match="authentication requirements",
    ):
        await invoker("list_items", {})


def test_legacy_operation_security_metadata_migrates_fail_closed() -> None:
    endpoint = EndpointSpec.model_validate(
        {
            "name": "legacy",
            "method": "GET",
            "path": "/legacy",
            "metadata": {"security": [{"LegacyKey": []}]},
        }
    )

    assert endpoint.auth_required is True
    requirement = endpoint.auth_requirements[0].schemes[0]
    assert requirement.name == "LegacyKey"
    assert requirement.kind == "unsupported"
    assert requirement.declared_type == "legacy_unknown"


def test_auth_contract_models_never_accept_secret_value_fields() -> None:
    requirement = AuthRequirementSet(
        schemes=[
            AuthSchemeRequirement(
                name="ApiKey",
                kind="api_key",
                location="header",
                parameter_name="X-API-Key",
            )
        ]
    )

    dumped = requirement.model_dump(mode="json")
    assert set(dumped["schemes"][0]) == {
        "name",
        "kind",
        "location",
        "parameter_name",
        "http_scheme",
        "scopes",
        "declared_type",
    }
