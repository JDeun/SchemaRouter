"""Pure AST source inventory for every package export, without installation.

This runs in the required fast contract job: changes in `__all__` or a new
tool-executing export cannot hide behind a slow full-suite or plugin import.
Local registered invoker execution is tested in the separate E2E job.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "benchmarks/public-execution-export-inventory-v1.json"
PACKAGE = ROOT / "src/schemarouter/__init__.py"
TOOL_EXECUTING_EXPORTS = frozenset({
    "ainvoke_selective",
    "execute_selective_plan",
    "observe_and_execute_paper_plan",
    "observe_and_execute_paper_understood_graph",
})


def _public_exports() -> list[str]:
    source = ast.parse(PACKAGE.read_text(encoding="utf-8"), filename=str(PACKAGE))
    declarations = [
        node for node in source.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        )
    ]
    assert len(declarations) == 1, "Public __all__ definition changed"
    exports = ast.literal_eval(declarations[0].value)
    assert isinstance(exports, list)
    assert all(isinstance(name, str) and name for name in exports)
    assert len(exports) == len(set(exports))
    return exports


def test_every_public_export_is_reviewed_on_the_fast_contract_path() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    exports = _public_exports()
    assert inventory["schema_version"] == 1
    assert inventory["evidence_tier"] == (
        "DEV_ONLY_LOCAL_REGISTERED_EXECUTION_NOT_INDEPENDENT_E2"
    )
    assert inventory["export_count"] == len(exports)
    assert inventory["exported_names"] == sorted(exports), (
        "Public API export added or removed without inventory review",
    )


def test_each_standalone_execution_export_has_distinct_real_test_references() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    rows = inventory["standalone_tool_execution_exports"]
    assert {row["name"] for row in rows} == TOOL_EXECUTING_EXPORTS
    assert TOOL_EXECUTING_EXPORTS <= set(_public_exports())
    for row in rows:
        source = ROOT / row["test_file"]
        assert source.is_file(), row["name"]
        parsed = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        functions = {
            node.name for node in parsed.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert row["positive"] in functions, row["name"]
        assert row["denied"] in functions, row["name"]
        assert row["positive"] != row["denied"], row["name"]
