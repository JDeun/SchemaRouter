"""A5 integration with real principal-scoped native source and frozen agent."""
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
    ParameterSpec,
    PolicyViolationError,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.paper_understood_direct_plan import (
    PaperIntentDeclaration,
    PaperIntentRegistry,
)
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_paper_scoped_agent_episode_e0 import (
    run_paper_scoped_agent_episode_e0,
)

QUERY = "Please show case status"
INTENTS = PaperIntentRegistry(intents=(PaperIntentDeclaration(
    intent_id="case.lookup", required_concept_ids=("case.status",),
),))
CATALOG = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
    concept_id="case.status", aliases=("case status",),
    required_fields=(CapabilityFieldContract(
        semantic_id="case.status", json_schema={"type": "string"},
    ),),
    source_type="crm", license="host-approved",
),))


def source(*, required_argument=False):
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="complete.read", roles_any=("viewer",),
        ),),
    ))
    router.add_tool(ToolSpec(
        name="complete", description="case status",
        source_type="crm", license="host-approved",
        endpoints=[EndpointSpec(
            name="read", read_only=True, description="case status",
            parameters=[ParameterSpec(
                name="case_id", location="query", required=True,
            )] if required_argument else [],
            output_fields=[FieldSpec(
                name="status", semantic_id="case.status",
                json_schema={"type": "string"},
            )],
        )],
    ))
    view = capture_authorized_agent_tool_surface(
        router, QUERY,
        principal=PrincipalContext(subject="synthetic", roles=("viewer",)),
    )
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    return view, index


class Agent:
    def __init__(self):
        self.turns = 0

    def generate(self, messages, tools):
        assert [item["name"] for item in tools] == ["complete__read"]
        result = (
            '<tool_call>{"name":"complete__read","arguments":{}}</tool_call>'
            if self.turns == 0 else "Complete."
        )
        self.turns += 1
        return {
            "text": result, "input_tokens": 2, "tool_tokens": 2,
            "output_tokens": 2, "latency_ms": 0.0,
            "context_overflow": False,
        }


def model_result(name="complete"):
    return {
        "intent_id": "case.lookup", "concept_ids": ["case.status"],
        "named_tools": [name], "parameter_hints": {},
    }


async def evaluate(model, agent, view, index, *, supported):
    task = {
        "semantic_task_id": "a5-synthetic-not-independent",
        "query": QUERY, "language": "en", "supported": supported,
        "required_routes": ["complete.read"] if supported else [],
        "executor_fixture": {"steps": [{
            "route_id": "complete.read", "argument_rules": {},
            "observation": {"status": "ok", "status_value": "open"},
        }]} if supported else {"steps": []},
    }
    return await run_paper_scoped_agent_episode_e0(
        model, agent, view=view, task=task, catalog=CATALOG,
        intent_registry=INTENTS, index=index,
        model_visible_intent_ids=("case.lookup",),
        model_visible_concept_ids=("case.status",),
    )


@pytest.mark.asyncio
async def test_actual_scoped_plan_executes_existing_agent_once():
    view, index = source()
    agent = Agent()
    decision, row = await evaluate(
        lambda payload: model_result(), agent, view, index, supported=True,
    )
    assert decision == "offer"
    assert row["passed"] is True
    assert row["tool_call_count"] == 1
    assert row["host_empty_menu_terminal"] is False
    assert agent.turns >= 1


@pytest.mark.asyncio
async def test_denied_named_tool_never_generates_agent_turn():
    view, index = source()

    class ForbiddenAgent:
        def generate(self, messages, tools):
            pytest.fail("empty verified menu must not call agent")

    decision, row = await evaluate(
        lambda payload: model_result("hidden"),
        ForbiddenAgent(), view, index, supported=False,
    )
    assert decision == "abstain"
    assert row["host_empty_menu_terminal"] is True
    assert row["tool_call_count"] == row["turns"] == 0


@pytest.mark.asyncio
async def test_required_argument_is_not_fabricated_by_scoped_planner():
    view, index = source(required_argument=True)
    agent = Agent()
    decision, row = await evaluate(
        lambda payload: model_result(), agent, view, index, supported=False,
    )
    assert decision == "request_arguments"
    assert row["tool_call_count"] == 1
    assert agent.turns >= 1
    assert row["passed"] is False


@pytest.mark.asyncio
async def test_source_mutation_during_understand_prevents_agent_execution():
    view, index = source()
    router = view.router

    class ForbiddenAgent:
        def generate(self, messages, tools):
            pytest.fail("mutated source must not reach agent")

    def mutate(payload):
        router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return model_result()

    with pytest.raises(PolicyViolationError):
        await evaluate(mutate, ForbiddenAgent(), view, index, supported=True)
