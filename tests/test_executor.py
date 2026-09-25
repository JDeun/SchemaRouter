import pytest

from schemarouter import (
    BindingDriftError,
    EndpointSpec,
    EvidenceRequirements,
    ExecutionError,
    ExecutionPlan,
    ExecutionPolicy,
    FallbackRoute,
    FieldSpec,
    InMemoryRegistry,
    InvocationUnavailableError,
    NonRetryableInvocationError,
    ParameterSpec,
    PlanRequest,
    PlanValidationError,
    PolicyRule,
    PolicyViolationError,
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



@pytest.mark.asyncio
async def test_execution_uses_same_registry_snapshot_that_was_validated() -> None:
    stable = ToolSpec(
        name="snapshot",
        endpoints=[EndpointSpec(name="run", read_only=True)],
    )
    drifted = stable.model_copy(
        update={"description": "changed between reads"},
        deep=True,
    )

    class AdversarialRegistry:
        def __init__(self) -> None:
            self.version = 1
            self.get_calls = 0
            self.endpoint_calls = 0

        def register(self, tool: ToolSpec, *, replace: bool = False) -> str:
            del tool, replace
            raise AssertionError("registration is not expected")

        def get(self, key: str) -> ToolSpec:
            assert key == "snapshot"
            self.get_calls += 1
            selected = stable if self.get_calls == 1 else drifted
            return selected.model_copy(deep=True)

        def tools(self) -> tuple[ToolSpec, ...]:
            return (stable.model_copy(deep=True),)

        def keys(self) -> tuple[str, ...]:
            return ("snapshot",)

        def endpoint(self, tool_key: str, endpoint_name: str) -> EndpointSpec:
            self.endpoint_calls += 1
            assert tool_key == "snapshot"
            assert endpoint_name == "run"
            return drifted.endpoint("run").model_copy(deep=True)

    registry = AdversarialRegistry()
    executor = RegistryExecutor(registry)
    executor.bind("snapshot", lambda endpoint, arguments: {"ok": True})

    # Reset the adversarial read counter after binding. Execution should need exactly one
    # ToolSpec snapshot and must not perform a second registry endpoint/tool read.
    registry.get_calls = 0
    call = ToolCall(
        tool="snapshot",
        endpoint="run",
        fields=[],
        schema_fingerprint=stable.endpoint("run").fingerprint,
        tool_fingerprint=stable.fingerprint,
    )

    result = await executor.execute_call(call)

    assert result.data == {"ok": True}
    assert registry.get_calls == 1
    assert registry.endpoint_calls == 0



def test_legacy_local_runtime_sensitive_call_requires_tool_fingerprint() -> None:
    registry = InMemoryRegistry()
    tool = ToolSpec(
        name="local_adapter",
        endpoints=[EndpointSpec(name="run", read_only=True)],
        execution_metadata={"adapter": "custom_local", "target": "worker-a"},
    )
    registry.register(tool)
    endpoint = registry.endpoint("local_adapter", "run")
    call = ToolCall(
        tool="local_adapter",
        endpoint="run",
        schema_fingerprint=endpoint.fingerprint,
    )

    with pytest.raises(PlanValidationError, match="tool_fingerprint is required"):
        RegistryExecutor(registry).validate_call(call)



def _fallback_tool(
    name: str,
    *,
    provider: str,
    access_mode: str,
    read_only: bool = True,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        provider=provider,
        access_mode=access_mode,
        endpoints=[
            EndpointSpec(
                name="search",
                read_only=read_only,
                parameters=[ParameterSpec(name="formula", required=True)],
                output_fields=[
                    FieldSpec(name="material_id", identifier=True),
                    FieldSpec(name="band_gap", aliases=["band gap"]),
                ],
                output_schema={
                    "type": "object",
                    "properties": {
                        "material_id": {"type": "string"},
                        "band_gap": {"type": "number"},
                    },
                    "required": ["material_id", "band_gap"],
                },
            )
        ],
    )


def _provider_fallback_plan(registry: InMemoryRegistry) -> ExecutionPlan:
    calls = []
    for key in ("mp_api", "mp_optimade", "oqmd_api"):
        tool = registry.get(key)
        endpoint = tool.endpoint("search")
        calls.append(
            ToolCall(
                tool=key,
                endpoint="search",
                arguments={"formula": "Si"},
                fields=["material_id", "band_gap"],
                schema_fingerprint=endpoint.fingerprint,
                tool_fingerprint=tool.fingerprint,
            )
        )
    return ExecutionPlan(
        query="Si band gap",
        registry_version=registry.version,
        calls=[calls[0]],
        fallback_routes=[
            FallbackRoute(
                primary_call_index=0,
                alternatives=[calls[1], calls[2]],
            )
        ],
    )


@pytest.mark.asyncio
async def test_executor_falls_back_same_provider_before_cross_provider() -> None:
    registry = InMemoryRegistry()
    registry.register(
        _fallback_tool(
            "mp_api",
            provider="materials_project",
            access_mode="openapi",
        )
    )
    registry.register(
        _fallback_tool(
            "mp_optimade",
            provider="materials_project",
            access_mode="optimade",
        )
    )
    registry.register(
        _fallback_tool(
            "oqmd_api",
            provider="oqmd",
            access_mode="openapi",
        )
    )
    plan = _provider_fallback_plan(registry)
    executor = RegistryExecutor(registry)
    seen = []

    def unavailable(endpoint, arguments):
        seen.append("mp_api")
        raise InvocationUnavailableError("temporary outage")

    def optimade(endpoint, arguments):
        seen.append("mp_optimade")
        return {"material_id": "mp-149", "band_gap": 1.1}

    def oqmd(endpoint, arguments):
        seen.append("oqmd_api")
        return {"material_id": "oqmd-1", "band_gap": 1.2}

    executor.bind("mp_api", unavailable)
    executor.bind("mp_optimade", optimade)
    executor.bind("oqmd_api", oqmd)

    result = (await executor.execute(plan))[0]

    assert result.tool == "mp_optimade"
    assert result.data == {"material_id": "mp-149", "band_gap": 1.1}
    assert seen == ["mp_api", "mp_optimade"]


@pytest.mark.asyncio
async def test_executor_crosses_provider_only_after_same_provider_paths_are_unavailable() -> None:
    registry = InMemoryRegistry()
    for tool in (
        _fallback_tool("mp_api", provider="materials_project", access_mode="openapi"),
        _fallback_tool("mp_optimade", provider="materials_project", access_mode="optimade"),
        _fallback_tool("oqmd_api", provider="oqmd", access_mode="openapi"),
    ):
        registry.register(tool)
    plan = _provider_fallback_plan(registry)
    executor = RegistryExecutor(registry)
    seen = []

    def unavailable(name):
        def invoke(endpoint, arguments):
            seen.append(name)
            raise InvocationUnavailableError(f"{name} unavailable")
        return invoke

    executor.bind("mp_api", unavailable("mp_api"))
    executor.bind("mp_optimade", unavailable("mp_optimade"))

    def oqmd(endpoint, arguments):
        seen.append("oqmd_api")
        return {"material_id": "oqmd-1", "band_gap": 1.2}

    executor.bind("oqmd_api", oqmd)

    result = (await executor.execute(plan))[0]

    assert result.tool == "oqmd_api"
    assert seen == ["mp_api", "mp_optimade", "oqmd_api"]


@pytest.mark.asyncio
async def test_non_retryable_failure_never_uses_provider_fallback() -> None:
    registry = InMemoryRegistry()
    for tool in (
        _fallback_tool("mp_api", provider="materials_project", access_mode="openapi"),
        _fallback_tool("mp_optimade", provider="materials_project", access_mode="optimade"),
        _fallback_tool("oqmd_api", provider="oqmd", access_mode="openapi"),
    ):
        registry.register(tool)
    plan = _provider_fallback_plan(registry)
    executor = RegistryExecutor(registry)
    fallback_called = False

    def primary(endpoint, arguments):
        raise NonRetryableInvocationError("HTTP 403")

    def fallback(endpoint, arguments):
        nonlocal fallback_called
        fallback_called = True
        return {"material_id": "mp-149", "band_gap": 1.1}

    executor.bind("mp_api", primary)
    executor.bind("mp_optimade", fallback)
    executor.bind("oqmd_api", fallback)

    with pytest.raises(NonRetryableInvocationError, match="403"):
        await executor.execute(plan)

    assert fallback_called is False


@pytest.mark.asyncio
async def test_output_schema_failure_never_uses_provider_fallback() -> None:
    registry = InMemoryRegistry()
    for tool in (
        _fallback_tool("mp_api", provider="materials_project", access_mode="openapi"),
        _fallback_tool("mp_optimade", provider="materials_project", access_mode="optimade"),
        _fallback_tool("oqmd_api", provider="oqmd", access_mode="openapi"),
    ):
        registry.register(tool)
    plan = _provider_fallback_plan(registry)
    executor = RegistryExecutor(registry)
    fallback_called = False

    executor.bind(
        "mp_api",
        lambda endpoint, arguments: {
            "material_id": "mp-149",
            "band_gap": "not-a-number",
        },
    )

    def fallback(endpoint, arguments):
        nonlocal fallback_called
        fallback_called = True
        return {"material_id": "mp-149", "band_gap": 1.1}

    executor.bind("mp_optimade", fallback)
    executor.bind("oqmd_api", fallback)

    with pytest.raises(SchemaValidationError):
        await executor.execute(plan)

    assert fallback_called is False


@pytest.mark.asyncio
async def test_fallback_chain_rejects_non_read_only_alternative() -> None:
    registry = InMemoryRegistry()
    primary = _fallback_tool(
        "primary",
        provider="provider",
        access_mode="openapi",
    )
    mutation = _fallback_tool(
        "mutation",
        provider="provider",
        access_mode="python",
        read_only=False,
    )
    registry.register(primary)
    registry.register(mutation)

    primary_endpoint = primary.endpoint("search")
    mutation_endpoint = mutation.endpoint("search")
    plan = ExecutionPlan(
        query="read",
        registry_version=registry.version,
        calls=[
            ToolCall(
                tool="primary",
                endpoint="search",
                arguments={"formula": "Si"},
                fields=["material_id", "band_gap"],
                schema_fingerprint=primary_endpoint.fingerprint,
                tool_fingerprint=primary.fingerprint,
            )
        ],
        fallback_routes=[
            FallbackRoute(
                primary_call_index=0,
                alternatives=[
                    ToolCall(
                        tool="mutation",
                        endpoint="search",
                        arguments={"formula": "Si"},
                        fields=["material_id", "band_gap"],
                        schema_fingerprint=mutation_endpoint.fingerprint,
                        tool_fingerprint=mutation.fingerprint,
                    )
                ],
            )
        ],
    )
    executor = RegistryExecutor(registry)
    executor.bind(
        "primary",
        lambda endpoint, arguments: (_ for _ in ()).throw(
            InvocationUnavailableError("down")
        ),
    )
    executor.bind("mutation", lambda endpoint, arguments: {"ok": True})

    with pytest.raises(PlanValidationError, match="explicitly read-only"):
        await executor.execute(plan)



@pytest.mark.asyncio
async def test_known_unavailable_primary_is_skipped_during_cooldown() -> None:
    registry = InMemoryRegistry()
    for tool in (
        _fallback_tool("mp_api", provider="materials_project", access_mode="openapi"),
        _fallback_tool("mp_optimade", provider="materials_project", access_mode="optimade"),
        _fallback_tool("oqmd_api", provider="oqmd", access_mode="openapi"),
    ):
        registry.register(tool)

    plan = _provider_fallback_plan(registry)
    executor = RegistryExecutor(registry, unavailable_cooldown_seconds=60)
    seen = []

    def primary(endpoint, arguments):
        seen.append("mp_api")
        return {"material_id": "mp-149", "band_gap": 1.0}

    def optimade(endpoint, arguments):
        seen.append("mp_optimade")
        return {"material_id": "mp-149", "band_gap": 1.1}

    def oqmd(endpoint, arguments):
        seen.append("oqmd_api")
        return {"material_id": "oqmd-1", "band_gap": 1.2}

    executor.bind("mp_api", primary)
    executor.bind("mp_optimade", optimade)
    executor.bind("oqmd_api", oqmd)
    executor.mark_access_unavailable("mp_api", "search")

    result = (await executor.execute(plan))[0]

    assert result.tool == "mp_optimade"
    assert seen == ["mp_optimade"]


@pytest.mark.asyncio
async def test_operator_reopen_restores_primary_access_path() -> None:
    registry = InMemoryRegistry()
    for tool in (
        _fallback_tool("mp_api", provider="materials_project", access_mode="openapi"),
        _fallback_tool("mp_optimade", provider="materials_project", access_mode="optimade"),
        _fallback_tool("oqmd_api", provider="oqmd", access_mode="openapi"),
    ):
        registry.register(tool)

    plan = _provider_fallback_plan(registry)
    executor = RegistryExecutor(registry, unavailable_cooldown_seconds=60)
    seen = []

    executor.bind(
        "mp_api",
        lambda endpoint, arguments: (
            seen.append("mp_api")
            or {"material_id": "mp-149", "band_gap": 1.0}
        ),
    )
    executor.bind(
        "mp_optimade",
        lambda endpoint, arguments: (
            seen.append("mp_optimade")
            or {"material_id": "mp-149", "band_gap": 1.1}
        ),
    )
    executor.bind(
        "oqmd_api",
        lambda endpoint, arguments: (
            seen.append("oqmd_api")
            or {"material_id": "oqmd-1", "band_gap": 1.2}
        ),
    )

    executor.mark_access_unavailable("mp_api", "search")
    executor.mark_access_available("mp_api", "search")

    result = (await executor.execute(plan))[0]

    assert result.tool == "mp_api"
    assert seen == ["mp_api"]


@pytest.mark.asyncio
async def test_all_precompiled_paths_in_cooldown_fail_without_network_invocation() -> None:
    registry = InMemoryRegistry()
    for tool in (
        _fallback_tool("mp_api", provider="materials_project", access_mode="openapi"),
        _fallback_tool("mp_optimade", provider="materials_project", access_mode="optimade"),
        _fallback_tool("oqmd_api", provider="oqmd", access_mode="openapi"),
    ):
        registry.register(tool)

    plan = _provider_fallback_plan(registry)
    executor = RegistryExecutor(registry, unavailable_cooldown_seconds=60)
    invoked = []

    def invoker(name):
        def call(endpoint, arguments):
            invoked.append(name)
            return {"material_id": name, "band_gap": 1.0}
        return call

    for name in ("mp_api", "mp_optimade", "oqmd_api"):
        executor.bind(name, invoker(name))
        executor.mark_access_unavailable(name, "search")

    with pytest.raises(
        InvocationUnavailableError,
        match="all executable precompiled access paths",
    ):
        await executor.execute(plan)

    assert invoked == []



@pytest.mark.asyncio
async def test_no_fallback_preserves_unclassified_primary_execution() -> None:
    registry = InMemoryRegistry()
    tool = ToolSpec(
        name="remote_mystery",
        remote=True,
        endpoints=[EndpointSpec(name="read", read_only=None)],
    )
    registry.register(tool)
    endpoint = tool.endpoint("read")
    call = ToolCall(
        tool=tool.key,
        endpoint=endpoint.name,
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )
    plan = ExecutionPlan(
        query="read",
        registry_version=registry.version,
        calls=[call],
    )
    executor = RegistryExecutor(
        registry,
        policy=ExecutionPolicy(allow_unclassified_remote=True),
    )
    executor.bind(tool.key, lambda endpoint, arguments: {"ok": True})

    result = await executor.execute(plan)

    assert result[0].data == {"ok": True}


@pytest.mark.asyncio
async def test_no_fallback_preserves_locally_allowed_mutation_execution() -> None:
    registry = InMemoryRegistry()
    tool = ToolSpec(
        name="writer",
        endpoints=[EndpointSpec(name="write", read_only=False)],
    )
    registry.register(tool)
    endpoint = tool.endpoint("write")
    call = ToolCall(
        tool=tool.key,
        endpoint=endpoint.name,
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )
    plan = ExecutionPlan(
        query="write",
        registry_version=registry.version,
        calls=[call],
    )
    executor = RegistryExecutor(
        registry,
        policy=ExecutionPolicy(allow_mutations=True),
    )
    executor.bind(tool.key, lambda endpoint, arguments: {"ok": True})

    result = await executor.execute(plan)

    assert result[0].data == {"ok": True}



@pytest.mark.asyncio
async def test_unbound_optional_fallback_does_not_block_bound_primary() -> None:
    registry = InMemoryRegistry()
    for tool in (
        _fallback_tool("mp_api", provider="materials_project", access_mode="openapi"),
        _fallback_tool("mp_optimade", provider="materials_project", access_mode="optimade"),
        _fallback_tool("oqmd_api", provider="oqmd", access_mode="openapi"),
    ):
        registry.register(tool)

    plan = _provider_fallback_plan(registry)
    executor = RegistryExecutor(registry)
    seen = []

    executor.bind(
        "mp_api",
        lambda endpoint, arguments: (
            seen.append("mp_api")
            or {"material_id": "mp-149", "band_gap": 1.0}
        ),
    )
    # mp_optimade intentionally remains unbound.
    executor.bind(
        "oqmd_api",
        lambda endpoint, arguments: (
            seen.append("oqmd_api")
            or {"material_id": "oqmd-1", "band_gap": 1.2}
        ),
    )

    result = (await executor.execute(plan))[0]

    assert result.tool == "mp_api"
    assert seen == ["mp_api"]


@pytest.mark.asyncio
async def test_unbound_primary_uses_bound_read_only_fallback() -> None:
    registry = InMemoryRegistry()
    for tool in (
        _fallback_tool("mp_api", provider="materials_project", access_mode="openapi"),
        _fallback_tool("mp_optimade", provider="materials_project", access_mode="optimade"),
        _fallback_tool("oqmd_api", provider="oqmd", access_mode="openapi"),
    ):
        registry.register(tool)

    plan = _provider_fallback_plan(registry)
    executor = RegistryExecutor(registry)
    seen = []

    # Primary intentionally remains unbound.
    executor.bind(
        "mp_optimade",
        lambda endpoint, arguments: (
            seen.append("mp_optimade")
            or {"material_id": "mp-149", "band_gap": 1.1}
        ),
    )
    executor.bind(
        "oqmd_api",
        lambda endpoint, arguments: (
            seen.append("oqmd_api")
            or {"material_id": "oqmd-1", "band_gap": 1.2}
        ),
    )

    result = (await executor.execute(plan))[0]

    assert result.tool == "mp_optimade"
    assert seen == ["mp_optimade"]


@pytest.mark.asyncio
async def test_stale_optional_binding_does_not_block_bound_primary() -> None:
    registry = InMemoryRegistry()
    primary = _fallback_tool(
        "mp_api",
        provider="materials_project",
        access_mode="openapi",
    )
    alternative = _fallback_tool(
        "mp_optimade",
        provider="materials_project",
        access_mode="optimade",
    )
    registry.register(primary)
    registry.register(alternative)

    primary_endpoint = primary.endpoint("search")
    alternative_endpoint = alternative.endpoint("search")
    plan = ExecutionPlan(
        query="Si band gap",
        registry_version=registry.version,
        calls=[
            ToolCall(
                tool="mp_api",
                endpoint="search",
                arguments={"formula": "Si"},
                fields=["material_id", "band_gap"],
                schema_fingerprint=primary_endpoint.fingerprint,
                tool_fingerprint=primary.fingerprint,
            )
        ],
        fallback_routes=[
            FallbackRoute(
                primary_call_index=0,
                alternatives=[
                    ToolCall(
                        tool="mp_optimade",
                        endpoint="search",
                        arguments={"formula": "Si"},
                        fields=["material_id", "band_gap"],
                        schema_fingerprint=alternative_endpoint.fingerprint,
                        tool_fingerprint=alternative.fingerprint,
                    )
                ],
            )
        ],
    )

    executor = RegistryExecutor(registry)
    seen = []
    executor.bind(
        "mp_api",
        lambda endpoint, arguments: (
            seen.append("mp_api")
            or {"material_id": "mp-149", "band_gap": 1.0}
        ),
    )
    executor.bind(
        "mp_optimade",
        lambda endpoint, arguments: (
            seen.append("mp_optimade")
            or {"material_id": "mp-149", "band_gap": 1.1}
        ),
    )

    replacement = alternative.model_copy(
        update={"access_mode": "optimade-v2"},
        deep=True,
    )
    registry.register(replacement, replace=True)

    result = (await executor.execute(plan))[0]

    assert result.tool == "mp_api"
    assert seen == ["mp_api"]


@pytest.mark.asyncio
async def test_all_read_only_fallbacks_unbound_fail_without_invocation() -> None:
    registry = InMemoryRegistry()
    for tool in (
        _fallback_tool("mp_api", provider="materials_project", access_mode="openapi"),
        _fallback_tool("mp_optimade", provider="materials_project", access_mode="optimade"),
        _fallback_tool("oqmd_api", provider="oqmd", access_mode="openapi"),
    ):
        registry.register(tool)

    plan = _provider_fallback_plan(registry)
    executor = RegistryExecutor(registry)

    with pytest.raises(ExecutionError, match="no currently bound executable access path"):
        await executor.execute(plan)

    assert executor.unavailable_access_paths() == ()



@pytest.mark.asyncio
async def test_parallel_read_only_uses_bound_fallback_when_primary_is_unbound() -> None:
    registry = InMemoryRegistry()
    for tool in (
        _fallback_tool("mp_api", provider="materials_project", access_mode="openapi"),
        _fallback_tool("mp_optimade", provider="materials_project", access_mode="optimade"),
        _fallback_tool("oqmd_api", provider="oqmd", access_mode="openapi"),
    ):
        registry.register(tool)

    plan = _provider_fallback_plan(registry)
    executor = RegistryExecutor(registry)
    seen = []

    executor.bind(
        "mp_optimade",
        lambda endpoint, arguments: (
            seen.append("mp_optimade")
            or {"material_id": "mp-149", "band_gap": 1.1}
        ),
    )
    executor.bind(
        "oqmd_api",
        lambda endpoint, arguments: (
            seen.append("oqmd_api")
            or {"material_id": "oqmd-1", "band_gap": 1.2}
        ),
    )

    result = await executor.execute_parallel_read_only(
        plan,
        max_concurrency=2,
    )

    assert result[0].tool == "mp_optimade"
    assert seen == ["mp_optimade"]



@pytest.mark.asyncio
async def test_removed_optional_fallback_does_not_block_valid_primary() -> None:
    registry = InMemoryRegistry()
    for tool in (
        _fallback_tool("mp_api", provider="materials_project", access_mode="openapi"),
        _fallback_tool("mp_optimade", provider="materials_project", access_mode="optimade"),
        _fallback_tool("oqmd_api", provider="oqmd", access_mode="openapi"),
    ):
        registry.register(tool)

    plan = _provider_fallback_plan(registry)
    registry.unregister("mp_optimade")

    executor = RegistryExecutor(registry)
    seen = []
    executor.bind(
        "mp_api",
        lambda endpoint, arguments: (
            seen.append("mp_api")
            or {"material_id": "mp-149", "band_gap": 1.0}
        ),
    )
    executor.bind(
        "oqmd_api",
        lambda endpoint, arguments: (
            seen.append("oqmd_api")
            or {"material_id": "oqmd-1", "band_gap": 1.2}
        ),
    )

    result = (await executor.execute(plan))[0]

    assert result.tool == "mp_api"
    assert seen == ["mp_api"]


@pytest.mark.asyncio
async def test_drifted_optional_fallback_that_became_mutating_is_pruned() -> None:
    registry = InMemoryRegistry()
    primary = _fallback_tool(
        "mp_api",
        provider="materials_project",
        access_mode="openapi",
    )
    alternative = _fallback_tool(
        "mp_optimade",
        provider="materials_project",
        access_mode="optimade",
    )
    registry.register(primary)
    registry.register(alternative)

    primary_endpoint = primary.endpoint("search")
    alternative_endpoint = alternative.endpoint("search")
    plan = ExecutionPlan(
        query="Si band gap",
        registry_version=registry.version,
        calls=[
            ToolCall(
                tool="mp_api",
                endpoint="search",
                arguments={"formula": "Si"},
                fields=["material_id", "band_gap"],
                schema_fingerprint=primary_endpoint.fingerprint,
                tool_fingerprint=primary.fingerprint,
            )
        ],
        fallback_routes=[
            FallbackRoute(
                primary_call_index=0,
                alternatives=[
                    ToolCall(
                        tool="mp_optimade",
                        endpoint="search",
                        arguments={"formula": "Si"},
                        fields=["material_id", "band_gap"],
                        schema_fingerprint=alternative_endpoint.fingerprint,
                        tool_fingerprint=alternative.fingerprint,
                    )
                ],
            )
        ],
    )

    replacement = alternative.model_copy(
        update={
            "endpoints": [
                alternative_endpoint.model_copy(
                    update={"read_only": False},
                    deep=True,
                )
            ]
        },
        deep=True,
    )
    registry.register(replacement, replace=True)

    executor = RegistryExecutor(registry)
    seen = []
    executor.bind(
        "mp_api",
        lambda endpoint, arguments: (
            seen.append("mp_api")
            or {"material_id": "mp-149", "band_gap": 1.0}
        ),
    )

    result = (await executor.execute(plan))[0]

    assert result.tool == "mp_api"
    assert seen == ["mp_api"]



@pytest.mark.asyncio
async def test_primary_policy_denial_never_falls_through_to_allowed_fallback() -> None:
    registry = InMemoryRegistry()
    for tool in (
        _fallback_tool("mp_api", provider="materials_project", access_mode="openapi"),
        _fallback_tool("mp_optimade", provider="materials_project", access_mode="optimade"),
        _fallback_tool("oqmd_api", provider="oqmd", access_mode="openapi"),
    ):
        registry.register(tool)

    plan = _provider_fallback_plan(registry)
    fallback_called = False

    executor = RegistryExecutor(
        registry,
        policy=ExecutionPolicy(
            rules=(
                PolicyRule(
                    name="deny-primary",
                    operation="mp_api.search",
                    effect="deny",
                ),
            ),
        ),
    )

    executor.bind(
        "mp_api",
        lambda endpoint, arguments: {"material_id": "mp-149", "band_gap": 1.0},
    )

    def fallback(endpoint, arguments):
        nonlocal fallback_called
        fallback_called = True
        return {"material_id": "mp-149", "band_gap": 1.1}

    executor.bind("mp_optimade", fallback)
    executor.bind("oqmd_api", fallback)

    with pytest.raises(PolicyViolationError, match="deny-primary"):
        await executor.execute(plan)

    assert fallback_called is False


def test_executor_rejects_forged_global_required_evidence() -> None:
    reg = InMemoryRegistry()
    reg.register(
        ToolSpec(
            name="unitless",
            endpoints=[
                EndpointSpec(
                    name="read",
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="value",
                            json_schema={"type": "number"},
                        )
                    ],
                )
            ],
        )
    )
    endpoint = reg.endpoint("unitless", "read")
    call = ToolCall(
        tool="unitless",
        endpoint="read",
        fields=["value"],
        required_evidence=EvidenceRequirements(units=True),
        schema_fingerprint=endpoint.fingerprint,
    )

    with pytest.raises(
        PlanValidationError,
        match="required evidence unavailable.*units",
    ):
        RegistryExecutor(reg).validate_call(call)


