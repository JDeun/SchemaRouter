"""Public SDK direct execution refuses non-executable paper receipts before I/O."""
from unittest.mock import Mock

import pytest

from schemarouter.errors import PolicyViolationError
from schemarouter.field_routing_session import SchemaFieldRoutingSession


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [
    "requires_arguments", "requires_observation", "no_proven_hit",
    "over_k_unranked", "budget_unsatisfied", "ambiguous_paths",
])
async def test_direct_sdk_refuses_nonready_paper_receipts(monkeypatch, status):
    import schemarouter.field_routing_session as paper

    session = object.__new__(SchemaFieldRoutingSession)
    object.__setattr__(session, "_router", Mock())
    object.__setattr__(session, "_index", Mock())
    monkeypatch.setattr(SchemaFieldRoutingSession, "_require_catalog", lambda self: Mock())
    monkeypatch.setattr(
        paper, "compile_paper_typed_tool_plan",
        lambda *args, **kwargs: Mock(
            status=status, executable_authority=False, bindings=(), calls=(),
        ),
    )
    with pytest.raises(PolicyViolationError, match="one ready independent route"):
        await session.aexecute_direct("query", principal=Mock())
    session._router.execute.assert_not_called()


@pytest.mark.asyncio
async def test_direct_sdk_dispatches_one_host_proven_native_call(monkeypatch):
    from contextlib import nullcontext
    from unittest.mock import AsyncMock

    import schemarouter.field_routing_session as module

    session = object.__new__(SchemaFieldRoutingSession)
    router = Mock()
    router.execute = AsyncMock(return_value=["native-result"])
    router.registry.get.return_value.endpoint.return_value.read_only = True
    router.registry.get.return_value.endpoint.return_value.destructive = False
    router.planner.availability_predicate = None
    binding = Mock(invoker=Mock(), generation=1)
    router.executor._binding_snapshot.return_value = binding
    object.__setattr__(session, "_router", router)
    index = Mock()
    object.__setattr__(session, "_index", index)
    monkeypatch.setattr(SchemaFieldRoutingSession, "_require_catalog", lambda self: Mock())
    call = Mock(
        executable=True, missing_required_arguments=(),
        tool="native", endpoint="get",
    )
    call.model_copy.return_value = call
    selected = Mock(call=call)
    plan = Mock(
        status="ready", executable_authority=False,
        bindings=(), calls=(selected,), registry_version=1,
    )
    monkeypatch.setattr(
        module, "compile_paper_typed_tool_plan",
        lambda *args, **kwargs: plan,
    )
    monkeypatch.setattr(module, "_check_current_call_scopes", Mock(), raising=False)
    import schemarouter.paper_typed_tool_plan as typed
    monkeypatch.setattr(typed, "_check_current_call_scopes", Mock())
    import schemarouter.executor as executor
    monkeypatch.setattr(
        executor, "_require_bound_invoker_generation",
        lambda *args, **kwargs: nullcontext(),
    )
    import schemarouter.models as models
    from schemarouter.authorization import PrincipalContext
    monkeypatch.setattr(models, "ExecutionPlan", lambda **kwargs: Mock(**kwargs))
    principal = PrincipalContext(subject="test-direct-sdk")
    result = await session.aexecute_direct("query", principal=principal)
    assert result == ["native-result"]
    router.execute.assert_awaited_once()
    execution_plan = router.execute.await_args.args[0]
    assert len(execution_plan.calls) == 1
    assert execution_plan.calls[0] is call
    index.field_index._assert_source.assert_called()


