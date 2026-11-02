"""Separate MCP stdio public execution source contract from MCP HTTP."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/public-execution-mcp-stdio-v1.json"


def test_mcp_stdio_has_distinct_registered_positive_and_negative_evidence() -> None:
    row = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert row["schema_version"] == 1
    assert row["route_id"] == "router.mcp.stdio"
    assert row["public_registration"] == "SchemaRouter.add_mcp_stdio"
    assert row["public_execution"] == "SchemaRouter.execute"
    assert row["transport"] == "stdio"
    assert row["evidence_tier"] == (
        "DEV_ONLY_REGISTERED_SUBPROCESS_NOT_INDEPENDENT_E2"
    )
    assert (ROOT / row["invoker_module"]).is_file()
    assert (ROOT / row["source_fixture"]).is_file()

    test_file = ROOT / row["test_file"]
    source = test_file.read_text(encoding="utf-8")
    parsed = ast.parse(source)
    functions = {
        node.name: node for node in parsed.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert row["positive_test"] in functions
    assert row["negative_test"] in functions
    assert row["positive_test"] != row["negative_test"]
    negative = ast.get_source_segment(source, functions[row["negative_test"]]) or ""
    assert "router.add_mcp_stdio(" in negative
    assert "router.execute(" in negative
    assert "audited.read_text" in negative
    assert set(row["negative_cases"]) == {
        "denied_principal_zero_source_invocations",
        "invalid_type_zero_source_invocations",
        "missing_required_zero_source_invocations",
        "stale_unregistered_plan_zero_additional_invocations",
    }
