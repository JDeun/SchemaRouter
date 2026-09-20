import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    ParameterSpec,
    PlanRequest,
    RegistryExecutor,
    SchemaDriftError,
    SchemaPlanner,
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
