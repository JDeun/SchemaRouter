"""A5: host-reviewed root input actually reaches the original fixed5 executor."""

from __future__ import annotations

import json

import pytest
from test_research_paper_scoped_agent_real_e0 import (
    CATALOG,
    INTENTS,
    source,
)

from schemarouter import AuthorizationPolicy, PolicyViolationError
from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    run_generated_episode,
)
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_paper_scoped_agent_episode_e0 import (
    run_paper_scoped_agent_episode_e0,
)


def _task(query: str, *, expected: str = "host-reviewed-7") -> dict:
    return {
        "semantic_task_id": "a5-real-agent-reviewed-root-e0",
        "query": query, "language": "en", "supported": True,
        "required_routes": ["complete.read"],
        "executor_fixture": {"steps": [{
            "route_id": "complete.read",
            "argument_rules": {"case_id": {"eq": expected}},
            "observation": {"status": "ok", "status_value": "open"},
        }]},
    }


def _understand(_payload):
    return {
        "intent_id": "case.lookup", "concept_ids": ["case.status"],
        "named_tools": ["complete"],
        "parameter_hints": {"case_id": "host-reviewed-7"},
    }


def _scoped(view, index):
    return dict(
        view=view, task=_task(view.original_query),
        catalog=CATALOG, intent_registry=INTENTS, index=index,
        model_visible_intent_ids=("case.lookup",),
        model_visible_concept_ids=("case.status",),
    )


class WrongInputAgent:
    def __init__(self, arguments=None, *, on_generate=None):
        self.arguments = arguments if arguments is not None else {
            "case_id": "forged-model-id", "unexpected": "malicious"
        }
        self.on_generate = on_generate
        self.turns = 0
        self.messages = []

    def generate(self, messages, tools):
        self.messages.append((messages, tools))
        if self.on_generate is not None:
            self.on_generate()
        tool_call = json.dumps({"name": "complete__read", "arguments": self.arguments})
        text = f"<tool_call>{tool_call}</tool_call>" if self.turns == 0 else "Done."
        self.turns += 1
        return {
            "text": text, "input_tokens": 2, "output_tokens": 2,
            "tool_tokens": 2, "latency_ms": 0.0, "context_overflow": False,
        }


class FixedTextAgent(WrongInputAgent):
    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def generate(self, messages, tools):
        self.messages.append((messages, tools))
        self.turns += 1
        return {
            "text": self.text if self.turns == 1 else "Done.",
            "input_tokens": 2, "output_tokens": 2, "tool_tokens": 2,
            "latency_ms": 0.0, "context_overflow": False,
        }


def _original_selector(_query, _source_ids):
    return ["complete.read"]


def test_fixed5_dispatch_hook_overrides_only_first_offered_call_and_counts_assist():
    view, _index = source(required_argument=True, host_direct=True)
    agent = WrongInputAgent()
    seen = []

    def host_binding(route, arguments):
        seen.append((route, arguments))
        return {"case_id": "host-reviewed-7"}, True

    trace = run_generated_episode(
        agent, view.router.registry, _task(view.original_query),
        EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=_original_selector,
        experimental_agent_tool_surface=view,
        experimental_host_empty_menu_terminal=True,
        experimental_scoped_call_binding=host_binding,
    )
    assert trace["passed"] is True
    assert trace["tool_call_count"] == 1
    assert trace["host_bound_tool_calls"] == 1
    assert seen == [("complete.read", {
        "case_id": "forged-model-id", "unexpected": "malicious",
    })]
    assert "host-reviewed-7" not in json.dumps(trace)


def test_fixed5_dispatch_hook_rejects_historical_or_unscoped_use_before_model():
    view, _index = source(required_argument=True, host_direct=True)

    class Forbidden:
        def generate(self, _messages, _tools):
            pytest.fail("invalid hook must fail before model generation")

    with pytest.raises(ValueError, match="binding|scoped|fixed5"):
        run_generated_episode(
            Forbidden(), view.router.registry, _task(view.original_query),
            "ORACLE", experimental_scoped_call_binding=lambda _r, a: (a, False),
        )
    with pytest.raises(ValueError, match="binding|scoped|fixed5"):
        run_generated_episode(
            Forbidden(), view.router.registry, _task(view.original_query),
            EXPERIMENTAL_FIXED5_CONDITION,
            experimental_candidate_selector=_original_selector,
            experimental_scoped_call_binding=lambda _r, a: (a, False),
        )


