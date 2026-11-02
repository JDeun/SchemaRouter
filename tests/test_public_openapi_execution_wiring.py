"""Real registered local OpenAPI HTTP transport: public execution and fail closed."""
from __future__ import annotations

import httpx
import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    ExecutionPlan,
    ExecutionPolicy,
    PlanValidationError,
    PolicyViolationError,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    SchemaValidationError,
    ToolCall,
)


def _source_document() -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Inventory", "version": "1.0.0"},
        "servers": [{"url": "https://inventory.example.test"}],
        "paths": {
            "/items/{item_id}": {
                "get": {
                    "operationId": "get_item",
                    "parameters": [
                        {
                            "name": "item_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "success",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
                                            "label": {"type": "string"},
                                        },
                                        "required": ["id", "label"],
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }


def _plan(router: SchemaRouter, tool_key: str, *, arguments: dict) -> ExecutionPlan:
    tool = router.registry.get(tool_key)
    endpoint = tool.endpoint("get_item")
    return ExecutionPlan(
        query="read inventory item",
        registry_version=router.registry.version,
        calls=[
            ToolCall(
                tool=tool.key,
                endpoint=endpoint.name,
                arguments=arguments,
                fields=["id", "label"],
                schema_fingerprint=endpoint.fingerprint,
                tool_fingerprint=tool.fingerprint,
            )
        ],
    )


@pytest.mark.asyncio
async def test_openapi_registered_http_public_execute_checks_authorization_and_inputs() -> None:
    """Spec discovery is permitted; data GET is unreachable to denied identities."""
    wire_calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/openapi.json":
            return httpx.Response(200, json=_source_document(), request=request)
        wire_calls.append((request.method, request.url.path))
        assert request.method == "GET"
        assert request.url.path == "/items/7"
        return httpx.Response(
            200,
            json={"id": 7, "label": "verified"},
            headers={"content-type": "application/json"},
            request=request,
        )

    auth = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow",
                operation="inventory.get_item",
                roles_any=("reader",),
            ),
        ),
        default_effect="deny",
    )
    reader = RunConfig(principal=PrincipalContext(subject="owner", roles=("reader",)))
    guest = RunConfig(principal=PrincipalContext(subject="guest", roles=("guest",)))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://inventory.example.test/openapi.json",
            kind="openapi",
            name="inventory",
            base_url="https://inventory.example.test",
            http_client=client,
            authorization_policy=auth,
            policy=ExecutionPolicy(allow_unclassified_remote=True),
        )
        tool = next(item for item in router.registry.tools() if item.key == "inventory")
        endpoint = tool.endpoint("get_item")
        assert endpoint.read_only is True
        plan = _plan(router, tool.key, arguments={"item_id": 7})

        with pytest.raises(PolicyViolationError, match="authorization denied"):
            await router.execute(plan, config=guest)
        assert wire_calls == []

        with pytest.raises((PlanValidationError, SchemaValidationError)):
            await router.execute(_plan(router, tool.key, arguments={}), config=reader)
        assert wire_calls == []

        result = await router.execute(plan, config=reader)
        assert len(result) == 1
        assert result[0].data == {"id": 7, "label": "verified"}
        assert wire_calls == [("GET", "/items/7")]



@pytest.mark.asyncio
async def test_openapi_denied_principal_never_reaches_http() -> None:
    """A denied user cannot produce a registered data GET after schema discovery."""
    wire_calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/openapi.json":
            return httpx.Response(200, json=_source_document(), request=request)
        wire_calls.append(str(request.url))
        raise AssertionError("denied request reached HTTP data endpoint")

    authorization = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow",
                operation="inventory.get_item",
                roles_any=("reader",),
            ),
        ),
        default_effect="deny",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://inventory.example.test/openapi.json",
            kind="openapi",
            name="inventory",
            base_url="https://inventory.example.test",
            http_client=client,
            authorization_policy=authorization,
            policy=ExecutionPolicy(allow_unclassified_remote=True),
        )
        guest = RunConfig(
            principal=PrincipalContext(subject="denied", roles=("guest",))
        )
        with pytest.raises(PolicyViolationError, match="authorization denied"):
            await router.execute(_plan(router, "inventory", arguments={"item_id": 7}), config=guest)
        assert wire_calls == []
