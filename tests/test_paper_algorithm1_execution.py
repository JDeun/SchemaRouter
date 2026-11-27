"""Algorithm 1 uses the existing executor without lexical or dependency replanning."""
from __future__ import annotations

import asyncio
import threading
from dataclasses import replace

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeSchemaGraphIndex,
    ParameterSpec,
    PlanCoverage,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.errors import PolicyViolationError
from schemarouter.hooks import ExecutionHooks
from schemarouter.paper_native_rank import PaperNativeRankPolicy
from schemarouter.paper_understood_direct_plan import (
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperUnderstanding,
)
from scripts.research_legacy_router import legacy_router

QUERY = "Compare the requested measurement across the named sources"


def _fixture(
    *, count=2, needs_input=True, missing_required=False, named=True, offload_sync=False,
    legacy=False,
):
    principal = PrincipalContext(subject="analyst", roles=("reader",))
    router_factory = legacy_router if legacy else SchemaRouter
    router = router_factory(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
    ))
    seen = []
    callbacks = {}
    names = tuple(f"source_{position}" for position in range(count))
    for name in names:
        def invoke(endpoint, arguments, source=name):
            seen.append((source, endpoint, dict(arguments)))
            if source in callbacks:
                callbacks[source]()
            return {
                "sample_id": arguments.get("sample_id", "sample-1"),
                "value": 1.25, "uncertainty": 0.01, "unrequested": "omit",
            }

        parameters = [ParameterSpec(
            name="sample_id", semantic_id="sample.id", required=True,
            json_schema={"type": "string", "minLength": 1},
        )] if needs_input else []
        input_schema = {
            "type": "object", "properties": {
                "sample_id": {"type": "string", "minLength": 1},
            }, "required": ["sample_id"], "additionalProperties": False,
        } if needs_input else {}
        router.add_bound_tool(ToolSpec(
            name=name, source_type="calculated", license="CC0-1.0",
            endpoints=[EndpointSpec(
                name="read", read_only=True, parameters=parameters,
                input_schema=input_schema,
                output_fields=[
                    FieldSpec(name="sample_id", semantic_id="sample.id", identifier=True,
                              json_schema={"type": "string"}),
                    FieldSpec(name="value", semantic_id="measurement.value", unit="eV",
                              json_schema={"type": "number"}),
                    FieldSpec(name="uncertainty", semantic_id="measurement.uncertainty",
                              unit="eV", json_schema={"type": "number"}),
                    FieldSpec(name="unrequested", json_schema={"type": "string"}),
                ],
            )],
        ), invoke, offload_sync=offload_sync)
    concepts = [NativeDeclaredConcept(
        concept_id="measurement.value", aliases=("measurement value",),
        required_fields=(CapabilityFieldContract(
            semantic_id="measurement.value", unit="eV", json_schema={"type": "number"},
        ),), source_type="calculated", license="CC0-1.0",
    )]
    if missing_required:
        concepts.append(NativeDeclaredConcept(
            concept_id="measurement.absent", aliases=("unavailable measurement",),
            required_fields=(CapabilityFieldContract(
                semantic_id="measurement.absent", json_schema={"type": "number"},
            ),), source_type="calculated", license="CC0-1.0",
        ))
    session = router.prepare_field_routing(catalog=NativeConceptCatalog(concepts=tuple(concepts)))
    intents = PaperIntentRegistry(
        intents=(PaperIntentDeclaration(
            intent_id="measurement.compare",
            required_concept_ids=tuple(concept.concept_id for concept in concepts),
            recall_group_ids=("measurement",),
        ),),
        projection_snapshot_id=session.snapshot_id,
        route_field_groups={
            f"{name}.read": {"measurement": ("value", "uncertainty")} for name in names
        },
        approved_direct_parameter_routes=(
            tuple(f"{name}.read" for name in names) if needs_input else ()
        ),
    )
    kwargs = {
        "principal": principal,
        "understanding": PaperUnderstanding(
            intent_id="measurement.compare", concept_ids=("measurement.value",),
            named_tools=names if named else (), source_type="calculated",
            parameter_hints={"sample_id": "model-forged"},
            raw_rank_concepts=("value",),
        ),
        "intent_registry": intents,
        "rank_policy": PaperNativeRankPolicy(
            snapshot_id=session.snapshot_id, direct_score_mode="paper_v1", focus_direct=True,
        ),
        "host_source_arguments": (
            {f"{name}.read": {"sample_id": "host-7"} for name in names} if needs_input else None
        ),
    }
    return session, kwargs, seen, callbacks


