from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compose_lightweight_negative_gte_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "compose_lightweight_negative_gte_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load lightweight composition module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest() -> dict:
    return {
        "experiment": "test",
        "canonical_dev": {"case_count": 4},
        "negative_veto": {
            "max_negative_score_min": 0.55,
            "negative_advantage_min": 0.05,
        },
        "gte_rescue": {
            "rules": {
                "tool.a": {
                    "min_gte_score": 0.50,
                    "min_gte_margin": 0.01,
                    "max_base_score_deficit": 0.05,
                    "max_base_margin_deficit": 0.0,
                }
            }
        },
        "promotion_gate": {
            "supported_exact_route_accuracy_min": 0.50,
            "near_domain_unsupported_rejection_min": 1.0,
            "out_of_domain_rejection": 1.0,
            "false_route_rate_max": 0.0,
            "authority_violations_max": 0,
            "execution_errors_max": 0,
        },
    }


def _gte_rows() -> list[dict]:
    return [
        {
            "case_id": "base-ok",
            "category": "v4_supported_natural",
            "language": "en",
            "expected": "tool.a",
            "base_raw_route": "tool.a",
            "base_accepted": True,
            "base_score_deficit": 0.0,
            "base_margin_deficit": 0.0,
            "gte_route": "tool.a",
            "gte_top_score": 0.8,
            "gte_margin": 0.1,
            "gte_agrees": True,
        },
        {
            "case_id": "base-false",
            "category": "near_domain_unsupported_operation",
            "language": "en",
            "expected": None,
            "base_raw_route": "tool.a",
            "base_accepted": True,
            "base_score_deficit": 0.0,
            "base_margin_deficit": 0.0,
            "gte_route": "tool.a",
            "gte_top_score": 0.8,
            "gte_margin": 0.1,
            "gte_agrees": True,
        },
        {
            "case_id": "rescue-ok",
            "category": "v4_supported_natural",
            "language": "en",
            "expected": "tool.a",
            "base_raw_route": "tool.a",
            "base_accepted": False,
            "base_score_deficit": 0.01,
            "base_margin_deficit": 0.0,
            "gte_route": "tool.a",
            "gte_top_score": 0.7,
            "gte_margin": 0.03,
            "gte_agrees": True,
        },
        {
            "case_id": "ood",
            "category": "out_of_domain",
            "language": "en",
            "expected": None,
            "base_raw_route": "tool.a",
            "base_accepted": False,
            "base_score_deficit": 0.2,
            "base_margin_deficit": 0.0,
            "gte_route": "tool.a",
            "gte_top_score": 0.4,
            "gte_margin": 0.0,
            "gte_agrees": False,
        },
    ]


def _negative_rows() -> list[dict]:
    return [
        {
            "case_id": "base-ok",
            "category": "v4_supported_natural",
            "language": "en",
            "unsupported_family": None,
            "expected": "tool.a",
            "raw_top_route": "tool.a",
            "max_negative_score": 0.50,
            "negative_advantage": 0.00,
        },
        {
            "case_id": "base-false",
            "category": "near_domain_unsupported_operation",
            "language": "en",
            "unsupported_family": "tool.family_1",
            "expected": None,
            "raw_top_route": "tool.a",
            "max_negative_score": 0.60,
            "negative_advantage": 0.10,
        },
        {
            "case_id": "rescue-ok",
            "category": "v4_supported_natural",
            "language": "en",
            "unsupported_family": None,
            "expected": "tool.a",
            "raw_top_route": "tool.a",
            "max_negative_score": 0.80,
            "negative_advantage": 0.20,
        },
        {
            "case_id": "ood",
            "category": "out_of_domain",
            "language": "en",
            "unsupported_family": None,
            "expected": None,
            "raw_top_route": "tool.a",
            "max_negative_score": 0.20,
            "negative_advantage": -0.20,
        },
    ]


def test_composition_vetoes_base_false_and_rescues_only_original_abstention() -> None:
    module = _module()
    result = module.compose(
        {"rows": _gte_rows()},
        {"rows": _negative_rows()},
        _manifest(),
    )

    rows = {row["case_id"]: row for row in result["rows"]}
    assert rows["base-ok"]["final_route"] == "tool.a"
    assert rows["base-false"]["final_route"] is None
    assert rows["base-false"]["decision_path"] == "negative_veto"
    assert rows["rescue-ok"]["final_route"] == "tool.a"
    assert rows["rescue-ok"]["decision_path"] == "gte_rescue"
    assert rows["ood"]["final_route"] is None

    summary = result["summary"]
    assert summary["supported_exact_route_accuracy"] == 1.0
    assert summary["near_domain_unsupported_rejection"] == 1.0
    assert summary["out_of_domain_rejection"] == 1.0
    assert summary["false_routes"] == 0
    assert summary["negative_veto_unsupported"] == 1
    assert summary["rescued_correct_supported"] == 1


def test_negative_vetoed_base_accept_is_never_rescued() -> None:
    module = _module()
    gte = _gte_rows()
    neg = _negative_rows()

    gte[1]["gte_agrees"] = True
    gte[1]["gte_top_score"] = 1.0
    gte[1]["gte_margin"] = 1.0
    gte[1]["base_score_deficit"] = 0.0

    result = module.compose({"rows": gte}, {"rows": neg}, _manifest())
    row = next(item for item in result["rows"] if item["case_id"] == "base-false")
    assert row["decision_path"] == "negative_veto"
    assert row["final_route"] is None


def test_source_case_id_mismatch_fails_closed() -> None:
    module = _module()
    neg = _negative_rows()
    neg.pop()

    try:
        module.compose({"rows": _gte_rows()}, {"rows": neg}, _manifest())
    except ValueError as exc:
        assert "identical case IDs" in str(exc)
    else:
        raise AssertionError("case-ID mismatch must fail")


def test_source_route_mismatch_fails_closed() -> None:
    module = _module()
    neg = deepcopy(_negative_rows())
    neg[0]["raw_top_route"] = "tool.b"

    try:
        module.compose({"rows": _gte_rows()}, {"rows": neg}, _manifest())
    except ValueError as exc:
        assert "BGE raw route mismatch" in str(exc)
    else:
        raise AssertionError("route mismatch must fail")
