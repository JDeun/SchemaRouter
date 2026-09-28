from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_top4_laya_noul_routing_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_top4_laya_noul_routing_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load top-4 Laya noul diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_protocol_constants_are_frozen() -> None:
    module = _module()
    assert module.RECALL_WIDTH == 4
    assert module.ACCEPTANCE_THRESHOLDS == (
        0.50,
        0.70,
        0.80,
        0.90,
        0.95,
        0.98,
        0.99,
        0.995,
    )


def test_questions_expose_only_four_noul_candidates() -> None:
    module = _module()
    row = {
        "topk_contracts": ["a", "b", "c", "d"],
    }
    questions = module._questions(row)
    assert list(questions) == [
        "candidate_0",
        "candidate_1",
        "candidate_2",
        "candidate_3",
    ]
    assert {item["type"] for item in questions.values()} == {"noul"}


def test_exact_probability_tie_is_lexical_not_bge_order() -> None:
    module = _module()
    row = {
        "topk_routes": ["z.route", "a.route", "m.route", "b.route"],
    }
    result = {
        "answers": {
            "candidate_0": {"noul": 0.90},
            "candidate_1": {"noul": 0.90},
            "candidate_2": {"noul": 0.20},
            "candidate_3": {"noul": 0.10},
        }
    }
    parsed = module._parse_result(row, result)
    assert parsed["selected_route"] == "a.route"
    assert parsed["max_probability"] == 0.90


def test_threshold_rule_counts_selection_not_bge_order() -> None:
    module = _module()
    rows = [
        {
            "expected": "a.route",
            "category": "v4_supported_natural",
            "language": "en",
        },
        {
            "expected": "b.route",
            "category": "v4_supported_natural",
            "language": "en",
        },
        {
            "expected": None,
            "category": "near_domain_unsupported_operation",
            "language": "en",
        },
        {
            "expected": None,
            "category": "out_of_domain",
            "language": "en",
        },
    ]
    selections = [
        {"selected_route": "a.route", "max_probability": 0.99},
        {"selected_route": "c.route", "max_probability": 0.99},
        {"selected_route": "a.route", "max_probability": 0.10},
        {"selected_route": "b.route", "max_probability": 0.10},
    ]
    result = module._evaluate_threshold(rows, selections, 0.90)
    assert result["supported_exact_route_accuracy"] == 0.5
    assert result["wrong_supported_accepted"] == 1
    assert result["near_domain_unsupported_rejection"] == 1.0
    assert result["out_of_domain_rejection"] == 1.0
    assert result["false_routes"] == 0
