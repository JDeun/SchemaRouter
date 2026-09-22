import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    PlanRequest,
    PlanValidationError,
    RegistryExecutor,
    SchemaPlanner,
    SchemaValidationError,
    ToolCall,
    ToolSpec,
)


def nested_tool() -> ToolSpec:
    return ToolSpec(
        name="users",
        endpoints=[
            EndpointSpec(
                name="get",
                description="Get a user profile",
                output_fields=[
                    FieldSpec(
                        name="user_id",
                        path=["user", "id"],
                        identifier=True,
                        aliases=["id"],
                    ),
                    FieldSpec(
                        name="display_name",
                        path=["user", "profile", "name"],
                        aliases=["name", "profile name"],
                    ),
                    FieldSpec(
                        name="city",
                        path=["user", "profile", "address", "city"],
                        aliases=["location"],
                    ),
                ],
                output_schema={
                    "type": "object",
                    "properties": {
                        "user": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "profile": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "address": {
                                            "type": "object",
                                            "properties": {
                                                "city": {"type": "string"},
                                                "secret": {"type": "string"},
                                            },
                                            "required": ["city", "secret"],
                                        },
                                    },
                                    "required": ["name", "address"],
                                },
                            },
                            "required": ["id", "profile"],
                        }
                    },
                    "required": ["user"],
                },
                read_only=True,
            )
        ],
    )


def test_field_spec_defaults_projection_path_to_logical_name() -> None:
    field = FieldSpec(name="temperature")

    assert field.path == []
    assert field.projection_path == ("temperature",)


def test_field_spec_rejects_empty_nested_path_segments() -> None:
    with pytest.raises(ValueError, match="non-empty string segments"):
        FieldSpec(name="name", path=["profile", ""])


def test_endpoint_rejects_duplicate_or_overlapping_projection_paths() -> None:
    with pytest.raises(ValueError, match="duplicate output field path"):
        EndpointSpec(
            name="get",
            output_fields=[
                FieldSpec(name="first", path=["profile", "name"]),
                FieldSpec(name="second", path=["profile", "name"]),
            ],
        )

    with pytest.raises(ValueError, match="overlapping output field paths"):
        EndpointSpec(
            name="get",
            output_fields=[
                FieldSpec(name="profile", path=["profile"]),
                FieldSpec(name="name", path=["profile", "name"]),
            ],
        )


@pytest.mark.asyncio
async def test_executor_projects_nested_fields_and_preserves_shape() -> None:
    registry = InMemoryRegistry()
    registry.register(nested_tool())
    endpoint = registry.endpoint("users", "get")

    call = ToolCall(
        tool="users",
        endpoint="get",
        fields=["user_id", "display_name"],
        schema_fingerprint=endpoint.fingerprint,
    )
    executor = RegistryExecutor(registry)
    executor.bind(
        "users",
        lambda endpoint_name, arguments: {
            "user": {
                "id": "42",
                "profile": {
                    "name": "Ada",
                    "address": {
                        "city": "Seoul",
                        "secret": "must-not-project",
                    },
                },
            }
        },
    )

    result = await executor.execute_call(call)

    assert result.data == {
        "user": {
            "id": "42",
            "profile": {
                "name": "Ada",
            },
        }
    }
    assert result.projected_fields == ["user_id", "display_name"]


@pytest.mark.asyncio
async def test_nested_projection_does_not_mutate_raw_output() -> None:
    registry = InMemoryRegistry()
    registry.register(nested_tool())
    endpoint = registry.endpoint("users", "get")
    raw = {
        "user": {
            "id": "42",
            "profile": {
                "name": "Ada",
                "address": {
                    "city": "Seoul",
                    "secret": "keep",
                },
            },
        }
    }

    call = ToolCall(
        tool="users",
        endpoint="get",
        fields=["city"],
        schema_fingerprint=endpoint.fingerprint,
    )
    executor = RegistryExecutor(registry)
    executor.bind("users", lambda endpoint_name, arguments: raw)

    result = await executor.execute_call(call)
    result.data["user"]["profile"]["address"]["city"] = "Busan"

    assert raw["user"]["profile"]["address"]["city"] == "Seoul"
    assert raw["user"]["profile"]["address"]["secret"] == "keep"


@pytest.mark.asyncio
async def test_output_validation_happens_before_nested_projection() -> None:
    registry = InMemoryRegistry()
    registry.register(nested_tool())
    endpoint = registry.endpoint("users", "get")

    call = ToolCall(
        tool="users",
        endpoint="get",
        fields=["display_name"],
        schema_fingerprint=endpoint.fingerprint,
    )
    executor = RegistryExecutor(registry)
    executor.bind(
        "users",
        lambda endpoint_name, arguments: {
            "user": {
                "id": "42",
                "profile": {
                    "name": "Ada",
                    "address": {
                        "city": "Seoul",
                        "secret": 123,
                    },
                },
            }
        },
    )

    with pytest.raises(SchemaValidationError, match="output from users.get"):
        await executor.execute_call(call)


@pytest.mark.asyncio
async def test_explicit_nested_paths_force_local_projection_for_call_aware_invoker() -> None:
    registry = InMemoryRegistry()
    registry.register(nested_tool())
    endpoint = registry.endpoint("users", "get")

    call = ToolCall(
        tool="users",
        endpoint="get",
        fields=["display_name"],
        schema_fingerprint=endpoint.fingerprint,
    )

    class CallAwareInvoker:
        projects_fields = True

        def invoke_call(self, received: ToolCall) -> dict:
            assert received.fields == ["display_name"]
            return {
                "user": {
                    "id": "42",
                    "profile": {
                        "name": "Ada",
                        "address": {
                            "city": "Seoul",
                            "secret": "hidden",
                        },
                    },
                }
            }

    executor = RegistryExecutor(registry)
    executor.bind("users", CallAwareInvoker())

    result = await executor.execute_call(call)

    assert result.data == {"user": {"profile": {"name": "Ada"}}}


def test_planner_matches_nested_path_segments_but_emits_logical_field_ids() -> None:
    registry = InMemoryRegistry()
    registry.register(nested_tool())

    plan = SchemaPlanner(registry).plan(PlanRequest(query="profile name"))

    assert len(plan.calls) == 1
    call = plan.calls[0]
    assert "user_id" in call.fields
    assert "display_name" in call.fields
    assert "user.profile.name" not in call.fields


@pytest.mark.asyncio
async def test_executor_rejects_forged_nested_path_as_field_id() -> None:
    registry = InMemoryRegistry()
    registry.register(nested_tool())
    endpoint = registry.endpoint("users", "get")

    forged = ToolCall(
        tool="users",
        endpoint="get",
        fields=["user.profile.name"],
        schema_fingerprint=endpoint.fingerprint,
    )
    executor = RegistryExecutor(registry)

    with pytest.raises(PlanValidationError, match="undeclared output fields"):
        executor.validate_call(forged)