@pytest.mark.parametrize("count", [1, 2, 5])
async def test_algorithm1_named_sources_keep_field_union_host_inputs_and_metadata(
    monkeypatch, count,
):
    import schemarouter.field_routing_session as module

    session, kwargs, seen, _callbacks = _fixture(count=count)
    receipt = session.compile_understood(**kwargs)
    assert receipt.status == "ready" and receipt.executable_authority is False
    assert len(receipt.calls) == count and receipt.bindings == ()
    for entry in receipt.calls:
        assert entry.call.arguments == {"sample_id": "host-7"}
        assert entry.call.fields == ["sample_id", "value", "uncertainty"]
        assert entry.source_type == "calculated" and entry.license == "CC0-1.0"
        assert next(meta for meta in entry.fields_meta if meta.name == "value").unit == "eV"

    def forbidden(*args, **kw):
        pytest.fail("Algorithm 1 direct execution entered a competing planner")

    monkeypatch.setattr(module, "compile_paper_typed_tool_plan", forbidden)
    monkeypatch.setattr(module, "compile_paper_understood_graph_plan", forbidden)
    from scripts.research_legacy_planning.planner import SchemaPlanner

    assert session._router.planner is None
    assert not hasattr(SchemaPlanner, "_build_paper_direct_plan")
    for name in ("_build_plan", "_analyze_sync", "_candidates"):
        monkeypatch.setattr(SchemaPlanner, name, forbidden)
    for name in ("lookup", "lookup_two_hop", "lookup_bounded_paths", "lookup_shared_root_forks"):
        monkeypatch.setattr(NativeSchemaGraphIndex, name, forbidden)

    results = await session.aexecute_direct(QUERY, **kwargs)
    assert [result.tool for result in results] == [entry.call.tool for entry in receipt.calls]
    assert [entry[0] for entry in seen] == [result.tool for result in results]
    assert all(arguments == {"sample_id": "host-7"} for _, _, arguments in seen)
    for result in results:
        assert result.data == {"sample_id": "host-7", "value": 1.25, "uncertainty": 0.01}
        assert result.projected_fields == ["sample_id", "value", "uncertainty"]
        assert result.field_contracts["value"].unit == "eV"
        assert result.field_contracts["value"].semantic_id == "measurement.value"
    assert receipt.executable_authority is False


async def test_algorithm1_unnamed_paper_rank_focus_executes_one_source():
    session, kwargs, seen, _callbacks = _fixture(needs_input=False, named=False)
    kwargs["rank_policy"].route_priorities = {"source_1.read": 10}
    receipt = session.compile_understood(**kwargs)
    assert receipt.status == "ready" and len(receipt.calls) == 1
    results = await session.aexecute_direct(QUERY, **kwargs)
    assert [result.tool for result in results] == ["source_1"]
    assert seen == [("source_1", "read", {})]


async def test_algorithm1_partial_concept_coverage_never_executes_partial_calls():
    session, kwargs, seen, _callbacks = _fixture(needs_input=False, missing_required=True)
    receipt = session.compile_understood(**kwargs)
    assert receipt.status == "no_proven_hit" and receipt.calls
    assert receipt.coverage is not None and not receipt.coverage.complete
    assert all(entry.call.executable for entry in receipt.calls)
    with pytest.raises(PolicyViolationError):
        await session.aexecute_direct(QUERY, **kwargs)
    assert seen == []


async def test_algorithm1_ready_label_cannot_hide_incomplete_coverage(monkeypatch):
    import schemarouter.field_routing_session as module

    session, kwargs, seen, _callbacks = _fixture()
    receipt = session.compile_understood(**kwargs)
    corrupt = replace(receipt, coverage=PlanCoverage(complete=False))
    monkeypatch.setattr(
        module, "compile_paper_understood_direct_plan", lambda *args, **kw: corrupt,
    )
    with pytest.raises(PolicyViolationError):
        await session.aexecute_direct(QUERY, **kwargs)
    assert seen == []


@pytest.mark.parametrize("case", ["legacy_rank", "unfocused", "wrong_snapshot"])
async def test_algorithm1_requires_current_original_paper_rank_contract(case):
    session, kwargs, seen, _callbacks = _fixture()
    policy = kwargs["rank_policy"]
    if case == "legacy_rank":
        policy.direct_score_mode = "typed"
    elif case == "unfocused":
        policy.focus_direct = False
    else:
        policy.snapshot_id = "0" * 64
    with pytest.raises((ValueError, PolicyViolationError)):
        await session.aexecute_direct(QUERY, **kwargs)
    assert seen == []


@pytest.mark.parametrize("case", [
    "rank", "intent", "understanding", "host_arguments", "catalog", "principal",
])
async def test_algorithm1_owner_mutation_in_awaited_hook_never_dispatches(case):
    session, kwargs, seen, _callbacks = _fixture()

    async def mutate(_tool, _endpoint, _call):
        await asyncio.sleep(0)
        if case == "rank":
            kwargs["rank_policy"].route_priorities["source_1.read"] = 1
        elif case == "intent":
            kwargs["intent_registry"].intents[0].domains = ("changed",)
        elif case == "understanding":
            kwargs["understanding"].parameter_hints["sample_id"] = "changed-model-hint"
        elif case == "host_arguments":
            kwargs["host_source_arguments"]["source_0.read"]["sample_id"] = "changed-host-input"
        elif case == "catalog":
            session._catalog.concepts[0].aliases = ("changed approved meaning",)
        else:
            kwargs["principal"].roles = ()

    session._router.executor.hooks = ExecutionHooks(before_call=(mutate,))
    with pytest.raises(PolicyViolationError):
        await session.aexecute_direct(QUERY, **kwargs)
    assert seen == []
    if case == "rank":
        # A failed proof must not leak its task-local guard into a fresh call.
        session._router.executor.hooks = ExecutionHooks()
        results = await session.aexecute_direct(QUERY, **kwargs)
        assert len(results) == 2 and len(seen) == 2


