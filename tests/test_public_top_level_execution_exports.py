"""Public export surface and top-level tool execution entrypoint E2E guards.

This inventory includes every __all__ export. Four top-level callable functions
which can initiate native tool execution must retain positive and denied tests.
The local fixture is not an external provider/model E2 benchmark.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

import schemarouter
from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    PlanRequest,
    PolicyViolationError,
    PrincipalContext,
    RetrievalAbstentionPolicy,
    RunConfig,
    SchemaRouter,
    ainvoke_selective,
    execute_selective_plan,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/public-execution-export-inventory-v1.json"
EXECUTION_EXPORTS = {
    "ainvoke_selective",
    "execute_selective_plan",
    "observe_and_execute_paper_plan",
    "observe_and_execute_paper_understood_graph",
}


def _registered() -> tuple[SchemaRouter, list[int], PlanRequest, RunConfig, RunConfig]:
    dispatched: list[int] = []

    def lookup(user_id: int) -> dict[str, str]:
        dispatched.append(user_id)
        return {"user_id": str(user_id)}

    router = SchemaRouter(
        authorization_policy=AuthorizationPolicy(
            rules=(AuthorizationRule(
                effect="allow", operation="lookup.call", roles_any=("reader",),
            ),),
            default_effect="deny",
        ),
    )
    assert router.add_callable(lookup, read_only=True) == "lookup"
    request = PlanRequest(
        query="lookup user",
        preferred_tools=["lookup"],
        arguments={"user_id": 7},
    )
    allowed = RunConfig(
        principal=PrincipalContext(subject="allow", roles=("reader",)),
    )
    denied = RunConfig(
        principal=PrincipalContext(subject="deny", roles=("guest",)),
    )
    return router, dispatched, request, allowed, denied


def _policy() -> RetrievalAbstentionPolicy:
    # Explicit developer-only score floor, NOT learned no-fit calibration.
    return RetrievalAbstentionPolicy(min_score=-1e8)


def _assert_result(items: list) -> None:
    assert len(items) == 1
    assert items[0].data == {"user_id": "7"}


@pytest.mark.asyncio
async def test_exported_selective_ainvoke_uses_registered_invoker() -> None:
    router, called, request, allowed, _ = _registered()
    output = await ainvoke_selective(
        router, request, policy=_policy(), config=allowed,
    )
    _assert_result(output)
    assert called == [7]


@pytest.mark.asyncio
async def test_exported_selective_ainvoke_denies_untrusted_principal() -> None:
    router, called, request, _, denied = _registered()
    with pytest.raises(PolicyViolationError):
        await ainvoke_selective(
            router, request, policy=_policy(), config=denied,
        )
    assert called == [], "Denied principal may not dispatch a registered callable"


@pytest.mark.asyncio
async def test_exported_selective_plan_executes_registered_invoker() -> None:
    router, called, request, allowed, _ = _registered()
    selection = await router.aretrieve_executable_authorized(
        request, principal=allowed.principal, k=5,
    )
    plan = await router.aplan_executable_authorized(
        request, principal=allowed.principal,
    )
    assert selection.candidates and plan.calls
    result = await execute_selective_plan(
        router, selection, plan, policy=_policy(), config=allowed,
    )
    _assert_result(result)
    assert called == [7]


@pytest.mark.asyncio
async def test_exported_selective_plan_denies_revoked_policy() -> None:
    router, called, request, allowed, _ = _registered()
    selection = await router.aretrieve_executable_authorized(
        request, principal=allowed.principal, k=5,
    )
    plan = await router.aplan_executable_authorized(
        request, principal=allowed.principal,
    )
    assert selection.candidates and plan.calls
    router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    with pytest.raises(PolicyViolationError):
        await execute_selective_plan(
            router, selection, plan, policy=_policy(), config=allowed,
        )
    assert called == [], "Revoked authority must not reach the bound native invoker"


def _declared_exports() -> list[str]:
    init = ast.parse(
        (ROOT / "src/schemarouter/__init__.py").read_text(encoding="utf-8"),
    )
    assignments = [
        node for node in init.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        )
    ]
    assert len(assignments) == 1, "Missing or ambiguous public __all__ inventory"
    names = ast.literal_eval(assignments[0].value)
    assert isinstance(names, list)
    assert all(isinstance(x, str) and x for x in names)
    assert len(names) == len(set(names)), "Duplicate exports conceal a mapping gap"
    return names


def test_all_public_exports_match_reviewed_inventory() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["evidence_tier"] == "DEV_ONLY_LOCAL_REGISTERED_EXECUTION_NOT_INDEPENDENT_E2"
    exported = _declared_exports()
    assert sorted(exported) == data["exported_names"], (
        "Public export surface changed: update and classify exported entrypoints",
    )
    assert data["export_count"] == len(exported)
    assert all(hasattr(schemarouter, name) for name in exported)


def test_every_standalone_executing_export_has_runnable_positive_and_denied_tests() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = data["standalone_tool_execution_exports"]
    assert {x["name"] for x in rows} == EXECUTION_EXPORTS
    for row in rows:
        assert callable(getattr(schemarouter, row["name"]))
        tests = ROOT / row["test_file"]
        assert tests.is_file()
        code = tests.read_text(encoding="utf-8")
        parsed = ast.parse(code)
        functions = {
            n.name for n in parsed.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert row["positive"] in functions, row["name"]
        assert row["denied"] in functions, row["name"]
        assert row["positive"] != row["denied"]
        assert row["name"] in code, "Cited evidence never references its export"
