"""Fail-closed contract for explicitly registered public execution wiring paths.

This checks declared source/test connections, not independent E2 qualification.
"""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/public-execution-wiring-v1.json"


def _functions(path: Path) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result[node.name] = node
    return result


def test_public_execution_wiring_manifest_is_source_and_test_attested():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["scope"] == "verified_public_execution_paths_only"
    paths = data["paths"]
    assert paths, "Do not silently drop all execution paths"
    assert len({row["id"] for row in paths}) == len(paths)

    for row in paths:
        assert row["qualification"] in {"DEV_ONLY", "NOT_VERIFIED", "QUALIFIED"}
        module, owner, method = row["public_entrypoint"].rsplit(".", 2)
        assert module == "schemarouter"
        source = ROOT / row["implementation"]
        assert source.is_file()
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
        target = next(cls for cls in classes if cls.name == owner)
        assert any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == method
            for node in target.body
        ), row["id"]

        for key in ("registry", "authorization", "planning", "executor", "invoker"):
            assert (ROOT / row[key]).is_file(), (row["id"], key)
        tests = ROOT / row["test_file"]
        assert tests.is_file()
        funcs = _functions(tests)
        for name in row["real_invoker_tests"] + row["denial_tests"]:
            assert name.startswith("test_") and name in funcs, (row["id"], name)
        assert row["real_invoker_tests"] and row["denial_tests"]
        for name in row["real_invoker_tests"]:
            fn = funcs[name]
            body = ast.get_source_segment(tests.read_text(encoding="utf-8"), fn) or ""
            assert "monkeypatch" not in body
            assert method + "(" in body
            if row["id"] == "paper.direct.native.read":
                assert "_fixture(" in body
            assert "assert " in body


# These are the adapter families already attested in the initial manifest.
# Pinning the complete set prevents a deleted row from escaping validation:
# the generic source/test checks above only iterate rows that still exist.
REQUIRED_EXECUTION_PATHS = frozenset({
    "paper.direct.native.read",
    "router.python.callable.sync",
    "router.sqlite.select",
    "router.http_json.get",
    "router.graphql.query",
    "router.openrpc.method",
    "router.odata.select",
    "router.mcp.http",
    "router.graph.neo4j",
    "router.record.mongodb",
    "router.vector.qdrant",
})


def test_verified_execution_adapter_families_cannot_silently_disappear():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    paths = {row["id"]: row for row in data["paths"]}
    missing = REQUIRED_EXECUTION_PATHS - paths.keys()
    assert not missing, f"Missing previously attested execution paths: {sorted(missing)}"
    # Preserve the actual status: a local invoker test is not independent E2.
    for path_id in REQUIRED_EXECUTION_PATHS:
        assert paths[path_id]["qualification"] == "DEV_ONLY", path_id