@pytest.mark.asyncio
async def test_direct_sdk_refuses_binding_mutated_by_availability(monkeypatch):
    from unittest.mock import AsyncMock

    import schemarouter.field_routing_session as module
    import schemarouter.paper_typed_tool_plan as typed

    session = object.__new__(SchemaFieldRoutingSession)
    router = Mock()
    router.execute = AsyncMock()
    object.__setattr__(session, "_router", router)
    object.__setattr__(session, "_index", Mock())
    monkeypatch.setattr(SchemaFieldRoutingSession, "_require_catalog", lambda self: Mock())
    call = Mock(executable=True, missing_required_arguments=(), tool="native", endpoint="get")
    plan = Mock(
        status="ready", executable_authority=False, bindings=(),
        calls=(Mock(call=call),), registry_version=1,
    )
    monkeypatch.setattr(module, "compile_paper_typed_tool_plan", lambda *a, **kw: plan)
    monkeypatch.setattr(typed, "_check_current_call_scopes", Mock())
    endpoint = router.registry.get.return_value.endpoint.return_value
    endpoint.read_only = True
    endpoint.destructive = False
    initial = Mock(invoker=Mock(), generation=1)
    changed = Mock(invoker=Mock(), generation=2)
    router.executor._binding_snapshot.side_effect = [initial, initial, changed]
    router.planner.availability_predicate = lambda tool, endpoint: True
    with pytest.raises(PolicyViolationError, match="source changed during availability"):
        await session.aexecute_direct("query", principal=Mock())
    router.execute.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["dependent", "unbound", "not_read_only"])
async def test_direct_sdk_rejects_unsafe_execution_shapes(monkeypatch, case):
    """Never dispatch a dependent, unbound or mutating paper route."""
    from unittest.mock import AsyncMock

    import schemarouter.field_routing_session as module

    session = object.__new__(SchemaFieldRoutingSession)
    router = Mock()
    router.execute = AsyncMock()
    object.__setattr__(session, "_router", router)
    object.__setattr__(session, "_index", Mock())
    monkeypatch.setattr(SchemaFieldRoutingSession, "_require_catalog", lambda self: Mock())
    call = Mock(
        executable=True, missing_required_arguments=(), tool="native", endpoint="get",
    )
    plan = Mock(
        status="ready", executable_authority=False,
        bindings=(Mock(),) if case == "dependent" else (),
        calls=(Mock(call=call),), registry_version=1,
    )
    monkeypatch.setattr(module, "compile_paper_typed_tool_plan", lambda *a, **kw: plan)
    binding = Mock(invoker=None if case == "unbound" else Mock(), generation=1)
    router.executor._binding_snapshot.return_value = binding
    endpoint = router.registry.get.return_value.endpoint.return_value
    endpoint.read_only = case != "not_read_only"
    endpoint.destructive = False
    import schemarouter.paper_typed_tool_plan as typed
    monkeypatch.setattr(typed, "_check_current_call_scopes", Mock())
    with pytest.raises(PolicyViolationError):
        await session.aexecute_direct("query", principal=Mock())
    router.execute.assert_not_called()


@pytest.mark.asyncio
async def test_direct_sdk_real_registered_native_invoker_end_to_end():
    """Public SDK must reach the real registered executor, not a mocked execute."""
    from test_research_paper_scoped_agent_real_e0 import CATALOG, QUERY
    from test_research_paper_scoped_native_direct_e1 import _fixture

    from schemarouter import PrincipalContext

    view, _index, seen = _fixture(requires_input=False)
    principal = PrincipalContext(subject="native-e1", roles=("viewer",))
    session = view.router.prepare_field_routing(catalog=CATALOG)
    results = await session.aexecute_direct(QUERY, principal=principal)
    assert seen == [{}]
    assert len(results) == 1
    assert results[0].tool == "complete"
    assert results[0].endpoint == "read"
    assert results[0].data["status"] == "open"


@pytest.mark.asyncio
async def test_direct_sdk_real_native_invoker_uses_only_host_arguments():
    from test_research_paper_scoped_agent_real_e0 import CATALOG, QUERY
    from test_research_paper_scoped_native_direct_e1 import _fixture

    from schemarouter import PrincipalContext

    view, _index, seen = _fixture()
    principal = PrincipalContext(subject="native-e1", roles=("viewer",))
    session = view.router.prepare_field_routing(
        catalog=CATALOG, approved_host_roots=frozenset({"complete.read"}),
    )
    results = await session.aexecute_direct(
        QUERY, principal=principal,
        host_source_arguments={"complete.read": {"case_id": "host-7"}},
    )
    assert seen == [{"case_id": "host-7"}]
    assert len(results) == 1
    assert results[0].data["case_id"] == "host-7"
