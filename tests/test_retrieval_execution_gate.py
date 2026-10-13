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
    PolicyViolationError,
    RetrievalAbstentionPolicy,
    SchemaRouter,
    ToolCall,
    ToolSpec,
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
    retrieval = router.retrieve("Search research papers", k=2)
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
