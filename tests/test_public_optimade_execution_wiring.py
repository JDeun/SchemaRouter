"""OPTIMADE source discovery through registered public execute with fail-closed guards.

Only local source-shaped HTTP fixture data is used; no provider E2 claim.
"""
from __future__ import annotations

import httpx
import pytest
from test_optimade_adapter import base_info, references_info, structures_info

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    ExecutionPlan,
    PlanValidationError,
    PolicyViolationError,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    ToolCall,
)
from schemarouter.errors import SchemaRouterError


@pytest.mark.asyncio
async def test_optimade_public_execution_denies_before_remote_data_and_stale_reuse() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/info":
            return httpx.Response(200, json=base_info(), request=request)
        if request.url.path == "/v1/info/structures":
            return httpx.Response(200, json=structures_info(), request=request)
        if request.url.path == "/v1/info/references":
            return httpx.Response(200, json=references_info(), request=request)
        calls.append(request.url.path)
        assert request.method == "GET" and request.url.path == "/v1/structures"
        return httpx.Response(
            200,
            json={"data": [
                {"id": "s-1", "type": "structures", "attributes": {
                    "chemical_formula_descriptive": "O2Si",
                }},
            ], "meta": {"data_returned": 1}},
            request=request,
        )

    policy = AuthorizationPolicy(
        rules=(AuthorizationRule(
            effect="allow",
            operation="materials.example.search_structures",
            roles_any=("reader",),
        ),),
        default_effect="deny",
    )
    allow = RunConfig(principal=PrincipalContext(subject="reader", roles=("reader",)))
    deny = RunConfig(principal=PrincipalContext(subject="guest", roles=("guest",)))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://materials.example/v1",
            kind="optimade",
            authorization_policy=policy,
            http_client=client,
        )
        tool = router.registry.get("materials.example")
        endpoint = tool.endpoint("search_structures")
        assert endpoint.read_only is True
        plan = ExecutionPlan(
            query="search silicon oxide",
            registry_version=router.registry.version,
            calls=[ToolCall(
                tool=tool.key,
                endpoint=endpoint.name,
                arguments={"page_limit": 1},
                fields=["chemical_formula_descriptive"],
                tool_fingerprint=tool.fingerprint,
                schema_fingerprint=endpoint.fingerprint,
            )],
        )

        with pytest.raises(PolicyViolationError, match="authorization denied"):
            await router.execute(plan, config=deny)
        assert calls == []

        malformed = plan.model_copy(deep=True)
        malformed.calls[0].arguments = {"undeclared_sql": "DELETE FROM records"}
        with pytest.raises(PlanValidationError):
            await router.execute(malformed, config=allow)
        assert calls == []

        response = await router.execute(plan, config=allow)
        assert len(response) == 1
        assert response[0].data == [{"chemical_formula_descriptive": "O2Si"}]
        assert calls == ["/v1/structures"]

        await router.aremove_tool(tool.key)
        with pytest.raises(PolicyViolationError):
            await router.execute(plan, config=allow)
        assert calls == ["/v1/structures"]



@pytest.mark.asyncio
async def test_optimade_source_unavailable_refuses_data_get_and_recovers_once() -> None:
    """A registered OPTIMADE endpoint must not issue data I/O during cooldown."""
    data_gets: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/info":
            return httpx.Response(200, json=base_info(), request=request)
        if request.url.path == "/v1/info/structures":
            return httpx.Response(200, json=structures_info(), request=request)
        if request.url.path == "/v1/info/references":
            return httpx.Response(200, json=references_info(), request=request)
        data_gets.append(request.url.path)
        assert request.method == "GET" and request.url.path == "/v1/structures"
        return httpx.Response(
            200, json={"data": [{"id": "s-1", "type": "structures",
                                   "attributes": {"chemical_formula_descriptive": "O2Si"}}],
                       "meta": {"data_returned": 1}}, request=request,
        )

    policy = AuthorizationPolicy(
        rules=(AuthorizationRule(
            effect="allow",
            operation="materials.example.search_structures",
            roles_any=("reader",),
        ),),
        default_effect="deny",
    )
    reader = RunConfig(
        principal=PrincipalContext(subject="reader", roles=("reader",))
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://materials.example/v1",
            kind="optimade",
            authorization_policy=policy,
            http_client=client,
        )
        tool = router.registry.get("materials.example")
        endpoint = tool.endpoint("search_structures")
        assert endpoint.read_only is True
        plan = ExecutionPlan(
            query="search silicon oxide",
            registry_version=router.registry.version,
            calls=[ToolCall(
                tool=tool.key,
                endpoint=endpoint.name,
                arguments={"page_limit": 1},
                fields=["chemical_formula_descriptive"],
                tool_fingerprint=tool.fingerprint,
                schema_fingerprint=endpoint.fingerprint,
            )],
        )

        router.mark_access_unavailable(tool.key, endpoint.name, cooldown_seconds=120)
        with pytest.raises(SchemaRouterError):
            await router.execute(plan, config=reader)
        assert data_gets == []

        router.mark_access_available(tool.key, endpoint.name)
        result = await router.execute(plan, config=reader)
        assert result[0].data == [{"chemical_formula_descriptive": "O2Si"}]
        assert data_gets == ["/v1/structures"]

        await router.aremove_tool(tool.key)
        with pytest.raises(SchemaRouterError):
            await router.execute(plan, config=reader)
        assert data_gets == ["/v1/structures"]
