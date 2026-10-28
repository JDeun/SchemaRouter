"""Source-scoped Algorithm 1 direct receipts in existing fixed5 agent; E0 only."""
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
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    ParameterSpec,
    PolicyViolationError,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.paper_understood_direct_plan import (
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperUnderstanding,
)
from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    run_generated_episode,
)
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_authorized_concept_fixed5_agent_bridge import (
    AuthorizedPaperUnderstoodDirectFixed5Selector,
)

QUERY = "Please show case status and priority"
PRINCIPAL = PrincipalContext(subject="case-reviewer", roles=("viewer",))
CATALOG = NativeConceptCatalog(concepts=(
    NativeDeclaredConcept(
        concept_id="support.case_status",
        aliases=("case status", "문의 상태", "問い合わせ状態"),
        required_fields=(CapabilityFieldContract(
            semantic_id="support.case_status", json_schema={"type": "string"},
        ),),
        source_type="support_records", license="host-reviewed",
    ),
    NativeDeclaredConcept(
        concept_id="support.priority",
        aliases=("priority", "우선순위", "優先度"),
        required_fields=(CapabilityFieldContract(
            semantic_id="support.priority", json_schema={"type": "string"},
        ),),
        source_type="support_records", license="host-reviewed",
    ),
))

INTENTS = PaperIntentRegistry(intents=(PaperIntentDeclaration(
    intent_id="case.lookup",
    required_concept_ids=("support.case_status", "support.priority"),
),))


def _complete_tool(name, *, required_input=False, license_id="host-reviewed"):
    return ToolSpec(
        name=name,
        description="Case status and priority",
        source_type="support_records", license=license_id,
        endpoints=[EndpointSpec(
            name="read", description="Read case status priority",
            read_only=True,
            output_fields=[
                FieldSpec(
                    name="case_status", semantic_id="support.case_status",
                    json_schema={"type": "string"},
                ),
                FieldSpec(
                    name="priority", semantic_id="support.priority",
                    json_schema={"type": "string"},
                ),
            ],
            parameters=[ParameterSpec(
                name="case_id", required=True,
                json_schema={"type": "string"},
            )] if required_input else [],
            input_schema={
                "type": "object",
                "properties": {"case_id": {"type": "string"}},
                "required": ["case_id"],
            } if required_input else {},
        )],
    )


def _router(*, hidden=False):
    policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("viewer",),
        ),),
        data_rules=(DataScopeRule(
            operation="complete.read", roles_any=("viewer",),
            hidden_fields=("priority",),
        ),) if hidden else (),
    )
    router = SchemaRouter(authorization_policy=policy)
    router.add_tool(_complete_tool("complete"))
    router.add_tool(ToolSpec(
        name="partial", description="Case status only",
        source_type="support_records", license="host-reviewed",
        endpoints=[EndpointSpec(
            name="read", read_only=True, description="Read case status",
            output_fields=[FieldSpec(
                name="case_status", semantic_id="support.case_status",
                json_schema={"type": "string"},
            )],
        )],
    ))
    return router


def _view(router):
    return capture_authorized_agent_tool_surface(router, QUERY, principal=PRINCIPAL)


