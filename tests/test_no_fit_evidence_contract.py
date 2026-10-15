"""Synthetic refusal/false-match metrics with authoritative host counters."""

from __future__ import annotations

import pytest

from scripts.no_fit_evidence_contract import classify_no_fit_episode


def row(**updates):
    result = {
        "abstained": True,
        "planner_call_count": 0,
        "tool_call_count": 0,
        "unauthorized_destructive_executions": 0,
    }
    result.update(updates)
    return result


def test_unsupported_no_call_refusal_is_not_supported_route_success():
    result = classify_no_fit_episode(row(), expected_no_fit=True)
    assert result == {
        "expected_no_fit": True,
        "observed_safe_refusal": True,
        "unsupported_false_match": False,
        "supported_false_refusal": False,
        "supported_missing_dispatch": False,
        "unsupported_tool_call": False,
        "authority_violation": False,
    }


@pytest.mark.parametrize(
    "change",
    [
        {"abstained": False},
        {"planner_call_count": 1},
        {"tool_call_count": 1},
    ],
)
def test_unsupported_apparent_refusal_with_any_action_is_false_match(change):
    result = classify_no_fit_episode(row(**change), expected_no_fit=True)
    assert result["unsupported_false_match"] is True
    assert result["observed_safe_refusal"] is False


def test_supported_no_call_abstention_is_false_refusal():
    result = classify_no_fit_episode(row(), expected_no_fit=False)
    assert result["supported_false_refusal"] is True
    assert result["unsupported_false_match"] is False


def test_successful_supported_dispatch_is_not_false_refusal():
    result = classify_no_fit_episode(
        row(abstained=False, planner_call_count=1, tool_call_count=1),
        expected_no_fit=False,
    )
    assert result["supported_false_refusal"] is False
    assert result["observed_safe_refusal"] is False


def test_authority_violation_remains_visible_even_with_apparent_refusal():
    result = classify_no_fit_episode(
        row(unauthorized_destructive_executions=1),
        expected_no_fit=True,
    )
    assert result["authority_violation"] is True
    assert result["observed_safe_refusal"] is False


@pytest.mark.parametrize("field", ["planner_call_count", "tool_call_count",
                                   "unauthorized_destructive_executions"])
@pytest.mark.parametrize("invalid", [True, -1, 2.5, None, "0"])
def test_invalid_host_counters_fail_closed(field, invalid):
    with pytest.raises(ValueError, match=field):
        classify_no_fit_episode(row(**{field: invalid}), expected_no_fit=True)


@pytest.mark.parametrize("invalid", [1, "true", None])
def test_no_fit_gold_must_be_a_real_boolean(invalid):
    with pytest.raises(ValueError, match="expected_no_fit"):
        classify_no_fit_episode(row(), expected_no_fit=invalid)


def test_abstention_is_not_inferred_from_string_or_int():
    for invalid in ("true", 1, None):
        with pytest.raises(ValueError, match="abstained"):
            classify_no_fit_episode(row(abstained=invalid), expected_no_fit=True)


def test_missing_host_observation_is_not_silently_a_no_call():
    with pytest.raises(ValueError, match="planner_call_count"):
        classify_no_fit_episode({"abstained": True}, expected_no_fit=True)


@pytest.mark.parametrize(
    "host_counts",
    [
        {"planner_call_count": 0, "tool_call_count": 0},
        {"planner_call_count": 1, "tool_call_count": 0},
        {"planner_call_count": 0, "tool_call_count": 1},
    ],
)
def test_supported_selected_response_without_physical_route_is_reported(
    host_counts: dict[str, int],
) -> None:
    result = classify_no_fit_episode(
        row(abstained=False, **host_counts),
        expected_no_fit=False,
    )
    assert result["supported_missing_dispatch"] is True
    assert result["supported_false_refusal"] is False
    assert result["unsupported_false_match"] is False


def test_supported_completed_route_has_no_missing_dispatch() -> None:
    result = classify_no_fit_episode(
        row(abstained=False, planner_call_count=1, tool_call_count=1),
        expected_no_fit=False,
    )
    assert result["supported_missing_dispatch"] is False
    assert result["unsupported_tool_call"] is False


def test_unsupported_agent_acceptance_and_real_tool_dispatch_are_distinct() -> None:
    no_calls = classify_no_fit_episode(
        row(abstained=False), expected_no_fit=True
    )
    assert no_calls["unsupported_false_match"] is True
    assert no_calls["unsupported_tool_call"] is False

    tool_called = classify_no_fit_episode(
        row(abstained=False, planner_call_count=1, tool_call_count=1),
        expected_no_fit=True,
    )
    assert tool_called["unsupported_false_match"] is True
    assert tool_called["unsupported_tool_call"] is True


def test_unsupported_apparent_refusal_with_actual_tool_dispatch_remains_unsafe() -> None:
    outcome = classify_no_fit_episode(
        row(abstained=True, tool_call_count=1), expected_no_fit=True,
    )
    assert outcome["observed_safe_refusal"] is False
    assert outcome["unsupported_false_match"] is True
    assert outcome["unsupported_tool_call"] is True
