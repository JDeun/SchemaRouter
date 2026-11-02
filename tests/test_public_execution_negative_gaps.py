"""Conservative #1821 public-execution negative gap ledger.

This guards complete adapter/wrapper enumeration and explicit NOT_TESTED owner
receipts. It is a source-level inventory, not runtime or independent E2 proof.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks"


def test_public_execution_negative_gaps_are_explicit_and_owned() -> None:
    report = json.loads(
        (BENCH / "public-execution-negative-gaps-v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["schema_version"] == 1
    assert report["scope"] == "conservative_execution_negative_gap_register"
    assert report["owner_issue"] == 1821
    assert report["product_qualified"] is False
    assert report["independent_e2_qualified"] is False

    canonical = json.loads(
        (BENCH / "public-execution-wiring-v1.json").read_text(encoding="utf-8")
    )
    native = json.loads(
        (BENCH / "public-source-family-wiring-v1.json").read_text(
            encoding="utf-8"
        )
    )
    stdio = json.loads(
        (BENCH / "public-execution-mcp-stdio-v1.json").read_text(
            encoding="utf-8"
        )
    )
    wrappers = json.loads(
        (BENCH / "public-execution-entrypoints-v1.json").read_text(
            encoding="utf-8"
        )
    )
    expected = (
        {row["id"] for row in canonical["paths"]}
        | {row["id"] for row in native["paths"]}
        | {stdio["route_id"]}
    )
    rows = report["paths"]
    ids = [row["id"] for row in rows]
    assert len(ids) == 19 and len(set(ids)) == len(ids)
    assert set(ids) == expected, "Every adapter/source/stdio entry must be dispositioned"
    assert report["wrapper_public_entrypoints"] == len(wrappers["paths"]) == 22

    for row in rows:
        assert row["public_entrypoint"].startswith("schemarouter.")
        assert row["evidence_limit"] == (
            "DEV_TEST_NAMES_AND_LOCAL_FIXTURES_NOT_INDEPENDENT_E2"
        )
        location = row["execution_location"]
        path = ROOT / location["file"]
        lines = path.read_text(encoding="utf-8").splitlines()
        assert isinstance(location["line"], int)
        assert 0 < location["line"] <= len(lines)
        assert "def " in lines[location["line"] - 1], row["id"]
        test_path = ROOT / row["observed_test_file"]
        assert test_path.is_file()
        tree = ast.parse(test_path.read_text(encoding="utf-8"))
        funcs = {
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert row["observed_test_names"]
        assert set(row["observed_test_names"]) <= funcs, row["id"]
        assert row["unresolved"], "Do not silently declare a complete adapter"
        for gap in row["unresolved"]:
            assert gap["status"] == "NOT_TESTED", row["id"]
            assert gap["owner_issue"] == 1821
            assert gap["scenario"] and gap["next_proof"]
            assert gap["baseline_command"] == (
                f'python -m pytest -q {row["observed_test_file"]}'
            )
