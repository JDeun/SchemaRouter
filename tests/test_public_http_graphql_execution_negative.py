"""Registered HTTP JSON and GraphQL public execution negative/regression cases.

Spec discovery is allowed, but denied/unavailable/invalid plans must issue zero
application data requests. Local MockTransport is DEV_ONLY, not provider E2.
"""
from __future__ import annotations

import json

import httpx
import pytest
from test_graphql_adapter import introspection
from test_http_json_adapter import _crossref_tool

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    ExecutionPlan,
    PlanValidationError,
    PolicyViolationError,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    SchemaValidationError,
    ToolCall,
)
from schemarouter.errors import SchemaRouterError


def _plan(router: SchemaRouter, tool_key: str, operation: str, args: dict, fields: list[str]):
    tool = router.registry.get(tool_key)
    endpoint = tool.endpoint(operation)
    return ExecutionPlan(
        query="read safe source",
        registry_version=router.registry.version,
        calls=[
            ToolCall(
                tool=tool.key,
                endpoint=endpoint.name,
                arguments=args,
                fields=fields,
                schema_fingerprint=endpoint.fingerprint,
                tool_fingerprint=tool.fingerprint,
            )
        ],
    )


def _policy(operation: str):
    return AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow", operation=operation, roles_any=("reader",)
            ),
        ),
        default_effect="deny",
    )


READER = RunConfig(
    principal=PrincipalContext(subject="reader", roles=("reader",))
)
GUEST = RunConfig(
    principal=PrincipalContext(subject="guest", roles=("guest",))
)


@pytest.mark.asyncio
async def test_http_json_public_denial_unavailable_recovery_and_stale_zero_io() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request):
        requests.append(request.url.path)
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "message": {"DOI": "10.1234/test", "title": ["Example"]},
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(
            http_client=client, authorization_policy=_policy("crossref.get_work")
        )
        key = router.add_http_tool(
            _crossref_tool(), base_url="https://api.crossref.test/v1",
            provider="crossref",
        )
        good = _plan(router, key, "get_work", {"doi": "10.1234/test"}, ["message.DOI"])
        bad = _plan(router, key, "get_work", {}, ["message.DOI"])

        with pytest.raises(PolicyViolationError):
            await router.execute(good, config=GUEST)
        assert requests == []

        with pytest.raises((PlanValidationError, SchemaValidationError)):
            await router.execute(bad, config=READER)
        assert requests == []

        router.mark_access_unavailable(key, "get_work", cooldown_seconds=120)
        with pytest.raises(SchemaRouterError):
            await router.execute(good, config=READER)
        assert requests == []

        router.mark_access_available(key, "get_work")
        result = await router.execute(good, config=READER)
        assert result[0].data == {"message.DOI": "10.1234/test"}
        assert len(requests) == 1

        await router.aremove_tool(key)
        with pytest.raises(SchemaRouterError):
            await router.execute(good, config=READER)
        assert len(requests) == 1


@pytest.mark.asyncio
async def test_graphql_readonly_public_denial_unavailable_recovery_and_stale_zero_io() -> None:
    application_queries: list[dict] = []

    def handler(request: httpx.Request):
        payload = json.loads(request.content)
        if "__schema" in payload["query"]:
            return httpx.Response(200, json=introspection(), request=request)
        application_queries.append(payload)
        return httpx.Response(
            200,
            json={"data": {"material": {"id": "mp-1"}}},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://graphql.example/graphql",
            kind="graphql",
            http_client=client,
            authorization_policy=_policy("graphql.example.material"),
        )
        tool = router.registry.get("graphql.example")
        assert tool.endpoint("material").read_only is True
        good = _plan(router, tool.key, "material", {"id": "mp-1"}, ["id"])
        bad = _plan(router, tool.key, "material", {}, ["id"])

        with pytest.raises(PolicyViolationError):
            await router.execute(good, config=GUEST)
        assert application_queries == []

        with pytest.raises((PlanValidationError, SchemaValidationError)):
            await router.execute(bad, config=READER)
        assert application_queries == []

        router.mark_access_unavailable(tool.key, "material", cooldown_seconds=120)
        with pytest.raises(SchemaRouterError):
            await router.execute(good, config=READER)
        assert application_queries == []

        router.mark_access_available(tool.key, "material")
        result = await router.execute(good, config=READER)
        assert result[0].data == {"id": "mp-1"}
        assert len(application_queries) == 1

        await router.aremove_tool(tool.key)
        with pytest.raises(SchemaRouterError):
            await router.execute(good, config=READER)
        assert len(application_queries) == 1
