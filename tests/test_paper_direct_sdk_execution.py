"""Public SDK executes only complete source-proven Algorithm 1 direct plans."""
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from test_research_paper_scoped_agent_real_e0 import CATALOG, INTENTS, QUERY
from test_research_paper_scoped_native_direct_e1 import _native_router

from schemarouter import ExecutionPlan, PrincipalContext
from schemarouter.errors import PolicyViolationError
from schemarouter.paper_native_rank import PaperNativeRankPolicy
from schemarouter.paper_typed_tool_plan import PaperPlanBinding
from schemarouter.paper_understood_direct_plan import PaperUnderstanding

PRINCIPAL = PrincipalContext(subject="native-e1", roles=("viewer",))


def _direct_kwargs(session):
    """Fresh owner declarations; untrusted proposals remain outside host inputs."""
    return {
        "understanding": PaperUnderstanding(
            intent_id="case.lookup", concept_ids=("case.status",),
            named_tools=("complete",), parameter_hints={"case_id": "model-forged"},
        ),
        "intent_registry": INTENTS.model_copy(deep=True),
        "rank_policy": PaperNativeRankPolicy(
            snapshot_id=session.snapshot_id, direct_score_mode="paper_v1",
            focus_direct=True,
        ),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [
    "requires_arguments", "requires_observation", "no_proven_hit",
    "over_k_unranked", "budget_unsatisfied", "ambiguous_paths",
])
async def test_direct_sdk_refuses_nonready_paper_receipts(monkeypatch, status):
    import schemarouter.field_routing_session as paper

    router, _index, seen = _native_router(requires_input=False)
    session = router.prepare_field_routing(catalog=CATALOG)
    kwargs = _direct_kwargs(session)
    ready = session.compile_understood(principal=PRINCIPAL, **kwargs)
    assert ready.status == "ready" and ready.calls[0].call.executable
    # Incomplete paper results can retain locally executable calls. Their
    # status, not only ToolCall.executable, must stop the whole dispatch.
    monkeypatch.setattr(
        paper, "compile_paper_understood_direct_plan",
        lambda *args, **kw: replace(ready, status=status),
    )
    with pytest.raises(PolicyViolationError):
        await session.aexecute_direct(QUERY, principal=PRINCIPAL, **kwargs)
    assert seen == []


@pytest.mark.asyncio
async def test_direct_sdk_dispatches_one_host_proven_native_call(monkeypatch):
    router, _index, seen = _native_router(requires_input=False)
    session = router.prepare_field_routing(catalog=CATALOG)
    execute = AsyncMock(wraps=router.execute)
    monkeypatch.setattr(router, "execute", execute)
    results = await session.aexecute_direct(
        QUERY, principal=PRINCIPAL, **_direct_kwargs(session),
    )
    assert seen == [{}]
    assert results[0].data["status"] == "open"
    execute.assert_awaited_once()
    plan = execute.await_args.args[0]
    assert isinstance(plan, ExecutionPlan)
    assert len(plan.calls) == 1 and not plan.fallback_routes
    assert plan.calls[0].tool == "complete"
    assert plan.calls[0].arguments == {}
    assert plan.calls[0].fields == ["status", "case_id"]


@pytest.mark.asyncio
async def test_direct_sdk_refuses_binding_mutated_by_availability(monkeypatch):
    import schemarouter.field_routing_session as paper

    router, _index, seen = _native_router(requires_input=False)
    session = router.prepare_field_routing(catalog=CATALOG)
    original = paper.compile_paper_understood_direct_plan
    compiled = 0
    replaced = []
    swapped = False

    def compile_plan(*args, **kwargs):
        nonlocal compiled
        result = original(*args, **kwargs)
        compiled += 1
        return result

    def replacement(endpoint, arguments):
        replaced.append((endpoint, arguments))
        return {"status": "changed", "case_id": "replacement"}

    def availability(_tool, _endpoint):
        nonlocal swapped
        if compiled and not swapped:
            swapped = True
            router.executor.bind(
                "complete", replacement,
                expected_fingerprint=router.registry.get("complete").fingerprint,
            )
        return True

    monkeypatch.setattr(paper, "compile_paper_understood_direct_plan", compile_plan)
    router._source_availability.predicate = availability
    with pytest.raises(PolicyViolationError):
        await session.aexecute_direct(QUERY, principal=PRINCIPAL, **_direct_kwargs(session))
    assert swapped and seen == [] and replaced == []


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["dependent", "unbound", "not_read_only"])
async def test_direct_sdk_rejects_unsafe_execution_shapes(monkeypatch, case):
    """Never dispatch a dependent, unbound or mutating paper route."""
    import schemarouter.field_routing_session as paper

    router, _index, seen = _native_router(requires_input=False)
    if case == "not_read_only":
        tool = router.registry.get("complete")
        tool.endpoint("read").read_only = False
        tool.endpoint("read").destructive = True
        invoker = router.executor._binding_snapshot("complete").invoker
        assert invoker is not None
        router.add_bound_tool(tool, invoker, replace=True)
    session = router.prepare_field_routing(catalog=CATALOG)
    kwargs = _direct_kwargs(session)
    if case == "dependent":
        ready = session.compile_understood(principal=PRINCIPAL, **kwargs)
        dependent = replace(ready, bindings=(PaperPlanBinding(0, "case_id", 0, "case_id"),))
        monkeypatch.setattr(
            paper, "compile_paper_understood_direct_plan", lambda *args, **kw: dependent,
        )
    elif case == "unbound":
        router.executor.unbind("complete")
    with pytest.raises(PolicyViolationError):
        await session.aexecute_direct(QUERY, principal=PRINCIPAL, **kwargs)
    assert seen == []


@pytest.mark.asyncio
async def test_direct_sdk_real_registered_native_invoker_end_to_end():
    """Public SDK must reach the real registered executor, not a mocked execute."""
    router, _index, seen = _native_router(requires_input=False)
    session = router.prepare_field_routing(catalog=CATALOG)
    results = await session.aexecute_direct(
        QUERY, principal=PRINCIPAL, **_direct_kwargs(session),
    )
    assert seen == [{}]
    assert len(results) == 1
    assert results[0].tool == "complete"
    assert results[0].endpoint == "read"
    assert results[0].data["status"] == "open"


@pytest.mark.asyncio
async def test_direct_sdk_real_native_invoker_uses_only_host_arguments():
    router, _index, seen = _native_router()
    session = router.prepare_field_routing(
        catalog=CATALOG, approved_host_roots=frozenset({"complete.read"}),
    )
    results = await session.aexecute_direct(
        QUERY, principal=PRINCIPAL, **_direct_kwargs(session),
        host_source_arguments={"complete.read": {"case_id": "host-7"}},
    )
    assert seen == [{"case_id": "host-7"}]
    assert len(results) == 1
    assert results[0].data["case_id"] == "host-7"
