from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    PlanRequest,
    PolicyViolationError,
    PrincipalContext,
    RetryPolicy,
    RunConfig,
    SchemaRouter,
    ToolSpec,
)


def _tool(name: str, description: str) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=description,
        endpoints=[
            EndpointSpec(
                name="read",
                description=description,
                output_fields=[
                    FieldSpec(
                        name="value",
                        description=description,
                        json_schema={"type": "string"},
                    )
                ],
                output_schema={
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                },
                read_only=True,
            )
        ],
    )


def _policy() -> AuthorizationPolicy:
    return AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                name="employees-public",
                effect="allow",
                operation="employee_records.*",
                roles_any=("employee", "manager", "executive"),
            ),
            AuthorizationRule(
                name="managers-operations",
                effect="allow",
                operation="management_metrics.*",
                roles_any=("manager", "executive"),
            ),
            AuthorizationRule(
                name="executive-board",
                effect="allow",
                operation="board_financials.*",
                roles_any=("executive",),
            ),
        ),
    )


def _router() -> SchemaRouter:
    router = SchemaRouter(authorization_policy=_policy())
    for name, description in (
        ("employee_records", "employee directory and public staff records"),
        ("management_metrics", "department management operations metrics"),
        ("board_financials", "board financial forecast and executive revenue"),
    ):
        tool = _tool(name, description)
        router.add_bound_tool(
            tool,
            lambda endpoint, arguments, value=name: {"value": value},
        )
    return router


def test_principal_authorization_hides_ineligible_capabilities_before_retrieval() -> None:
    router = _router()
    employee = PrincipalContext(subject="alice", roles=("employee",))
    executive = PrincipalContext(subject="ceo", roles=("executive",))

    employee_view = router.retrieve_authorized(
        "board financial forecast",
        principal=employee,
        k=5,
    )
    executive_view = router.retrieve_authorized(
        "board financial forecast",
        principal=executive,
        k=5,
    )

    assert all(item.tool != "board_financials" for item in employee_view.candidates)
    assert any(item.tool == "board_financials" for item in executive_view.candidates)


def test_configured_authorization_requires_principal_fail_closed() -> None:
    router = _router()

    with pytest.raises(PolicyViolationError, match="principal context is required"):
        router.retrieve("employee directory", k=5)

    with pytest.raises(PolicyViolationError, match="principal context is required"):
        router.plan("employee directory")


@pytest.mark.asyncio
async def test_execution_revalidates_principal_against_forged_or_stale_plan() -> None:
    router = _router()
    employee = PrincipalContext(subject="alice", roles=("employee",))
    executive = PrincipalContext(subject="ceo", roles=("executive",))

    plan = router.plan_authorized(
        PlanRequest(query="board financial forecast"),
        principal=executive,
    )
    assert plan.calls
    assert plan.calls[0].tool == "board_financials"

    with pytest.raises(PolicyViolationError, match="authorization denied"):
        await router.execute(
            plan,
            config=RunConfig(principal=employee),
        )

    result = await router.execute(
        plan,
        config=RunConfig(principal=executive),
    )
    assert result[0].data == {"value": "board_financials"}


def test_rbac_abac_combines_department_team_and_attributes() -> None:
    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                name="sales-apac",
                effect="allow",
                operation="sales_pipeline.*",
                departments_any=("sales",),
                teams_any=("enterprise",),
                attributes=(("region", "apac"),),
            ),
        )
    )
    tool = _tool("sales_pipeline", "sales pipeline")
    endpoint = tool.endpoint("read")

    allowed = PrincipalContext(
        subject="manager-1",
        roles=("manager",),
        departments=("sales",),
        teams=("enterprise",),
        attributes={"region": "apac"},
    )
    wrong_region = allowed.model_copy(
        update={"attributes": {"region": "emea"}}
    )

    assert policy.visible(allowed, tool, endpoint) is True
    assert policy.visible(wrong_region, tool, endpoint) is False


