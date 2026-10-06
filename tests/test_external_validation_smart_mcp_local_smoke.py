from __future__ import annotations

from pathlib import Path

from scripts.external_validation_smart_mcp import (
    load_package,
    score,
    validate_package,
)
from scripts.run_lexical_external_validation import run as run_lexical
from scripts.run_schemarouter_external_validation import run as run_schemarouter

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "benchmarks" / "external-validation-smart-mcp-dev-v1"


def test_local_cross_project_runners_cover_full_development_fixture() -> None:
    manifest, catalog, cases = load_package(PACKAGE)
    validate_package(manifest, catalog, cases)
    expected_ids = {case["id"] for case in cases["cases"]}

    for submitted in (
        run_lexical(package_dir=PACKAGE, repeats=1),
        run_schemarouter(package_dir=PACKAGE, repeats=1),
    ):
        assert {row["id"] for row in submitted["results"]} == expected_ids
        result = score(manifest, catalog, cases, submitted)
        summary = result["summary"]

        assert summary["supported_recall_at_1"] is not None
        assert summary["supported_recall_at_3"] is not None
        assert summary["supported_recall_at_5"] is not None
        assert summary["supported_full_coverage_at_5"] is not None
        assert summary["supported_mrr"] is not None
        assert summary["median_retrieval_ms"] is not None
        assert summary["p95_retrieval_ms"] is not None
        assert summary["mean_exposed_contract_bytes"] > 0
