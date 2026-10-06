import pytest

from schemarouter import (
    AuthorizationAuditDeliveryError,
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    ExecutionPlan,
    PolicyViolationError,
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



def _allowing_policy() -> AuthorizationPolicy:
    return AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                name="read-policy",
                effect="allow",
                operation="company_records.read",
            ),
        )
    )


@pytest.mark.asyncio
async def test_audit_sink_failure_is_best_effort_for_allowed_execution() -> None:
    invoked = False

    def fail_audit(_event: AuthorizationAuditEvent) -> None:
        raise RuntimeError("audit sink unavailable")

    def invoke(endpoint: str, arguments: dict) -> dict:
        nonlocal invoked
        del endpoint, arguments
        invoked = True
        return {"id": "1"}

    router = SchemaRouter(
        authorization_policy=_allowing_policy(),
        authorization_audit_hook=fail_audit,
    )
    router.add_bound_tool(tool(), invoke)

    result = await router.execute(
        plan(router),
        config={"principal": PrincipalContext(subject="alice")},
    )

    assert invoked is True
    assert result[0].data == {"id": "1"}
    snapshot = router.authorization_audit_delivery_snapshot()
    assert snapshot.mode == "best_effort"
    assert snapshot.configured is True
    assert snapshot.failure_count == 1
    assert snapshot.last_error_type == "RuntimeError"
    assert snapshot.last_delivery_succeeded is False


@pytest.mark.asyncio
async def test_audit_sink_failure_preserves_original_deny_in_best_effort_mode() -> None:
    def fail_audit(_event: AuthorizationAuditEvent) -> None:
        raise RuntimeError("audit sink unavailable")

    router = SchemaRouter(
        authorization_policy=AuthorizationPolicy(),
        authorization_audit_hook=fail_audit,
    )
    router.add_bound_tool(tool(), lambda endpoint, arguments: {"id": "1"})

    with pytest.raises(
        PolicyViolationError,
        match="authorization denied for requested capability",
    ) as exc_info:
        await router.execute(
            plan(router),
            config={"principal": PrincipalContext(subject="blocked")},
        )

    assert type(exc_info.value) is PolicyViolationError
    snapshot = router.authorization_audit_delivery_snapshot()
    assert snapshot.failure_count == 1
    assert snapshot.last_error_type == "RuntimeError"
    assert snapshot.last_delivery_succeeded is False


@pytest.mark.asyncio
async def test_strict_audit_failure_fails_closed_before_allowed_invocation() -> None:
    invoked = False

    def fail_audit(_event: AuthorizationAuditEvent) -> None:
        raise OSError("audit service offline")

    def invoke(endpoint: str, arguments: dict) -> dict:
        nonlocal invoked
        del endpoint, arguments
        invoked = True
        return {"id": "1"}

    router = SchemaRouter(
        authorization_policy=_allowing_policy(),
        authorization_audit_hook=fail_audit,
        authorization_audit_mode="strict",
    )
    router.add_bound_tool(tool(), invoke)

    with pytest.raises(AuthorizationAuditDeliveryError) as exc_info:
        await router.execute(
            plan(router),
            config={"principal": PrincipalContext(subject="alice")},
        )

    assert invoked is False
    assert exc_info.value.decision_effect == "allow"
    assert exc_info.value.phase == "execution"
    assert exc_info.value.operation == "company_records.read"
    assert isinstance(exc_info.value, PolicyViolationError)
    snapshot = router.authorization_audit_delivery_snapshot()
    assert snapshot.mode == "strict"
    assert snapshot.failure_count == 1
    assert snapshot.last_error_type == "OSError"
    assert snapshot.last_delivery_succeeded is False


@pytest.mark.asyncio
async def test_strict_audit_failure_preserves_denied_decision_semantics() -> None:
    def fail_audit(_event: AuthorizationAuditEvent) -> None:
        raise RuntimeError("audit sink unavailable")

    router = SchemaRouter(
        authorization_policy=AuthorizationPolicy(),
        authorization_audit_hook=fail_audit,
        authorization_audit_mode="strict",
    )
    router.add_bound_tool(tool(), lambda endpoint, arguments: {"id": "1"})

    with pytest.raises(AuthorizationAuditDeliveryError) as exc_info:
        await router.execute(
            plan(router),
            config={"principal": PrincipalContext(subject="blocked")},
        )

    assert exc_info.value.decision_effect == "deny"
    assert exc_info.value.phase == "execution"
    assert isinstance(exc_info.value, PolicyViolationError)


