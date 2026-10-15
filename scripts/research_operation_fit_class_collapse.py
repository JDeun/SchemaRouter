"""Deterministic development diagnostics for operation-class collapse.

These summaries describe validated, same-run per-case predictions. They do not
retrain models, fit thresholds, infer permissions or promote a DEV result.
Warning thresholds are heuristic diagnostics, not calibrated release criteria.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from scripts.research_operation_fit_conveyor import KINDS

LANGUAGES = ("en", "ko", "ja")
# Published *after* the observed NLI collapse; WARNING heuristics, not a
# prospective quality threshold or an independent validation result.
DOMINANT_ALL_SHARE_WARNING = 0.50
DOMINANT_ACCEPTED_SHARE_WARNING = 0.65
MIN_ACCEPTED_WARNING = 5


def _distribution(predictions: list[str | None]) -> dict[str, int]:
    counts = Counter(predictions)
    return {
        **{kind: counts[kind] for kind in KINDS},
        "abstain": counts[None],
    }


def _dominance(predictions: list[str | None]) -> dict[str, Any]:
    accepted = [name for name in predictions if name is not None]
    total = len(predictions)
    ranking = sorted(KINDS, key=lambda kind: (-accepted.count(kind), kind))
    majority = ranking[0] if accepted else None
    majority_count = accepted.count(majority) if majority else 0
    return {
        "total_cases": total,
        "accepted_cases": len(accepted),
        "abstained_cases": total - len(accepted),
        "majority_operation": majority,
        "majority_count": majority_count,
        "majority_fraction_all": majority_count / total if total else None,
        "majority_fraction_accepted": (
            majority_count / len(accepted) if accepted else None
        ),
        "predicted_counts": _distribution(predictions),
    }


def class_collapse_diagnostics(
    arms: dict[str, dict[str, Any]],
    corpus: dict[str, Any],
) -> dict[str, Any]:
    """Analyze output from *_metric_rows-verified reports only.

    The caller MUST check corpus identity and per-case ground truth first.
    This function does not relax or replace the existing provenance gate.
    """
    cases = corpus["cases"]
    if not isinstance(cases, list) or not cases:
        raise ValueError("operation diagnostic requires a nonempty corpus")
    ids = [item["id"] for item in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate original case in diagnostics")
    result: dict[str, Any] = {}
    for arm_name in sorted(arms):
        raw = arms[arm_name]["rows"]
        if len(raw) != len(cases):
            raise ValueError("incomplete input to class-collapse diagnostics")
        rows = {row["case_id"]: row for row in raw}
        if len(rows) != len(ids) or set(rows) != set(ids):
            raise ValueError("missing or duplicate predictions in diagnostics")
        predicted = {
            key: rows[key]["predicted_operation"] for key in ids
        }
        total = _dominance([predicted[key] for key in ids])
        majority = total["majority_operation"]
        supported = [
            case for case in cases if case["kind"] == "supported"
        ]
        unsupported = [
            case for case in cases if case["kind"] == "unsupported"
        ]
        wrong_majority_supported = sum(
            predicted[case["id"]] == majority
            and case["expected_operation"] != majority
            for case in supported
        ) if majority else 0
        majority_unsupported = sum(
            predicted[case["id"]] == majority for case in unsupported
        ) if majority else 0
        by_language = {
            lang: _dominance([
                predicted[case["id"]] for case in cases
                if case["language"] == lang
            ])
            for lang in LANGUAGES
        }
        confusion = {
            kind: {
                **{
                    predicted_kind: sum(
                        case["expected_operation"] == kind
                        and predicted[case["id"]] == predicted_kind
                        for case in supported
                    )
                    for predicted_kind in KINDS
                },
                "abstain": sum(
                    case["expected_operation"] == kind
                    and predicted[case["id"]] is None
                    for case in supported
                ),
            }
            for kind in KINDS
        }
        unsupported_predictions = _distribution([
            predicted[case["id"]] for case in unsupported
        ])
        supported_wrong_destinations = {
            kind: sum(
                predicted[case["id"]] == kind
                and case["expected_operation"] != kind
                for case in supported
            )
            for kind in KINDS
        }
        warnings = []
        if (
            majority is not None
            and total["majority_fraction_all"] is not None
            and total["majority_fraction_all"] >= DOMINANT_ALL_SHARE_WARNING
            and wrong_majority_supported > 0
        ):
            warnings.append("MAJORITY_OF_ALL_CASES_WRONG_OPERATION_CONCENTRATION")
        if (
            majority is not None
            and total["accepted_cases"] >= MIN_ACCEPTED_WARNING
            and total["majority_fraction_accepted"] is not None
            and total["majority_fraction_accepted"]
            >= DOMINANT_ACCEPTED_SHARE_WARNING
            and wrong_majority_supported > 0
        ):
            warnings.append("ACCEPTED_PREDICTIONS_CONCENTRATED_ON_WRONG_OPERATION")
        result[arm_name] = {
            "total": total,
            "by_language": by_language,
            "supported_confusion": confusion,
            "supported_wrong_destinations": supported_wrong_destinations,
            "unsupported_predictions": unsupported_predictions,
            "majority_wrong_supported_count": wrong_majority_supported,
            "majority_unsupported_count": majority_unsupported,
            "heuristic_warnings": warnings,
        }
    return {
        "status": "DESCRIPTIVE_DEV_ONLY_NOT_CALIBRATED",
        "rule": {
            "dominant_all_fraction": DOMINANT_ALL_SHARE_WARNING,
            "dominant_accepted_fraction": DOMINANT_ACCEPTED_SHARE_WARNING,
            "minimum_accepted_cases": MIN_ACCEPTED_WARNING,
            "calibrated": False,
            "may_change_routing": False,
        },
        "arms": result,
    }
