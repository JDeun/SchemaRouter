import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    ExecutionPlan,
    PrincipalContext,
    SchemaRouter,
    ToolCall,
    ToolSpec,
)
from schemarouter.authorization_audit import AuthorizationAuditEvent
from schemarouter.models import EndpointSpec, FieldSpec


def tool() -> ToolSpec:
    return ToolSpec(
        name="company_records",
        provider="company",
        access_mode="python",
        endpoints=[
            EndpointSpec(
                name="read",
                description="read records",
                output_fields=[FieldSpec(name="id", json_schema={"type": "string"})],
            )
        ],
    )


def plan(router: SchemaRouter) -> ExecutionPlan:
    spec = router.registry.get("company_records")
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
                    name="read-policy",
                    effect="allow",
                    operation="company_records.read",
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

    await router.execute(
        plan(router),
        config={
            "principal": principal,
            "run_id": "run-123",
            "principal_audit_id": "principal-opaque-7",
        },
    )

    assert len(events) == 1
    event = events[0]
    assert event.effect == "allow"
    assert event.rule_name == "read-policy"
    assert event.run_id == "run-123"
    assert event.phase == "execution"
    assert event.principal_audit_id == "principal-opaque-7"
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
    assert events[0].run_id
    assert events[0].phase == "execution"
    assert "blocked-user" not in repr(events[0])


def test_authorization_audit_default_behavior_does_not_persist_identity() -> None:
    router = SchemaRouter(
        authorization_policy=AuthorizationPolicy(
            rules=(
                AuthorizationRule(
                    name="read-policy",
                    effect="allow",
                    operation="company_records.read",
                ),
            )
        )
    )
    router.add_bound_tool(tool(), lambda endpoint, arguments: {"id": "1"})

    assert router.authorization_audit_hook is None


@pytest.mark.asyncio
async def test_authorization_audit_stream_events_reuses_stream_run_id() -> None:
    events: list[AuthorizationAuditEvent] = []
    router = SchemaRouter(
        authorization_policy=AuthorizationPolicy(
            rules=(
                AuthorizationRule(
                    name="read-policy",
                    effect="allow",
                    operation="company_records.read",
                    roles_any=("employee",),
                ),
            )
        ),
        authorization_audit_hook=events.append,
    )
    router.add_bound_tool(tool(), lambda endpoint, arguments: {"id": "1"})
    principal = PrincipalContext(subject="stream-user", roles=("employee",))

    run_events = [
        event
        async for event in router.astream_events(
            "read records",
            config={
                "principal": principal,
                "run_id": "stream-run-1",
                "principal_audit_id": "opaque-stream-principal",
            },
        )
    ]

    assert run_events
    assert all(event.run_id == "stream-run-1" for event in run_events)
    assert len(events) == 1
    assert events[0].effect == "allow"
    assert events[0].phase == "execution"
    assert events[0].run_id == "stream-run-1"
    assert events[0].principal_audit_id == "opaque-stream-principal"
    assert "stream-user" not in repr(events[0])


@pytest.mark.asyncio
async def test_authorization_audit_stream_events_emits_terminal_error_on_denial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit_events: list[AuthorizationAuditEvent] = []
    scoped_tool = ToolSpec(
        name="company_records",
        provider="company",
        access_mode="python",
        endpoints=[
            EndpointSpec(
                name="read",
                description="read records",
                output_fields=[
                    FieldSpec(
                        name="id",
                        json_schema={"type": "string"},
                    ),
                    FieldSpec(
                        name="secret_note",
                        aliases=["secret"],
                        json_schema={"type": "string"},
                    ),
                ],
            )
        ],
    )
    router = SchemaRouter(
        authorization_policy=AuthorizationPolicy(
            rules=(
                AuthorizationRule(
                    name="read-policy",
                    effect="allow",
                    operation="company_records.read",
                    roles_any=("employee",),
                ),
            ),
            data_rules=(
                DataScopeRule(
                    name="employee-scope",
                    operation="company_records.read",
                    roles_any=("employee",),
                    visible_fields=("id",),
                ),
            ),
        ),
        authorization_audit_hook=audit_events.append,
    )
    router.add_bound_tool(
        scoped_tool,
        lambda endpoint, arguments: {"id": "1", "secret_note": "private"},
    )

    # Scoped planning now removes hidden fields before candidate compilation. Exercise the
    # final authorization boundary directly with a deliberately unsafe planner result so this
    # audit test continues to prove defense-in-depth instead of depending on metadata leakage.
    registered = router.registry.get("company_records")
    registered_endpoint = registered.endpoint("read")

    async def unsafe_plan(_request: object) -> ExecutionPlan:
        return ExecutionPlan(
            query="secret",
            registry_version=router.registry.version,
            calls=[
                ToolCall(
                    tool=registered.key,
                    endpoint=registered_endpoint.name,
                    arguments={},
                    fields=["secret_note"],
                    schema_fingerprint=registered_endpoint.fingerprint,
                    tool_fingerprint=registered.fingerprint,
                )
            ],
        )

    monkeypatch.setattr(router, "aplan_executable", unsafe_plan)
    principal = PrincipalContext(
        subject="blocked-stream-user",
        roles=("employee",),
    )

    run_events = []
    with pytest.raises(Exception, match="authorization denied"):
        async for event in router.astream_events(
            "secret",
            config={
                "principal": principal,
                "run_id": "stream-denied-1",
                "principal_audit_id": "opaque-denied-principal",
            },
        ):
            run_events.append(event)

    assert [event.event for event in run_events] == ["run.start", "run.error"]
    terminal = run_events[-1]
    assert terminal.run_id == "stream-denied-1"
    assert terminal.data["stage"] == "authorization"
    assert terminal.data["error_type"] == "PolicyViolationError"
    assert "blocked-stream-user" not in repr(terminal)
    assert len(audit_events) == 1
    assert audit_events[0].effect == "deny"
    assert audit_events[0].run_id == "stream-denied-1"
