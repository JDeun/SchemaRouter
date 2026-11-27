"""Paper-first offline quickstart using a deterministic host Understand callback.

The callback is a local contract fixture, not a real-model evaluation.
"""

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


def main() -> None:
    principal = PrincipalContext(subject="example", roles=("reader",))
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="current_weather.read", roles_any=("reader",),
        ),),
    ))

    def current_weather(endpoint, arguments):
        assert endpoint == "read"
        return {"city": arguments["city"], "temperature": 20.5}

    router.add_bound_tool(ToolSpec(
        name="current_weather", source_type="calculated", license="CC0-1.0",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            parameters=[ParameterSpec(
                name="city", required=True, json_schema={"type": "string"},
            )],
            input_schema={
                "type": "object", "properties": {"city": {"type": "string"}},
                "required": ["city"], "additionalProperties": False,
            },
            output_fields=[
                FieldSpec(name="city", semantic_id="weather.city", identifier=True,
                          json_schema={"type": "string"}),
                FieldSpec(name="temperature", semantic_id="weather.temperature",
                          json_schema={"type": "number"}),
            ],
        )],
    ), current_weather)
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="weather.temperature", aliases=("city temperature",),
        required_fields=(CapabilityFieldContract(
            semantic_id="weather.temperature", json_schema={"type": "number"},
        ),),
        source_type="calculated", license="CC0-1.0",
    ),))
    session = router.prepare_field_routing(catalog=catalog)
    intents = PaperIntentRegistry(
        intents=(PaperIntentDeclaration(
            intent_id="weather.read", required_concept_ids=("weather.temperature",),
            recall_group_ids=("weather",),
        ),),
        projection_snapshot_id=session.snapshot_id,
        route_field_groups={"current_weather.read": {"weather": ("temperature",)}},
        approved_direct_parameter_routes=("current_weather.read",),
    )

    def owner_model(payload):
        assert "schema_catalog" not in payload
        return {
            "intent_id": "weather.read",
            "needs": [{
                "concept": "city temperature", "unit": None,
                "source_type": "calculated", "qualifiers": {},
            }],
            "needs_truncated": False,
            "excluded_concepts": [],
            "named_tools": ["current_weather"],
            "parameter_hints": {},
            "source_type": "calculated",
        }

    router.configure_field_routing(
        session, model=owner_model, intent_registry=intents,
        rank_policy=PaperNativeRankPolicy(
            snapshot_id=session.snapshot_id, direct_score_mode="paper_v1", focus_direct=True,
        ),
        model_visible_intent_ids=("weather.read",),
    )
    assert not hasattr(router, "planner")
    results = router.invoke(
        PaperPlanRequest(
            query="city temperature from current_weather",
            host_source_arguments={"current_weather.read": {"city": "Seoul"}},
        ),
        config=RunConfig(principal=principal),
    )
    assert results[0].data == {"city": "Seoul", "temperature": 20.5}
    print(results[0].data)


if __name__ == "__main__":
    main()
