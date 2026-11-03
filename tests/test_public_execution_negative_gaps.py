"""Source-verified #1821 negative ledger with immutable scenario inventory.

Registered public DEV proofs are pinned to the exact merged source commit
and passing GitHub CI. This validation is not independent provider E2.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks"

# Frozen original #1856 inventory: no scenario can disappear during evidence
# reconciliation. New scenarios require explicit updates here and in the ledger.
ORIGINAL_SCENARIOS = {
  "paper.direct.native.read": [
    "stale_bound_invoker_generation"
  ],
  "router.python.callable.sync": [
    "temporarily_unavailable_source",
    "stale_bound_invoker_generation",
    "write_effect_policy"
  ],
  "router.python.callable.async": [
    "temporarily_unavailable_source",
    "stale_bound_invoker_generation",
    "write_effect_policy"
  ],
  "router.sqlite.select": [
    "temporarily_unavailable_source",
    "stale_bound_invoker_generation"
  ],
  "router.http_json.get": [
    "temporarily_unavailable_source",
    "stale_bound_invoker_generation"
  ],
  "router.graphql.query": [
    "temporarily_unavailable_source",
    "stale_bound_invoker_generation",
    "denied_principal"
  ],
  "router.openrpc.method": [
    "temporarily_unavailable_source"
  ],
  "router.odata.select": [
    "temporarily_unavailable_source",
    "unrecognized_input"
  ],
  "router.mcp.http": [
    "temporarily_unavailable_source",
    "stale_bound_invoker_generation"
  ],
  "router.graph.neo4j": [
    "temporarily_unavailable_source",
    "stale_bound_invoker_generation"
  ],
  "router.record.mongodb": [
    "temporarily_unavailable_source",
    "stale_bound_invoker_generation"
  ],
  "router.vector.qdrant": [
    "temporarily_unavailable_source",
    "stale_bound_invoker_generation"
  ],
  "router.openapi.get": [
    "temporarily_unavailable_source",
    "stale_bound_invoker_generation"
  ],
  "router.sqlalchemy.select": [
    "temporarily_unavailable_source"
  ],
  "router.optimade.source": [
    "temporarily_unavailable_source"
  ],
  "router.graph_store.generic": [],
  "router.vector_store.generic": [],
  "router.record_store.generic": [],
  "router.mcp.stdio": [
    "temporarily_unavailable_source"
  ]
}
PROOF_COMMIT = "0d59d2753e4a00ebffbd76d44d89cb0dbee7e56e"
PROOF_CI_RUN = "https://github.com/JDeun/SchemaRouter/actions/runs/41547954823"


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

    verified_total = 0
    unresolved_total = 0
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
        verified = row["verified"]
        unresolved = row["unresolved"]
        original = ORIGINAL_SCENARIOS[row["id"]]
        scenarios = [entry["scenario"] for entry in verified + unresolved]
        assert len(scenarios) == len(set(scenarios)), row["id"]
        assert set(scenarios) == set(original), (
            row["id"], "Never silently drop or invent historical scenarios"
        )
        assert verified or unresolved or row.get("not_applicable"), (
            row["id"], "A route must retain its explicit scenario disposition"
        )
        verified_total += len(verified)
        unresolved_total += len(unresolved)
        for proof in verified:
            assert proof["status"] == "DEV_VERIFIED", row["id"]
            assert proof["owner_issue"] == 1821
            assert proof["evidence_tier"] == (
                "DEV_REGISTERED_PUBLIC_NO_INDEPENDENT_E2"
            )
            assert proof["proof_commit"] == PROOF_COMMIT
            assert proof["ci_run_url"] == PROOF_CI_RUN
            assert proof["proof_file"].startswith("tests/")
            source_path = ROOT / proof["proof_file"]
            source = source_path.read_text(encoding="utf-8")
            test_tree = ast.parse(source)
            definitions = {
                node.name: node for node in test_tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            function = definitions.get(proof["proof_function"])
            assert function is not None, (row["id"], proof["proof_function"])
            assert proof["proof_function"].startswith("test_")
            test_source = ast.get_source_segment(source, function) or ""
            assert "assert " in test_source, row["id"]
            assert any(marker in test_source for marker in (
                "router.execute(", "session.aexecute_direct(",
                "router.ainvoke(", "router.invoke(", "_invoke(",
            )), (row["id"], proof["proof_function"])
            if "proof_parameter" in proof:
                assert proof["proof_parameter"] in source, row["id"]
        for excluded in row.get("not_applicable", []):
            assert row["id"] in {
                "router.graph_store.generic",
                "router.vector_store.generic",
                "router.record_store.generic",
            }
            assert excluded["scenario"] == "write_effect_policy"
            assert excluded["status"] == "NOT_APPLICABLE"
            assert excluded["owner_issue"] == 1821
            assert "read_only=True" in excluded["reason"]
            assert "destructive=False" in excluded["reason"]
            assert excluded["proof_file"] == (
                "tests/test_public_generic_store_execution_negative.py"
            )
            assert excluded["proof_function"] == "_registered"
            proof = (ROOT / excluded["proof_file"]).read_text(
                encoding="utf-8"
            )
            assert (
                "all(x.read_only is True and x.destructive is False for x in tool.endpoints)"
                in proof
            )
        for gap in row["unresolved"]:
            assert gap["status"] == "NOT_TESTED", row["id"]
            assert gap["owner_issue"] == 1821
            assert gap["scenario"] and gap["next_proof"]
            assert gap["baseline_command"] == (
                f'python -m pytest -q {row["observed_test_file"]}'
            )

    assert verified_total + unresolved_total == 30
    assert verified_total == 20
    assert unresolved_total == 10
