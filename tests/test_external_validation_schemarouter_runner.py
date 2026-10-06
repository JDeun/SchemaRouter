from __future__ import annotations

from pathlib import Path

from scripts.external_validation_smart_mcp import load_package
from scripts.run_schemarouter_external_validation import build_router

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "benchmarks" / "external-validation-smart-mcp-dev-v1"


def test_schemarouter_external_runner_uses_public_retrieval_surface() -> None:
    _, catalog, _ = load_package(PACKAGE)
    router = build_router(catalog)

    retrieval = router.retrieve(
        "Cancel running computation job JOB-5.",
        k=5,
    )
    names = [candidate.tool for candidate in retrieval.candidates]

    assert "jobs__cancel" in names
    assert len(names) <= 5
    assert all(candidate.input_schema for candidate in retrieval.candidates)