@pytest.mark.asyncio
async def test_missing_principal_keeps_policy_denial_when_best_effort_audit_fails() -> None:
    def fail_audit(_event: AuthorizationAuditEvent) -> None:
        raise RuntimeError("audit sink unavailable")

    router = SchemaRouter(
        authorization_policy=_allowing_policy(),
        authorization_audit_hook=fail_audit,
    )
    router.add_bound_tool(tool(), lambda endpoint, arguments: {"id": "1"})

    with pytest.raises(
        PolicyViolationError,
        match="principal context is required",
    ) as exc_info:
        await router.execute(plan(router))

    assert type(exc_info.value) is PolicyViolationError
    snapshot = router.authorization_audit_delivery_snapshot()
    assert snapshot.failure_count == 1
    assert snapshot.last_error_type == "RuntimeError"


def test_audit_sink_failure_is_best_effort_for_planning_and_export() -> None:
    def fail_audit(_event: AuthorizationAuditEvent) -> None:
        raise RuntimeError("audit sink unavailable")

    router = SchemaRouter(
        authorization_policy=_allowing_policy(),
        authorization_audit_hook=fail_audit,
    )
    router.add_bound_tool(tool(), lambda endpoint, arguments: {"id": "1"})
    principal = PrincipalContext(subject="alice")

    planned = router.plan_authorized("read records", principal=principal)
    assert planned.calls

    spec = router.registry.get("company_records")
    endpoint = spec.endpoint("read")
    assert (
        router._audit_export_authorization(
            principal,
            spec,
            endpoint,
            run_id="export-run",
        )
        is True
    )

    snapshot = router.authorization_audit_delivery_snapshot()
    assert snapshot.failure_count >= 2
    assert snapshot.last_error_type == "RuntimeError"


def test_strict_audit_requires_configured_sink_and_fails_closed_on_export() -> None:
    router = SchemaRouter(
        authorization_policy=_allowing_policy(),
        authorization_audit_mode="strict",
    )
    router.add_bound_tool(tool(), lambda endpoint, arguments: {"id": "1"})
    principal = PrincipalContext(subject="alice")
    spec = router.registry.get("company_records")
    endpoint = spec.endpoint("read")

    with pytest.raises(AuthorizationAuditDeliveryError) as exc_info:
        router._audit_export_authorization(
            principal,
            spec,
            endpoint,
            run_id="export-run",
        )

    assert exc_info.value.decision_effect == "allow"
    assert exc_info.value.phase == "export"
    snapshot = router.authorization_audit_delivery_snapshot()
    assert snapshot.configured is False
    assert snapshot.failure_count == 1
    assert snapshot.last_error_type == "MissingAuditHook"


def test_audit_delivery_health_recovers_after_successful_delivery() -> None:
    attempts = 0

    def flaky_audit(_event: AuthorizationAuditEvent) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary audit outage")

    router = SchemaRouter(
        authorization_policy=_allowing_policy(),
        authorization_audit_hook=flaky_audit,
    )
    router.add_bound_tool(tool(), lambda endpoint, arguments: {"id": "1"})
    principal = PrincipalContext(subject="alice")
    spec = router.registry.get("company_records")
    endpoint = spec.endpoint("read")

    assert router._audit_export_authorization(principal, spec, endpoint) is True
    assert router._audit_export_authorization(principal, spec, endpoint) is True

    snapshot = router.authorization_audit_delivery_snapshot()
    assert snapshot.failure_count == 1
    assert snapshot.last_error_type is None
    assert snapshot.last_delivery_succeeded is True


def test_authorization_audit_mode_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="authorization_audit_mode"):
        SchemaRouter(authorization_audit_mode="unknown")  # type: ignore[arg-type]
