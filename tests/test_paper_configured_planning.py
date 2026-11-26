"""Configured product planning keeps Algorithm 1 proof through every execution surface."""
from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_paper_algorithm1_execution import _fixture as _direct_source

from schemarouter import (
    AuthorizationPolicy,
    DataScopeRule,
    ExecutionPlan,
    PaperPlanRequest,
    PlanRequest,
    PrincipalContext,
    RunConfig,
)
from schemarouter.errors import PolicyViolationError
from schemarouter.hooks import ExecutionHooks


class _Model:
    def __init__(self, response):
        self.response = response
        self.payloads = []

    def __call__(self, payload):
        self.payloads.append(deepcopy(payload))
        return deepcopy(self.response)


def _configure(ctx, *, session=None, model=None):
    ctx.router.configure_field_routing(
        session or ctx.session,
        model=model or ctx.model,
        intent_registry=ctx.owner["intent_registry"],
        rank_policy=ctx.owner["rank_policy"],
        model_visible_intent_ids=("measurement.compare",),
    )


def _configured(*, count=2, needs_input=False, configure=True):
    session, owner, seen, callbacks = _direct_source(count=count, needs_input=needs_input)
    names = [f"source_{position}" for position in range(count)]
    query = "measurement value in eV from " + " and ".join(names)
    response = {
        "intent_id": "measurement.compare",
        "needs": [{
            "concept": "measurement value", "unit": "eV",
            "source_type": "calculated", "qualifiers": {},
        }],
        "needs_truncated": False,
        "excluded_concepts": [],
        "named_tools": names,
        "parameter_hints": {},
        "source_type": "calculated",
    }
    ctx = SimpleNamespace(
        router=session._router, session=session, owner=owner,
        principal=owner["principal"], model=_Model(response), seen=seen,
        callbacks=callbacks,
        request=PaperPlanRequest(
            query=query, host_source_arguments=owner["host_source_arguments"] or {},
        ),
    )
    if configure:
        _configure(ctx)
    return ctx


