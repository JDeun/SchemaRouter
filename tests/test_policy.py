import pytest

from schemarouter import (
    EndpointSpec,
    ExecutionPlan,
    ExecutionPolicy,
    InMemoryRegistry,
    PolicyRule,
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


@pytest.mark.asyncio
async def test_scoped_allow_rule_grants_one_mutation_without_global_mutation_access() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="jobs",
            endpoints=[
                EndpointSpec(name="create", read_only=False, destructive=False),
                EndpointSpec(name="update", read_only=False, destructive=False),
            ],
            metadata={"adapter": "openapi"},
        )
    )
    executor = RegistryExecutor(
        registry,
        policy=ExecutionPolicy(
            rules=(
                PolicyRule(
                    name="allow-create",
                    operation="jobs.create",
                    effect="allow",
                ),
            ),
        ),
    )
    executor.bind("jobs", lambda endpoint, arguments: {"endpoint": endpoint})

    allowed = await executor.execute(plan_for(registry, "jobs", "create"))
    assert allowed[0].data == {"endpoint": "create"}

    with pytest.raises(PolicyViolationError, match="allow_mutations"):
        await executor.execute(plan_for(registry, "jobs", "update"))


@pytest.mark.asyncio
async def test_explicit_deny_rule_can_narrow_globally_allowed_mutations() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="jobs",
            endpoints=[EndpointSpec(name="delete", read_only=False, destructive=False)],
            metadata={"adapter": "openapi"},
        )
    )
    executor = RegistryExecutor(
        registry,
        policy=ExecutionPolicy(
            allow_mutations=True,
            rules=(PolicyRule(operation="jobs.delete", effect="deny", name="protect-delete"),),
        ),
    )
    executor.bind("jobs", lambda endpoint, arguments: {"ok": True})

    with pytest.raises(PolicyViolationError, match="protect-delete"):
        await executor.execute(plan_for(registry, "jobs", "delete"))


def test_policy_rules_are_first_match_wins() -> None:
    registry = InMemoryRegistry()
    tool = ToolSpec(
        name="jobs",
        endpoints=[EndpointSpec(name="create", read_only=False, destructive=False)],
        metadata={"adapter": "openapi"},
    )
    registry.register(tool)
    endpoint = registry.endpoint("jobs", "create")
    call = plan_for(registry, "jobs", "create").calls[0]
    policy = ExecutionPolicy(
        rules=(
            PolicyRule(operation="jobs.*", effect="deny", name="broad-deny"),
            PolicyRule(operation="jobs.create", effect="allow", name="later-allow"),
        )
    )

    decision = policy.evaluate(tool, endpoint, call)

    assert decision.effect == "deny"
    assert decision.rule_name == "broad-deny"


def test_policy_rule_can_match_side_effect_classification() -> None:
    registry = InMemoryRegistry()
    tool = ToolSpec(
        name="remote",
        endpoints=[EndpointSpec(name="mystery", read_only=None)],
        metadata={"adapter": "mcp"},
    )
    registry.register(tool)
    endpoint = registry.endpoint("remote", "mystery")
    call = plan_for(registry, "remote", "mystery").calls[0]
    policy = ExecutionPolicy(
        rules=(
            PolicyRule(
                operation="remote.*",
                effect="allow",
                remote=True,
                unclassified=True,
            ),
        )
    )

    assert policy.evaluate(tool, endpoint, call).effect == "allow"


def test_policy_rule_can_exclude_unclassified_operations() -> None:
    registry = InMemoryRegistry()
    tool = ToolSpec(
        name="remote",
        endpoints=[EndpointSpec(name="known", read_only=True)],
        metadata={"adapter": "mcp"},
    )
    registry.register(tool)
    endpoint = registry.endpoint("remote", "known")
    call = plan_for(registry, "remote", "known").calls[0]
    policy = ExecutionPolicy(
        rules=(
            PolicyRule(
                operation="remote.*",
                effect="deny",
                unclassified=True,
                name="deny-unclassified",
            ),
        )
    )

    decision = policy.evaluate(tool, endpoint, call)

    assert decision.effect == "allow"
    assert decision.source == "default"


def test_policy_rule_rejects_contradictory_unclassified_and_read_only_predicates() -> None:
    with pytest.raises(ValueError, match="unclassified=True"):
        PolicyRule(
            operation="remote.*",
            effect="allow",
            read_only=True,
            unclassified=True,
        )
