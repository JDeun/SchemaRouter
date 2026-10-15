"""Zero-network, zero-model tests for #1291 opt-in no-call execution gate.

These prove that the gate prevents tool invocation on abstention and identity
drift, not that any score threshold can identify all unsupported intents.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from schemarouter import (
    EndpointSpec,
    ExecutionPlan,
    FallbackRoute,
    PlanRequest,
    PolicyViolationError,
    PrincipalContext,
    RetrievalAbstentionPolicy,
    SchemaRouter,
    ToolCall,
    ToolSpec,
    ainvoke_selective,
    execute_selective_plan,
    validate_selective_execution,
)


class FakeDispatchRouter:
    """Fake execution edge: no actual tools are ever called."""

    def __init__(self, version: int) -> None:
        self.registry = SimpleNamespace(version=version)
        self.dispatched: list[ExecutionPlan] = []

    async def execute(self, plan, *, config=None):
        self.dispatched.append(plan)
        return []


def fixture():
    router = SchemaRouter()
    router.add_tool(
        ToolSpec(
            name="paper",
            description="Scientific paper database",
            endpoints=[
                EndpointSpec(
                    name="search",
                    description="Search academic literature",
                    read_only=True,
                ),
                EndpointSpec(
                    name="get",
                    description="Retrieve a paper by identifier",
                    read_only=True,
                ),
            ],
        )
    )
    # The runner fixture deliberately simulates the host's previously scoped
    # executable-only result; no real endpoint binding or execution occurs.
    retrieval = router.retrieve("Search research papers", k=2).model_copy(
        update={"executable_only": True}
    )
    assert len(retrieval.candidates) == 2
    candidate = retrieval.candidates[0]
    call = ToolCall(
        tool=candidate.tool,
        endpoint=candidate.endpoint,
        schema_fingerprint=candidate.endpoint_fingerprint,
        tool_fingerprint=candidate.tool_fingerprint,
    )
    plan = ExecutionPlan(
        query=retrieval.query,
        registry_version=retrieval.registry_version,
        calls=[call],
    )
    sink = FakeDispatchRouter(version=retrieval.registry_version)
    return retrieval, plan, sink


@pytest.mark.asyncio
async def test_abstained_result_physically_never_invokes_execute():
    retrieval, plan, sink = fixture()
    top = retrieval.candidates[0].score
    with pytest.raises(PolicyViolationError, match="no-match: below_min_score"):
        await execute_selective_plan(
            sink,
            retrieval,
            plan,
            policy=RetrievalAbstentionPolicy(min_score=top + 1.0),
        )
    assert sink.dispatched == []


@pytest.mark.asyncio
async def test_selected_in_scope_plan_reaches_normal_execution_edge_once():
    retrieval, plan, sink = fixture()
    result = await execute_selective_plan(
        sink,
        retrieval,
        plan,
        policy=RetrievalAbstentionPolicy(min_score=-1e8),
    )
    assert result == []
    assert sink.dispatched == [plan]


@pytest.mark.parametrize(("mutation", "reason"), [
    (
        lambda retrieval, plan, sink: setattr(sink.registry, "version", 99),
        "stale registry",
    ),
    (
        lambda retrieval, plan, sink: plan.model_copy(
            update={"registry_version": True}
        ),
        "stale registry",
    ),
    (
        lambda retrieval, plan, sink: plan.model_copy(
            update={"query": "delete all orders"}
        ),
        "mismatched query",
    ),
    (
        lambda retrieval, plan, sink: plan.model_copy(
            update={"calls": []}
        ),
        "no executable calls",
    ),
    (
        lambda retrieval, plan, sink: plan.model_copy(
            update={"calls": [plan.calls[0].model_copy(
                update={"endpoint": "missing_operation"}
            )]}
        ),
        "outside selected shortlist",
    ),
    (
        lambda retrieval, plan, sink: plan.model_copy(
            update={"calls": [plan.calls[0].model_copy(
                update={"schema_fingerprint": "replaced-schema"}
            )]}
        ),
        "provenance",
    ),
    (
        lambda retrieval, plan, sink: plan.model_copy(
            update={"calls": [plan.calls[0].model_copy(
                update={"tool_fingerprint": None}
            )]}
        ),
        "provenance",
    ),
    (
        lambda retrieval, plan, sink: plan.model_copy(
            update={"calls": [plan.calls[0].model_copy(
                update={"missing_required_arguments": ["required"]}
            )]}
        ),
        "missing required arguments",
    ),
    (
        lambda retrieval, plan, sink: plan.model_copy(
            update={"calls": [plan.calls[0].model_copy(
                update={"fields": ["hidden_output"]}
            )]}
        ),
        "fields outside",
    ),
])
@pytest.mark.asyncio
async def test_invalid_plan_never_triggers_execute(mutation, reason):
    retrieval, plan, sink = fixture()
    changed = mutation(retrieval, plan, sink)
    if changed is not None:
        plan = changed
    with pytest.raises(PolicyViolationError, match=reason):
        await execute_selective_plan(
            sink,
            retrieval,
            plan,
            policy=RetrievalAbstentionPolicy(min_score=-1e8),
        )
    assert sink.dispatched == []


@pytest.mark.asyncio
async def test_unknown_fallback_cannot_bypass_selected_primary():
    retrieval, plan, sink = fixture()
    original = plan.calls[0]
    unsafe = original.model_copy(update={"endpoint": "delete_everything"})
    poisoned = plan.model_copy(update={
        "fallback_routes": [
            FallbackRoute(primary_call_index=0, alternatives=[unsafe])
        ]
    })
    with pytest.raises(PolicyViolationError, match="outside selected shortlist"):
        await execute_selective_plan(
            sink,
            retrieval,
            poisoned,
            policy=RetrievalAbstentionPolicy(min_score=-1e8),
        )
    assert sink.dispatched == []


@pytest.mark.asyncio
async def test_shortlist_mismatch_rejected_without_any_backend_invocation():
    retrieval, plan, sink = fixture()
    decision = validate_selective_execution(
        retrieval,
        plan,
        policy=RetrievalAbstentionPolicy(min_score=-1e8),
        registry_version=sink.registry.version,
    )
    assert not decision.abstained
    assert {c.route_id for c in decision.candidates} == {
        c.route_id for c in retrieval.candidates
    }
    assert sink.dispatched == []


@pytest.mark.asyncio
async def test_low_margin_blocks_dispatch_not_just_shortlist_display():
    retrieval, plan, sink = fixture()
    scores = [candidate.score for candidate in retrieval.candidates]
    requested_margin = scores[0] - scores[1] + 1
    with pytest.raises(PolicyViolationError, match="no-match: below_min_margin"):
        await execute_selective_plan(
            sink,
            retrieval,
            plan,
            policy=RetrievalAbstentionPolicy(min_margin=requested_margin),
        )
    assert sink.dispatched == []


class FakeScopedFlow(FakeDispatchRouter):
    def __init__(self, retrieval, plan) -> None:
        super().__init__(retrieval.registry_version)
        self.retrieval = retrieval
        self.plan = plan
        self.events: list[tuple] = []

    async def aretrieve_executable(self, request, *, k=5):
        self.events.append(("retrieve", request, k))
        return self.retrieval

    async def aplan_executable(self, request):
        self.events.append(("plan", request))
        return self.plan

    async def aretrieve_executable_authorized(
        self, request, *, principal, k=5,
    ):
        self.events.append(("retrieve_authorized", request, principal, k))
        return self.retrieval

    async def aplan_executable_authorized(self, request, *, principal):
        self.events.append(("plan_authorized", request, principal))
        return self.plan

    async def execute(self, plan, *, config=None):
        self.events.append(("execute", config.principal))
        return await super().execute(plan, config=config)


@pytest.mark.asyncio
async def test_atomic_selective_workflow_dispatches_only_after_both_bound_stages():
    retrieval, plan, _ = fixture()
    router = FakeScopedFlow(retrieval, plan)
    out = await ainvoke_selective(
        router,
        retrieval.query,
        k=2,
        policy=RetrievalAbstentionPolicy(min_score=-1e8),
    )
    assert out == []
    assert [x[0] for x in router.events] == ["retrieve", "plan", "execute"]
    assert router.events[0][1] == router.events[1][1] == retrieval.query
    assert router.dispatched == [plan]


@pytest.mark.asyncio
async def test_atomic_selective_workflow_uses_one_trusted_principal():
    retrieval, plan, _ = fixture()
    router = FakeScopedFlow(retrieval, plan)
    principal = PrincipalContext(subject="test-user", roles=("reader",))
    result = await ainvoke_selective(
        router,
        retrieval.query,
        k=2,
        config={"principal": principal},
        policy=RetrievalAbstentionPolicy(min_score=-1e8),
    )
    assert result == []
    assert [x[0] for x in router.events] == [
        "retrieve_authorized", "plan_authorized", "execute",
    ]
    assert router.events[0][2] == principal
    assert router.events[1][2] == principal
    assert router.events[2][1] == principal


@pytest.mark.asyncio
async def test_atomic_selective_workflow_does_not_dispatch_on_no_match():
    retrieval, plan, _ = fixture()
    router = FakeScopedFlow(retrieval, plan)
    with pytest.raises(PolicyViolationError, match="no-match: below_min_score"):
        await ainvoke_selective(
            router,
            retrieval.query,
            k=2,
            policy=RetrievalAbstentionPolicy(
                min_score=retrieval.candidates[0].score + 1,
            ),
        )
    assert [x[0] for x in router.events] == ["retrieve"]
    assert router.dispatched == []


@pytest.mark.asyncio
async def test_atomic_selective_workflow_rejects_cross_request_retrieval():
    retrieval, plan, _ = fixture()
    router = FakeScopedFlow(
        retrieval.model_copy(update={"query": "different query"}), plan,
    )
    with pytest.raises(PolicyViolationError, match="mismatched query"):
        await ainvoke_selective(
            router, retrieval.query, k=2,
            policy=RetrievalAbstentionPolicy(min_score=-1e8),
        )
    assert router.dispatched == []


@pytest.mark.asyncio
@pytest.mark.parametrize("k", [0, -1, True, 2.5, "2"])
async def test_atomic_selective_workflow_rejects_invalid_k_before_any_call(k):
    retrieval, plan, _ = fixture()
    router = FakeScopedFlow(retrieval, plan)
    with pytest.raises(ValueError, match="positive integer"):
        await ainvoke_selective(
            router, retrieval.query, k=k,
            policy=RetrievalAbstentionPolicy(min_score=-1e8),
        )
    assert router.events == []


@pytest.mark.asyncio
@pytest.mark.parametrize("scope_flag", [False, 1, "true", None])
async def test_non_executable_or_forged_scope_never_dispatches(scope_flag):
    retrieval, plan, sink = fixture()
    retrieval = retrieval.model_copy(update={"executable_only": scope_flag})
    with pytest.raises(PolicyViolationError, match="non-executable retrieval"):
        await execute_selective_plan(
            sink, retrieval, plan,
            policy=RetrievalAbstentionPolicy(min_score=-1e8),
        )
    assert sink.dispatched == []



@pytest.mark.asyncio
@pytest.mark.parametrize("poison", [
    {"min_score": None, "min_margin": None},
    {"min_score": float("inf")},
    {"min_score": True},
    {"min_score": "0.3"},
    {"min_margin": -1},
])
async def test_forged_policy_model_copy_never_dispatches(poison):
    retrieval, plan, sink = fixture()
    calibrated = RetrievalAbstentionPolicy(min_score=-1e8)
    unvalidated = calibrated.model_copy(update=poison)
    with pytest.raises(PolicyViolationError, match="invalid calibrated policy"):
        await execute_selective_plan(
            sink, retrieval, plan, policy=unvalidated,
        )
    assert sink.dispatched == []



@pytest.mark.asyncio
async def test_no_match_margin_rejects_before_costly_planning():
    retrieval, plan, _ = fixture()
    router = FakeScopedFlow(retrieval, plan)
    scores = [item.score for item in retrieval.candidates]
    with pytest.raises(PolicyViolationError, match="below_min_margin"):
        await ainvoke_selective(
            router, retrieval.query, k=2,
            policy=RetrievalAbstentionPolicy(
                min_margin=scores[0] - scores[1] + 1,
            ),
        )
    assert [event[0] for event in router.events] == ["retrieve"]


@pytest.mark.asyncio
async def test_stale_registry_short_circuits_before_any_plan():
    retrieval, plan, _ = fixture()
    router = FakeScopedFlow(retrieval, plan)
    router.registry.version += 1
    with pytest.raises(PolicyViolationError, match="stale registry"):
        await ainvoke_selective(
            router, retrieval.query, k=2,
            policy=RetrievalAbstentionPolicy(min_score=-1e8),
        )
    assert [event[0] for event in router.events] == ["retrieve"]


@pytest.mark.asyncio
async def test_mismatched_retrieval_budget_short_circuits_before_plan():
    retrieval, plan, _ = fixture()
    router = FakeScopedFlow(
        retrieval.model_copy(update={"requested_k": 100}), plan,
    )
    with pytest.raises(PolicyViolationError, match="shortlist budget"):
        await ainvoke_selective(
            router, retrieval.query, k=2,
            policy=RetrievalAbstentionPolicy(min_score=-1e8),
        )
    assert [event[0] for event in router.events] == ["retrieve"]


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_threshold", [
    True, "0.3", float("inf"), 10 ** 1000,
])
async def test_invalid_policy_rejects_before_retrieval_or_plan(bad_threshold):
    retrieval, plan, _ = fixture()
    router = FakeScopedFlow(retrieval, plan)
    forged = RetrievalAbstentionPolicy(min_score=-1e8).model_copy(
        update={"min_score": bad_threshold},
    )
    with pytest.raises(PolicyViolationError, match="invalid calibrated policy"):
        await ainvoke_selective(
            router, retrieval.query, k=2, policy=forged,
        )
    assert router.events == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "poison",
    [
        {"principal": "forged-principal"},
        {"max_concurrency": 0},
        {"raw_trace_payloads": True},
    ],
)
async def test_copied_run_config_is_revalidated_before_any_routing(poison):
    # Pydantic's model_copy(update=...) bypasses both field and cross-field
    # validation; no forged principal or invalid execution config may reach
    # authorized retrieval, planning, or tool dispatch.
    from schemarouter.runs import RunConfig

    retrieval, plan, _ = fixture()
    router = FakeScopedFlow(retrieval, plan)
    forged = RunConfig().model_copy(update=poison)
    with pytest.raises(PolicyViolationError, match="invalid run configuration"):
        await ainvoke_selective(
            router,
            retrieval.query,
            k=2,
            config=forged,
            policy=RetrievalAbstentionPolicy(min_score=-1e8),
        )
    assert router.events == []
    assert router.dispatched == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "request",
    [
        None,
        [],
        {},
        123,
        "",
        "   ",
        PlanRequest(query="search papers").model_copy(update={"query": 123}),
        PlanRequest(query="search papers").model_copy(update={"max_calls": 0}),
        PlanRequest(query="search papers").model_copy(
            update={"preferred_tools": "fake.tool"}
        ),
    ],
)
async def test_atomic_selective_request_is_validated_before_any_retrieval(
    request,
):
    retrieval, plan, _ = fixture()
    router = FakeScopedFlow(retrieval, plan)
    with pytest.raises(PolicyViolationError, match="invalid request|empty or invalid"):
        await ainvoke_selective(
            router, request, k=2,
            policy=RetrievalAbstentionPolicy(min_score=-1e8),
        )
    assert router.events == []
    assert router.dispatched == []


@pytest.mark.asyncio
async def test_valid_structured_request_uses_same_validated_query_scope():
    retrieval, plan, _ = fixture()
    router = FakeScopedFlow(retrieval, plan)
    request = PlanRequest(query=retrieval.query, max_calls=2)
    result = await ainvoke_selective(
        router, request, k=2,
        policy=RetrievalAbstentionPolicy(min_score=-1e8),
    )
    assert result == []
    assert [event[0] for event in router.events] == ["retrieve", "plan", "execute"]
    assert router.events[0][1].query == router.events[1][1].query == request.query