def test_executor_rejects_forged_field_evidence() -> None:
    reg = InMemoryRegistry()
    reg.register(
        ToolSpec(
            name="unitless",
            endpoints=[
                EndpointSpec(
                    name="read",
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="gap",
                            semantic_id="band_gap",
                            json_schema={"type": "number"},
                        )
                    ],
                )
            ],
        )
    )
    endpoint = reg.endpoint("unitless", "read")
    call = ToolCall(
        tool="unitless",
        endpoint="read",
        fields=["gap"],
        field_evidence={
            "gap": EvidenceRequirements(units=True),
        },
        schema_fingerprint=endpoint.fingerprint,
    )

    with pytest.raises(
        PlanValidationError,
        match="field evidence requirements unavailable.*gap.units",
    ):
        RegistryExecutor(reg).validate_call(call)


def test_executor_rejects_field_evidence_for_unselected_field() -> None:
    reg = InMemoryRegistry()
    reg.register(
        ToolSpec(
            name="materials",
            endpoints=[
                EndpointSpec(
                    name="read",
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="band_gap",
                            json_schema={"type": "number"},
                            unit="eV",
                        ),
                        FieldSpec(
                            name="density",
                            json_schema={"type": "number"},
                            unit="g/cm3",
                        ),
                    ],
                )
            ],
        )
    )
    endpoint = reg.endpoint("materials", "read")
    call = ToolCall(
        tool="materials",
        endpoint="read",
        fields=["band_gap"],
        field_evidence={
            "density": EvidenceRequirements(units=True),
        },
        schema_fingerprint=endpoint.fingerprint,
    )

    with pytest.raises(
        PlanValidationError,
        match="field evidence requirements unavailable.*density.selected_field",
    ):
        RegistryExecutor(reg).validate_call(call)


