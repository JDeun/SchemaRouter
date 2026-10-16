"""No-model E0 scope/redaction controls, NOT tenant execution certification."""
from __future__ import annotations

import json

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PolicyViolationError,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    run_generated_episode,
)
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)

SECRET = "SECRET_HIDDEN_CANARY_1749"
VIEWER = PrincipalContext(subject="synthetic-viewer", roles=("viewer",))
OUTSIDER = PrincipalContext(subject="synthetic-outsider", roles=("outsider",))


def fixture_router() -> SchemaRouter:
    router = SchemaRouter(
        authorization_policy=AuthorizationPolicy(
            default_effect="deny",
            rules=(
                AuthorizationRule(
                    name="viewer-deny-archive", effect="deny",
                    operation="archive.*", roles_any=("viewer",),
                ),
                AuthorizationRule(
                    name="viewer-can-read", effect="allow",
                    operation="*.*", roles_any=("viewer",),
                ),
            ),
            data_rules=(
                DataScopeRule(
                    operation="*.*", roles_any=("viewer",),
                    hidden_fields=("secret_field",),
                ),
            ),
        ),
    )
    for name in ("marine", "papers", "archive"):
        router.add_tool(ToolSpec(
            name=name,
            description=f"{name} public records and {SECRET} hidden field",
            endpoints=[
                EndpointSpec(
                    name="read",
                    description=f"Read {name} values {SECRET}",
                    read_only=True,
                    parameters=[
                        ParameterSpec(
                            name="place", location="query", required=True,
                            description=f"Public location {SECRET}",
                            json_schema={
                                "type": "string", "description": SECRET,
                                "examples": [SECRET],
                            },
                        ),
                        ParameterSpec(
                            name="filter__secret_field", location="query",
                            json_schema={
                                "type": "string", "examples": [SECRET],
                            },
                        ),
                    ],
                    output_fields=[
                        FieldSpec(name="public_field"),
                        FieldSpec(name="secret_field"),
                    ],
                ),
            ],
        ))
    return router


def captured(router=None, principal=VIEWER):
    return capture_authorized_agent_tool_surface(
        router or fixture_router(),
        "marine public papers read values", principal=principal,
    )


def test_authorized_agent_view_excludes_denied_routes_and_hidden_descriptions():
    view = captured()
    assert set(view.visible_route_ids) == {"marine.read", "papers.read"}
    model_tools = view.tool_definitions(list(view.visible_route_ids), k=5)
    data = json.dumps(model_tools)
    assert SECRET not in data
    assert "secret_field" not in data
    assert "archive" not in data
    assert "public_field" in data
    assert "place" in data
    assert "filter__secret_field" not in data
    assert "examples" not in data
    assert "description" not in model_tools[0]["parameters"]["properties"]["place"]
    assert not view.executable_authority
    assert not view.independent_quality_evidence


def test_outsider_receives_empty_model_view_without_hidden_catalog_count():
    view = captured(principal=OUTSIDER)
    assert view.visible_route_ids == ()
    assert view.tool_definitions([]) == []
    summary = view.public_trace({
        "passed": False, "candidate_history": [],
        "required_routes": ["archive.read"],
    })
    public = json.dumps(summary)
    assert "archive" not in public
    assert "registered_route_count" not in public
    assert "visible_scored_route_count" in summary
    assert summary["visible_scored_route_count"] == 0


@pytest.mark.parametrize("selected,k", (
    (["archive.read"], 5),
    (["fake.read"], 5),
    (["marine.read", "marine.read"], 5),
    (["marine.read", "papers.read"], 1),
    ("marine.read", 5),
    ([None], 5),
    (["marine.read"], 0),
    (["marine.read"], 6),
))
def test_bad_source_selection_or_budget_fails_closed(selected, k):
    with pytest.raises((PolicyViolationError, ValueError)):
        captured().tool_definitions(selected, k=k)


def test_observation_only_exports_approved_scalar_fields():
    view = captured()
    outcome = view.project_observation("marine.read", {
        "status": "ok", "public_field": 4.25,
        "secret_field": SECRET, "unexpected": SECRET,
    })
    assert outcome == {"status": "ok", "public_field": 4.25}
    assert SECRET not in json.dumps(outcome)
    error = view.project_observation("marine.read", {
        "status": "error", "error": SECRET, "message": SECRET,
    })
    assert error == {"status": "error", "error": "provider_call_failed"}


def test_nested_sensitive_value_cannot_flow_to_agent():
    with pytest.raises(PolicyViolationError, match="nested output"):
        captured().project_observation("marine.read", {
            "status": "ok",
            "public_field": {"safe": "ok", "secret_field": SECRET},
        })


def test_report_drops_raw_query_gold_arguments_observations_and_final_text():
    view = captured()
    source = {
        "passed": True, "supported": True, "tool_call_count": 1,
        "policy_blocks": 0, "candidate_history": [
            ["marine.read", "archive.read"]
        ],
        "query": SECRET, "final_text": SECRET,
        "required_routes": ["archive.read"],
        "attempts": [{"route_id": "archive.read", "arguments": {"key": SECRET},
                      "observation": {"secret_field": SECRET}}],
        "turn_rows": [{"tool_calls": [{"arguments": {"key": SECRET}}],
                       "visible_observations": [{"secret_field": SECRET}]}],
    }
    redacted = view.public_trace(source)
    serialized = json.dumps(redacted)
    assert SECRET not in serialized
    assert "archive.read" not in serialized
    assert redacted["visible_candidate_counts"] == [1]
    assert redacted["passed"] is True
    assert redacted["tool_call_count"] == 1
    assert source["attempts"][0]["observation"]["secret_field"] == SECRET


