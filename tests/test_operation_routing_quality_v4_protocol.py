from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CYCLE = ROOT / "benchmarks" / "operation-fit-0.11-quality-v4-cycle.json"
BENCHMARK = ROOT / "scripts" / "benchmark_decision_routing.py"
PAIRWISE_TOOL_ABLATION = (
    ROOT / "benchmarks" / "operation-routing-v4-hierarchical-pairwise-tool-ablation.json"
)


def _benchmark_module():
    spec = importlib.util.spec_from_file_location(
        "benchmark_decision_routing_v4_protocol",
        BENCHMARK,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load decision-routing benchmark")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_v4_preregistered_shapes_and_gates_are_locked() -> None:
    cycle = json.loads(CYCLE.read_text(encoding="utf-8"))

    assert cycle["status"] == "preregistered_no_corpus_generated"
    assert cycle["target_corpus_shapes"]["development"] == {
        "case_count": 1800,
        "supported_operation_cases": 1152,
        "near_domain_unsupported_operation_cases": 576,
        "out_of_domain_cases": 72,
        "languages": ["en", "ko", "es", "ja", "de", "mixed"],
        "cases_per_language": 300,
        "supported_route_count": 16,
        "cases_per_supported_route": 72,
    }
    gates = cycle["preregistered_gates"]
    assert gates["supported_exact_route_accuracy_min"] == 0.70
    assert gates["near_domain_unsupported_rejection_min"] == 0.96
    assert gates["false_route_rate_max"] == 0.02
    assert gates["invalid_plan_rate_max"] == 0.0
    assert gates["execution_authority_violation_rate_max"] == 0.0
    assert gates["execution_errors_max"] == 0
    assert gates["promotion_requires_all_gates"] is True


def test_v4_consumed_predecessor_data_is_not_tuning_eligible() -> None:
    cycle = json.loads(CYCLE.read_text(encoding="utf-8"))

    forbidden = cycle["tuning_policy"]["forbidden"]
    assert "0.10 graph development rows" in forbidden
    assert "0.10 graph fresh calibration rows" in forbidden
    assert cycle["tuning_policy"]["eligible"] == ["fresh v4 development only"]
    assert cycle["fresh_data_contract"]["calibration_generated_only_after_candidate_freeze"] is True
    assert cycle["fresh_data_contract"]["blind_generated_only_after_fresh_calibration_pass"] is True


def test_benchmark_preserves_unsupported_family(tmp_path: Path) -> None:
    module = _benchmark_module()
    corpus = tmp_path / "corpus.json"
    corpus.write_text(
        json.dumps(
            [
                {
                    "id": "near-1",
                    "query": "print a warehouse barcode label for SKU-711",
                    "expected": None,
                    "category": "near_domain_unsupported_operation",
                    "expect_abstain": True,
                    "split": "development",
                    "language": "en",
                    "unsupported_family": "inventory.family_1",
                }
            ]
        ),
        encoding="utf-8",
    )

    cases = module.load_corpus(
        corpus,
        allowed_routes={
            f"{tool.key}.{endpoint.name}"
            for tool in module.reference_registry().tools()
            for endpoint in tool.endpoints
        },
    )

    assert cases[0].unsupported_family == "inventory.family_1"


def test_pairwise_tool_ablation_is_frozen_before_execution() -> None:
    ablation = json.loads(PAIRWISE_TOOL_ABLATION.read_text(encoding="utf-8"))

    assert ablation["status"] == "design_frozen_before_implementation"
    assert ablation["implementation"]["planner_core_change_required"] is False
    assert ablation["implementation"]["pairwise_tool_min_score"] == 0.0
    assert ablation["implementation"]["operation_pairwise_min_score"] == 0.01


def test_benchmark_exposes_generic_graph_seed_score_telemetry() -> None:
    module = _benchmark_module()
    fields = module.BenchmarkRow.__dataclass_fields__

    assert "graph_seed_score_kind" in fields
    assert "graph_seed_top_score" in fields
    assert "graph_seed_second_score" in fields

    source = BENCHMARK.read_text(encoding="utf-8")
    assert "--graph-semantic-seed-pairwise-callable" in source
    assert "--graph-semantic-seed-min-score" in source
