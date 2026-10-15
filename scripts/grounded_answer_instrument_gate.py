"""Pre-release, outcome-blind readiness gate for a prospective answer instrument.

This gate consumes separately frozen *new* case labels, not any #424/#506
result rows. There are intentionally no default thresholds: the experiment
owner must preregister its numeric acceptance policy before scoring.
No model execution or downstream benchmark is performed by this module.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from scripts.grounded_answer_contract import classify_grounded_answer_episode
from scripts.no_fit_evidence_contract import classify_no_fit_episode


@dataclass(frozen=True)
class InstrumentReadinessPolicy:
    min_supported: int
    min_unsupported: int
    min_grounded_rate: float
    max_false_match_rate: float
    max_false_refusal_rate: float

    def __post_init__(self) -> None:
        for key in ("min_supported", "min_unsupported"):
            value = getattr(self, key)
            if type(value) is not int or value < 1:
                raise ValueError(f"{key} must be a positive integer")
        for key in (
            "min_grounded_rate",
            "max_false_match_rate",
            "max_false_refusal_rate",
        ):
            value = getattr(self, key)
            if type(value) not in (int, float):
                raise ValueError(f"{key} must be a finite rate in [0,1]")
            try:
                valid = math.isfinite(value) and 0 <= value <= 1
            except (OverflowError, TypeError, ValueError):
                valid = False
            if not valid:
                raise ValueError(f"{key} must be a finite rate in [0,1]")


def evaluate_instrument_readiness(
    *,
    frozen_cases: Mapping[str, Mapping[str, Any]],
    observed_rows: Sequence[Mapping[str, Any]],
    policy: InstrumentReadinessPolicy,
) -> dict[str, Any]:
    """Score a *separately labeled* prospective instrument-qualification set.

    Every frozen ID must have exactly one observed row. Unsupported tasks
    never enter the grounded-fact recall denominator. The row is not
    authoritative for its expected label or fact count.
    """
    if not isinstance(policy, InstrumentReadinessPolicy):
        raise ValueError("an explicit preregistered readiness policy is required")
    if not isinstance(frozen_cases, Mapping) or not frozen_cases:
        raise ValueError("nonempty frozen case manifest required")
    if isinstance(observed_rows, (str, bytes)) or not isinstance(
        observed_rows, Sequence
    ):
        raise ValueError("observed rows must be a sequence")

    known: set[str] = set()
    supported = grounded = supported_route_observed = unsupported = bad_match = bad_refusal = 0
    violations = 0
    for row in observed_rows:
        if not isinstance(row, Mapping):
            raise ValueError("each observed row must be a mapping")
        task_id = row.get("task_id")
        if type(task_id) is not str or not task_id:
            raise ValueError("task_id must be a nonempty string")
        if task_id in known:
            raise ValueError("duplicate observed task_id")
        known.add(task_id)
        if task_id not in frozen_cases:
            raise ValueError("unknown observed task_id")
        label = frozen_cases[task_id]
        if not isinstance(label, Mapping):
            raise ValueError("invalid frozen task label")
        expected_no_fit = label.get("expected_no_fit")
        if type(expected_no_fit) is not bool:
            raise ValueError("frozen expected_no_fit must be Boolean")
        result = classify_no_fit_episode(
            row.get("no_fit"), expected_no_fit=expected_no_fit
        )
        violations += int(result["authority_violation"])
        if expected_no_fit:
            unsupported += 1
            bad_match += int(result["unsupported_false_match"])
            if "grounded" in row:
                raise ValueError("no-fit tasks may not receive factual scores")
        else:
            fact_count = label.get("expected_fact_count")
            supported += 1
            bad_refusal += int(result["supported_false_refusal"])
            truth = classify_grounded_answer_episode(
                row.get("grounded"), expected_fact_count=fact_count
            )
            # An answer-quality score is not proof that the routed capability
            # was actually used. Require host-observed planner/tool dispatch;
            # abstention plus a tool call is contradictory, not valid routing.
            route_observed = (
                not row["no_fit"]["abstained"]
                and row["no_fit"]["planner_call_count"] > 0
                and row["no_fit"]["tool_call_count"] > 0
            )
            supported_route_observed += int(route_observed)
            grounded += int(truth["answer_grounded_complete"] and route_observed)

    if known != set(frozen_cases):
        raise ValueError("missing observed rows from frozen case manifest")

    sufficient = (
        supported >= policy.min_supported
        and unsupported >= policy.min_unsupported
    )
    grounded_rate = grounded / supported if supported else None
    false_match_rate = bad_match / unsupported if unsupported else None
    false_refusal_rate = bad_refusal / supported if supported else None
    qualifies = (
        sufficient
        and violations == 0
        and grounded_rate is not None
        and false_match_rate is not None
        and false_refusal_rate is not None
        and grounded_rate >= policy.min_grounded_rate
        and false_match_rate <= policy.max_false_match_rate
        and false_refusal_rate <= policy.max_false_refusal_rate
    )
    return {
        "status": "instrument_qualified" if qualifies else "instrument_unqualified",
        "qualified": bool(qualifies),
        "supported_cases": supported,
        "supported_route_observed_cases": supported_route_observed,
        "unsupported_cases": unsupported,
        "grounded_success_rate": grounded_rate,
        "unsupported_false_match_rate": false_match_rate,
        "supported_false_refusal_rate": false_refusal_rate,
        "authority_violations": violations,
        "complete_frozen_manifest": True,
    }


def require_instrument_ready(
    *,
    frozen_cases: Mapping[str, Mapping[str, Any]],
    observed_rows: Sequence[Mapping[str, Any]],
    policy: InstrumentReadinessPolicy,
) -> dict[str, Any]:
    """Fail closed before any caller authorizes expensive confirmation."""
    result = evaluate_instrument_readiness(
        frozen_cases=frozen_cases, observed_rows=observed_rows, policy=policy
    )
    if not result["qualified"]:
        raise RuntimeError("instrument_unqualified: confirmation forbidden")
    return result