def test_executor_rejects_available_evidence_overclaim() -> None:
    reg = InMemoryRegistry()
    reg.register(
        ToolSpec(
            name="unitless",
            endpoints=[
                EndpointSpec(
                    name="read",
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="value",
                            json_schema={"type": "number"},
                        )
                    ],
                )
            ],
        )
    )
    endpoint = reg.endpoint("unitless", "read")
    call = ToolCall(
        tool="unitless",
        endpoint="read",
        fields=["value"],
        evidence=EvidenceRequirements(units=True),
        schema_fingerprint=endpoint.fingerprint,
    )

    with pytest.raises(
        PlanValidationError,
        match="call evidence overclaims current contract.*units",
    ):
        RegistryExecutor(reg).validate_call(call)


def test_executor_rejects_conflicting_global_and_field_source_types() -> None:
    reg = InMemoryRegistry()
    reg.register(
        ToolSpec(
            name="mixed_source",
            source_type="calculated",
            endpoints=[
                EndpointSpec(
                    name="read",
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="value",
                            source_type="experimental",
                        )
                    ],
                )
            ],
        )
    )
    endpoint = reg.endpoint("mixed_source", "read")
    call = ToolCall(
        tool="mixed_source",
        endpoint="read",
        fields=["value"],
        required_evidence=EvidenceRequirements(source_type="calculated"),
        field_evidence={
            "value": EvidenceRequirements(source_type="experimental"),
        },
        schema_fingerprint=endpoint.fingerprint,
    )

    with pytest.raises(
        PlanValidationError,
        match="field evidence source_type conflicts with global required evidence",
    ):
        RegistryExecutor(reg).validate_call(call)


@pytest.mark.asyncio
async def test_executor_accepts_planner_compiled_evidence_contract() -> None:
    reg = InMemoryRegistry()
    reg.register(
        ToolSpec(
            name="materials",
            source_type="calculated",
            license="CC BY 4.0",
            endpoints=[
                EndpointSpec(
                    name="read",
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="band_gap",
                            semantic_id="band_gap",
                            aliases=["band gap"],
                            json_schema={"type": "number"},
                            unit="eV",
                        )
                    ],
                )
            ],
        )
    )
    plan = SchemaPlanner(reg).plan(
        PlanRequest(
            query="band gap",
            evidence=EvidenceRequirements(
                provenance=True,
                license=True,
                units=True,
                source_type="calculated",
            ),
            field_evidence={
                "band_gap": EvidenceRequirements(units=True),
            },
        )
    )
    executor = RegistryExecutor(reg)
    executor.bind("materials", lambda endpoint, arguments: {"band_gap": 2.1})

    result = (await executor.execute(plan))[0]

    assert result.data == {"band_gap": 2.1}
