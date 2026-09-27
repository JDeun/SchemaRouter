from __future__ import annotations

import importlib.util
from pathlib import Path

from schemarouter.models import ExecutionPlan, ToolCall

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "benchmark_decision_routing.py"


def _module():
    spec = importlib.util.spec_from_file_location("benchmark_decision_routing", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load decision-routing benchmark")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_authority_audit_accepts_planner_compiled_call() -> None:
    module = _module()
    registry = module.reference_registry()
    planner = module.SchemaPlanner(registry)

    plan = planner.plan(
        module.PlanRequest(
            query="current temperature in Seoul",
            preferred_tools=["weather"],
        )
    )

    assert plan.calls
    assert module._plan_authority_violations(planner, plan) == []


def test_authority_audit_detects_undeclared_arguments_fields_and_fingerprints() -> None:
    module = _module()
    registry = module.reference_registry()
    planner = module.SchemaPlanner(registry)
    tool = registry.get("weather")
    endpoint = tool.endpoint("current")

    plan = ExecutionPlan(
        query="bad authority surface",
        registry_version=registry.version,
        calls=[
            ToolCall(
                tool=tool.key,
                endpoint=endpoint.name,
                arguments={"undeclared_argument": "x"},
                fields=["undeclared_field"],
                schema_fingerprint="wrong-endpoint-fingerprint",
                tool_fingerprint="wrong-tool-fingerprint",
            )
        ],
    )

    violations = module._plan_authority_violations(planner, plan)

    assert any("undeclared arguments" in violation for violation in violations)
    assert any("undeclared fields" in violation for violation in violations)
    assert any("endpoint fingerprint mismatch" in violation for violation in violations)
    assert any("tool fingerprint mismatch" in violation for violation in violations)


def test_authority_audit_detects_unknown_route() -> None:
    module = _module()
    registry = module.reference_registry()
    planner = module.SchemaPlanner(registry)

    plan = ExecutionPlan(
        query="bad route",
        registry_version=registry.version,
        calls=[
            ToolCall(
                tool="missing-tool",
                endpoint="missing-endpoint",
                schema_fingerprint="missing",
            )
        ],
    )

    violations = module._plan_authority_violations(planner, plan)

    assert violations == ["calls[0]: unknown tool 'missing-tool'"]
