# ruff: noqa: I001
from json import loads
from pathlib import Path

from schemarouter import SchemaRouter


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "tests" / "fixtures" / "product_path_matrix.json"
README_PATH = ROOT / "README.md"
INGRESS_DOC_PATH = ROOT / "docs" / "guides" / "universal-ingestion.md"
REQUIRED_EXECUTION_STAGES = {
    "register",
    "bind",
    "retrieve",
    "plan",
    "execute",
    "project",
    "inspect",
}


def _matrix() -> list[dict]:
    return loads(MATRIX_PATH.read_text(encoding="utf-8"))


def test_documented_ingress_surfaces_have_machine_checked_product_paths() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    ingress_docs = INGRESS_DOC_PATH.read_text(encoding="utf-8")
    rows = _matrix()
    assert rows
    assert "docs/guides/universal-ingestion.md" in readme

    for row in rows:
        assert row["source"] in ingress_docs
        entrypoint = getattr(SchemaRouter, row["entrypoint"], None)
        assert callable(entrypoint), row
        assert (ROOT / row["test_file"]).is_file(), row

        stages = set(row["stages"])
        if row["source"] != "Custom protocol":
            assert REQUIRED_EXECUTION_STAGES <= stages, row


def test_refreshable_ingress_paths_declare_refresh_and_rebind_coverage() -> None:
    refreshable = {
        "OpenAPI",
        "MCP Streamable HTTP",
        "MCP stdio",
        "MCP custom transport",
        "OPTIMADE",
        "GraphQL",
        "OData",
        "OpenRPC",
    }
    by_source = {row["source"]: row for row in _matrix()}
    assert refreshable <= by_source.keys()
    for source in refreshable:
        stages = set(by_source[source]["stages"])
        assert {"refresh", "rebind"} <= stages, source
