from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_bge_m3_colbert_operation_gate_v4.py"
MANIFEST = (
    ROOT
    / "benchmarks"
    / "operation-routing-v4-bge-m3-colbert-operation-gate.json"
)


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_bge_m3_colbert_operation_gate_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load ColBERT operation-gate diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows() -> list[dict]:
    return [
        {
            "case_id": "supported-correct",
            "category": "v4_supported_natural",
            "language": "en",
            "expected": "weather.current",
            "dense_winner": "weather.current",
            "colbert_winner_score": 0.9,
            "colbert_global_agree": True,
            "colbert_same_tool_agree": True,
        },
        {
            "case_id": "supported-wrong",
            "category": "v4_supported_natural",
            "language": "en",
            "expected": "weather.forecast",
            "dense_winner": "weather.current",
            "colbert_winner_score": 0.8,
            "colbert_global_agree": True,
            "colbert_same_tool_agree": True,
        },
        {
            "case_id": "near",
            "category": "near_domain_unsupported_operation",
            "language": "en",
            "expected": None,
            "dense_winner": "weather.current",
            "colbert_winner_score": 0.4,
            "colbert_global_agree": True,
            "colbert_same_tool_agree": True,
        },
        {
            "case_id": "ood",
            "category": "out_of_domain",
            "language": "en",
            "expected": None,
            "dense_winner": "weather.current",
            "colbert_winner_score": 0.2,
            "colbert_global_agree": False,
            "colbert_same_tool_agree": False,
        },
    ]


def test_manifest_freezes_new_representation_without_fresh_data() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert data["model"]["name"] == "BAAI/bge-m3"
    assert data["model"]["revision"] == (
        "5617a9f61b028005a4858fdac845db406aefb181"
    )
    assert data["model"]["inference_library_version"] == "1.4.2"
    assert data["reference_authority"]["required_raw_winner_parity_mismatches"] == 0
    assert data["data"]["forbidden_fresh_issues"] == [270, 287, 326]
    assert data["data"]["calibration_or_blind_forbidden"] is True


def test_manifest_keeps_colbert_veto_only_and_sparse_diagnostic_only() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    authority = data["dense_authority"]

    assert authority["raw_registered_top1_only"] is True
    assert authority["colbert_can_change_route"] is False
    assert authority["sparse_can_change_route"] is False
    assert authority["rank2_fallback"] is False
    assert authority["pseudo_route"] is False
    assert data["sparse_policy"]["diagnostic_only"] is True
    assert data["sparse_policy"]["may_define_promoted_rule"] is False


def test_manifest_allows_exactly_four_preregistered_colbert_families() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    families = data["rule_families"]

    assert set(families) == {"A", "B", "C", "D"}
    assert families["A"]["threshold"] is None
    assert families["B"]["threshold"] is None
    assert families["C"]["threshold_scope"] == "one_global_threshold"
    assert families["D"]["threshold_scope"] == "one_global_threshold"
    assert families["C"]["false_route_budgets"] == [0, 6, 12]
    assert families["D"]["false_route_budgets"] == [0, 6, 12]


def test_metrics_uses_full_population_denominators() -> None:
    module = _module()
    rows = _rows()

    result = module._metrics(
        rows,
        agreement_field="colbert_global_agree",
        threshold=0.5,
    )

    assert result["supported_exact_route_accuracy"] == 0.5
    assert result["wrong_supported_accepted"] == 1
    assert result["near_domain_unsupported_rejection"] == 1.0
    assert result["out_of_domain_rejection"] == 1.0
    assert result["false_routes"] == 0


def test_global_frontier_can_reject_unsupported_without_route_local_rules() -> None:
    module = _module()
    rows = _rows()

    frontier = module._frontier(
        rows,
        agreement_field="colbert_global_agree",
        false_budgets=(0,),
    )
    selected = frontier["selected_by_false_budget"]["0"]

    assert selected is not None
    assert selected["false_routes"] == 0
    assert selected["supported_correct"] == 1
    assert selected["threshold"] > 0.4


def test_candidate_gate_requires_parity_runtime_and_full_quality() -> None:
    module = _module()
    metrics = {
        "supported_exact_route_accuracy": 0.85,
        "near_domain_unsupported_rejection": 0.97,
        "out_of_domain_rejection": 1.0,
        "false_route_rate": 0.01,
    }

    assert module._gate_pass(
        metrics,
        p95_ms=250.0,
        parity_mismatches=0,
        authority_violations=0,
        execution_errors=0,
    )
    assert not module._gate_pass(
        metrics,
        p95_ms=250.0,
        parity_mismatches=1,
        authority_violations=0,
        execution_errors=0,
    )
    assert not module._gate_pass(
        metrics,
        p95_ms=250.001,
        parity_mismatches=0,
        authority_violations=0,
        execution_errors=0,
    )


def test_frontier_gate_checks_budget_zero_not_only_budget_six() -> None:
    module = _module()
    passing = {
        "threshold": 0.91,
        "supported_exact_route_accuracy": 0.86,
        "near_domain_unsupported_rejection": 1.0,
        "out_of_domain_rejection": 1.0,
        "false_route_rate": 0.0,
    }
    failing_budget6 = {
        "threshold": 0.72,
        "supported_exact_route_accuracy": 0.88,
        "near_domain_unsupported_rejection": 0.99,
        "out_of_domain_rejection": 0.99,
        "false_route_rate": 0.009,
    }
    frontier = {
        "selected_by_false_budget": {
            "0": passing,
            "6": failing_budget6,
            "12": failing_budget6,
        }
    }

    result = module._passing_frontier_rules(
        frontier,
        family_id="C",
        false_budgets=[0, 6, 12],
        p95_ms=200.0,
        parity_mismatches=0,
        authority_violations=0,
        execution_errors=0,
    )

    assert len(result) == 1
    assert result[0]["family"] == "C"
    assert result[0]["selected_false_budgets"] == [0]
    assert result[0]["rule"]["threshold"] == 0.91


def test_frontier_gate_deduplicates_same_threshold_across_budgets() -> None:
    module = _module()
    point = {
        "threshold": 0.91,
        "supported_exact_route_accuracy": 0.86,
        "near_domain_unsupported_rejection": 1.0,
        "out_of_domain_rejection": 1.0,
        "false_route_rate": 0.0,
    }
    frontier = {
        "selected_by_false_budget": {
            "0": point,
            "6": point,
            "12": point,
        }
    }

    result = module._passing_frontier_rules(
        frontier,
        family_id="D",
        false_budgets=[0, 6, 12],
        p95_ms=200.0,
        parity_mismatches=0,
        authority_violations=0,
        execution_errors=0,
    )

    assert len(result) == 1
    assert result[0]["selected_false_budgets"] == [0, 6, 12]
