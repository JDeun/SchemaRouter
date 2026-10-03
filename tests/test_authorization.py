from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    EndpointSpec,
    FieldSpec,
    PlanRequest,
    PolicyViolationError,
    PrincipalContext,
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

    employee_view = router.retrieve(
        "board financial forecast",
        principal=employee,
        k=5,
    )
    executive_view = router.retrieve(
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

    plan = router.plan(
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


def test_no_authorization_policy_preserves_existing_no_principal_behavior() -> None:
    router = SchemaRouter()
    tool = _tool("public", "public information")
    router.add_bound_tool(tool, lambda endpoint, arguments: {"value": "ok"})

    retrieval = router.retrieve("public information")
    assert retrieval.candidates
    assert retrieval.candidates[0].tool == "public"
