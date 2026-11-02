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
        if row["id"] != "router.optimade.source":
            runtime = row["public_runtime_negative"]
            assert runtime["qualification"] == "DEV_ONLY"
            assert runtime["evidence"] == (
                "registered-original-invoker-fake-vendor-not-executor-mock"
            )
            assert runtime["scenario_kind"] in {"graph", "vector", "record"}
            assert runtime["test_file"] == (
                "tests/test_public_generic_store_execution_negative.py"
            )
            negative_file = ROOT / runtime["test_file"]
            negative_code = negative_file.read_text(encoding="utf-8")
            negative_tree = ast.parse(negative_code)
            negative_functions = {
                n.name: n for n in negative_tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            assert set(runtime["test_names"]) == {
                "test_registered_generic_store_fail_closed_and_recovers",
                "test_registered_generic_store_revoked_policy_never_calls_backend",
            }
            for name in runtime["test_names"]:
                fn = negative_functions[name]
                body = ast.get_source_segment(negative_code, fn) or ""
                assert "router.execute(" in body
                assert "assert calls == []" in body
                assert "pytest.mark.parametrize" in negative_code
                assert all(f'"{kind}"' in negative_code for kind in ("graph", "vector", "record"))
            first = negative_functions[runtime["test_names"][0]]
            first_body = ast.get_source_segment(negative_code, first) or ""
            assert "mark_access_unavailable(" in first_body
            assert "mark_access_available(" in first_body
            assert "router.aremove_tool(" in first_body
            assert "len(calls) == 1" in first_body
            assert set(runtime["checked"]) == {
                "denied_principal_zero_backend_calls",
                "undeclared_input_zero_backend_calls",
                "unavailable_source_zero_backend_calls",
                "availability_recovery_exactly_one_backend_call",
                "removed_tool_stale_plan_zero_additional_calls",
                "revoked_authority_zero_backend_calls",
            }
        assert row["evidence"] in {
            "registered-fake-backend",
            "mocktransport-discovered-native-registered",
        }
