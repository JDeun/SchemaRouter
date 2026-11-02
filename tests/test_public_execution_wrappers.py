"""Registered public execution wrappers: real callable dispatch plus principal denial.

One fixture per parameter case; no monkeypatching of the public invoker.
This is DEV integration evidence, not independent provider/model E2.
"""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    PlanRequest,
    PolicyViolationError,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
)


def _registered_router():
    calls: list[int] = []

    def lookup(user_id: int) -> dict[str, str]:
        calls.append(user_id)
        return {"user_id": str(user_id)}

    router = SchemaRouter(
        authorization_policy=AuthorizationPolicy(
            rules=(
                AuthorizationRule(
                    effect="allow", operation="lookup.call", roles_any=("member",)
                ),
            ),
            default_effect="deny",
        ),
    )
    assert router.add_callable(lookup, read_only=True) == "lookup"
    request = PlanRequest(
        query="lookup user",
        preferred_tools=["lookup"],
        arguments={"user_id": 7},
    )
    allowed = RunConfig(
        principal=PrincipalContext(subject="member-1", roles=("member",))
    )
    denied = RunConfig(
        principal=PrincipalContext(subject="guest-1", roles=("guest",))
    )
    return router, calls, request, allowed, denied


def _check_results(results, *, executed: bool) -> None:
    if not executed:
        assert results == [], "Unauthorized request must abstain without a tool result"
        return
    assert len(results) == 1
    assert results[0].data == {"user_id": "7"}


def _sync_call(target, method: str, request, *, config=None, executed: bool):
    if method in {"batch", "batch_as_completed"}:
        args = ([request],)
    else:
        args = (request,)
    keyword = {} if config is None else {"config": config}
    value = getattr(target, method)(*args, **keyword)
    if method == "batch":
        _check_results(value[0], executed=executed)
    elif method == "batch_as_completed":
        outcome = list(value)
        assert [index for index, _ in outcome] == [0]
        _check_results(outcome[0][1], executed=executed)
    elif method == "stream":
        _check_results(list(value), executed=executed)
    else:
        _check_results(value, executed=executed)


async def _async_call(target, method: str, request, *, config=None, executed: bool):
    keyword = {} if config is None else {"config": config}
    if method in {"abatch", "abatch_as_completed"}:
        args = ([request],)
    else:
        args = (request,)
    value = getattr(target, method)(*args, **keyword)
    if method == "abatch":
        _check_results((await value)[0], executed=executed)
    elif method == "abatch_as_completed":
        outcome = [row async for row in value]
        assert [index for index, _ in outcome] == [0]
        _check_results(outcome[0][1], executed=executed)
    elif method == "astream":
        _check_results([result async for result in value], executed=executed)
    elif method == "astream_events":
        events = [event async for event in value]
        expected = (
            ["run.start", "plan.end", "tool.start", "tool.end", "run.end"]
            if executed else ["run.start", "plan.end", "run.end"]
        )
        assert [event.event for event in events] == expected
        assert [event.sequence for event in events] == list(range(len(expected)))
    else:
        _check_results(await value, executed=executed)


@pytest.mark.parametrize(
    "method", ["invoke", "batch", "batch_as_completed", "stream"]
)
def test_router_sync_wrappers_check_auth_at_dispatch(method: str) -> None:
    router, calls, request, allowed, denied = _registered_router()
    _sync_call(router, method, request, config=allowed, executed=True)
    assert calls == [7]
    _sync_call(router, method, request, config=denied, executed=False)
    assert calls == [7], "Denied request must not dispatch a registered callable"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method",
    ["ainvoke", "run", "arun", "abatch", "abatch_as_completed", "astream", "astream_events"],
)
async def test_router_async_wrappers_check_auth_at_dispatch(method: str) -> None:
    router, calls, request, allowed, denied = _registered_router()
    await _async_call(router, method, request, config=allowed, executed=True)
    assert calls == [7]
    await _async_call(router, method, request, config=denied, executed=False)
    assert calls == [7], "Denied request must not dispatch a registered callable"


@pytest.mark.parametrize(
    "method", ["invoke", "batch", "batch_as_completed", "stream"]
)
def test_configured_sync_wrappers_check_auth_at_dispatch(method: str) -> None:
    router, calls, request, allowed, denied = _registered_router()
    _sync_call(router.with_config(allowed), method, request, executed=True)
    assert calls == [7]
    _sync_call(router.with_config(denied), method, request, executed=False)
    assert calls == [7], "Configured denied context must not call provider"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method", ["ainvoke", "abatch", "abatch_as_completed", "astream", "astream_events"]
)
async def test_configured_async_wrappers_check_auth_at_dispatch(
    method: str,
) -> None:
    router, calls, request, allowed, denied = _registered_router()
    await _async_call(router.with_config(allowed), method, request, executed=True)
    assert calls == [7]
    await _async_call(router.with_config(denied), method, request, executed=False)
    assert calls == [7], "Configured denied context must not call provider"



@pytest.mark.asyncio
async def test_unavailable_registered_callable_abstains_then_recovers() -> None:
    """Temporary runtime unavailability blocks public execution, not registration."""
    router, calls, request, allowed, _ = _registered_router()
    router.mark_access_unavailable("lookup", "call", cooldown_seconds=120)
    assert ("lookup", "call") in router.unavailable_access_paths()
    result = await router.ainvoke(request, config=allowed)
    assert result == []
    events = [
        event async for event in router.astream_events(request, config=allowed)
    ]
    assert [event.event for event in events] == [
        "run.start", "plan.end", "run.end"
    ]
    assert calls == []

    router.mark_access_available("lookup", "call")
    assert ("lookup", "call") not in router.unavailable_access_paths()
    _check_results(await router.ainvoke(request, config=allowed), executed=True)
    assert calls == [7]


@pytest.mark.asyncio
async def test_removed_registered_callable_cannot_execute_stale_plan() -> None:
    """Old authorized plan receipts must not survive registry deregistration."""
    router, calls, request, allowed, _ = _registered_router()
    plan = router.plan_executable_authorized(
        request,
        principal=allowed.principal,
    )
    assert plan.executable and len(plan.calls) == 1
    await router.aremove_tool("lookup")
    with pytest.raises(PolicyViolationError, match="authorization denied"):
        await router.execute(plan, config=allowed)
    assert calls == [], "Removed source must never be dispatched by stale receipt"
