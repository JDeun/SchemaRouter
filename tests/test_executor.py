import pytest

from schemarouter import (
    EndpointSpec,
    ExecutionPlan,
    FieldSpec,
    InMemoryRegistry,
    ParameterSpec,
    PlanRequest,
    PlanValidationError,
    RegistryExecutor,
    SchemaDriftError,
    SchemaPlanner,
    ToolCall,
    ToolSpec,
)


def make_registry() -> InMemoryRegistry:
    reg = InMemoryRegistry()
    reg.register(
        ToolSpec(
            name="weather",
            endpoints=[
                EndpointSpec(
                    name="current",
                    parameters=[ParameterSpec(name="city", required=True)],
                    output_fields=[
                        FieldSpec(name="city", identifier=True),
                        FieldSpec(name="temperature", aliases=["temperature"]),
                        FieldSpec(name="debug_blob"),
                    ],
                )
            ],
        )
    )
    return reg


@pytest.mark.asyncio
async def test_executor_projects_result() -> None:
    reg = make_registry()
    plan = SchemaPlanner(reg).plan(
        PlanRequest(query="temperature", arguments={"city": "Seoul"})
    )
    executor = RegistryExecutor(reg)
    executor.bind(
        "weather",
        lambda endpoint, arguments: {
            "city": arguments["city"],
            "temperature": 20,
            "debug_blob": "large",
        },
    )

    result = (await executor.execute(plan))[0]
    assert result.data == {"city": "Seoul", "temperature": 20}


@pytest.mark.asyncio
async def test_executor_rejects_schema_drift() -> None:
    reg = make_registry()
    plan = SchemaPlanner(reg).plan(
        PlanRequest(query="temperature", arguments={"city": "Seoul"})
    )
    changed = ToolSpec(
        name="weather",
        endpoints=[
            EndpointSpec(
                name="current",
                parameters=[
                    ParameterSpec(name="city", required=True),
                    ParameterSpec(name="units"),
                ],
                output_fields=[FieldSpec(name="temperature")],
            )
        ],
    )
    reg.register(changed, replace=True)
    executor = RegistryExecutor(reg)
    executor.bind("weather", lambda endpoint, arguments: {})

    with pytest.raises(SchemaDriftError):
        await executor.execute(plan)


def test_executor_recomputes_required_arguments() -> None:
    reg = make_registry()
    endpoint = reg.endpoint("weather", "current")
    call = ToolCall(
        tool="weather",
        endpoint="current",
        arguments={},
        fields=["city", "temperature"],
        schema_fingerprint=endpoint.fingerprint,
        missing_required_arguments=[],
    )

    with pytest.raises(PlanValidationError, match="missing required arguments"):
        RegistryExecutor(reg).validate_call(call)


def test_executor_rejects_undeclared_output_fields() -> None:
    reg = make_registry()
    endpoint = reg.endpoint("weather", "current")
    call = ToolCall(
        tool="weather",
        endpoint="current",
        arguments={"city": "Seoul"},
        fields=["city", "secret_internal_field"],
        schema_fingerprint=endpoint.fingerprint,
    )

    with pytest.raises(PlanValidationError, match="undeclared output fields"):
        RegistryExecutor(reg).validate_call(call)


def test_executor_requires_projection_for_typed_outputs() -> None:
    reg = make_registry()
    endpoint = reg.endpoint("weather", "current")
    call = ToolCall(
        tool="weather",
        endpoint="current",
        arguments={"city": "Seoul"},
        fields=[],
        schema_fingerprint=endpoint.fingerprint,
    )
    plan = ExecutionPlan(
        query="manual",
        registry_version=reg.version,
        calls=[call],
    )

    with pytest.raises(PlanValidationError, match="explicit output projection"):
        RegistryExecutor(reg).validate_call(plan.calls[0])
