"""Minimal paper-first LangGraph StateGraph integration with a local Understand fixture."""

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperNativeRankPolicy,
    PaperPlanRequest,
    ParameterSpec,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.integrations import to_langgraph_node


class State(TypedDict, total=False):
    schemarouter_request: dict[str, Any]
    schemarouter_results: list[dict[str, Any]]


def main() -> None:
    principal = PrincipalContext(subject="langgraph-example", roles=("reader",))
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="add.call", roles_any=("reader",),
        ),),
    ))

    def invoke(endpoint: str, arguments: dict[str, Any]) -> dict[str, int]:
        assert endpoint == "call"
        return {"result": arguments["a"] + arguments["b"]}

    router.add_bound_tool(ToolSpec(
        name="add", source_type="calculated", license="MIT",
        endpoints=[EndpointSpec(
            name="call", read_only=True,
            parameters=[
                ParameterSpec(name=name, required=True, json_schema={"type": "integer"})
                for name in ("a", "b")
            ],
            input_schema={
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"], "additionalProperties": False,
            },
            output_fields=[FieldSpec(
                name="result", semantic_id="arithmetic.sum", json_schema={"type": "integer"},
            )],
            output_schema={
                "type": "object", "properties": {"result": {"type": "integer"}},
                "required": ["result"], "additionalProperties": False,
            },
        )],
    ), invoke)

    session = router.prepare_field_routing(catalog=NativeConceptCatalog(concepts=(
        NativeDeclaredConcept(
            concept_id="arithmetic.sum", aliases=("sum",),
            required_fields=(CapabilityFieldContract(
                semantic_id="arithmetic.sum", json_schema={"type": "integer"},
            ),), source_type="calculated", license="MIT",
        ),
    )))
    intents = PaperIntentRegistry(
        intents=(PaperIntentDeclaration(
            intent_id="arithmetic.add", required_concept_ids=("arithmetic.sum",),
            recall_group_ids=("arithmetic",),
        ),),
        projection_snapshot_id=session.snapshot_id,
        route_field_groups={"add.call": {"arithmetic": ("result",)}},
        approved_direct_parameter_routes=("add.call",),
    )

    def owner_model(payload):
        # Local contract fixture, not a real-model accuracy measurement.
        assert "schema_catalog" not in payload
        return {
            "intent_id": "arithmetic.add",
            "needs": [{
                "concept": "sum", "unit": None,
                "source_type": "calculated", "qualifiers": {},
            }],
            "needs_truncated": False, "excluded_concepts": [],
            "named_tools": ["add"], "parameter_hints": {},
            "source_type": "calculated",
        }

    router.configure_field_routing(
        session, model=owner_model, intent_registry=intents,
        rank_policy=PaperNativeRankPolicy(
            snapshot_id=session.snapshot_id, direct_score_mode="paper_v1", focus_direct=True,
        ),
        model_visible_intent_ids=("arithmetic.add",),
    )

    builder = StateGraph(State)
    builder.add_node("schema_router", to_langgraph_node(
        router, run_config=RunConfig(principal=principal),
    ))
    builder.add_edge(START, "schema_router")
    builder.add_edge("schema_router", END)
    graph = builder.compile()

    request = PaperPlanRequest(
        query="sum two integers using add",
        host_source_arguments={"add.call": {"a": 2, "b": 3}},
    )
    state = graph.invoke({"schemarouter_request": request.model_dump(mode="json")})
    assert state["schemarouter_results"][0]["data"] == {"result": 5}
    print(state["schemarouter_results"][0]["data"])


if __name__ == "__main__":
    main()
