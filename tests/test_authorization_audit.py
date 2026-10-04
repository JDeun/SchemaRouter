import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    ExecutionPlan,
    OutputField,
    PrincipalContext,
    SchemaRouter,
    ToolCall,
    ToolEndpoint,
    ToolSpec,
)
from schemarouter.authorization_audit import AuthorizationAuditEvent


def tool() -> ToolSpec:
    return ToolSpec(
        key="company.records",
        name="records",
        provider="company",
        access_mode="python",
        endpoints=[
            ToolEndpoint(
                name="read",
                description="read records",
                output_fields=[OutputField(name="id", json_schema={"type": "string"})],
            )
        ],
    )


def plan(router: SchemaRouter) -> ExecutionPlan:
    spec = router.registry.get("company.records")
    endpoint = spec.endpoint("read")
    return ExecutionPlan(
        query="records",
        registry_version=router.registry.version,
        calls=[
            ToolCall(
                tool=spec.key,
                endpoint=endpoint.name,
                arguments={},
                fields=["id"],
                schema_fingerprint=endpoint.fingerprint,
                tool_fingerprint=spec.fingerprint,
            )
        ],
    )


@pytest.mark.asyncio
async def test_authorization_audit_emits_allow_without_raw_principal_claims() -> None:
    events: list[AuthorizationAuditEvent] = []
    router = SchemaRouter(
        authorization_policy=AuthorizationPolicy(
            rules=(
                AuthorizationRule(
                    name="employee-read",
                    effect="allow",
                    operation="company.records.read",
                    roles_any=("employee",),
                ),
            )
        ),
        authorization_audit_hook=events.append,
    )
    router.add_bound_tool(tool(), lambda endpoint, arguments: {"id": "1"})
    principal = PrincipalContext(
        subject="alice@example.test",
        roles=("employee",),
        attributes={"tenant_secret": "tenant-a"},
    )

    await router.execute(plan(router), config={"principal": principal})

    assert len(events) == 1
    event = events[0]
    assert event.effect == "allow"
    assert event.rule_name == "employee-read"
    rendered = repr(event)
    assert "alice@example.test" not in rendered
    assert "tenant-a" not in rendered
    assert "employee" not in rendered


@pytest.mark.asyncio
async def test_authorization_audit_emits_deny_without_persisting_principal() -> None:
    events: list[AuthorizationAuditEvent] = []
    router = SchemaRouter(
        authorization_policy=AuthorizationPolicy(),
        authorization_audit_hook=events.append,
    )
    router.add_bound_tool(tool(), lambda endpoint, arguments: {"id": "1"})

    with pytest.raises(Exception, match="authorization denied"):
        await router.execute(
            plan(router),
            config={"principal": PrincipalContext(subject="blocked-user")},
        )

    assert len(events) == 1
    assert events[0].effect == "deny"
    assert events[0].decision_source == "default"
    assert "blocked-user" not in repr(events[0])
