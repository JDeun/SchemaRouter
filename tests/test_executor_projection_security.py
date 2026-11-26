from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    ExecutionPlan,
    FieldSpec,
    InMemoryRegistry,
    PrincipalContext,
    RegistryExecutor,
    RunConfig,
    SchemaRouter,
    ToolCall,
    ToolSpec,
)


class _LeakyProjectingInvoker:
    """Claims projection support but deliberately returns the full declared record."""

    projects_fields = True

    def invoke_call(self, call: ToolCall) -> dict[str, object]:
        assert call.fields == ["public"]
        return {
            "public": "visible",
            "secret": "must-not-leak",
        }


class _LeakyListProjectingInvoker:
    projects_fields = True

    def invoke_call(self, call: ToolCall) -> list[dict[str, object]]:
        assert call.fields == ["public"]
        return [
            {"public": "one", "secret": "hidden-one"},
            {"public": "two", "secret": "hidden-two"},
        ]


def _tool(*, array: bool = False) -> ToolSpec:
    item_schema = {
        "type": "object",
        "properties": {
            "public": {"type": "string"},
            "secret": {"type": "string"},
        },
        "required": ["public", "secret"],
    }
    output_schema = (
        {"type": "array", "items": item_schema}
        if array
        else item_schema
    )
    return ToolSpec(
        name="leaky",
        endpoints=[
            EndpointSpec(
                name="read",
                read_only=True,
                output_fields=[
                    FieldSpec(name="public"),
                    FieldSpec(name="secret"),
                ],
                output_schema=output_schema,
            )
        ],
    )


def _call(tool: ToolSpec) -> ToolCall:
    endpoint = tool.endpoint("read")
    return ToolCall(
        tool=tool.key,
        endpoint=endpoint.name,
        fields=["public"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )


@pytest.mark.asyncio
async def test_projects_fields_hint_cannot_bypass_final_local_projection() -> None:
    tool = _tool()
    registry = InMemoryRegistry()
    registry.register(tool)
    executor = RegistryExecutor(registry)
    executor.bind(tool.key, _LeakyProjectingInvoker())

    result = await executor.execute_call(_call(tool))

    assert result.data == {"public": "visible"}
    assert "secret" not in result.data


@pytest.mark.asyncio
async def test_final_local_projection_preserves_list_shape_and_strips_extras() -> None:
    tool = _tool(array=True)
    registry = InMemoryRegistry()
    registry.register(tool)
    executor = RegistryExecutor(registry)
    executor.bind(tool.key, _LeakyListProjectingInvoker())

    result = await executor.execute_call(_call(tool))

    assert result.data == [
        {"public": "one"},
        {"public": "two"},
    ]


@pytest.mark.asyncio
async def test_authorization_visible_subset_cannot_leak_from_projecting_adapter() -> None:
    tool = _tool()
    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow",
                operation=f"{tool.key}.read",
                roles_any=("reader",),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation=f"{tool.key}.read",
                roles_any=("reader",),
                visible_fields=("public",),
            ),
        ),
    )
    router = SchemaRouter(authorization_policy=policy)
    router.registry.register(tool)
    router.executor.bind(tool.key, _LeakyProjectingInvoker())
    principal = PrincipalContext(subject="alice", roles=("reader",))
    plan = ExecutionPlan(
        query="read public field",
        registry_version=router.registry.version,
        calls=[_call(tool)],
    )

    result = await router.execute(
        plan,
        config=RunConfig(principal=principal),
    )

    assert result[0].data == {"public": "visible"}
    assert "secret" not in result[0].data
