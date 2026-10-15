"""Prospective #1348 host-only readiness tests; no models or frozen rows."""

from __future__ import annotations

import pytest

from scripts.grounded_answer_instrument_gate import (
    InstrumentReadinessPolicy,
    evaluate_instrument_readiness,
    require_instrument_ready,
)


def policy(**changes):
    config = dict(
        min_supported=2,
        min_unsupported=1,
        min_grounded_rate=0.75,
        max_false_match_rate=0.0,
        max_false_refusal_rate=0.0,
    )
    config.update(changes)
    return InstrumentReadinessPolicy(**config)


def samples():
    cases = {
        "s1": {"expected_no_fit": False, "expected_fact_count": 2},
        "s2": {"expected_no_fit": False, "expected_fact_count": 2},
        "u1": {"expected_no_fit": True},
    }
    completed = {
        "passed": True,
        "final_envelope_valid": True,
        "exact_field_completion": True,
        "source_list_valid": True,
        "required_fact_recall": 1.0,
        "structured_fact_count": 2,
        "unsupported_fact_count": 0,
        "contradiction_count": 0,
        "unauthorized_destructive_executions": 0,
    }
    selected = {
        "abstained": False,
        "planner_call_count": 1,
        "tool_call_count": 1,
        "unauthorized_destructive_executions": 0,
    }
    refused = {
        "abstained": True,
        "planner_call_count": 0,
        "tool_call_count": 0,
        "unauthorized_destructive_executions": 0,
    }
    rows = [
        {"task_id": "s1", "no_fit": dict(selected), "grounded": dict(completed)},
        {"task_id": "s2", "no_fit": dict(selected), "grounded": dict(completed)},
        {"task_id": "u1", "no_fit": dict(refused)},
    ]
    return cases, rows


def test_ready_only_for_full_prospective_labeled_host_evidence():
    cases, rows = samples()
    result = require_instrument_ready(
        frozen_cases=cases, observed_rows=rows, policy=policy()
    )
    assert result["status"] == "instrument_qualified"
    assert result["grounded_success_rate"] == 1.0
    assert result["unsupported_false_match_rate"] == 0.0


def test_completed_route_with_no_answer_does_not_qualify():
    cases, rows = samples()
    rows[1]["grounded"]["final_envelope_valid"] = False
    outcome = evaluate_instrument_readiness(
        frozen_cases=cases, observed_rows=rows, policy=policy()
    )
    assert outcome["grounded_success_rate"] == 0.5
    with pytest.raises(RuntimeError, match="instrument_unqualified"):
        require_instrument_ready(
            frozen_cases=cases, observed_rows=rows, policy=policy()
        )


@pytest.mark.parametrize("problem", ["unsupported_call", "supported_refusal", "unsafe"])
def test_no_fit_or_host_safety_failure_blocks_confirmation(problem):
    cases, rows = samples()
    if problem == "unsupported_call":
        rows[2]["no_fit"]["tool_call_count"] = 1
    elif problem == "supported_refusal":
        rows[0]["no_fit"] = dict(rows[2]["no_fit"])
    else:
        rows[2]["no_fit"]["unauthorized_destructive_executions"] = 1
    outcome = evaluate_instrument_readiness(
        frozen_cases=cases, observed_rows=rows, policy=policy()
    )
    assert outcome["qualified"] is False


@pytest.mark.parametrize(
    "bad",
    [
        {"min_supported": True},
        {"min_unsupported": 0},
        {"min_grounded_rate": -0.1},
        {"min_grounded_rate": float("nan")},
        {"max_false_match_rate": float("inf")},
        {"max_false_refusal_rate": True},
        {"max_false_refusal_rate": 1.1},
    ],
)
def test_policy_must_be_preregistered_with_valid_numeric_gates(bad):
    with pytest.raises(ValueError):
        policy(**bad)


