"""Detect unmapped public execution wrappers across three documented owners.

This is an AST inventory safeguard. Actual positive/denied dispatch is tested
by test_public_execution_wrappers.py or the indicated existing adapter tests.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/public-execution-entrypoints-v1.json"
SOURCES = {
    "SchemaRouter": ROOT / "src/schemarouter/runtime.py",
    "ConfiguredSchemaRouter": ROOT / "src/schemarouter/runtime.py",
    "SchemaFieldRoutingSession": ROOT / "src/schemarouter/field_routing_session.py",
}
EXECUTION_METHODS = frozenset({
    "execute",
    "invoke",
    "ainvoke",
    "run",
    "arun",
    "batch",
    "abatch",
    "batch_as_completed",
    "abatch_as_completed",
    "stream",
    "astream",
    "astream_events",
    "aexecute_direct",
})


def _declared_methods(owner: str, source: Path) -> set[str]:
    parsed = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    cls = next(
        node for node in parsed.body
        if isinstance(node, ast.ClassDef) and node.name == owner
    )
    return {
        node.name
        for node in cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in EXECUTION_METHODS
    }


def _test_functions(path: Path):
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name: node for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_declared_public_execution_entrypoints_cannot_go_unmapped() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["evidence_tier"] == "DEV_ONLY_LOCAL_REGISTERED_INVOKER_NOT_INDEPENDENT_E2"
    assert (ROOT / data["reference_adapter_matrix"]).is_file()

    declared = {
        f"schemarouter.{owner}.{method}"
        for owner, source in SOURCES.items()
        for method in _declared_methods(owner, source)
    }
    paths = data["paths"]
    mapped = {row["public_entrypoint"] for row in paths}
    assert len(mapped) == len(paths), "Duplicate entrypoints hide evidence omissions"
    assert mapped == declared, {
        "unmapped": sorted(declared - mapped),
        "stale": sorted(mapped - declared),
    }

    for row in paths:
        assert row["qualification"] == "DEV_ONLY"
        tests = ROOT / row["test_file"]
        assert tests.is_file()
        functions = _test_functions(tests)
        name = row["test_name"]
        assert name in functions, (row["public_entrypoint"], name)
        if "case" in row:
            assert row["test_file"] == "tests/test_public_execution_wrappers.py"
            # The wrapper test's parameter list is a literal, reviewed finite set:
            case = row["case"]
            assert isinstance(case, str) and case in EXECUTION_METHODS
            fn = functions[name]
            literal_cases = {
                node.value
                for decorator in fn.decorator_list
                if isinstance(decorator, ast.Call)
                for node in ast.walk(decorator)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
            }
            assert case in literal_cases, (name, case)
            assert "auth_at_dispatch" in name
