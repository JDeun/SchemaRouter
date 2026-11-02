"""E0: source-owned indexed FieldGroup routes reach the existing fixed5 agent."""
from __future__ import annotations

import json
from copy import deepcopy

import pytest
from test_native_semantic_index import ANALYST, CATALOG, VIEWER, _field, _router

from schemarouter import EndpointSpec, ParameterSpec, ToolSpec
from schemarouter.errors import PolicyViolationError
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts import research_authorized_concept_fixed5_agent_bridge as bridge
from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    run_generated_episode,
)
from scripts.research_authorized_agent_tool_surface import (
    AuthorizedAgentToolSurface,
    capture_authorized_agent_tool_surface,
)

QUERY = "show case status and priority"


def _new_selector(router, *, query=QUERY, principal=ANALYST, ranker=None, catalog=CATALOG):
    selector_type = getattr(bridge, "AuthorizedIndexedFieldFixed5Selector", None)
    assert callable(selector_type), "missing source-safe indexed fixed5 bridge"
    view = capture_authorized_agent_tool_surface(router, query, principal=principal)
    selected = selector_type(
        view, catalog, NativeSchemaPostingIndex.build(router.registry),
        research_ranker=ranker,
    )
    return view, selected


def test_indexed_bridge_exposes_only_conjunctively_complete_direct_fields():
    router = _router(many_partial=6)
    router.add_tool(ToolSpec(
        name="bound", source_type="crm", license="reviewed",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            parameters=[ParameterSpec(
                name="case_id", required=True, json_schema={"type": "string"},
            )],
            input_schema={"type": "object", "properties": {
                "case_id": {"type": "string"},
            }, "required": ["case_id"]},
            output_fields=[_field("status", "crm.status"),
                           _field("priority", "crm.priority")],
        )],
    ))
    view, selector = _new_selector(router)
    assert selector(QUERY, view.visible_route_ids) == ["complete.read"]
    assert selector.last_status == "complete"
    assert selector.independent_quality_evidence is False
    assert selector.calibrated_no_fit is False
    assert selector.executable_authority is False


def test_indexed_bridge_over_k_abstains_and_research_ranker_remains_unverified():
    router = _router(many_complete=6)
    view, selector = _new_selector(router)
    assert selector(QUERY, view.visible_route_ids) == []
    assert selector.last_status == "over_k_unranked"

    view, ranked = _new_selector(router, ranker=lambda _q, _c, _k: (6, 5, 4, 3, 2))
    assert ranked(QUERY, view.visible_route_ids) == [
        "full_5.read", "full_4.read", "full_3.read", "full_2.read", "full_1.read",
    ]
    assert ranked.last_status == "ranked_unverified"
    assert ranked.independent_quality_evidence is False


def test_indexed_bridge_preserves_unknown_concept_and_hidden_field_abstention():
    router = _router()
    view, selector = _new_selector(router, query="unrelated request")
    assert selector("unrelated request", view.visible_route_ids) == []
    assert selector.last_status == "no_declared_concept_not_calibrated_no_fit"

    view, selector = _new_selector(router, principal=VIEWER)
    assert selector(QUERY, view.visible_route_ids) == []
    assert selector.last_status == "no_proven_hit"


def test_indexed_bridge_rejects_policy_drift_and_query_forgery():
    router = _router()
    view, selector = _new_selector(router)
    with pytest.raises(PolicyViolationError, match="query/view mismatch"):
        selector("case status", view.visible_route_ids)
    policy = router.authorization_policy
    assert policy is not None
    object.__setattr__(policy, "default_effect", "allow")
    with pytest.raises(PolicyViolationError):
        selector(QUERY, view.visible_route_ids)


def test_indexed_bridge_rejects_source_mutation_during_untrusted_ranking():
    router = _router(many_complete=6)

    def mutate_source(_query, _candidates, _k):
        router.add_tool(ToolSpec(
            name="late", source_type="crm", license="reviewed",
            endpoints=[EndpointSpec(name="read", read_only=True,
                                    output_fields=[_field("status", "crm.status")])],
        ))
        return (0, 1, 2, 3, 4)

    view, selector = _new_selector(router, ranker=mutate_source)
    with pytest.raises(PolicyViolationError):
        selector(QUERY, view.visible_route_ids)


def test_indexed_bridge_rejects_concept_contract_mutation_during_ranking():
    router = _router(many_complete=6)
    catalog = deepcopy(CATALOG)

    def mutate_catalog(_query, _candidates, _k):
        object.__setattr__(catalog, "concepts", ())
        return (0, 1, 2, 3, 4)

    view, selector = _new_selector(router, ranker=mutate_catalog, catalog=catalog)
    with pytest.raises(PolicyViolationError, match="concept catalog mutated"):
        selector(QUERY, view.visible_route_ids)


def test_indexed_bridge_rejects_unavailable_model_schema_budget(monkeypatch):
    router = _router()
    view, selector = _new_selector(router)

    def reject_budget(*_args, **_kwargs):
        raise ValueError("model-visible tool definitions exceed research byte cap")

    monkeypatch.setattr(AuthorizedAgentToolSurface, "tool_definitions", reject_budget)
    assert selector(QUERY, view.visible_route_ids) == []
    assert selector.last_status == "budget_unsatisfied"


class ScriptedAgent:
    def __init__(self):
        self.turn = 0
        self.visible_counts = []

    def generate(self, messages, tools):
        del messages
        self.visible_counts.append(len(tools))
        payload = "<tool_call>" + json.dumps({
            "name": "complete__read", "arguments": {},
        }) + "</tool_call>"
        text = payload if self.turn == 0 else "Done."
        self.turn += 1
        return {
            "text": text, "input_tokens": 4, "tool_tokens": 4,
            "output_tokens": 3, "latency_ms": 0., "context_overflow": False,
        }


def test_indexed_bridge_runs_in_original_e0_agent_executor_without_gold_access():
    router = _router(many_partial=6)
    view, selector = _new_selector(router)
    task = {
        "semantic_task_id": "index-direct-e0", "query": QUERY,
        "language": "en", "supported": True,
        "required_routes": ["complete.read"],
        "executor_fixture": {"steps": [{
            "route_id": "complete.read", "argument_rules": {},
            "observation": {"status": "ok", "priority": "high"},
        }]},
    }
    agent = ScriptedAgent()
    row = run_generated_episode(
        agent, router.registry, task, EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=selector,
        experimental_agent_tool_surface=view,
    )
    assert row["passed"] is True
    assert row["visible_candidate_counts"][0] == 1
    assert row["unauthorized_destructive_executions"] == 0
    assert max(agent.visible_counts) == 1
    assert selector.last_status == "complete"
