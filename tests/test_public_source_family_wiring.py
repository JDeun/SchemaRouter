"""Source-backed public store families that were absent from the initial 14 paths.

Positive and negative tests referenced here are executed by the dedicated CI.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/public-source-family-wiring-v1.json"


def test_public_source_families_have_registered_executable_test_evidence() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["qualification"] == "DEV_ONLY_REGISTERED_SOURCE_NOT_INDEPENDENT_E2"
    assert data["public_entrypoint"] == "schemarouter.SchemaRouter.execute"
    paths = data["paths"]
    assert {row["id"] for row in paths} == {
        "router.optimade.source",
        "router.graph_store.generic",
        "router.vector_store.generic",
        "router.record_store.generic",
    }
    for row in paths:
        assert (ROOT / row["adapter"]).is_file()
        source = ROOT / row["test_file"]
        assert source.is_file()
        code = source.read_text(encoding="utf-8")
        parsed = ast.parse(code)
        functions = {
            node.name: node for node in parsed.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for key in ("positive", "negative"):
            name = row[key]
            assert name in functions, (row["id"], name)
            body = ast.get_source_segment(code, functions[name]) or ""
            assert "router.execute(" in body, (row["id"], name)
        assert row["negative_categories"]
        assert row["evidence"] in {
            "registered-fake-backend",
            "mocktransport-discovered-native-registered",
        }
