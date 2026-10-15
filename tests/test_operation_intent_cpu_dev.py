"""Offline integrity checks for operation-intent real CPU DEV study."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.evaluate_operation_intent_cpu_dev import (
    DIAGNOSTIC_THRESHOLDS,
    DESCRIPTIONS,
    evaluate_baseline,
    load_corpus,
    summarize,
)

CORPUS = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/operation-intent-trilingual-dev-20261015.json"
)


def test_frozen_development_corpus_is_explicitly_nonindependent() -> None:
    corpus, digest = load_corpus(CORPUS)
    assert len(digest) == 64
    assert len(corpus["cases"]) == 72
    assert len(DESCRIPTIONS) == 9
    assert corpus["independent_holdout"] is False
    assert corpus["calibrated_no_match"] is False
    assert corpus["execution_safety"] is False
    for language in ("en", "ko", "ja"):
        rows = [row for row in corpus["cases"] if row["language"] == language]
        assert sum(row["kind"] == "supported" for row in rows) == 18
        assert sum(row["kind"] == "unsupported" for row in rows) == 6
    assert DIAGNOSTIC_THRESHOLDS == (0.5, 0.6, 0.7, 0.8)


def test_lexical_baseline_is_fully_scored_without_any_weights() -> None:
    corpus, digest = load_corpus(CORPUS)
    result = evaluate_baseline(corpus, digest)
    assert len(result["rows"]) == 72
    assert result["grants_execution_authority"] is False
    summary = result["summary"]["overall"]
    assert summary["supported_count"] == 54
    assert summary["unsupported_count"] == 18
    assert 0 <= summary["supported_correct_rate"] <= 1
    assert 0 <= summary["supported_false_refusal_rate"] <= 1
    assert 0 <= summary["unsupported_false_accept_rate"] <= 1
    # Includes unsupported/negated requests that must not count in recall.


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("independent_holdout", True, "validation"),
        ("calibrated_no_match", True, "calibration"),
        ("execution_safety", True, "safety"),
    ],
)
def test_development_corpus_cannot_claim_qualification(
    tmp_path: Path, field: str, value: bool, reason: str,
) -> None:
    corpus, _ = load_corpus(CORPUS)
    altered = copy.deepcopy(corpus)
    altered[field] = value
    path = tmp_path / "forged.json"
    path.write_text(json.dumps(altered), encoding="utf-8")
    with pytest.raises(ValueError, match="DEV data"):
        load_corpus(path)


def test_poisoned_operation_and_duplicate_case_are_rejected(tmp_path: Path) -> None:
    corpus, _ = load_corpus(CORPUS)
    altered = copy.deepcopy(corpus)
    altered["cases"][0]["expected_operation"] = "transfer"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(altered), encoding="utf-8")
    with pytest.raises(ValueError, match="declared operation"):
        load_corpus(path)
    altered = copy.deepcopy(corpus)
    altered["cases"][1]["id"] = altered["cases"][0]["id"]
    path.write_text(json.dumps(altered), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_corpus(path)


def test_diagnostic_denominators_do_not_mix_negatives_and_positives() -> None:
    rows = [
        {
            "language": "ko", "kind": "supported", "expected_operation": "search",
            "predicted_operation": "search", "top_similarity": 0.8,
            "latency_ms": 8.0,
        },
        {
            "language": "ko", "kind": "supported", "expected_operation": "update",
            "predicted_operation": "delete", "top_similarity": 0.7,
            "latency_ms": 12.0,
        },
        {
            "language": "ko", "kind": "supported", "expected_operation": "lookup",
            "predicted_operation": None, "top_similarity": 0.3,
            "latency_ms": 10.0,
        },
        {
            "language": "ko", "kind": "unsupported", "expected_operation": None,
            "predicted_operation": "delete", "top_similarity": 0.75,
            "latency_ms": 9.0,
        },
        {
            "language": "ko", "kind": "unsupported", "expected_operation": None,
            "predicted_operation": None, "top_similarity": 0.2,
            "latency_ms": 7.0,
        },
    ]
    all_summary = summarize(rows, confidence_thresholds=(0.6,))["overall"]
    assert all_summary["supported_correct_rate"] == pytest.approx(1 / 3)
    assert all_summary["supported_false_refusal_rate"] == pytest.approx(1 / 3)
    assert all_summary["supported_wrong_operation_rate"] == pytest.approx(1 / 3)
    assert all_summary["unsupported_false_accept_rate"] == pytest.approx(0.5)
    diagnostic = all_summary["posthoc_threshold_diagnostics_only"]["0.6"]
    assert diagnostic["supported_wrong_operation_accepted_rate"] == pytest.approx(1 / 3)
    assert diagnostic["supported_false_refusal_rate"] == pytest.approx(1 / 3)
    assert diagnostic["unsupported_false_accept_rate"] == 0.5
    assert all_summary["latency_ms_p95"] == pytest.approx(11.6)