def test_parallel_calls_do_not_receive_host_binding_even_when_first_is_offered():
    view, _ = source(required_argument=True, host_direct=True)
    agent = FixedTextAgent(
        '<tool_call>{"name":"complete__read","arguments":{"case_id":"wrong"}}</tool_call>'
        '<tool_call>{"name":"unknown__read","arguments":{}}</tool_call>'
    )
    seen = []
    with pytest.raises(PolicyViolationError, match="unavailable scoped observation route"):
        run_generated_episode(
            agent, view.router.registry, _task(view.original_query),
            EXPERIMENTAL_FIXED5_CONDITION,
            experimental_candidate_selector=_original_selector,
            experimental_agent_tool_surface=view,
            experimental_scoped_call_binding=lambda route, args: (
                seen.append((route, args)) or {"case_id": "host-reviewed-7"}, True
            ),
        )
    assert seen == []


def test_noncall_or_unoffered_route_never_receives_host_arguments():
    view, _ = source(required_argument=True, host_direct=True)
    seen = []

    def host_binding(route, arguments):
        seen.append((route, arguments))
        return {"case_id": "host-reviewed-7"}, True

    for text in (
        "Done.",
        '<tool_call>{"name":"hidden__read","arguments":{"case_id":"wrong"}}</tool_call>',
    ):
        agent = FixedTextAgent(text)
        if text == "Done.":
            trace = run_generated_episode(
                agent, view.router.registry, _task(view.original_query),
                EXPERIMENTAL_FIXED5_CONDITION,
                experimental_candidate_selector=_original_selector,
                experimental_agent_tool_surface=view,
                experimental_scoped_call_binding=host_binding,
            )
            assert trace["passed"] is False
            assert trace["host_bound_tool_calls"] == 0
        else:
            with pytest.raises(PolicyViolationError, match="unavailable scoped observation"):
                run_generated_episode(
                    agent, view.router.registry, _task(view.original_query),
                    EXPERIMENTAL_FIXED5_CONDITION,
                    experimental_candidate_selector=_original_selector,
                    experimental_agent_tool_surface=view,
                    experimental_scoped_call_binding=host_binding,
                )
    assert seen == []


@pytest.mark.asyncio
async def test_reviewed_a5_plan_materializes_host_id_in_original_agent_episode():
    view, index = source(required_argument=True, host_direct=True)
    agent = WrongInputAgent()
    decision, trace = await run_paper_scoped_agent_episode_e0(
        _understand, agent, **_scoped(view, index),
        review_model_root_arguments=lambda _proposal: True,
    )
    assert decision == "offer" and trace["passed"] is True
    assert trace["tool_call_count"] == 1
    assert trace["host_bound_tool_calls"] == 1
    assert agent.turns >= 1
    assert "host-reviewed-7" not in str(agent.messages[0])
    assert "host-reviewed-7" not in json.dumps(trace)


@pytest.mark.asyncio
async def test_approved_root_can_supply_model_omitted_argument_without_prompt_leak():
    view, index = source(required_argument=True, host_direct=True)
    agent = WrongInputAgent(arguments={})
    decision, trace = await run_paper_scoped_agent_episode_e0(
        _understand, agent, **_scoped(view, index),
        review_model_root_arguments=lambda _proposal: True,
    )
    assert decision == "offer" and trace["passed"] is True
    assert trace["host_bound_tool_calls"] == trace["tool_call_count"] == 1
    assert "host-reviewed-7" not in str(agent.messages)
    assert "host-reviewed-7" not in json.dumps(trace)


