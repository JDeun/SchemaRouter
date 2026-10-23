"""G5 source-scoped route sets enter the existing fixed5 agent menu."""

from __future__ import annotations

import json

import pytest
from test_native_concept_graph_vertical_slice import (
    ACTOR,
    VIEWER,
    _catalog,
    _index,
    _joined_router,
)

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    PolicyViolationError,
    SchemaRouter,
    ToolSpec,
)
from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    run_generated_episode,
)
from scripts.research_authorized_agent_tool_surface import (
    AuthorizedAgentToolSurface,
    capture_authorized_agent_tool_surface,
)
from scripts.research_authorized_concept_fixed5_agent_bridge import (
    AuthorizedConceptGraphFixed5Selector,
)


def _view(router, query="case status", *, principal=ACTOR):
    return capture_authorized_agent_tool_surface(router, query, principal=principal)


def _selector(router, query="case status"):
    view = _view(router, query)
    return view, AuthorizedConceptGraphFixed5Selector(view, _catalog(), _index(router))


class TwoToolAgent:
    def __init__(self):
        self.turn = 0
        self.seen_tools = []

    def generate(self, messages, tools):
        del messages
        self.seen_tools.append(tools)
        name = ("contacts__read", "cases__read", None)[min(self.turn, 2)]
        self.turn += 1
        if name is None:
            content = "Finished."
        else:
            args = {} if name == "contacts__read" else {
                "contact_id": "c1", "region_id": "r1",
            }
            content = "<tool_call>" + json.dumps({"name": name, "arguments": args}) + "</tool_call>"
        return {
            "text": content, "input_tokens": 4, "tool_tokens": 4,
            "output_tokens": 3, "latency_ms": 0., "context_overflow": False,
        }


def test_graph_selector_passes_two_routes_to_existing_agent() -> None:
    router = _joined_router()
    view, selector = _selector(router)
    assert selector("case status", view.visible_route_ids) == ["contacts.read", "cases.read"]
    assert selector.last_status == "complete"
    assert selector.executable_authority is False
    assert selector.independent_quality_evidence is False
    assert selector.calibrated_no_fit is False
    agent = TwoToolAgent()
    row = run_generated_episode(
        agent, router.registry,
        {
            "semantic_task_id": "developer-authored-typed-join",
            "query": "case status", "language": "en", "supported": True,
            "required_routes": ["contacts.read", "cases.read"],
            "executor_fixture": {"steps": [
                {"route_id": "contacts.read", "argument_rules": {},
                 "observation": {"status": "ok", "contact_id": "c1", "region_id": "r1"}},
                {"route_id": "cases.read", "argument_rules": {
                    "contact_id": {"eq": "c1"}, "region_id": {"eq": "r1"}},
                 "observation": {"status": "ok"}},
            ]},
        },
        EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=selector,
        experimental_agent_tool_surface=view,
    )
    assert row["passed"] is True
    assert row["task_complete"] is True
    assert row["tool_call_count"] == 2
    assert row["visible_candidate_counts"][0] == 2
    assert all({tool["name"] for tool in tools} == {
        "contacts__read", "cases__read",
    } for tools in agent.seen_tools if tools)


def test_graph_view_redacts_nested_hidden_metadata() -> None:
    # Real registered source metadata contains the hidden nested label, not
    # merely a string asserted absent from an unrelated generated schema.
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(effect="allow", operation="*.*", roles_any=("viewer",)),),
        data_rules=(DataScopeRule(
            operation="sensitive.read", roles_any=("viewer",),
            hidden_fields=("private_nested_secret",),
        ),),
    ))
    router.add_tool(ToolSpec(
        name="sensitive", source_type="crm", license="owner-reviewed",
        description="Raw private_nested_secret should not be shown",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            description="Do not disclose private_nested_secret",
            output_fields=[
                FieldSpec(name="status", semantic_id="crm.status",
                          json_schema={"type": "string"}),
                FieldSpec(name="private_nested_secret", json_schema={"type": "object"}),
            ],
            output_schema={"type": "object", "properties": {
                "status": {"type": "string"},
                "private_nested_secret": {"$ref": "#/$defs/private_nested_secret"},
            }, "$defs": {"private_nested_secret": {
                "type": "object", "properties": {"secret": {"type": "string"}},
            }}},
        )],
    ))
    view = _view(router, principal=VIEWER)
    selector = AuthorizedConceptGraphFixed5Selector(view, _catalog(), _index(router))
    scoped = view.tool_definitions(["sensitive.read"])
    assert "private_nested_secret" not in json.dumps(scoped)
    assert selector("case status", view.visible_route_ids) == ["sensitive.read"]


def test_graph_selector_rejects_policy_content_drift() -> None:
    router = _joined_router()
    view, selector = _selector(router)
    policy = router.authorization_policy
    assert policy is not None
    object.__setattr__(policy, "default_effect", "allow")
    with pytest.raises(PolicyViolationError):
        selector("case status", view.visible_route_ids)


def test_graph_selector_rejects_schema_fingerprint_drift() -> None:
    router = _joined_router()
    view, selector = _selector(router)
    router.add_tool(ToolSpec(name="changed", endpoints=[EndpointSpec(name="read", read_only=True)]))
    with pytest.raises(PolicyViolationError):
        selector("case status", view.visible_route_ids)


def test_graph_selector_rejects_over_k_or_byte_budget(monkeypatch) -> None:
    router = _joined_router(extra_consumers=5)
    view, selector = _selector(router)
    assert selector("case status", view.visible_route_ids) == []
    assert selector.last_status == "over_k_unranked"

    fresh_router = _joined_router()
    view, selector = _selector(fresh_router)
    def reject_budget(*_args, **_kwargs):
        raise ValueError("model-visible tool definitions exceed research byte cap")
    monkeypatch.setattr(AuthorizedAgentToolSurface, "tool_definitions", reject_budget)
    assert selector("case status", view.visible_route_ids) == []
    assert selector.last_status == "budget_unsatisfied"


def test_graph_selector_no_gold_or_execution_access(monkeypatch) -> None:
    router = _joined_router()
    view, selector = _selector(router)
    def forbidden(*_args, **_kwargs):
        raise AssertionError("candidate discovery invoked execution")
    monkeypatch.setattr(router, "plan", forbidden)
    monkeypatch.setattr(router, "execute", forbidden)
    assert selector("case status", view.visible_route_ids) == ["contacts.read", "cases.read"]
    assert not any("gold" in key or "fixture" in key for key in vars(selector))


@pytest.mark.parametrize("query", ("case status", "문의 상태", "問い合わせ状態"))
def test_graph_selector_multilingual_host_aliases(query: str) -> None:
    router = _joined_router()
    view, selector = _selector(router, query)
    assert selector(query, view.visible_route_ids) == ["contacts.read", "cases.read"]