def _task():
    return {
        "semantic_task_id": "paper-structured-direct-e0-not-independent",
        "query": QUERY, "language": "en", "supported": True,
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
        output = (
            "<tool_call>" + json.dumps({"name": "complete__read", "arguments": {}})
            + "</tool_call>"
            if self.turns == 0 else "Complete."
        )
        self.turns += 1
        return {
            "text": output, "input_tokens": 4, "tool_tokens": 6,
            "output_tokens": 3, "latency_ms": 0.0,
            "context_overflow": False,
        }


def _selector(router, *, names=("complete",), hints=None, catalog=CATALOG,
              intents=INTENTS, source_type=None, view=None):
    view = view or _view(router)
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    return AuthorizedPaperUnderstoodDirectFixed5Selector(
        view=view, catalog=catalog, index=index, intent_registry=intents,
        understanding=PaperUnderstanding(
            intent_id="case.lookup", named_tools=names,
            source_type=source_type, parameter_hints=hints or {},
        ),
    )


def test_paper_understood_direct_ready_route_passes_through_existing_agent():
    router = _router()
    selector = _selector(router)
    agent = ScriptedAgent()
    row = run_generated_episode(
        agent, router.registry, _task(), EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=selector,
        experimental_agent_tool_surface=selector.view,
        experimental_host_empty_menu_terminal=True,
    )
    assert row["passed"] is True
    assert row["host_empty_menu_terminal"] is False
    assert row["tool_call_count"] == 1
    assert row["visible_candidate_counts"] == [1]
    assert selector.last_status == "ready"
    assert selector.executable_authority is False
    assert selector.calibrated_no_fit is False
    assert all(len(model_tools) == 1 for model_tools in agent.seen_tools)


@pytest.mark.parametrize("name,hidden,license_id", [
    ("nonexistent", False, "host-reviewed"),
    ("complete", True, "host-reviewed"),
    ("unapproved", False, "other-license"),
])
def test_paper_understood_absent_hidden_or_wrong_license_has_same_empty_menu(
    name, hidden, license_id,
):
    router = _router(hidden=hidden)
    if name == "unapproved":
        router.add_tool(_complete_tool("unapproved", license_id=license_id))
    selector = _selector(router, names=(name,))
    routes = selector(QUERY, selector.view.visible_route_ids)
    assert routes == []
    assert selector.last_status == "no_proven_hit"
    assert selector.calibrated_no_fit is False
    assert name not in repr(routes)


def test_paper_understood_unnamed_over_k_is_not_a_semantic_no_fit():
    router = _router()
    for n in range(6):
        router.add_tool(_complete_tool(f"additional_{n}"))
    view = _view(router)
    unranked = _selector(router, names=(), view=view)
    assert unranked(QUERY, view.visible_route_ids) == []
    assert unranked.last_status == "over_k_unranked"
    assert unranked.calibrated_no_fit is False

    named_sixth = _selector(router, names=("additional_5",), view=view)
    assert named_sixth(QUERY, view.visible_route_ids) == ["additional_5.read"]
    assert named_sixth.last_status == "ready"


def test_paper_understood_empty_menu_stops_agent_without_execution():
    router = _router()
    selector = _selector(router, names=("unregistered_tool",))
    task = _task()
    task.update(supported=False, required_routes=[], executor_fixture={"steps": []})

    class MustNotGenerate:
        def generate(self, messages, tools):
            pytest.fail("no model turn is allowed after host empty-menu refusal")

    row = run_generated_episode(
        MustNotGenerate(), router.registry, task,
        EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=selector,
        experimental_agent_tool_surface=selector.view,
        experimental_host_empty_menu_terminal=True,
    )
    assert row["passed"] is True
    assert row["host_empty_menu_terminal"] is True
    assert row["turns"] == row["tool_call_count"] == 0
    assert selector.last_status == "no_proven_hit"
    assert "unregistered_tool" not in repr(row)


def test_paper_understood_drifted_catalog_or_intent_or_hints_fail_closed():
    router = _router()
    selector = _selector(
        router, catalog=CATALOG.model_copy(deep=True),
        intents=INTENTS.model_copy(deep=True),
    )
    object.__setattr__(
        selector.catalog.concepts[0], "aliases",
        ("new case status", "문의 상태", "問い合わせ状態"),
    )
    with pytest.raises(PolicyViolationError, match="declaration|catalog"):
        selector(QUERY, selector.view.visible_route_ids)

    selector = _selector(router, intents=INTENTS.model_copy(deep=True))
    object.__setattr__(
        selector.intent_registry.intents[0], "required_concept_ids",
        ("support.case_status",),
    )
    with pytest.raises(PolicyViolationError, match="declaration"):
        selector(QUERY, selector.view.visible_route_ids)

    selector = _selector(router)
    object.__setattr__(selector.understanding, "named_tools", ("partial",))
    with pytest.raises(PolicyViolationError, match="declaration"):
        selector(QUERY, selector.view.visible_route_ids)


def test_paper_understood_source_or_arg_hints_are_not_authority():
    router = _router()
    router.add_tool(_complete_tool("parameterized", required_input=True))
    selector = _selector(
        router, names=("parameterized",),
        hints={"case_id": "untrusted-agent-text"},
    )
    assert selector(QUERY, selector.view.visible_route_ids) == ["parameterized.read"]
    assert selector.last_status == "requires_arguments"
    assert selector.executable_authority is False

    restricted = _selector(router, names=("parameterized",), source_type="web")
    assert restricted(QUERY, restricted.view.visible_route_ids) == []
    assert restricted.last_status == "no_proven_hit"


def test_paper_understood_callback_rejects_forged_routes_or_changed_source():
    router = _router()
    selector = _selector(router)
    with pytest.raises(PolicyViolationError, match="query/view"):
        selector("wrong query", selector.view.visible_route_ids)
    with pytest.raises(PolicyViolationError, match="query/view"):
        selector(QUERY, ("invented.read",))
    router.add_tool(_complete_tool("new_source"))
    with pytest.raises(PolicyViolationError):
        selector(QUERY, selector.view.visible_route_ids)