@pytest.mark.parametrize("mutation", ("policy", "registry", "availability"))
def test_authority_swap_between_capture_and_model_publication_fails(mutation):
    router = fixture_router()
    view = captured(router)
    if mutation == "policy":
        router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    elif mutation == "registry":
        router.add_tool(ToolSpec(
            name="new_source",
            endpoints=[EndpointSpec(name="read", read_only=True)],
        ))
    else:
        router.planner.availability_predicate = lambda _tool, _endpoint: False
    with pytest.raises(PolicyViolationError, match="retrieval authority changed"):
        view.tool_definitions(["marine.read"])
    with pytest.raises(PolicyViolationError, match="retrieval authority changed"):
        view.public_trace({"passed": True})


def test_research_model_inputs_do_not_trigger_planning_or_tool_execution():
    router = fixture_router()

    def forbidden(*args, **kwargs):
        raise AssertionError("source discovery cannot execute")
    router.plan = forbidden
    router.execute = forbidden
    view = captured(router)
    assert view.tool_definitions(["marine.read"])
    assert view.project_observation("marine.read", {
        "status": "ok", "public_field": 3,
    })["public_field"] == 3


class CapturingSyntheticAgent:
    """Deterministic no-model tool-call control; retains model-facing messages."""

    def __init__(self, *, attack_router=None, wrong_route=False):
        self.calls = 0
        self.snapshots = []
        self.attack_router = attack_router
        self.wrong_route = wrong_route

    def generate(self, messages, tools):
        self.snapshots.append(json.dumps({
            "messages": messages, "tools": tools,
        }, ensure_ascii=False))
        if self.attack_router is not None:
            self.attack_router.authorization_policy = AuthorizationPolicy(
                default_effect="deny",
            )
        if self.calls == 0:
            selected = "archive__read" if self.wrong_route else "marine__read"
            text = "<tool_call>" + json.dumps({
                "name": selected, "arguments": {"place": "Seoul"},
            }) + "</tool_call>"
        else:
            text = "Final answer deliberately includes " + SECRET
        self.calls += 1
        return {
            "text": text,
            "input_tokens": 13,
            "tool_tokens": 7,
            "output_tokens": 5,
            "latency_ms": 0.0,
            "context_overflow": False,
        }


def scoped_synthetic_task():
    return {
        "semantic_task_id": "host-scope-E0-only",
        "language": "ko",
        "query": "marine public papers read values",
        "supported": True,
        "required_routes": ["marine.read"],
        "executor_fixture": {
            "steps": [{
                "route_id": "marine.read",
                "argument_rules": {"place": {"eq": "Seoul"}},
                "observation": {
                    "status": "ok",
                    "public_field": "public-data",
                    "secret_field": SECRET,
                    "unexpected": SECRET,
                },
            }],
        },
    }


def test_same_existing_agent_loop_uses_scoped_schema_and_observations_only():
    router = fixture_router()
    view = captured(router)
    agent = CapturingSyntheticAgent()
    observed = []

    def select(original_query, visible_ids):
        observed.append((original_query, visible_ids))
        assert "archive.read" not in visible_ids
        return ["marine.read"]

    result = run_generated_episode(
        agent, router.registry, scoped_synthetic_task(),
        EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=select,
        experimental_agent_tool_surface=view,
    )
    assert result["passed"] is True
    assert result["tool_call_count"] == 1
    assert result["visible_candidate_counts"] == [1]
    assert len(observed) == 1 and len(agent.snapshots) == 2
    for model_view in agent.snapshots:
        assert SECRET not in model_view
        assert "secret_field" not in model_view
        assert "filter__secret_field" not in model_view
        assert "archive" not in model_view
    assert SECRET not in json.dumps(result)
    assert "required_routes" not in result
    assert "attempts" not in result
    assert "turn_rows" not in result
    assert "final_text" not in result


def test_authority_revoked_during_model_generation_blocks_publication():
    router = fixture_router()
    agent = CapturingSyntheticAgent(attack_router=router)
    with pytest.raises(PolicyViolationError, match="retrieval authority changed"):
        run_generated_episode(
            agent, router.registry, scoped_synthetic_task(),
            EXPERIMENTAL_FIXED5_CONDITION,
            experimental_candidate_selector=lambda _query, ids: ["marine.read"],
            experimental_agent_tool_surface=captured(router),
        )
    assert agent.calls == 1


def test_no_unapproved_route_can_be_processed_via_scoped_agent_hook():
    router = fixture_router()
    agent = CapturingSyntheticAgent(wrong_route=True)
    with pytest.raises(PolicyViolationError, match="unavailable scoped observation route"):
        run_generated_episode(
            agent, router.registry, scoped_synthetic_task(),
            EXPERIMENTAL_FIXED5_CONDITION,
            experimental_candidate_selector=lambda _query, ids: ["marine.read"],
            experimental_agent_tool_surface=captured(router),
        )
    assert agent.calls == 1


def test_scoped_surface_cannot_attach_to_legacy_frozen_condition_or_other_registry():
    router = fixture_router()
    view = captured(router)
    with pytest.raises(ValueError, match="isolated fixed5"):
        run_generated_episode(
            CapturingSyntheticAgent(), router.registry, scoped_synthetic_task(),
            "FULL",
            experimental_candidate_selector=lambda _query, ids: list(ids[:5]),
            experimental_agent_tool_surface=view,
        )
    other = fixture_router()
    with pytest.raises(ValueError, match="principal-scoped registry mismatch"):
        run_generated_episode(
            CapturingSyntheticAgent(), other.registry, scoped_synthetic_task(),
            EXPERIMENTAL_FIXED5_CONDITION,
            experimental_candidate_selector=lambda _query, ids: list(ids[:5]),
            experimental_agent_tool_surface=view,
        )
