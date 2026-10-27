"""E0 source-root model argument suggestions require explicit host review."""

from __future__ import annotations

from dataclasses import replace

import pytest
from test_paper_understood_graph_plan import CATALOG, INTENTS
from test_paper_understood_observed_graph_a9_e0 import _fixture
from test_research_paper_scoped_agent_real_e0 import (
    CATALOG as DIRECT_CATALOG,
)
from test_research_paper_scoped_agent_real_e0 import (
    INTENTS as DIRECT_INTENTS,
)
from test_research_paper_scoped_agent_real_e0 import (
    Agent as ExistingAgent,
)
from test_research_paper_scoped_agent_real_e0 import (
    source as direct_source,
)
from test_research_paper_scoped_answered_graph_a9_e0 import FixedFinalizer

from schemarouter import (
    AuthorizationPolicy,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    PrincipalContext,
)
from schemarouter.errors import PolicyViolationError
from schemarouter.paper_understood_direct_plan import PaperUnderstanding
from schemarouter.paper_understood_graph_plan import compile_paper_understood_graph_plan
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_paper_reviewed_model_arguments_e0 import (
    review_paper_root_model_arguments_e0,
)
from scripts.research_paper_scoped_answered_graph_a9_e0 import (
    run_paper_scoped_answered_graph_a9_e0,
)
from scripts.research_paper_scoped_observed_graph_a9_e0 import (
    run_paper_scoped_named_graph_a9_e0,
)
from scripts.research_paper_scoped_plan_e0 import analyze_and_plan_paper_scoped_e0


def _graph_context(*, hops=2, host_root=True):
    router, index, seen = _fixture(hops=hops, host_root=host_root)
    view = capture_authorized_agent_tool_surface(
        router, "Please find the case status for external customer id e7",
        principal=PrincipalContext(subject="root-review", roles=("reader",)),
    )
    return router, index, view, seen


def _graph_model(*, hints=None):
    def model(_payload):
        return {
            "intent_id": "case.lookup",
            "concept_ids": ["crm.status"],
            "named_tools": ["target_0"],
            "parameter_hints": hints if hints is not None else {"external_id": "e7"},
        }
    return model