def _forbid_lexical(ctx, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("configured product planning entered the retired lexical candidate path")
    for name in ("_analyze_sync", "_analyze_async", "_candidates", "_build_plan"):
        monkeypatch.setattr(ctx.router.planner, name, forbidden)


async def _run_surface(ctx, surface, request=None):
    request = request or ctx.request
    config = RunConfig(principal=ctx.principal)
    if surface in ("execute", "parallel"):
        plan = await ctx.router.aplan_authorized(request, principal=ctx.principal)
        if surface == "parallel":
            config.execution_mode = "parallel_read_only"
        results = await ctx.router.execute(plan, config=config)
    elif surface == "ainvoke":
        results = await ctx.router.ainvoke(request, config=config)
    elif surface == "astream":
        results = [result async for result in ctx.router.astream(request, config=config)]
    elif surface == "astream_events":
        events = [event async for event in ctx.router.astream_events(request, config=config)]
        assert events[-1].event == "run.end"
        assert not any(event.event == "tool.fallback" for event in events)
        return [event.tool for event in events if event.event == "tool.end"]
    elif surface == "configured_wrapper":
        results = await ctx.router.with_config(config).ainvoke(request)
    else:
        raise AssertionError(surface)
    return [result.tool for result in results]


SURFACES = ("execute", "ainvoke", "astream", "astream_events", "parallel", "configured_wrapper")


def test_configured_plan_and_aplan_share_algorithm1_without_lexical_analysis(monkeypatch):
    ctx = _configured(needs_input=True)
    _forbid_lexical(ctx, monkeypatch)
    sync = ctx.router.plan_authorized(ctx.request, principal=ctx.principal)
    asynchronous = asyncio.run(ctx.router.aplan_authorized(ctx.request, principal=ctx.principal))
    assert sync.model_dump() == asynchronous.model_dump()
    assert sync.planning_status == "ready" and sync.executable
    assert sync.coverage is not None and sync.coverage.complete
    assert len(sync.calls) == 2 and not sync.fallback_routes
    assert all(call.arguments == {"sample_id": "host-7"} for call in sync.calls)
    assert all(call.fields == ["sample_id", "value", "uncertainty"] for call in sync.calls)
    assert ctx.seen == [] and len(ctx.model.payloads) == 2
    for payload in ctx.model.payloads:
        assert payload["query"] == ctx.request.query
        assert payload["intents"] == ["measurement.compare"]
        assert "needs" in payload["response_schema"]["properties"]
        assert not {"schema_catalog", "offered_concepts", "tools", "routes"} & payload.keys()
        assert "measurement.value" not in json.dumps(payload)
        assert "CC0-1.0" not in json.dumps(payload)


def test_configured_input_schema_describes_active_paper_request_contract():
    ctx = _configured(configure=False)
    assert ctx.router.input_schema == PlanRequest.model_json_schema()
    _configure(ctx)
    assert ctx.router.input_schema == PaperPlanRequest.model_json_schema()
    assert "host_source_arguments" in ctx.router.input_schema["properties"]
    assert "arguments" not in ctx.router.input_schema["properties"]


@pytest.mark.parametrize("surface", SURFACES)
async def test_configured_execution_surfaces_use_one_understanding_and_same_native_plan(
    monkeypatch, surface,
):
    ctx = _configured(needs_input=True)
    _forbid_lexical(ctx, monkeypatch)
    assert sorted(await _run_surface(ctx, surface)) == ["source_0", "source_1"]
    assert sorted(source for source, _, _ in ctx.seen) == ["source_0", "source_1"]
    assert all(arguments == {"sample_id": "host-7"} for _, _, arguments in ctx.seen)
    assert len(ctx.model.payloads) == 1, "dispatch must revalidate needs without another model call"


def test_configured_sync_wrapper_uses_the_same_paper_path(monkeypatch):
    ctx = _configured(count=1)
    _forbid_lexical(ctx, monkeypatch)
    results = ctx.router.with_config(RunConfig(principal=ctx.principal)).invoke(ctx.request.query)
    assert [result.tool for result in results] == ["source_0"]
    assert ctx.seen == [("source_0", "read", {})]
    assert len(ctx.model.payloads) == 1


@pytest.mark.parametrize("case,status", [
    ("missing_need", "no_proven_hit"),
    ("unit", "no_proven_hit"),
    ("qualifier", "no_proven_hit"),
    ("source", "no_proven_hit"),
    ("exclusion", "ambiguous_paths"),
    ("truncated", "budget_unsatisfied"),
    ("no_intent", "no_proven_hit"),
    ("invented_named_source", "no_proven_hit"),
])
async def test_configured_plan_preserves_full_needs_and_nonready_execution_gate(case, status):
    ctx = _configured()
    raw = ctx.model.response
    if case == "missing_need":
        raw["needs"].append({"concept": "unregistered additional answer"})
    elif case == "unit":
        raw["needs"][0]["unit"] = "J"
    elif case == "qualifier":
        raw["needs"][0]["qualifiers"] = {"role": "forecast"}
    elif case == "source":
        raw["needs"][0]["source_type"] = "experimental"
    elif case == "exclusion":
        raw["excluded_concepts"] = ["measurement value"]
    elif case == "truncated":
        raw["needs_truncated"] = True
    elif case == "no_intent":
        raw["intent_id"] = None
    else:
        raw["named_tools"] = ["not stated by user"]
    plan = await ctx.router.aplan_authorized(ctx.request, principal=ctx.principal)
    assert plan.planning_status == status and not plan.executable
    assert plan.coverage is not None and not plan.coverage.complete
    if case == "missing_need":
        assert plan.calls, "retain useful partial diagnostics without making them executable"
    with pytest.raises(PolicyViolationError):
        await ctx.router.execute(plan, config=RunConfig(principal=ctx.principal))
    assert ctx.seen == [] and len(ctx.model.payloads) == 1


@pytest.mark.parametrize("surface", SURFACES)
async def test_configured_nonready_plan_is_denied_on_every_execution_surface(surface):
    ctx = _configured()
    ctx.model.response["needs"].append({"concept": "unregistered additional answer"})
    with pytest.raises(PolicyViolationError):
        await _run_surface(ctx, surface)
    assert ctx.seen == [] and len(ctx.model.payloads) == 1


async def test_configured_model_parameters_never_become_host_arguments():
    ctx = _configured(count=1, needs_input=True)
    ctx.model.response["parameter_hints"] = {"sample_id": "model-only"}
    no_host = PaperPlanRequest(query=ctx.request.query)
    plan = await ctx.router.aplan_authorized(no_host, principal=ctx.principal)
    assert plan.planning_status == "requires_arguments" and not plan.executable
    assert plan.calls[0].arguments == {}
    assert plan.calls[0].missing_required_arguments == ["sample_id"]
    with pytest.raises(PolicyViolationError):
        await ctx.router.execute(plan, config=RunConfig(principal=ctx.principal))
    assert ctx.seen == [] and len(ctx.model.payloads) == 1


async def test_configured_hard_call_budget_keeps_diagnostics_without_truncating_sources():
    ctx = _configured()
    request = ctx.request.model_copy(update={"max_calls": 1})
    plan = await ctx.router.aplan_authorized(request, principal=ctx.principal)
    assert plan.planning_status == "budget_unsatisfied" and not plan.executable
    assert [call.tool for call in plan.calls] == ["source_0", "source_1"]
    with pytest.raises(PolicyViolationError):
        await ctx.router.execute(plan, config=RunConfig(principal=ctx.principal))
    assert ctx.seen == []


async def test_configured_plan_executable_does_not_substitute_an_unbound_named_source():
    ctx = _configured()
    ctx.router.executor.unbind("source_1")
    with pytest.raises(PolicyViolationError):
        await ctx.router.aplan_executable_authorized(ctx.request, principal=ctx.principal)
    assert ctx.seen == [] and len(ctx.model.payloads) == 1


async def test_configured_plan_witness_survives_deep_copy_but_not_serialization():
    ctx = _configured()
    plan = await ctx.router.aplan_authorized(ctx.request, principal=ctx.principal)
    copy = plan.model_copy(deep=True)
    results = await ctx.router.execute(copy, config=RunConfig(principal=ctx.principal))
    assert [result.tool for result in results] == ["source_0", "source_1"]
    ctx.seen.clear()
    restored = ExecutionPlan.model_validate_json(plan.model_dump_json())
    with pytest.raises(PolicyViolationError):
        await ctx.router.execute(restored, config=RunConfig(principal=ctx.principal))
    assert ctx.seen == [] and len(ctx.model.payloads) == 1


async def test_configured_execute_snapshots_plan_before_caller_can_append_an_unsealed_call():
    ctx = _configured(count=1)
    plan = await ctx.router.aplan_authorized(ctx.request, principal=ctx.principal)
    changed = False

    async def append_unsealed_call(_tool, _endpoint, _call):
        nonlocal changed
        await asyncio.sleep(0)
        if not changed:
            changed = True
            original = plan.calls[0]
            plan.calls.append(type(original).model_validate_json(original.model_dump_json()))

    ctx.router.executor.hooks = ExecutionHooks(before_call=(append_unsealed_call,))
    results = await ctx.router.execute(plan, config=RunConfig(principal=ctx.principal))
    assert changed and len(plan.calls) == 2
    assert [result.tool for result in results] == ["source_0"]
    assert ctx.seen == [("source_0", "read", {})]
    assert len(ctx.model.payloads) == 1


@pytest.mark.parametrize("mutation", ["fields", "calls", "status", "query"])
async def test_configured_modified_plan_cannot_reuse_its_private_witness(mutation):
    ctx = _configured()
    plan = await ctx.router.aplan_authorized(ctx.request, principal=ctx.principal)
    changed = plan.model_copy(deep=True)
    if mutation == "fields":
        changed.calls[0].fields = ["sample_id"]
    elif mutation == "calls":
        changed.calls = changed.calls[:1]
    elif mutation == "status":
        changed.planning_status = None
    else:
        changed.query = "different user request"
    with pytest.raises(PolicyViolationError):
        await ctx.router.execute(changed, config=RunConfig(principal=ctx.principal))
    assert ctx.seen == [] and len(ctx.model.payloads) == 1


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("mutation", ["binding", "configuration"])
async def test_configured_awaited_hook_cannot_replace_bound_source_or_configuration(
    surface, mutation,
):
    ctx = _configured()
    replacements = []

    async def change(tool, _endpoint, _call):
        await asyncio.sleep(0)
        if mutation == "configuration":
            _configure(ctx)
        else:
            def replacement(endpoint, arguments):
                replacements.append((endpoint, arguments))
                return {"sample_id": "other", "value": 9.0, "uncertainty": 0.2}
            ctx.router.executor.bind(tool.key, replacement, expected_fingerprint=tool.fingerprint)

    ctx.router.executor.hooks = ExecutionHooks(before_call=(change,))
    with pytest.raises(PolicyViolationError):
        await _run_surface(ctx, surface)
    assert ctx.seen == [] and replacements == []
    assert len(ctx.model.payloads) == 1


async def test_configured_source_change_during_model_await_fails_without_provider_io():
    ctx = _configured(configure=False)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def model(payload):
        ctx.model.payloads.append(deepcopy(payload))
        entered.set()
        await release.wait()
        return deepcopy(ctx.model.response)

    _configure(ctx, model=model)
    task = asyncio.create_task(ctx.router.aplan_authorized(ctx.request, principal=ctx.principal))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        tool = ctx.router.registry.get("source_0")
        ctx.router.registry.register(tool, replace=True)
        release.set()
        with pytest.raises(PolicyViolationError):
            await asyncio.wait_for(task, 5)
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert ctx.seen == [] and len(ctx.model.payloads) == 1


async def test_configured_owner_declarations_are_detached_from_caller_mutation():
    ctx = _configured()
    ctx.owner["rank_policy"].direct_score_mode = "typed"
    ctx.owner["intent_registry"].intents[0].required_concept_ids = ("not-reviewed",)
    plan = await ctx.router.aplan_authorized(ctx.request, principal=ctx.principal)
    assert plan.planning_status == "ready" and plan.executable
    results = await ctx.router.execute(plan, config=RunConfig(principal=ctx.principal))
    assert [result.tool for result in results] == ["source_0", "source_1"]
    assert len(ctx.model.payloads) == 1


@pytest.mark.parametrize("case", ["legacy_request", "no_principal", "stale_source"])
async def test_configured_invalid_requests_fail_before_model_disclosure(case):
    ctx = _configured()
    if case == "legacy_request":
        request = PlanRequest(query=ctx.request.query)
    else:
        request = ctx.request
    if case == "stale_source":
        ctx.router.registry.register(ctx.router.registry.get("source_0"), replace=True)
    with pytest.raises((TypeError, ValueError, PolicyViolationError)):
        if case == "no_principal":
            await ctx.router.aplan(request)
        else:
            await ctx.router.aplan_authorized(request, principal=ctx.principal)
    assert ctx.model.payloads == [] and ctx.seen == []


async def test_paper_request_requires_configuration_before_lexical_planning(monkeypatch):
    ctx = _configured(configure=False)
    _forbid_lexical(ctx, monkeypatch)
    with pytest.raises((TypeError, ValueError, PolicyViolationError)):
        await ctx.router.aplan_authorized(ctx.request, principal=ctx.principal)
    assert ctx.model.payloads == [] and ctx.seen == []


@pytest.mark.parametrize("case", ["foreign_session", "stale_session", "legacy_rank"])
def test_configure_rejects_foreign_or_stale_source_before_model(case):
    ctx = _configured(configure=False)
    session = ctx.session
    if case == "foreign_session":
        session = _configured(configure=False).session
    elif case == "stale_session":
        ctx.router.registry.register(ctx.router.registry.get("source_0"), replace=True)
    else:
        ctx.owner["rank_policy"].direct_score_mode = "typed"
    with pytest.raises((TypeError, ValueError, PolicyViolationError)):
        _configure(ctx, session=session)
    assert ctx.model.payloads == [] and ctx.seen == []


async def test_configured_plan_remains_bound_to_the_current_principal():
    ctx = _configured()
    plan = await ctx.router.aplan_authorized(ctx.request, principal=ctx.principal)
    other = PrincipalContext(subject="different-reader", roles=("reader",))
    with pytest.raises(PolicyViolationError):
        await ctx.router.execute(plan, config=RunConfig(principal=other))
    assert ctx.seen == [] and len(ctx.model.payloads) == 1


@pytest.mark.parametrize("change", ["authorization", "field_scope", "availability"])
async def test_configured_execute_rechecks_live_policy_scope_and_availability(change):
    ctx = _configured(count=1)
    plan = await ctx.router.aplan_authorized(ctx.request, principal=ctx.principal)
    assert plan.executable
    if change == "authorization":
        ctx.router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    elif change == "field_scope":
        ctx.router.authorization_policy = replace(ctx.router.authorization_policy, data_rules=(
            DataScopeRule(
                operation="source_0.read", roles_any=("reader",), hidden_fields=("value",),
            ),
        ))
    else:
        ctx.router.mark_access_unavailable("source_0", "read", cooldown_seconds=120)
    with pytest.raises(PolicyViolationError):
        await ctx.router.execute(plan, config=RunConfig(principal=ctx.principal))
    assert ctx.seen == [] and len(ctx.model.payloads) == 1


async def test_configured_trace_redacts_nested_paper_host_inputs_before_model_call():
    ctx = _configured(count=1)
    canary = "PAPER_TRACE_PRIVATE_CANARY"
    request = PaperPlanRequest(
        query=ctx.request.query,
        host_source_arguments={"source_0.read": {"api_key": canary}},
    )
    stream = ctx.router.astream_events(request, config=RunConfig(
        principal=ctx.principal, include_payloads=True, raw_trace_payloads=False,
    ))
    try:
        event = await anext(stream)
        assert event.event == "run.start"
        assert type(event.data["input"]) is dict
        nested = event.data["input"]["host_source_arguments"]["source_0.read"]
        assert type(nested) is dict and nested["api_key"] == "[REDACTED]"
        assert canary not in json.dumps(event.data)
        assert canary not in event.model_dump_json()
        assert ctx.model.payloads == [] and ctx.seen == []
    finally:
        await stream.aclose()


async def test_configured_model_request_mutation_does_not_expose_private_serialization_error():
    ctx = _configured(count=1, needs_input=True, configure=False)

    class PrivateRequestValue:
        def __repr__(self):
            return "PRIVATE_REQUEST_CANARY"

    def mutate_request(payload):
        ctx.model.payloads.append(deepcopy(payload))
        ctx.request.host_source_arguments["source_0.read"]["sample_id"] = PrivateRequestValue()
        return deepcopy(ctx.model.response)

    _configure(ctx, model=mutate_request)
    with pytest.raises(PolicyViolationError) as caught:
        await ctx.router.aplan_authorized(ctx.request, principal=ctx.principal)
    message = str(caught.value)
    assert "PRIVATE_REQUEST_CANARY" not in message
    assert PrivateRequestValue.__name__ not in message
    assert caught.value.__cause__ is None and caught.value.__suppress_context__
    assert ctx.seen == [] and len(ctx.model.payloads) == 1


async def test_configured_session_direct_execution_is_retired_before_compilation(monkeypatch):
    import schemarouter.field_routing_session as module

    ctx = _configured(count=1)
    compiler_calls = []

    def forbidden(*args, **kwargs):
        compiler_calls.append((args, kwargs))
        pytest.fail("configured session direct entry must refuse before compilation")

    monkeypatch.setattr(module, "compile_paper_understood_direct_plan", forbidden)
    with pytest.raises(
        PolicyViolationError,
        match="configured field routing uses router.plan/aplan and execute",
    ):
        await ctx.session.aexecute_direct(ctx.request.query, **ctx.owner)
    assert compiler_calls == [] and ctx.model.payloads == [] and ctx.seen == []
