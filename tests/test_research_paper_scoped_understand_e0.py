"""Real model-callback Understand(q) input, source safe E0 only."""
from __future__ import annotations

import json

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    PolicyViolationError,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.errors import ModelAnalysisError
from schemarouter.paper_understood_direct_plan import (
    PaperIntentDeclaration,
    PaperIntentRegistry,
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
from scripts.research_paper_scoped_understand_e0 import (
    analyze_paper_understanding_scoped,
)

QUERY = "Please show case status and priority"
VIEWER = PrincipalContext(subject="allowed", roles=("viewer",))
OUTSIDER = PrincipalContext(subject="outsider", roles=("outsider",))
SECRET = "NEVER_DISCLOSE_PRIVATE_TOOL_CANARY"
INTENTS = PaperIntentRegistry(intents=(PaperIntentDeclaration(
    intent_id="case.lookup", required_concept_ids=("case.status", "case.priority"),
),))
CATALOG = NativeConceptCatalog(concepts=(
    NativeDeclaredConcept(
        concept_id="case.status", aliases=("case status", "문의 상태", "状態"),
        required_fields=(CapabilityFieldContract(
            semantic_id="case.status", json_schema={"type": "string"},
        ),),
        source_type="crm", license="host-approved",
    ),
    NativeDeclaredConcept(
        concept_id="case.priority", aliases=("priority", "우선순위", "優先度"),
        required_fields=(CapabilityFieldContract(
            semantic_id="case.priority", json_schema={"type": "string"},
        ),),
        source_type="crm", license="host-approved",
    ),
))


def _tool(name, *, description="case status priority"):
    return ToolSpec(
        name=name, description=description,
        source_type="crm", license="host-approved",
        endpoints=[EndpointSpec(
            name="read", read_only=True, description=description,
            output_fields=[
                FieldSpec(
                    name="status", semantic_id="case.status",
                    json_schema={"type": "string"},
                ),
                FieldSpec(
                    name="priority", semantic_id="case.priority",
                    json_schema={"type": "string"},
                ),
            ],
        )],
    )


def _router():
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(
            AuthorizationRule(
                effect="deny", operation="secret.read", roles_any=("viewer",),
            ),
            AuthorizationRule(
                effect="allow", operation="*.read", roles_any=("viewer",),
            ),
        ),
    ))
    router.add_tool(_tool("complete"))
    router.add_tool(_tool("secret", description=SECRET))
    return router


def _view(router, *, query=QUERY, principal=VIEWER):
    return capture_authorized_agent_tool_surface(
        router, query, principal=principal,
    )


def _input(model, view, *, catalog=CATALOG, intents=INTENTS, **kwargs):
    return analyze_paper_understanding_scoped(
        model, view=view, intent_registry=intents, catalog=catalog,
        model_visible_intent_ids=("case.lookup",),
        model_visible_concept_ids=("case.status", "case.priority"),
        **kwargs,
    )


def _model_result(*, tool="complete", hint="not_authoritative"):
    return {
        "intent_id": "case.lookup",
        "concept_ids": ["case.status"],
        "named_tools": [tool],
        "parameter_hints": {"case_id": hint},
    }


@pytest.mark.asyncio
async def test_scoped_model_understand_feeds_existing_native_direct_agent():
    router = _router()
    view = _view(router)
    recorded = []

    async def source_scoped_model(payload):
        recorded.append(payload)
        return _model_result()

    understood = await _input(source_scoped_model, view)
    assert understood is not None
    assert understood.intent_id == "case.lookup"
    assert understood.named_tools == ("complete",)
    assert understood.parameter_hints == {"case_id": "not_authoritative"}
    assert len(recorded) == 1
    exposed = json.dumps(recorded[0], ensure_ascii=False)
    assert recorded[0]["query"] == QUERY
    assert "complete.read" in exposed
    assert SECRET not in exposed and "secret.read" not in exposed
    assert "case.lookup" in exposed and "case.status" in exposed

    selector = AuthorizedPaperUnderstoodDirectFixed5Selector(
        view=view, catalog=CATALOG, intent_registry=INTENTS,
        index=NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry)),
        understanding=understood,
    )

    class ExistingAgent:
        def __init__(self):
            self.turn = 0

        def generate(self, messages, tools):
            del messages
            assert [item["name"] for item in tools] == ["complete__read"]
            output = (
                '<tool_call>{"name":"complete__read","arguments":{}}</tool_call>'
                if self.turn == 0 else "Done."
            )
            self.turn += 1
            return {
                "text": output, "input_tokens": 2, "tool_tokens": 2,
                "output_tokens": 2, "latency_ms": 0.0,
                "context_overflow": False,
            }

    task = {
        "semantic_task_id": "model-callback-paper-e0-fixture",
        "query": QUERY, "language": "en", "supported": True,
        "required_routes": ["complete.read"],
        "executor_fixture": {"steps": [{
            "route_id": "complete.read", "argument_rules": {},
            "observation": {"status": "ok", "priority": "high"},
        }]},
    }
    row = run_generated_episode(
        ExistingAgent(), router.registry, task, EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=selector,
        experimental_agent_tool_surface=view,
        experimental_host_empty_menu_terminal=True,
    )
    assert row["passed"] is True
    assert row["tool_call_count"] == 1
    assert row["host_empty_menu_terminal"] is False
    assert selector.last_status == "ready"
    assert selector.executable_authority is False


