"""Guard source-only decision contracts and prevent a second installed engine."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETIRED = {
    "CallableDecisionBackend",
    "DecisionBackend",
    "DecisionCallable",
    "DecisionOption",
    "DecisionOptionTextCallable",
    "DecisionRequest",
    "DecisionResult",
    "DecisionSelection",
    "ModelCallable",
    "ModelIntent",
    "ModelQueryAnalyzer",
    "EmbeddingCallable",
    "EmbeddingDecisionBackend",
    "FirstOptionDecisionBackend",
    "choose_async",
    "choose_sync",
}


def test_runtime_does_not_import_research_decision_contracts() -> None:
    for path in (ROOT / "src/schemarouter").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert module not in {"schemarouter.decisions", "decisions"}, path
                assert module not in {"schemarouter.analyzers", "analyzers"}, path
                assert not module.startswith("schemarouter.analyzers."), path
                assert not module.startswith("scripts.research_legacy_decisions"), path
                assert not module.startswith("scripts.research_legacy_model_analyzer"), path
                if module == "schemarouter":
                    assert RETIRED.isdisjoint(alias.name for alias in node.names), path
            elif isinstance(node, ast.Import):
                assert not any(
                    alias.name.startswith(("schemarouter.decisions", "schemarouter.analyzers",
                                           "scripts.research_legacy_decisions",
                                           "scripts.research_legacy_model_analyzer"))
                    for alias in node.names
                ), path


def test_checkout_consumers_use_archived_decision_contracts() -> None:
    for root in ("scripts", "tests", "examples"):
        for path in (ROOT / root).rglob("*.py"):
            if any(part in {".venv", "venv", "build", "dist"} for part in path.parts):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    assert node.module != "schemarouter.decisions", path
                    assert not (node.module or "").startswith("schemarouter.analyzers"), path
                    if node.module == "schemarouter":
                        assert RETIRED.isdisjoint(alias.name for alias in node.names), path
                elif isinstance(node, ast.Import):
                    assert all(
                        not alias.name.startswith((
                            "schemarouter.decisions", "schemarouter.analyzers",
                        ))
                        for alias in node.names
                    ), path
