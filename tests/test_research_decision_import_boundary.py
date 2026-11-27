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
    "KeywordAnalyzer",
    "QueryAnalyzer",
    "SchemaPlanner",
    "PlanRequest",
    "CapabilityCandidate",
    "CapabilityRetrieval",
    "CapabilityRouteCandidate",
    "CapabilityRouteRetrieval",
    "StateAwareCapabilityCandidate",
    "StateAwareCapabilityRetrieval",
    "evaluate_candidate_state",
    "filter_retrieval_by_state",
    "ainvoke_selective",
    "RetrievalAbstentionPolicy",
    "SelectiveCapabilityRetrieval",
    "apply_retrieval_abstention",
    "validate_selective_execution",
    "execute_selective_plan",
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
                assert module not in {
                    "planner", "planning_context", "planning_stages", "state_retrieval",
                    "schemarouter.state_retrieval",
                    "retrieval_abstention", "retrieval_execution_gate",
                    "schemarouter.retrieval_abstention", "schemarouter.retrieval_execution_gate",
                }, path
                assert not module.startswith("schemarouter.planner"), path
                assert not module.startswith("scripts.research_legacy_planning"), path
                if module in {"schemarouter", "schemarouter.models", "models"}:
                    assert RETIRED.isdisjoint(alias.name for alias in node.names), path
            elif isinstance(node, ast.Import):
                assert not any(
                    alias.name.startswith(("schemarouter.decisions", "schemarouter.analyzers",
                                           "scripts.research_legacy_decisions",
                                           "scripts.research_legacy_model_analyzer",
                                           "scripts.research_legacy_planning",
                                           "schemarouter.planner",
                                           "schemarouter.planning_context",
                                           "schemarouter.planning_stages",
                                           "schemarouter.state_retrieval",
                                           "schemarouter.retrieval_abstention",
                                           "schemarouter.retrieval_execution_gate"))
                    for alias in node.names
                ), path


def test_checkout_consumers_use_archived_decision_contracts() -> None:
    for root in ("scripts", "tests", "examples"):
        for path in (ROOT / root).rglob("*.py"):
            if any(part in {".venv", "venv", "build", "dist"} for part in path.parts):
                continue
            if path in {
                ROOT / "scripts/verify_v018_installed_wheel_alias_regression.py",
                ROOT / "scripts/published_pypi_smoke.py",
            }:
                # These exercise actual historical installed releases, not current source.
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    assert node.module != "schemarouter.decisions", path
                    assert node.module not in {
                        "schemarouter.planner", "schemarouter.planning_context",
                        "schemarouter.planning_stages",
                        "schemarouter.state_retrieval",
                        "schemarouter.retrieval_abstention",
                        "schemarouter.retrieval_execution_gate",
                    }, path
                    assert not (node.module or "").startswith("schemarouter.analyzers"), path
                    if node.module in {"schemarouter", "schemarouter.models"}:
                        assert RETIRED.isdisjoint(alias.name for alias in node.names), path
                elif isinstance(node, ast.Import):
                    assert all(
                        not alias.name.startswith((
                            "schemarouter.decisions", "schemarouter.analyzers",
                            "schemarouter.planner", "schemarouter.planning_context",
                            "schemarouter.planning_stages",
                            "schemarouter.state_retrieval",
                            "schemarouter.retrieval_abstention",
                            "schemarouter.retrieval_execution_gate",
                        ))
                        for alias in node.names
                    ), path
