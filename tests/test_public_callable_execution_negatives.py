"""Public Python callable sync/async fail-closed registered invoker tests.

These tests exercise actual SchemaRouter dispatch and native registered callable
effects rather than an executor mock. Developer fixtures, not independent E2.
"""
from __future__ import annotations

import asyncio

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    ExecutionPlan,
    PolicyViolationError,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    ToolCall,
)
from schemarouter.errors import SchemaRouterError
from schemarouter.models import PlanRequest


def _fixture(mode: str, *, read_only: bool = True):
    calls: list[int] = []

    if mode == "sync":
        def lookup(record_id: int) -> dict[str, str]:
            calls.append(record_id)
            return {"record_id": str(record_id)}
    elif mode == "async":
        async def lookup(record_id: int) -> dict[str, str]:
            calls.append(record_id)
            return {"record_id": str(record_id)}
    else:
        raise ValueError(mode)

    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow",
                operation="lookup.call",
                roles_any=("reader",),
            ),
        ),
        default_effect="deny",
    )
    router = SchemaRouter(authorization_policy=policy)
    assert router.add_callable(lookup, read_only=read_only) == "lookup"
    request = PlanRequest(
        query="lookup record",
        preferred_tools=["lookup"],
        arguments={"record_id": 7},
    )
    allowed = RunConfig(
        principal=PrincipalContext(subject="reader", roles=("reader",))
    )
    denied = RunConfig(
        principal=PrincipalContext(subject="guest", roles=("guest",))
    )
    return router, calls, request, allowed, denied, policy


async def _invoke(router, request, config, mode):
    if mode == "sync":
        # The synchronous public API deliberately rejects an active event loop.
        return await asyncio.to_thread(router.invoke, request, config=config)
    return await router.ainvoke(request, config=config)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ("sync", "async"))
async def test_public_python_registered_callable_denial_availability_and_stale(
    mode: str,
) -> None:
    router, calls, request, allowed, denied, initial_policy = _fixture(mode)

    # Keep a pre-existing executable receipt; denial must be rechecked at I/O.
    plan = router.plan_executable_authorized(
        request, principal=allowed.principal
    )
    assert plan.executable and len(plan.calls) == 1

    with pytest.raises(PolicyViolationError):
        await router.execute(plan, config=denied)
    assert calls == []

    # Unavailable source abstains on both public invoke and ainvoke routes.
    router.mark_access_unavailable("lookup", "call", cooldown_seconds=120)
    assert await _invoke(router, request, allowed, mode) == []
    assert calls == []

    router.mark_access_available("lookup", "call")
    result = await _invoke(router, request, allowed, mode)
    assert len(result) == 1
    assert result[0].data == {"record_id": "7"}
    assert calls == [7]

    # A previously valid receipt loses dispatch authorization upon revocation.
    router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    with pytest.raises(PolicyViolationError):
        await router.execute(plan, config=allowed)
    assert calls == [7]

    router.authorization_policy = initial_policy
    await router.aremove_tool("lookup")
    with pytest.raises(SchemaRouterError):
        await router.execute(plan, config=allowed)
    assert calls == [7], "Stale receipt must never reach removed callable"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ("sync", "async"))
async def test_public_python_mutating_callable_requires_explicit_policy(
    mode: str,
) -> None:
    router, calls, _request, allowed, _denied, _policy = _fixture(
        mode, read_only=False
    )
    tool = router.registry.get("lookup")
    endpoint = tool.endpoint("call")
    assert endpoint.read_only is False
    call = ToolCall(
        tool=tool.key,
        endpoint=endpoint.name,
        arguments={"record_id": 7},
        fields=[],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )
    plan = ExecutionPlan(
        query="attempt mutating callable without host approval",
        registry_version=router.registry.version,
        calls=[call],
    )
    with pytest.raises(PolicyViolationError, match="mutating operation"):
        await router.execute(plan, config=allowed)
    assert calls == []
