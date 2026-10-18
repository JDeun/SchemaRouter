"""E0: field-group callback in the existing generated-agent loop, no new agent."""
from __future__ import annotations

import json

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
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
from scripts.research_authorized_concept_fixed5_agent_bridge import (
    AuthorizedConceptFixed5Selector,
)

PRINCIPAL = PrincipalContext(subject="reviewer", roles=("viewer",))
CATALOG = NativeConceptCatalog(concepts=(
    NativeDeclaredConcept(
        concept_id="support.case_status", aliases=("case status", "문의 상태", "問い合わせ状態"),
        required_fields=(CapabilityFieldContract(
            semantic_id="support.case_status", json_schema={"type": "string"},
        ),),
        source_type="support_records", license="host-reviewed",
    ),
    NativeDeclaredConcept(
        concept_id="support.priority", aliases=("priority", "우선순위", "優先度"),
        required_fields=(CapabilityFieldContract(
            semantic_id="support.priority", json_schema={"type": "string"},
        ),),
        source_type="support_records", license="host-reviewed",
    ),
))
QUERY = "Please show case status and priority"


def _router(*, hidden: bool = False) -> SchemaRouter:
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("viewer",),
        ),),
        data_rules=(DataScopeRule(
            operation="complete.read", roles_any=("viewer",),
            hidden_fields=("priority",),
        ),) if hidden else (),
    ))
    for tool_name, fields in (
        ("complete", [
            FieldSpec(name="case_status", semantic_id="support.case_status",
                      json_schema={"type": "string"}),
            FieldSpec(name="priority", semantic_id="support.priority",
                      json_schema={"type": "string"}),
        ]),
        ("partial", [
            FieldSpec(name="case_status", semantic_id="support.case_status",
                      json_schema={"type": "string"}),
        ]),
    ):
        router.add_tool(ToolSpec(
            name=tool_name, description="Case status and priority",
            source_type="support_records", license="host-reviewed",
            endpoints=[EndpointSpec(
                name="read", description="Read case status priority",
                read_only=True, output_fields=fields,
            )],
        ))
    return router


def _task(query: str = QUERY) -> dict:
    # Gold lives exclusively inside the *existing* evaluator's fixture.
    # Neither callback nor registered catalog is built from this record.
    return {
        "semantic_task_id": "developer-authored-e0-not-independent",
        "query": query, "language": "en", "supported": True,
        "required_routes": ["complete.read"],
        "executor_fixture": {"steps": [{
            "route_id": "complete.read", "argument_rules": {},
            "observation": {
                "status": "ok", "case_status": "open", "priority": "high",
            },
        }]},
    }


class ScriptedAgent:
    def __init__(self):
        self.turns = 0
        self.seen_tools = []

    def generate(self, messages, tools):
        del messages
        self.seen_tools.append(tools)
        payload = {"name": "complete__read", "arguments": {}}
        output = (
            "<tool_call>" + json.dumps(payload) + "</tool_call>"
            if self.turns == 0 else "Complete."
        )
        self.turns += 1
        return {
            "text": output, "input_tokens": 4, "tool_tokens": 6,
            "output_tokens": 3, "latency_ms": 0.0,
            "context_overflow": False,
        }


def _view(router: SchemaRouter, query: str = QUERY):
    return capture_authorized_agent_tool_surface(
        router, query, principal=PRINCIPAL,
    )


def test_actual_existing_agent_e0_uses_nonexecuting_concept_selector():
    router = _router()
    view = _view(router)
    selector = AuthorizedConceptFixed5Selector(view, CATALOG)
    agent = ScriptedAgent()
    row = run_generated_episode(
        agent, router.registry, _task(),
        EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=selector,
        experimental_agent_tool_surface=view,
    )
    assert row["passed"] is True
    assert row["task_complete"] is True
    assert row["visible_candidate_counts"] == [1]
    assert row["tool_call_count"] == 1
    assert row["unauthorized_destructive_executions"] == 0
    assert selector.last_status == "unverified_declared_concept_candidates"
    assert selector.calibrated_no_fit is False
    assert selector.executable_authority is False
    assert selector.independent_quality_evidence is False
    assert all(len(tools) == 1 for tools in agent.seen_tools)
    assert "required_routes" not in json.dumps(view.public_trace(row))


