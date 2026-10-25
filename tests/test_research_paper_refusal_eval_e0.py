"""Contract tests for opt-in E0 refusal evaluation."""
import pytest

from scripts.research_paper_refusal_eval_e0 import Case, decision_from_plan_status, evaluate

@pytest.mark.parametrize(("status", "decision"), [
    ("ready", "offer"), ("requires_arguments", "request_arguments"),
    ("requires_observation", "request_observation"),
    ("no_proven_hit", "abstain"), ("over_k_unranked", "abstain"),
    ("budget_unsatisfied", "abstain"), ("ambiguous_paths", "abstain"),
])
def test_plan_status_mapping(status, decision):
    assert decision_from_plan_status(status) == decision

def test_unknown_status_rejected():
    with pytest.raises(ValueError):
        decision_from_plan_status("globally_nonexistent")

def test_separate_denominators_and_deferred():
    cases = (
        Case("s1", "ko", "supported", "abstain", True),
        Case("s2", "en", "supported", "request_observation", True),
        Case("u1", "ja", "unsupported", "offer", True),
        Case("u2", "ko", "unsupported", "request_arguments", True),
        Case("x", "ja", "unresolved", "abstain", False),
    )
    m = evaluate(cases)
    assert (m["all"].false_refusal_rate, m["all"].false_accept_rate) == (0.5, 0.5)
    assert (
        m["all"].supported_deferred, m["all"].unsupported_deferred, m["all"].unresolved
    ) == (1, 1, 1)
    assert m["ko"].false_refusal == 1
    assert m["ja"].false_accept == 1

def test_unverified_resolved_gold_rejected():
    with pytest.raises(ValueError):
        evaluate((Case("x", "ko", "unsupported", "abstain", False),))

def test_duplicate_case_rejected():
    c = Case("x", "en", "supported", "offer", True)
    with pytest.raises(ValueError):
        evaluate((c, c))

def test_no_denominator_reports_none():
    metrics = evaluate((Case("x", "ja", "unresolved", "abstain", False),))
    assert metrics["all"].false_accept_rate is None