async def test_algorithm1_later_source_binding_is_pinned_before_first_dispatch():
    session, kwargs, seen, callbacks = _fixture()
    router = session._router
    receipt = session.compile_understood(**kwargs)
    first, second = (entry.call.tool for entry in receipt.calls)
    replacement_calls = []

    def replace_later_source():
        def replacement(endpoint, arguments):
            replacement_calls.append((endpoint, arguments))
            return {"sample_id": "other", "value": 8.0, "uncertainty": 0.5}
        router.executor.bind(
            second, replacement, expected_fingerprint=router.registry.get(second).fingerprint,
        )

    callbacks[first] = replace_later_source
    with pytest.raises(PolicyViolationError):
        await session.aexecute_direct(QUERY, **kwargs)
    assert seen == [(first, "read", {"sample_id": "host-7"})]
    assert replacement_calls == []


async def test_algorithm1_sync_offload_keeps_proof_and_invokes_in_worker():
    session, kwargs, seen, callbacks = _fixture(count=1, offload_sync=True)
    event_loop_thread = threading.get_ident()
    worker_threads = []
    callbacks["source_0"] = lambda: worker_threads.append(threading.get_ident())
    try:
        results = await session.aexecute_direct(QUERY, **kwargs)
        assert len(results) == 1 and results[0].data["value"] == 1.25
        assert seen == [("source_0", "read", {"sample_id": "host-7"})]
        assert len(worker_threads) == 1 and worker_threads[0] != event_loop_thread
    finally:
        await session._router.aclose()


@pytest.mark.parametrize("case", ["rank", "binding"])
async def test_algorithm1_worker_rechecks_witness_after_submission(monkeypatch, case):
    session, kwargs, seen, _callbacks = _fixture(count=1, offload_sync=True)
    router = session._router
    executor = router.executor
    entered_worker = threading.Event()
    release_worker = threading.Event()
    original = executor._invoke_sync_with_policy_snapshot
    replacement_calls = []

    def pause_before_worker_guard(policy, invoker, *args):
        entered_worker.set()
        assert release_worker.wait(5), "test did not release the submitted worker"
        return original(policy, invoker, *args)

    monkeypatch.setattr(executor, "_invoke_sync_with_policy_snapshot", pause_before_worker_guard)
    task = asyncio.create_task(session.aexecute_direct(QUERY, **kwargs))
    try:
        assert await asyncio.to_thread(entered_worker.wait, 5), "sync work was not submitted"
        assert seen == [], "provider must wait behind the worker's final proof check"
        if case == "rank":
            kwargs["rank_policy"].route_priorities["source_0.read"] = 1
        else:
            def replacement(endpoint, arguments):
                replacement_calls.append((endpoint, arguments))
                return {"sample_id": "changed", "value": 9.0, "uncertainty": 0.2}
            executor.bind(
                "source_0", replacement,
                expected_fingerprint=router.registry.get("source_0").fingerprint,
                offload_sync=True,
            )
        release_worker.set()
        with pytest.raises(PolicyViolationError):
            await asyncio.wait_for(task, 5)
        assert seen == [] and replacement_calls == []
    finally:
        release_worker.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await router.aclose()


@pytest.mark.parametrize("component", ["planner", "executor", "source"])
@pytest.mark.parametrize("timing", ["before_entry", "awaited_hook"])
async def test_algorithm1_same_version_component_registry_swap_is_not_original_source(
    component, timing,
):
    session, kwargs, seen, _callbacks = _fixture(count=1, legacy=component == "planner")
    router = session._router
    original = router.registry
    replacement = InMemoryRegistry()
    for tool in original.tools():
        replacement.register(tool)
    assert replacement is not original and replacement.version == original.version
    assert tuple(tool.fingerprint for tool in replacement.tools()) == tuple(
        tool.fingerprint for tool in original.tools()
    )

    def replace_source():
        if component == "source":
            router._source_registry = replacement
        else:
            getattr(router, component).registry = replacement

    if timing == "before_entry":
        replace_source()
    else:
        async def swap(_tool, _endpoint, _call):
            await asyncio.sleep(0)
            replace_source()
        router.executor.hooks = ExecutionHooks(before_call=(swap,))

    with pytest.raises(PolicyViolationError):
        await session.aexecute_direct(QUERY, **kwargs)
    assert seen == []