@pytest.mark.parametrize("query", (
    QUERY, "문의 상태와 우선순위를 알려주세요", "問い合わせ状態と優先度を教えて",
))
def test_host_approved_multilingual_mentions_only_visible_original_routes(query):
    view = _view(_router(), query)
    result = AuthorizedConceptFixed5Selector(view, CATALOG)(
        query, view.visible_route_ids,
    )
    assert result == ["complete.read"]


def test_data_scope_hidden_requirement_is_not_a_partial_success():
    view = _view(_router(hidden=True))
    selector = AuthorizedConceptFixed5Selector(view, CATALOG)
    assert selector(QUERY, view.visible_route_ids) == []
    assert selector.last_status == "declared_concept_unmet_not_calibrated_no_fit"
    assert selector.calibrated_no_fit is False


def test_unknown_query_is_unproven_not_an_unsupported_task_verdict():
    query = "What is the weather tomorrow?"
    view = _view(_router(), query)
    selector = AuthorizedConceptFixed5Selector(view, CATALOG)
    assert selector(query, view.visible_route_ids) == []
    assert selector.last_status == "no_declared_concept_not_calibrated_no_fit"


def test_wrong_query_and_adversarial_offered_routes_abort():
    view = _view(_router())
    selector = AuthorizedConceptFixed5Selector(view, CATALOG)
    with pytest.raises(PolicyViolationError, match="query/view"):
        selector("bad query", view.visible_route_ids)
    with pytest.raises(PolicyViolationError, match="query/view"):
        selector(QUERY, ("forged.route",))


def test_registered_source_drift_cannot_be_used_to_select_agent_candidates():
    router = _router()
    view = _view(router)
    selector = AuthorizedConceptFixed5Selector(view, CATALOG)
    router.add_tool(ToolSpec(
        name="extra", endpoints=[EndpointSpec(name="read", read_only=True)],
    ))
    with pytest.raises(PolicyViolationError):
        selector(QUERY, view.visible_route_ids)


def test_mutated_declared_concept_and_ambiguous_intent_fail_closed():
    view = _view(_router())
    catalog = CATALOG.model_copy(deep=True)
    object.__setattr__(catalog.concepts[0], "aliases", ("",))
    with pytest.raises(ValueError, match="invalid bounded owner-declared concept"):
        AuthorizedConceptFixed5Selector(view, catalog)

    from schemarouter import NativeDeclaredConcept
    ambiguous = NativeConceptCatalog(concepts=(
        CATALOG.concepts[0],
        NativeDeclaredConcept(
            concept_id="ambiguous", aliases=("case status and",),
            required_fields=(CapabilityFieldContract(
                semantic_id="support.another", json_schema={"type": "string"},
            ),),
            source_type="support_records", license="host-reviewed",
        ),
    ))
    selector = AuthorizedConceptFixed5Selector(view, ambiguous)
    with pytest.raises(ValueError, match="ambiguous overlapping"):
        selector(QUERY, view.visible_route_ids)


def test_cannot_enable_selector_under_any_frozen_condition():
    view = _view(_router())
    selector = AuthorizedConceptFixed5Selector(view, CATALOG)
    for condition in ("FULL", "SR-5", "SR-10", "SR-PROGRESSIVE", "ORACLE"):
        with pytest.raises(ValueError, match="isolated fixed5"):
            run_generated_episode(
                ScriptedAgent(), view.router.registry, _task(), condition,
                experimental_candidate_selector=selector,
                experimental_agent_tool_surface=view,
            )


def test_valid_but_changed_concept_catalog_content_is_not_silently_reapproved():
    view = _view(_router())
    catalog = CATALOG.model_copy(deep=True)
    selector = AuthorizedConceptFixed5Selector(view, catalog)
    # It is still a *valid* catalog with a different source-owner alias.
    # Validation alone cannot detect post-approval semantic-map drift.
    object.__setattr__(
        catalog.concepts[0], "aliases",
        ("different case status", "문의 상태", "問い合わせ状態"),
    )
    with pytest.raises(PolicyViolationError, match="catalog mutated"):
        selector(QUERY, view.visible_route_ids)
    selector.catalog = CATALOG
    with pytest.raises(PolicyViolationError, match="catalog mutated"):
        selector(QUERY, view.visible_route_ids)