@pytest.mark.asyncio
async def test_hallucinated_model_named_tool_stops_before_agent_generation():
    router = _router()
    view = _view(router)
    understood = await _input(lambda _payload: _model_result(tool="secret"), view)
    assert understood is not None
    selector = AuthorizedPaperUnderstoodDirectFixed5Selector(
        view=view, catalog=CATALOG, intent_registry=INTENTS,
        index=NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry)),
        understanding=understood,
    )

    class ForbiddenAgent:
        def generate(self, messages, tools):
            pytest.fail("host must not call agent for unavailable named tool")

    task = {
        "semantic_task_id": "model-callback-missing-tool-e0-fixture",
        "query": QUERY, "language": "en", "supported": False,
        "required_routes": [], "executor_fixture": {"steps": []},
    }
    row = run_generated_episode(
        ForbiddenAgent(), router.registry, task, EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=selector,
        experimental_agent_tool_surface=view,
        experimental_host_empty_menu_terminal=True,
    )
    assert row["passed"] is True
    assert row["tool_call_count"] == row["turns"] == 0
    assert selector.last_status == "no_proven_hit"
    assert SECRET not in repr(row) and "secret.read" not in repr(row)


@pytest.mark.asyncio
async def test_empty_authorized_catalog_short_circuits_model_without_no_fit_claim():
    view = _view(_router(), principal=OUTSIDER)

    def forbidden_model(_payload):
        pytest.fail("empty principal view must not invoke a model")

    assert view.visible_route_ids == ()
    assert await _input(forbidden_model, view) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["문의 상태와 우선순위", "状態と優先度を教えて"])
async def test_multilingual_source_query_is_passed_unchanged(query):
    view = _view(_router(), query=query)
    seen = []

    def model(payload):
        seen.append(payload["query"])
        return json.dumps(_model_result(), ensure_ascii=False)

    result = await _input(model, view)
    assert result is not None and result.intent_id == "case.lookup"
    assert seen == [query]


@pytest.mark.asyncio
@pytest.mark.parametrize("malformed", [
    '{"intent_id":"case.lookup","intent_id":"private"}',
    '```json\n{"intent_id":"case.lookup"}\n```',
    '{"intent_id":"case.lookup","parameter_hints":{"id":NaN}}',
    '{"intent_id":"case.lookup","surprise":1}',
    '{"intent_id":"undeclared"}',
    '{"intent_id":"case.lookup","concept_ids":["secret.concept"]}',
    {"intent_id": "case.lookup", "named_tools": [42]},
    {"intent_id": "case.lookup", "parameter_hints": {"id": ["nested"]}},
])
async def test_model_malformed_or_undeclared_payload_fails_without_exposure(malformed):
    view = _view(_router())
    with pytest.raises(ModelAnalysisError, match="invalid|unavailable") as error:
        await _input(lambda _payload: malformed, view)
    assert SECRET not in str(error.value)
    assert "secret.concept" not in str(error.value)


@pytest.mark.asyncio
async def test_model_input_and_output_byte_budgets_fail_closed():
    view = _view(_router())

    def forbidden_model(_payload):
        pytest.fail("oversized input must fail before model")

    with pytest.raises(ModelAnalysisError, match="budget"):
        await _input(forbidden_model, view, max_model_input_bytes=64)
    with pytest.raises(ModelAnalysisError, match="budget"):
        await _input(
            lambda _payload: json.dumps(_model_result(hint="x" * 5000)),
            view, max_model_output_bytes=4096,
        )


@pytest.mark.asyncio
async def test_model_source_and_host_declaration_mutation_is_fatal():
    router = _router()
    view = _view(router)

    def mutate_source(_payload):
        router.add_tool(_tool("new_native_tool"))
        return _model_result()

    with pytest.raises(PolicyViolationError):
        await _input(mutate_source, view)

    router = _router()
    view = _view(router)
    catalog = CATALOG.model_copy(deep=True)

    def mutate_catalog(_payload):
        object.__setattr__(catalog.concepts[0], "aliases", ("changed status",))
        return _model_result()

    with pytest.raises(PolicyViolationError, match="owner|catalog"):
        await _input(mutate_catalog, view, catalog=catalog)


@pytest.mark.asyncio
async def test_model_disclosure_allowlist_and_callback_failure_are_safe():
    view = _view(_router())

    def forbidden_model(_payload):
        pytest.fail("invalid host disclosure list must reject before model")

    with pytest.raises(ValueError, match="visible|approved"):
        await analyze_paper_understanding_scoped(
            forbidden_model, view=view, intent_registry=INTENTS,
            catalog=CATALOG, model_visible_intent_ids=("case.lookup",),
            model_visible_concept_ids=("case.status",),
        )

    def model_throws(_payload):
        raise RuntimeError(SECRET)

    with pytest.raises(ModelAnalysisError, match="failed") as error:
        await _input(model_throws, view)
    assert SECRET not in str(error.value)
