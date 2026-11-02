"""Fail-closed inventory of every public method declared on the three owner APIs.

Execution wrappers are distinct from retrieval/planning and registration.
The actual dispatcher evidence is tracked in separately executed tests.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import schemarouter

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/public-method-boundary-v1.json"
EXECUTION_NAMES = frozenset({
    "execute", "invoke", "ainvoke", "run", "arun",
    "batch", "abatch", "batch_as_completed", "abatch_as_completed",
    "stream", "astream", "astream_events", "aexecute_direct",
})
KINDS = {
    "registered-tool-execution",
    "retrieval-or-planning-no-execution",
    "registration-inspection-or-lifecycle",
}


def _actual_methods(owner: str, path: Path) -> dict[str, int]:
    parsed = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    body = [x for x in parsed.body if isinstance(x, ast.ClassDef) and x.name == owner]
    assert len(body) == 1, "Public owner class changed without inventory review"
    methods = {
        x.name: x.lineno
        for x in body[0].body
        if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not x.name.startswith("_")
    }
    return methods


def test_owner_methods_are_all_classified_and_synchronized() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["qualification"] == (
        "DEV_ONLY_STATIC_METHOD_SURFACE_AND_SEPARATE_REAL_EXECUTOR_TESTS"
    )
    assert {row["owner"] for row in data["owners"]} == {
        "SchemaRouter", "ConfiguredSchemaRouter", "SchemaFieldRoutingSession",
    }
    for row in data["owners"]:
        assert row["owner"] in schemarouter.__all__
        owner = getattr(schemarouter, row["owner"])
        assert isinstance(owner, type)
        source = ROOT / row["source"]
        actual = _actual_methods(row["owner"], source)
        declared = row["methods"]
        names = [item["name"] for item in declared]
        assert len(names) == len(set(names))
        assert set(names) == set(actual), (
            row["owner"], "Public method added without scope classification",
        )
        for entry in declared:
            name = entry["name"]
            assert entry["kind"] in KINDS
            assert entry["source_line"] >= 1
            assert hasattr(owner, name)
            assert (
                entry["kind"] == "registered-tool-execution"
            ) == (name in EXECUTION_NAMES), (row["owner"], name)


def test_retrieval_and_planning_are_not_mislabeled_as_invocation() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    names_by_owner = {
        row["owner"]: {
            item["name"]: item["kind"] for item in row["methods"]
        }
        for row in data["owners"]
    }
    assert names_by_owner["SchemaRouter"]["retrieve"] == (
        "retrieval-or-planning-no-execution"
    )
    assert names_by_owner["SchemaRouter"]["plan"] == (
        "retrieval-or-planning-no-execution"
    )
    assert names_by_owner["SchemaFieldRoutingSession"]["discover"] == (
        "retrieval-or-planning-no-execution"
    )
    assert names_by_owner["SchemaFieldRoutingSession"]["aexecute_direct"] == (
        "registered-tool-execution"
    )