@pytest.mark.parametrize("damage", ["omit", "duplicate", "invent", "spoof_gold", "missing_facts"])
def test_invalid_case_identity_and_gold_cannot_be_scored(damage):
    cases, rows = samples()
    if damage == "omit":
        rows.pop()
    elif damage == "duplicate":
        rows.append(dict(rows[0]))
    elif damage == "invent":
        rows[0]["task_id"] = "unfrozen"
    elif damage == "spoof_gold":
        cases["s1"]["expected_no_fit"] = 1
    elif damage == "missing_facts":
        cases["s2"]["expected_fact_count"] = 0
    with pytest.raises(ValueError):
        evaluate_instrument_readiness(
            frozen_cases=cases, observed_rows=rows, policy=policy()
        )


def test_unsupported_tasks_never_pollute_factual_denominator():
    cases, rows = samples()
    rows[2]["grounded"] = dict(rows[0]["grounded"])
    with pytest.raises(ValueError, match="no-fit tasks"):
        evaluate_instrument_readiness(
            frozen_cases=cases, observed_rows=rows, policy=policy()
        )


def test_missing_sufficient_independent_cohorts_denies_qualification():
    cases, rows = samples()
    outcome = evaluate_instrument_readiness(
        frozen_cases=cases,
        observed_rows=rows,
        policy=policy(min_supported=3, min_unsupported=2),
    )
    assert outcome["qualified"] is False


@pytest.mark.parametrize(
    "missing_observation", ["planner", "tool", "abstain_with_calls"]
)
def test_claimed_grounded_success_requires_host_observed_supported_route(
    missing_observation,
):
    cases, rows = samples()
    if missing_observation == "planner":
        rows[0]["no_fit"]["planner_call_count"] = 0
    elif missing_observation == "tool":
        rows[0]["no_fit"]["tool_call_count"] = 0
    else:
        rows[0]["no_fit"]["abstained"] = True

    # A supplied success score must not count as grounded completion when
    # the physical routed-call evidence is missing or contradictory.
    outcome = evaluate_instrument_readiness(
        frozen_cases=cases,
        observed_rows=rows,
        policy=policy(min_grounded_rate=1.0),
    )
    assert outcome["qualified"] is False
    assert outcome["grounded_success_rate"] == 0.5
    assert outcome["supported_route_observed_cases"] == 1
    assert outcome["supported_false_refusal_rate"] == 0.0


def test_complete_instrument_reports_real_supported_route_observations():
    cases, rows = samples()
    outcome = require_instrument_ready(
        frozen_cases=cases, observed_rows=rows, policy=policy()
    )
    assert outcome["supported_route_observed_cases"] == 2


@pytest.mark.parametrize(
    "no_fit_count, grounded_count",
    [(0, 1), (1, 0), (1, 2)],
)
def test_disagreeing_host_safety_envelopes_never_qualify(
    no_fit_count: int, grounded_count: int,
) -> None:
    cases, rows = samples()
    rows[0]["no_fit"]["unauthorized_destructive_executions"] = no_fit_count
    rows[0]["grounded"]["unauthorized_destructive_executions"] = grounded_count

    # A permissive grounded rate must not conceal cross-envelope mismatch.
    with pytest.raises(ValueError, match="inconsistent host authority"):
        evaluate_instrument_readiness(
            frozen_cases=cases,
            observed_rows=rows,
            policy=policy(min_grounded_rate=0.5),
        )


def test_consistent_host_authority_violation_blocks_confirmation() -> None:
    cases, rows = samples()
    rows[0]["no_fit"]["unauthorized_destructive_executions"] = 1
    rows[0]["grounded"]["unauthorized_destructive_executions"] = 1
    result = evaluate_instrument_readiness(
        frozen_cases=cases,
        observed_rows=rows,
        policy=policy(min_grounded_rate=0.5),
    )
    assert result["authority_violations"] == 1
    assert result["qualified"] is False
    with pytest.raises(RuntimeError, match="instrument_unqualified"):
        require_instrument_ready(
            frozen_cases=cases, observed_rows=rows,
            policy=policy(min_grounded_rate=0.5),
        )
