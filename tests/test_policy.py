import pytest

from schemarouter import (
    EndpointSpec,
    ExecutionPlan,
    ExecutionPolicy,
    InMemoryRegistry,
    PolicyViolationError,
    RegistryExecutor,
    ToolCall,
    ToolSpec,
)


def plan_for(registry: InMemoryRegistry, tool_key: str, endpoint_name: str) -> ExecutionPlan:
    endpoint = registry.endpoint(tool_key, endpoint_name)
    return ExecutionPlan(
        query="policy test",
        registry_version=registry.version,
        calls=[
            ToolCall(
                tool=tool_key,
                endpoint=endpoint_name,
                schema_fingerprint=endpoint.fingerprint,
            )
        ],
    )


@pytest.mark.asyncio
async def test_known_remote_mutation_is_blocked_by_default() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="jobs",
            endpoints=[
                EndpointSpec(
                    name="create",
                    method="POST",
                    path="/jobs",
                    read_only=False,
                    destructive=False,
                )
            ],
            metadata={"adapter": "openapi"},
        )
    )
    executor = RegistryExecutor(registry)
    executor.bind("jobs", lambda endpoint, arguments: {"ok": True})

    with pytest.raises(PolicyViolationError, match="allow_mutations"):
        await executor.execute(plan_for(registry, "jobs", "create"))


@pytest.mark.asyncio
async def test_known_remote_mutation_can_be_locally_allowed() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="jobs",
            endpoints=[
                EndpointSpec(
                    name="create",
                    method="POST",
                    path="/jobs",
                    read_only=False,
                    destructive=False,
                )
            ],
            metadata={"adapter": "openapi"},
        )
    )
    executor = RegistryExecutor(
        registry,
        policy=ExecutionPolicy(allow_mutations=True),
    )
    executor.bind("jobs", lambda endpoint, arguments: {"ok": True})

    result = await executor.execute(plan_for(registry, "jobs", "create"))
    assert result[0].data == {"ok": True}


@pytest.mark.asyncio
async def test_destructive_operation_requires_separate_opt_in() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="jobs",
            endpoints=[
                EndpointSpec(
                    name="delete",
                    method="DELETE",
                    path="/jobs/{id}",
                    read_only=False,
                    destructive=True,
                )
            ],
            metadata={"adapter": "openapi"},
        )
    )
    executor = RegistryExecutor(
        registry,
        policy=ExecutionPolicy(allow_mutations=True),
    )
    executor.bind("jobs", lambda endpoint, arguments: {"deleted": True})

    with pytest.raises(PolicyViolationError, match="allow_destructive"):
        await executor.execute(plan_for(registry, "jobs", "delete"))


@pytest.mark.asyncio
async def test_unclassified_mcp_operation_is_blocked_by_default() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="remote",
            endpoints=[EndpointSpec(name="mystery")],
            metadata={"adapter": "mcp", "remote_metadata_untrusted": True},
        )
    )
    executor = RegistryExecutor(registry)
    executor.bind("remote", lambda endpoint, arguments: {"ok": True})

    with pytest.raises(PolicyViolationError, match="unclassified"):
        await executor.execute(plan_for(registry, "remote", "mystery"))


@pytest.mark.asyncio
async def test_unclassified_mcp_operation_requires_local_trust() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="remote",
            endpoints=[EndpointSpec(name="mystery")],
            metadata={"adapter": "mcp", "remote_metadata_untrusted": True},
        )
    )
    executor = RegistryExecutor(
        registry,
        policy=ExecutionPolicy(allow_unclassified_remote=True),
    )
    executor.bind("remote", lambda endpoint, arguments: {"ok": True})

    result = await executor.execute(plan_for(registry, "remote", "mystery"))
    assert result[0].data == {"ok": True}


@pytest.mark.asyncio
async def test_manual_local_contract_keeps_existing_default_behavior() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="local",
            endpoints=[EndpointSpec(name="custom")],
        )
    )
    executor = RegistryExecutor(registry)
    executor.bind("local", lambda endpoint, arguments: {"ok": True})

    result = await executor.execute(plan_for(registry, "local", "custom"))
    assert result[0].data == {"ok": True}
