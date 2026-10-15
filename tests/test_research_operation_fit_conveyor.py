"""Offline conveyor guards; mock records are contract tests, not model scores."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.evaluate_operation_fit_nli_dev import (
    DIAGNOSTIC_THRESHOLD,
    HYPOTHESES,
    choose,
    evaluate,
)
from scripts.research_operation_fit_conveyor import (
    ARMS,
    CORPUS_SHA,
    KINDS,
    NLI_REVISION,
    _metric_rows,
    aggregate,
    load_inputs,
)


def make_reports() -> tuple[dict, dict, dict, dict, str]:
    plan, corpus, digest = load_inputs()
    rows = [{
        "case_id": case["id"],
        "language": case["language"],
        "kind": case["kind"],
        "expected_operation": case["expected_operation"],
        "predicted_operation": (
            case["expected_operation"] if case["kind"] == "supported" else None
        ),
        "latency_ms": 2.0,
    } for case in corpus["cases"]]
    baseline = {
        "model_key": "lexical_baseline",
        "corpus_sha256": digest,
        "independent_validation": False,
        "grants_execution_authority": False,
        "rows": rows,
    }
    arms = {}
    for name in ARMS[1:]:
        arms[name] = {
            "corpus_sha256": digest,
            "independent_validation": False,
            "grants_execution_authority": False,
            "rows": copy.deepcopy(rows),
        }
    nli = {
        "model_key": "multilingual_nli",
        "model_id": plan["candidates"][1]["model"],
        "model_revision": NLI_REVISION,
        "threshold_calibrated": False,
        "no_tool_execution": True,
        "arms": arms,
    }
    return plan, corpus, baseline, nli, digest


def test_preflight_has_no_independent_confirmation_authority() -> None:
    plan, corpus, digest = load_inputs()
    assert digest == CORPUS_SHA
    assert len(corpus["cases"]) == 72
    assert plan["external_confirmation"]["enabled"] is False
    assert plan["external_confirmation"]["approved"] is False
    assert plan["frozen_v014_unchanged"] is True
    assert plan["candidates"][-1]["status"].startswith("blocked_")
    assert list(HYPOTHESES) == list(KINDS)
    assert DIAGNOSTIC_THRESHOLD == 0.7


@pytest.mark.parametrize("alteration", [
    {"status": "ready_for_release"},
    {"frozen_v014_unchanged": False},
    {"permitted_execution": ["tool_dispatch"]},
    {"forbidden_execution": []},
    {"external_confirmation": {
        "enabled": True, "approved": True,
        "must_not_read_existing_v014_heldout": True,
    }},
])
def test_plan_escalation_or_drift_is_denied(
    tmp_path: Path, alteration: dict,
) -> None:
    plan, _, _ = load_inputs()
    plan.update(alteration)
    path = tmp_path / "modified-plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(ValueError):
        load_inputs(path)


def test_nli_scoring_never_calls_tool_or_claims_independent_evidence() -> None:
    _, corpus, digest = load_inputs()
    scores = {kind: 0.01 for kind in KINDS}
    scores["search"] = 0.6
    report = evaluate(corpus, digest, scorer=lambda _query: scores)
    assert set(report) == set(ARMS[1:])
    for arm in report.values():
        assert len(arm["rows"]) == 72
        assert arm["grants_execution_authority"] is False
        assert arm["independent_validation"] is False
    assert report["nli_forced"]["rows"][0]["predicted_operation"] == "search"
    assert report["nli_diagnostic_gate"]["rows"][0]["predicted_operation"] is None


def test_nli_choice_rejects_invalid_probabilities() -> None:
    scores = {kind: 0.0 for kind in KINDS}
    scores["update"] = 0.99
    assert choose(scores, gated=True) == "update"
    assert choose(scores, gated=False) == "update"
    scores["update"] = float("nan")
    with pytest.raises(ValueError, match="invalid NLI"):
        choose(scores, gated=True)
    scores["update"] = 0.9
    scores.pop("search")
    with pytest.raises(ValueError, match="nine"):
        choose(scores, gated=False)


def test_successful_dev_screen_cannot_promote_product_or_holdout() -> None:
    plan, corpus, baseline, nli, digest = make_reports()
    result = aggregate(baseline, nli, plan, corpus, digest)
    assert all(x["passes_development_screen_only"] for x in result["arms"].values())
    assert result["independent_confirmation"].startswith("BLOCKED")
    assert result["task_specific_classifier"].startswith("BLOCKED")
    assert result["may_promote_to_product"] is False
    assert result["may_merge_release"] is False
    assert result["may_execute_tools"] is False


@pytest.mark.parametrize("change", [
    "missing_row", "duplicate", "forged_label", "forged_language",
    "forged_corpus", "claimed_independent", "claimed_authority",
    "nonfinite_latency", "unregistered_prediction",
])
def test_tampered_baseline_provenance_is_rejected(change: str) -> None:
    plan, corpus, baseline, nli, digest = make_reports()
    rows = baseline["rows"]
    if change == "missing_row":
        rows.pop()
    elif change == "duplicate":
        rows[1]["case_id"] = rows[0]["case_id"]
    elif change == "forged_label":
        rows[0]["expected_operation"] = "delete"
    elif change == "forged_language":
        rows[0]["language"] = "fr"
    elif change == "forged_corpus":
        baseline["corpus_sha256"] = "0" * 64
    elif change == "claimed_independent":
        baseline["independent_validation"] = True
    elif change == "claimed_authority":
        baseline["grants_execution_authority"] = True
    elif change == "nonfinite_latency":
        rows[0]["latency_ms"] = float("nan")
    elif change == "unregistered_prediction":
        rows[0]["predicted_operation"] = "transfer_funds"
    with pytest.raises(ValueError):
        aggregate(baseline, nli, plan, corpus, digest)


def test_nli_wrong_checkpoint_and_missing_arm_are_blocked() -> None:
    plan, corpus, baseline, nli, digest = make_reports()
    nli["model_revision"] = "latest"
    with pytest.raises(ValueError, match="unpinned"):
        aggregate(baseline, nli, plan, corpus, digest)
    nli["model_revision"] = NLI_REVISION
    nli["arms"].pop("nli_diagnostic_gate")
    with pytest.raises(ValueError, match="both"):
        aggregate(baseline, nli, plan, corpus, digest)


def test_negative_cases_count_independently_of_supported() -> None:
    plan, corpus, baseline, nli, digest = make_reports()
    negatives = [x for x in baseline["rows"] if x["kind"] == "unsupported"]
    negatives[0]["predicted_operation"] = "delete"
    metric = _metric_rows(baseline, corpus, digest, arm="lexical_baseline")
    assert metric["supported_correct"] == 54
    assert metric["unsupported_false_accepted"] == 1
    result = aggregate(baseline, nli, plan, corpus, digest)
    assert result["arms"]["lexical_baseline"]["passes_development_screen_only"] is False
