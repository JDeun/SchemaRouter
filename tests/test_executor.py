import pytest

from schemarouter import (
    BindingDriftError,
    EndpointSpec,
    ExecutionPlan,
    FieldSpec,
    InMemoryRegistry,
    ParameterSpec,
    PlanRequest,
    PlanValidationError,
    RegistryExecutor,
    RetryPolicy,
    SchemaDriftError,
    SchemaPlanner,
    SchemaValidationError,
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


def test_executor_rejects_argument_type_violation() -> None:
    reg = InMemoryRegistry()
    reg.register(
        ToolSpec(
            name="search",
            endpoints=[
                EndpointSpec(
                    name="find",
                    parameters=[
                        ParameterSpec(
                            name="limit",
                            required=True,
                            json_schema={
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 100,
                            },
                        )
                    ],
                    output_fields=[FieldSpec(name="count", json_schema={"type": "integer"})],
                )
            ],
        )
    )
    endpoint = reg.endpoint("search", "find")
    call = ToolCall(
        tool="search",
        endpoint="find",
        arguments={"limit": "10"},
        fields=["count"],
        schema_fingerprint=endpoint.fingerprint,
    )

    with pytest.raises(SchemaValidationError, match="arguments for search.find"):
        RegistryExecutor(reg).validate_call(call)


def test_executor_rejects_argument_enum_violation() -> None:
    reg = InMemoryRegistry()
    reg.register(
        ToolSpec(
            name="weather",
            endpoints=[
                EndpointSpec(
                    name="forecast",
                    parameters=[
                        ParameterSpec(
                            name="units",
                            required=True,
                            json_schema={"type": "string", "enum": ["metric", "imperial"]},
                        )
                    ],
                )
            ],
        )
    )
    endpoint = reg.endpoint("weather", "forecast")
    call = ToolCall(
        tool="weather",
        endpoint="forecast",
        arguments={"units": "kelvin"},
        schema_fingerprint=endpoint.fingerprint,
    )

    with pytest.raises(SchemaValidationError, match="metric"):
        RegistryExecutor(reg).validate_call(call)


@pytest.mark.asyncio
async def test_executor_rejects_invalid_tool_output_before_projection() -> None:
    reg = InMemoryRegistry()
    reg.register(
        ToolSpec(
            name="users",
            endpoints=[
                EndpointSpec(
                    name="get",
                    parameters=[ParameterSpec(name="user_id", required=True)],
                    output_fields=[
                        FieldSpec(name="user_id", json_schema={"type": "string"}),
                        FieldSpec(name="age", json_schema={"type": "integer"}),
                    ],
                    output_schema={
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string"},
                            "age": {"type": "integer", "minimum": 0},
                        },
                        "required": ["user_id", "age"],
                    },
                )
            ],
        )
    )
    endpoint = reg.endpoint("users", "get")
    call = ToolCall(
        tool="users",
        endpoint="get",
        arguments={"user_id": "42"},
        fields=["user_id", "age"],
        schema_fingerprint=endpoint.fingerprint,
    )
    plan = ExecutionPlan(query="user", registry_version=reg.version, calls=[call])
    executor = RegistryExecutor(reg)
    executor.bind(
        "users",
        lambda endpoint, arguments: {"user_id": "42", "age": "not-an-integer"},
    )

    with pytest.raises(SchemaValidationError, match="output from users.get"):
        await executor.execute(plan)


@pytest.mark.asyncio
async def test_executor_validates_output_before_field_projection() -> None:
    reg = InMemoryRegistry()
    reg.register(
        ToolSpec(
            name="users",
            endpoints=[
                EndpointSpec(
                    name="get",
                    parameters=[ParameterSpec(name="user_id", required=True)],
                    output_fields=[
                        FieldSpec(name="user_id"),
                        FieldSpec(name="name"),
                    ],
                    output_schema={
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string"},
                            "name": {"type": "string"},
                            "internal_count": {"type": "integer"},
                        },
                        "required": ["user_id", "name", "internal_count"],
                    },
                )
            ],
        )
    )
    endpoint = reg.endpoint("users", "get")
    call = ToolCall(
        tool="users",
        endpoint="get",
        arguments={"user_id": "42"},
        fields=["name"],
        schema_fingerprint=endpoint.fingerprint,
    )
    plan = ExecutionPlan(query="name", registry_version=reg.version, calls=[call])
    executor = RegistryExecutor(reg)
    executor.bind(
        "users",
        lambda endpoint, arguments: {
            "user_id": "42",
            "name": "Ada",
            "internal_count": "invalid",
        },
    )

    with pytest.raises(SchemaValidationError, match="internal_count"):
        await executor.execute(plan)


@pytest.mark.asyncio
async def test_executor_rejects_stale_invoker_after_tool_replacement() -> None:
    reg = make_registry()
    executor = RegistryExecutor(reg)
    executor.bind(
        "weather",
        lambda endpoint, arguments: {
            "city": arguments["city"],
            "temperature": 20,
            "debug_blob": "old",
        },
    )

    replacement = ToolSpec(
        name="weather",
        endpoints=[
            EndpointSpec(
                name="current",
                parameters=[ParameterSpec(name="city", required=True)],
                output_fields=[
                    FieldSpec(name="city", identifier=True),
                    FieldSpec(name="temperature", aliases=["temperature"]),
                    FieldSpec(name="humidity"),
                ],
            )
        ],
    )
    reg.register(replacement, replace=True)
    plan = SchemaPlanner(reg).plan(
        PlanRequest(query="temperature", arguments={"city": "Seoul"})
    )

    with pytest.raises(BindingDriftError, match="rebind"):
        await executor.execute(plan)


@pytest.mark.asyncio
async def test_output_schema_violation_is_never_retried() -> None:
    reg = InMemoryRegistry()
    reg.register(
        ToolSpec(
            name="users",
            endpoints=[
                EndpointSpec(
                    name="get",
                    parameters=[ParameterSpec(name="user_id", required=True)],
                    output_fields=[FieldSpec(name="age", json_schema={"type": "integer"})],
                    output_schema={
                        "type": "object",
                        "properties": {"age": {"type": "integer"}},
                        "required": ["age"],
                    },
                    read_only=True,
                )
            ],
        )
    )
    endpoint = reg.endpoint("users", "get")
    call = ToolCall(
        tool="users",
        endpoint="get",
        arguments={"user_id": "42"},
        fields=["age"],
        schema_fingerprint=endpoint.fingerprint,
    )
    executor = RegistryExecutor(reg)
    attempts = 0

    async def invalid_output(endpoint_name: str, arguments: dict) -> dict:
        nonlocal attempts
        attempts += 1
        return {"age": "invalid"}

    executor.bind("users", invalid_output)

    with pytest.raises(SchemaValidationError, match="output from users.get"):
        await executor.execute_call(
            call,
            retry=RetryPolicy(max_attempts=3),
        )

    assert attempts == 1
