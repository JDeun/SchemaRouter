"""Operation-class collapse diagnostics are descriptive DEV artifacts only."""
from __future__ import annotations

import copy

import pytest

from scripts.research_operation_fit_class_collapse import (
    DOMINANT_ACCEPTED_SHARE_WARNING,
    DOMINANT_ALL_SHARE_WARNING,
    MIN_ACCEPTED_WARNING,
    class_collapse_diagnostics,
)
from scripts.research_operation_fit_conveyor import KINDS, load_inputs
from scripts.research_operation_fit_opportunities import compile_opportunities


def synthetic_inputs() -> tuple[dict, dict[str, dict], dict, dict]:
    plan, corpus, digest = load_inputs()
    raw_rows = [
        {
            "case_id": item["id"],
            "language": item["language"],
            "kind": item["kind"],
            "expected_operation": item["expected_operation"],
            "predicted_operation": (
                item["expected_operation"] if item["kind"] == "supported"
                else None
            ),
            "latency_ms": 0.2,
        }
        for item in corpus["cases"]
    ]
    baseline = {
        "model_key": "lexical_baseline",
        "corpus_sha256": digest,
        "independent_validation": False,
        "grants_execution_authority": False,
        "rows": copy.deepcopy(raw_rows),
    }
    forced = copy.deepcopy(raw_rows)
    for idx, item in enumerate(forced):
        item["predicted_operation"] = "directions" if idx < 50 else "lookup"
    gated = copy.deepcopy(raw_rows)
    for idx, item in enumerate(gated):
        item["predicted_operation"] = "directions" if idx < 25 else None
    arms = {
        "lexical_baseline": baseline,
        "nli_forced": {
            "corpus_sha256": digest,
            "independent_validation": False,
            "grants_execution_authority": False,
            "rows": forced,
        },
        "nli_diagnostic_gate": {
            "corpus_sha256": digest,
            "independent_validation": False,
            "grants_execution_authority": False,
            "rows": gated,
        },
    }
    nli = {
        "model_key": "multilingual_nli",
        "model_id": plan["candidates"][1]["model"],
        "model_revision": plan["candidates"][1]["revision"],
        "threshold_calibrated": False,
        "no_tool_execution": True,
        "arms": {
            "nli_forced": arms["nli_forced"],
            "nli_diagnostic_gate": arms["nli_diagnostic_gate"],
        },
    }
    return corpus, arms, baseline, nli


def test_majority_collapse_warns_and_records_denominators() -> None:
    corpus, arms, _, _ = synthetic_inputs()
    result = class_collapse_diagnostics(arms, corpus)
    assert result["status"] == "DESCRIPTIVE_DEV_ONLY_NOT_CALIBRATED"
    assert result["rule"]["calibrated"] is False
    assert result["rule"]["may_change_routing"] is False
    assert result["rule"]["dominant_all_fraction"] == DOMINANT_ALL_SHARE_WARNING
    assert result["rule"]["dominant_accepted_fraction"] == (
        DOMINANT_ACCEPTED_SHARE_WARNING
    )
    assert result["rule"]["minimum_accepted_cases"] == MIN_ACCEPTED_WARNING

    forced = result["arms"]["nli_forced"]
    assert forced["total"]["total_cases"] == 72
    assert forced["total"]["accepted_cases"] == 72
    assert forced["total"]["majority_operation"] == "directions"
    assert forced["total"]["majority_count"] == 50
    assert forced["total"]["majority_fraction_all"] == pytest.approx(50 / 72)
    assert forced["total"]["predicted_counts"]["lookup"] == 22
    assert forced["total"]["predicted_counts"]["abstain"] == 0
    assert len(forced["heuristic_warnings"]) == 2
    assert forced["majority_wrong_supported_count"] > 0

    gate = result["arms"]["nli_diagnostic_gate"]
    assert gate["total"]["accepted_cases"] == 25
    assert gate["total"]["abstained_cases"] == 47
    assert gate["total"]["majority_fraction_accepted"] == 1.0
    assert gate["heuristic_warnings"] == [
        "ACCEPTED_PREDICTIONS_CONCENTRATED_ON_WRONG_OPERATION"
    ]
    assert result["arms"]["lexical_baseline"]["heuristic_warnings"] == []


def test_confusion_and_unsupported_wrong_route_have_exact_denominators() -> None:
    corpus, arms, _, _ = synthetic_inputs()
    result = class_collapse_diagnostics(arms, corpus)
    for report in result["arms"].values():
        assert sum(report["total"]["predicted_counts"].values()) == 72
        assert sum(report["unsupported_predictions"].values()) == 18
        assert all(sum(report["supported_confusion"][kind].values()) == 6
                   for kind in KINDS)
        assert sum(x["total_cases"] for x in report["by_language"].values()) == 72
        assert len(report["supported_wrong_destinations"]) == 9


def test_integration_with_fail_closed_opportunity_report() -> None:
    _, _, baseline, nli = synthetic_inputs()
    result = compile_opportunities(baseline, nli)
    forced = result["class_collapse_diagnostics"]["arms"]["nli_forced"]
    assert forced["total"]["majority_count"] == 50
    assert result["no_independent_qualification"] is True
    assert result["no_automatic_experiment_dispatch"] is True
    assert result["may_promote_to_product"] is False
    assert result["may_merge_release"] is False
    assert result["may_execute_tools"] is False


def test_invalid_or_missing_predictions_do_not_generate_diagnostics() -> None:
    corpus, arms, _, _ = synthetic_inputs()
    arms["nli_forced"]["rows"][0]["case_id"] = "unregistered-case"
    with pytest.raises(ValueError, match="missing or duplicate"):
        class_collapse_diagnostics(arms, corpus)
    corpus, arms, _, _ = synthetic_inputs()
    arms["nli_forced"]["rows"].pop()
    with pytest.raises(ValueError, match="incomplete"):
        class_collapse_diagnostics(arms, corpus)
    corpus, arms, _, _ = synthetic_inputs()
    corpus["cases"].append(corpus["cases"][0])
    with pytest.raises(ValueError, match="duplicate original"):
        class_collapse_diagnostics(arms, corpus)
