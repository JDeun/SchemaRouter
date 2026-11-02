"""Explicit OpenAPI/SQLAlchemy public adapter gap list; no false E2 promotion."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/public-execution-adapter-gaps-v1.json"


def test_public_openapi_sqlalchemy_gap_matrix_is_executable_and_versioned() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["qualification"] == "DEV_ONLY"
    assert (ROOT / data["prior_adapter_matrix"]).is_file()
    assert {item["id"] for item in data["paths"]} == {
        "router.openapi.get",
        "router.sqlalchemy.select",
    }
    for item in data["paths"]:
        assert item["public_entrypoint"] == "schemarouter.SchemaRouter.execute"
        source = ROOT / item["test_file"]
        functions = ast.parse(source.read_text(encoding="utf-8"))
        tests = {
            node.name
            for node in functions.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name.startswith("test_")
        }
        assert item["test"] in tests
        assert item["qualification"] == "DEV_ONLY"
        assert item["positive"] and item["denial"] and item["invalid_arguments"]