@pytest.mark.asyncio
async def test_explicit_host_root_also_binds_and_review_denial_cannot_execute():
    view, index = source(required_argument=True, host_direct=True)
    decision, trace = await run_paper_scoped_agent_episode_e0(
        _understand, WrongInputAgent(), **_scoped(view, index),
        host_source_arguments={"complete.read": {"case_id": "host-reviewed-7"}},
    )
    assert decision == "offer" and trace["passed"] is True
    assert trace["host_bound_tool_calls"] == 1

    class Forbidden:
        def generate(self, _messages, _tools):
            pytest.fail("host denied proposal must not generate a tool call")

    decision, refused = await run_paper_scoped_agent_episode_e0(
        _understand, Forbidden(), **_scoped(view, index),
        review_model_root_arguments=lambda _proposal: False,
    )
    assert decision == "request_arguments"
    assert refused["host_empty_menu_terminal"] is True
    assert refused["tool_call_count"] == refused["turns"] == 0
    assert refused.get("host_bound_tool_calls", 0) == 0


@pytest.mark.asyncio
async def test_empty_explicit_host_mapping_cannot_bypass_present_reviewer_gate():
    view, index = source(required_argument=True, host_direct=True)

    class Forbidden:
        def generate(self, _messages, _tools):
            pytest.fail("empty host mapping must never expose unreviewed input route")

    decision, trace = await run_paper_scoped_agent_episode_e0(
        _understand, Forbidden(), **_scoped(view, index),
        host_source_arguments={},
        review_model_root_arguments=lambda _proposal: False,
    )
    assert decision == "request_arguments"
    assert trace["host_empty_menu_terminal"] is True
    assert trace["turns"] == trace["tool_call_count"] == 0


@pytest.mark.asyncio
async def test_no_host_review_does_not_upgrade_wrong_agent_value():
    view, index = source(required_argument=True, host_direct=True)
    decision, trace = await run_paper_scoped_agent_episode_e0(
        _understand, WrongInputAgent(arguments={"case_id": "model-wrong"}),
        **_scoped(view, index),
    )
    assert decision == "request_arguments" and trace["passed"] is False
    assert trace.get("host_bound_tool_calls", 0) == 0


@pytest.mark.asyncio
async def test_mutated_authorization_during_agent_call_blocks_bound_dispatch():
    view, index = source(required_argument=True, host_direct=True)
    agent = WrongInputAgent(on_generate=lambda: setattr(
        view.router, "authorization_policy",
        AuthorizationPolicy(default_effect="deny"),
    ))
    with pytest.raises(PolicyViolationError):
        await run_paper_scoped_agent_episode_e0(
            _understand, agent, **_scoped(view, index),
            review_model_root_arguments=lambda _proposal: True,
        )
    assert agent.turns == 1


@pytest.mark.asyncio
async def test_mutated_graph_approval_during_agent_call_blocks_bound_dispatch():
    view, index = source(required_argument=True, host_direct=True)
    agent = WrongInputAgent(on_generate=lambda: setattr(
        index.graph, "capability_ids", (),
    ))
    with pytest.raises(PolicyViolationError, match="source|root|changed"):
        await run_paper_scoped_agent_episode_e0(
            _understand, agent, **_scoped(view, index),
            review_model_root_arguments=lambda _proposal: True,
        )
    assert agent.turns == 1


@pytest.mark.asyncio
async def test_availability_callback_cannot_mutate_catalog_after_final_probe():
    view, index = source(required_argument=True, host_direct=True)
    catalog = CATALOG.model_copy(deep=True)
    state = {"armed": False, "probes": 0}

    def available(_tool, _endpoint):
        if state["armed"]:
            state["probes"] += 1
            if state["probes"] == 2:
                catalog.concepts[0].aliases = ("mutated case status",)
        return True

    view.router.planner.availability_predicate = available
    view = capture_authorized_agent_tool_surface(
        view.router, view.original_query, principal=view._principal,
    )
    agent = WrongInputAgent(on_generate=lambda: state.update(armed=True))
    with pytest.raises(PolicyViolationError, match="source|changed"):
        await run_paper_scoped_agent_episode_e0(
            _understand, agent, **{**_scoped(view, index), "catalog": catalog},
            review_model_root_arguments=lambda _proposal: True,
        )
    assert state["probes"] >= 2
    assert agent.turns == 1