def _graph_args(view, index):
    return dict(
        view=view, catalog=CATALOG, intent_registry=INTENTS, index=index,
        model_visible_intent_ids=("case.lookup",),
        model_visible_concept_ids=("crm.status",),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("hops", (1, 2))
async def test_reviewed_model_root_scalar_flows_through_registered_graph_executor(hops):
    _, index, view, seen = _graph_context(hops=hops)
    proposals = []

    async def reviewer(proposal):
        proposals.append(proposal)
        assert proposal.route_id == "root.read"
        assert proposal.parameter_values == (("external_id", "e7"),)
        assert proposal.tool_fingerprint and proposal.endpoint_fingerprint
        return True

    decision, receipt = await run_paper_scoped_named_graph_a9_e0(
        _graph_model(hints={"external_id": "e7"}),
        **_graph_args(view, index), review_model_root_arguments=reviewer,
    )
    assert decision == "offer" and receipt is not None
    assert len(proposals) == 1
    assert seen[0] == ("root", {"external_id": "e7"})
    assert len(seen) == hops + 1
    assert seen[-1][0] == "target_0"
    assert receipt.executable_authority is False
    assert receipt.independent_e2 is False


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", (False, "yes", 1, None))
async def test_unapproved_or_nonboolean_review_never_executes(answer):
    _, index, view, seen = _graph_context()
    decision, receipt = await run_paper_scoped_named_graph_a9_e0(
        _graph_model(), **_graph_args(view, index),
        review_model_root_arguments=lambda proposal: answer,
    )
    assert (decision, receipt) == ("request_arguments", None)
    assert seen == []


@pytest.mark.asyncio
@pytest.mark.parametrize("hints", (
    {},
    {"external_id": "e7", "case_id": "consumer-injection"},
    {"external_id": 42},
    {"external_id": ""},
))
async def test_extra_missing_or_invalid_hint_is_never_offered_to_host(hints):
    _, index, view, seen = _graph_context()
    reviewed = []
    decision, receipt = await run_paper_scoped_named_graph_a9_e0(
        _graph_model(hints=hints), **_graph_args(view, index),
        review_model_root_arguments=lambda proposal: reviewed.append(proposal) or True,
    )
    assert (decision, receipt) == ("request_arguments", None)
    assert reviewed == [] and seen == []


@pytest.mark.asyncio
async def test_unapproved_g5_root_cannot_be_upgraded_by_model_or_host():
    router, _, view, seen = _graph_context(host_root=True)
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    called = []
    decision, receipt = await run_paper_scoped_named_graph_a9_e0(
        _graph_model(), **_graph_args(view, index),
        review_model_root_arguments=lambda proposal: called.append(1) or True,
    )
    assert (decision, receipt) == ("abstain", None)
    assert called == [] and seen == []


@pytest.mark.asyncio
async def test_reviewer_mutating_source_authorization_prevents_all_execution():
    router, index, view, seen = _graph_context()

    def revoke(_proposal):
        router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return True

    with pytest.raises(PolicyViolationError):
        await run_paper_scoped_named_graph_a9_e0(
            _graph_model(), **_graph_args(view, index),
            review_model_root_arguments=revoke,
        )
    assert seen == []


@pytest.mark.asyncio
async def test_reviewer_mutating_pinned_graph_prevents_all_execution():
    _, index, view, seen = _graph_context()

    def mutate_graph(_proposal):
        index.graph.edges = ()
        return True

    with pytest.raises(PolicyViolationError, match="graph|source"):
        await run_paper_scoped_named_graph_a9_e0(
            _graph_model(), **_graph_args(view, index),
            review_model_root_arguments=mutate_graph,
        )
    assert seen == []


@pytest.mark.asyncio
async def test_host_review_of_direct_scalar_creates_typed_plan_but_does_not_execute():
    view, index = direct_source(required_argument=True, host_direct=True)
    reviewed = []
    decision, plan = await analyze_and_plan_paper_scoped_e0(
        lambda payload: {
            "intent_id": "case.lookup", "concept_ids": ["case.status"],
            "named_tools": ["complete"],
            "parameter_hints": {"case_id": "owner-reviewed-7"},
        },
        view=view, catalog=DIRECT_CATALOG, intent_registry=DIRECT_INTENTS,
        index=index, model_visible_intent_ids=("case.lookup",),
        model_visible_concept_ids=("case.status",),
        review_model_root_arguments=lambda proposal: reviewed.append(proposal) or True,
    )
    assert decision == "offer"
    assert plan is not None and plan.status == "ready"
    assert plan.calls[0].call.arguments == {"case_id": "owner-reviewed-7"}
    assert plan.executable_authority is False
    assert len(reviewed) == 1


@pytest.mark.asyncio
async def test_no_reviewer_retains_untrusted_model_hints_deferred():
    _, index, view, seen = _graph_context()
    decision, receipt = await run_paper_scoped_named_graph_a9_e0(
        _graph_model(), **_graph_args(view, index),
    )
    assert (decision, receipt) == ("request_arguments", None)
    assert seen == []


@pytest.mark.asyncio
async def test_scoped_agent_reports_missing_graph_root_as_arguments_not_observation():
    _, index, view, seen = _graph_context()
    decision, plan = await analyze_and_plan_paper_scoped_e0(
        _graph_model(), **_graph_args(view, index),
    )
    assert decision == "request_arguments"
    assert plan is not None and plan.status == "requires_observation"
    assert plan.calls[0].call.missing_required_arguments == ["external_id"]
    assert seen == []


@pytest.mark.asyncio
async def test_public_review_helper_refuses_forged_plan_before_host_disclosure():
    _, index, view, _ = _graph_context()
    understanding = PaperUnderstanding(
        intent_id="case.lookup", named_tools=("target_0",),
        parameter_hints={"external_id": "e7"},
    )
    plan = compile_paper_understood_graph_plan(
        view.router, understanding, principal=view._principal,
        catalog=CATALOG, intent_registry=INTENTS, index=index,
    )
    reviewed = []
    with pytest.raises(PolicyViolationError, match="plan|proof"):
        await review_paper_root_model_arguments_e0(
            lambda proposed: reviewed.append(proposed) or True,
            view=view, understanding=understanding,
            plan=replace(plan, registry_version=-1), index=index,
            catalog=CATALOG, intent_registry=INTENTS,
        )
    assert reviewed == []


@pytest.mark.asyncio
async def test_host_mutating_model_hint_mid_review_cannot_replace_approved_input():
    _, index, view, seen = _graph_context()
    response = _graph_model()({})

    def model(_payload):
        return response

    # The model response is detached by the scoped JSON validator. Mutating
    # the original callback result after parsing never changes the proposal.
    def reviewer(proposal):
        response["parameter_hints"]["external_id"] = "forged-after-review"
        assert proposal.parameter_values == (("external_id", "e7"),)
        return True

    decision, receipt = await run_paper_scoped_named_graph_a9_e0(
        model, **_graph_args(view, index), review_model_root_arguments=reviewer,
    )
    assert decision == "offer" and receipt is not None
    assert seen[0] == ("root", {"external_id": "e7"})


@pytest.mark.asyncio
async def test_explicit_host_inputs_bypass_untrusted_hint_review():
    _, index, view, seen = _graph_context()
    decision, receipt = await run_paper_scoped_named_graph_a9_e0(
        _graph_model(hints={"external_id": "model-wrong"}),
        **_graph_args(view, index),
        host_source_arguments={"root.read": {"external_id": "owner-value"}},
        review_model_root_arguments=lambda _: pytest.fail("must not review"),
    )
    assert decision == "offer" and receipt is not None
    assert seen[0] == ("root", {"external_id": "owner-value"})


@pytest.mark.asyncio
async def test_original_fixed5_episode_consumes_host_reviewed_direct_plan(monkeypatch):
    from scripts import research_paper_scoped_agent_episode_e0 as episode

    view, index = direct_source(required_argument=True, host_direct=True)
    observed = []

    def existing_agent(_agent, *, plan, **_kwargs):
        observed.append(plan)
        return {"tool_call_count": 0, "final_text": "not executed in test"}

    monkeypatch.setattr(episode, "run_paper_fixed5_episode_e0", existing_agent)
    decision, result = await episode.run_paper_scoped_agent_episode_e0(
        lambda _payload: {
            "intent_id": "case.lookup", "concept_ids": ["case.status"],
            "named_tools": ["complete"],
            "parameter_hints": {"case_id": "reviewed-episode"},
        },
        object(), view=view, task={"query": view.original_query},
        catalog=DIRECT_CATALOG, intent_registry=DIRECT_INTENTS,
        index=index, model_visible_intent_ids=("case.lookup",),
        model_visible_concept_ids=("case.status",),
        review_model_root_arguments=lambda _proposal: True,
    )
    assert decision == "offer" and result["tool_call_count"] == 0
    assert len(observed) == 1
    assert observed[0].calls[0].call.arguments == {"case_id": "reviewed-episode"}


@pytest.mark.asyncio
async def test_existing_graph_answer_wrapper_wires_reviewed_root_to_finalizer():
    _, index, view, seen = _graph_context()
    finalizer = FixedFinalizer()
    decision, answer = await run_paper_scoped_answered_graph_a9_e0(
        _graph_model(), finalizer, **_graph_args(view, index),
        review_model_root_arguments=lambda _proposal: True,
    )
    assert decision == "offer" and answer is not None
    assert answer.answer == "The case status is open."
    assert seen[0] == ("root", {"external_id": "e7"})
    assert len(finalizer.calls) == 1
    assert finalizer.calls[0][1] == []


@pytest.mark.asyncio
async def test_rejected_review_blocks_original_fixed5_agent_and_tool_attempts():
    from scripts.research_paper_scoped_agent_episode_e0 import (
        run_paper_scoped_agent_episode_e0,
    )

    view, index = direct_source(required_argument=True, host_direct=True)

    class ForbiddenAgent:
        def generate(self, _messages, _tools):
            pytest.fail("rejected host input must not reach the agent")

    decision, row = await run_paper_scoped_agent_episode_e0(
        lambda _payload: {
            "intent_id": "case.lookup", "concept_ids": ["case.status"],
            "named_tools": ["complete"],
            "parameter_hints": {"case_id": "unapproved-model-id"},
        },
        ForbiddenAgent(), view=view, task={
            "semantic_task_id": "root-host-reject-e0",
            "query": view.original_query, "language": "en", "supported": True,
            "required_routes": ["complete.read"],
            "executor_fixture": {"steps": [{
                "route_id": "complete.read", "argument_rules": {},
                "observation": {"status": "ok", "status_value": "open"},
            }]},
        },
        catalog=DIRECT_CATALOG, intent_registry=DIRECT_INTENTS,
        index=index, model_visible_intent_ids=("case.lookup",),
        model_visible_concept_ids=("case.status",),
        review_model_root_arguments=lambda _proposal: False,
    )
    assert decision == "request_arguments"
    assert row["host_empty_menu_terminal"] is True
    assert row["tool_call_count"] == row["turns"] == 0


@pytest.mark.asyncio
async def test_explicit_host_argument_mode_does_not_activate_reviewer_denial_gate():
    from scripts.research_paper_scoped_agent_episode_e0 import (
        run_paper_scoped_agent_episode_e0,
    )

    view, index = direct_source(required_argument=True, host_direct=True)
    decision, row = await run_paper_scoped_agent_episode_e0(
        lambda _payload: {
            "intent_id": "case.lookup", "concept_ids": ["case.status"],
            "named_tools": ["complete"],
            "parameter_hints": {"case_id": "model-hint"},
        },
        ExistingAgent(), view=view, task={
            "semantic_task_id": "legacy-host-explicit-empty-e0",
            "query": view.original_query, "language": "en", "supported": False,
            "required_routes": [], "executor_fixture": {"steps": []},
        },
        catalog=DIRECT_CATALOG, intent_registry=DIRECT_INTENTS,
        index=index, model_visible_intent_ids=("case.lookup",),
        model_visible_concept_ids=("case.status",),
        host_source_arguments={},
        review_model_root_arguments=lambda _proposal: pytest.fail("review bypassed"),
    )
    assert decision == "request_arguments"
    assert row["host_empty_menu_terminal"] is False
    assert row["tool_call_count"] >= 1
