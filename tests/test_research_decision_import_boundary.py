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
    "QueryIntent",
    "RetrievalMode",
    "FallbackScope",
    "ScoreComponent",
    "PlanExplanation",
    "FieldSelectionExplanation",
    "CandidateSelectionSource",
    "FieldSelectionReason",
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
    "dependency_cycles",
    "dependency_strongly_connected_components",
    "satisfiable_capability_ids",
    "ResolvedNativeConcepts",
    "resolve_native_concepts",
    "NativeConceptGraphSelection",
    "NativeConceptRouteSet",
    "retrieve_authorized_concept_graph",
    "PaperFieldAlternative",
    "PaperFieldCoverage",
    "retrieve_paper_field_coverage",
    "compile_paper_typed_tool_plan",
    "NativeObservedArgumentEvidence",
    "materialize_native_observed_arguments",
    "PaperUnderstoodExecutedGraph",
    "observe_and_execute_paper_understood_graph",
}


def test_runtime_does_not_import_research_decision_contracts() -> None:
    for path in (ROOT / "src/schemarouter").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.arg):
                assert node.arg not in {
                    "_research_ranker", "model_visible_concept_ids", "_paper_rank_aliases",
                    "_fork_arm_internal", "_fork_root_filter", "_fork_target_filter",
                }, path
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert module not in {"schemarouter.decisions", "decisions"}, path
                assert module not in {"schemarouter.analyzers", "analyzers"}, path
                assert not module.startswith("schemarouter.analyzers."), path
                assert not module.startswith("scripts.research_legacy_decisions"), path
                assert not module.startswith("scripts.research_legacy_model_analyzer"), path
                assert not module.startswith("scripts.research_legacy_g5_execution"), path
                assert not module.startswith("scripts.research_legacy_g5_deep_paths"), path
                assert not module.startswith("scripts.research_legacy_capability_graph_analysis"), path
                assert not module.startswith("scripts.research_legacy_posting_rank"), path
                assert not module.startswith("scripts.research_legacy_field_session"), path
                assert not module.startswith("scripts.research_legacy_offered_query"), path
                assert not module.startswith("scripts.research_legacy_paper_field_retrieval"), path
                assert not module.startswith("scripts.research_legacy_paper_typed_plan"), path
                assert not module.startswith("scripts.research_legacy_native_fork"), path
                assert not module.startswith("scripts.research_legacy_fork_arm"), path
                assert not module.startswith("scripts.research_legacy_concept_retrieval"), path
                assert not module.startswith("scripts.research_legacy_indexed_concept_graph"), path
                assert not module.startswith("scripts.research_legacy_concept_graph"), path
                assert not module.startswith("scripts.research_legacy_paper_observed_binding"), path
                assert not module.startswith("scripts.research_legacy_paper_consumer_execution"), path
                assert not module.startswith("scripts.research_legacy_paper_graph_execution"), path
                assert not module.startswith("scripts.research_legacy_paper_graph_plan"), path
                assert not module.startswith("scripts.research_legacy_graph_rank"), path
                assert not module.startswith("scripts.research_legacy_graph_observation"), path
                assert not module.startswith("scripts.research_legacy_direct_rank"), path
                assert not module.startswith("scripts.research_legacy_direct_plan"), path
                assert not module.startswith("scripts.research_legacy_g5_rank"), path
                assert module not in {
                    "planner", "planning_context", "planning_stages", "state_retrieval",
                    "schemarouter.state_retrieval",
                    "retrieval_abstention", "retrieval_execution_gate",
                    "schemarouter.retrieval_abstention", "schemarouter.retrieval_execution_gate",
                    "native_graph_execution", "schemarouter.native_graph_execution",
                    "native_graph_observation", "schemarouter.native_graph_observation",
                    "native_deep_paths", "schemarouter.native_deep_paths",
                    "paper_observed_binding", "schemarouter.paper_observed_binding",
                    "paper_consumer_execution", "schemarouter.paper_consumer_execution",
                    "paper_understood_graph_plan", "schemarouter.paper_understood_graph_plan",
                    "paper_field_retrieval", "schemarouter.paper_field_retrieval",
                    "native_fork_index", "schemarouter.native_fork_index",
                    "concept_graph_retrieval", "schemarouter.concept_graph_retrieval",
                }, path
                assert not module.startswith("schemarouter.planner"), path
                assert not module.startswith("scripts.research_legacy_planning"), path
                if module in {"schemarouter", "schemarouter.models", "models",
                              "paper_typed_tool_plan", "schemarouter.paper_typed_tool_plan",
                              "concept_retrieval", "schemarouter.concept_retrieval",
                              "schemarouter.capability_graph", "capability_graph"}:
                    assert RETIRED.isdisjoint(alias.name for alias in node.names), path
            elif isinstance(node, ast.Import):
                assert not any(
                    alias.name.startswith(("schemarouter.decisions", "schemarouter.analyzers",
                                           "scripts.research_legacy_decisions",
                                           "scripts.research_legacy_model_analyzer",
                                           "scripts.research_legacy_g5_execution",
                                           "scripts.research_legacy_g5_deep_paths",
                                           "scripts.research_legacy_capability_graph_analysis",
                                           "scripts.research_legacy_posting_rank",
                                           "scripts.research_legacy_field_session",
                                           "scripts.research_legacy_offered_query",
                                           "scripts.research_legacy_paper_field_retrieval",
                                           "scripts.research_legacy_paper_typed_plan",
                                           "scripts.research_legacy_native_fork",
                                           "scripts.research_legacy_fork_arm",
                                           "scripts.research_legacy_concept_retrieval",
                                           "scripts.research_legacy_indexed_concept_graph",
                                           "scripts.research_legacy_concept_graph",
                                           "scripts.research_legacy_paper_observed_binding",
                                           "scripts.research_legacy_paper_consumer_execution",
                                           "scripts.research_legacy_paper_graph_execution",
                                           "scripts.research_legacy_paper_graph_plan",
                                           "scripts.research_legacy_graph_rank",
                                           "scripts.research_legacy_graph_observation",
                                           "schemarouter.native_graph_observation",
                                           "scripts.research_legacy_direct_rank",
                                           "scripts.research_legacy_direct_plan",
                                           "schemarouter.paper_understood_graph_plan",
                                           "schemarouter.paper_consumer_execution",
                                           "schemarouter.paper_observed_binding",
                                           "schemarouter.paper_field_retrieval",
                                           "schemarouter.native_fork_index",
                                           "schemarouter.concept_graph_retrieval",
                                           "scripts.research_legacy_g5_rank",
                                           "schemarouter.native_deep_paths",
                                           "schemarouter.native_graph_execution",
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
                        "schemarouter.native_graph_execution",
                        "schemarouter.native_graph_observation",
                        "schemarouter.native_deep_paths",
                        "schemarouter.paper_observed_binding",
                        "schemarouter.paper_consumer_execution",
                        "schemarouter.paper_understood_graph_plan",
                        "schemarouter.paper_field_retrieval",
                        "schemarouter.native_fork_index",
                        "schemarouter.concept_graph_retrieval",
                    }, path
                    assert not (node.module or "").startswith("schemarouter.analyzers"), path
                    if node.module in {"schemarouter", "schemarouter.models",
                                       "schemarouter.paper_typed_tool_plan",
                                       "schemarouter.concept_retrieval",
                                       "schemarouter.capability_graph"}:
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
                            "schemarouter.native_graph_execution",
                            "schemarouter.native_graph_observation",
                            "schemarouter.native_deep_paths",
                            "schemarouter.paper_observed_binding",
                            "schemarouter.paper_consumer_execution",
                            "schemarouter.paper_understood_graph_plan",
                            "schemarouter.paper_field_retrieval",
                            "schemarouter.native_fork_index",
                            "schemarouter.concept_graph_retrieval",
                        ))
                        for alias in node.names
                    ), path


def test_native_graph_observation_is_checkout_only() -> None:
    assert not (ROOT / "src/schemarouter/native_graph_observation.py").exists()
    assert (ROOT / "scripts/research_legacy_graph_observation.py").is_file()