@pytest.mark.asyncio
async def test_with_config_applies_principal_to_retrieval_and_invoke() -> None:
    router = _router()
    employee = PrincipalContext(subject="alice", roles=("employee",))
    configured = router.with_config(RunConfig(principal=employee))

    retrieval = configured.retrieve("board financial forecast", k=5)
    assert all(item.tool != "board_financials" for item in retrieval.candidates)

    result = await configured.ainvoke("employee directory")
    assert result
    assert result[0].tool == "employee_records"


@pytest.mark.asyncio
async def test_parallel_event_stream_preflight_preserves_explicit_principal() -> None:
    router = _router()
    employee = PrincipalContext(subject="alice", roles=("employee",))

    events = [
        event
        async for event in router.astream_events(
            "employee directory",
            config=RunConfig(
                principal=employee,
                execution_mode="parallel_read_only",
            ),
        )
    ]

    assert any(event.event == "tool.end" for event in events)
    assert events[-1].event == "run.end"


@pytest.mark.asyncio
async def test_direct_executor_call_cannot_bypass_router_authorization() -> None:
    router = _router()
    executive = PrincipalContext(subject="ceo", roles=("executive",))
    plan = router.plan_authorized("board financial forecast", principal=executive)
    assert plan.calls and plan.calls[0].tool == "board_financials"

    with pytest.raises(PolicyViolationError, match="authorization denied"):
        await router.executor.execute(plan)


def test_no_authorization_policy_preserves_existing_no_principal_behavior() -> None:
    router = SchemaRouter()
    tool = _tool("public", "public information")
    router.add_bound_tool(tool, lambda endpoint, arguments: {"value": "ok"})

    retrieval = router.retrieve("public information")
    assert retrieval.candidates
    assert retrieval.candidates[0].tool == "public"

@pytest.mark.asyncio
async def test_retry_reauthorizes_capability_after_policy_revocation() -> None:
    allow_rule = AuthorizationRule(
        name="retry-allow",
        effect="allow",
        operation="retry_records.*",
    )
    router = SchemaRouter(
        authorization_policy=AuthorizationPolicy(rules=(allow_rule,))
    )
    tool = _tool("retry_records", "retry records")
    attempts = 0

    async def invoker(endpoint: str, arguments: dict) -> dict:
        nonlocal attempts
        del endpoint, arguments
        attempts += 1
        if attempts == 1:
            router.executor.authorization_policy = AuthorizationPolicy(
                default_effect="deny"
            )
            raise RuntimeError("transient failure")
        return {"value": "should-not-run"}

    router.add_bound_tool(tool, invoker)
    principal = PrincipalContext(subject="alice")
    plan = router.plan_authorized("retry records", principal=principal)

    with pytest.raises(PolicyViolationError, match="authorization denied"):
        await router.execute(
            plan,
            config=RunConfig(
                principal=principal,
                retry=RetryPolicy(max_attempts=2),
            ),
        )

    assert attempts == 1


@pytest.mark.asyncio
async def test_retry_recomputes_data_scope_before_second_invocation() -> None:
    allow_rule = AuthorizationRule(
        name="retry-allow",
        effect="allow",
        operation="retry_records.*",
    )
    router = SchemaRouter(
        authorization_policy=AuthorizationPolicy(
            rules=(allow_rule,),
            data_rules=(
                DataScopeRule(
                    operation="retry_records.*",
                    visible_fields=("value",),
                ),
            ),
        )
    )
    tool = _tool("retry_records", "retry records")
    attempts = 0

    async def invoker(endpoint: str, arguments: dict) -> dict:
        nonlocal attempts
        del endpoint, arguments
        attempts += 1
        if attempts == 1:
            router.executor.authorization_policy = AuthorizationPolicy(
                rules=(allow_rule,),
                data_rules=(
                    DataScopeRule(
                        operation="retry_records.*",
                        visible_fields=(),
                    ),
                ),
            )
            raise RuntimeError("transient failure")
        return {"value": "should-not-run"}

    router.add_bound_tool(tool, invoker)
    principal = PrincipalContext(subject="alice")
    plan = router.plan_authorized("retry records", principal=principal)

    with pytest.raises(PolicyViolationError, match="data scope"):
        await router.execute(
            plan,
            config=RunConfig(
                principal=principal,
                retry=RetryPolicy(max_attempts=2),
            ),
        )

    assert attempts == 1

