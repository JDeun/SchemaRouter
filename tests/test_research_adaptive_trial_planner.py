"""Offline guard tests for automatically generated, unscored research proposals."""
from __future__ import annotations

import copy
import json

import pytest

from scripts.research_adaptive_trial_planner import (
    MARKER, END, candidate_configs, digest, issue_comment, load_evidence,
    load_policy, make_proposal, proposals_from_comments,
)


def test_real_policy_and_seed_produce_a_new_nonhardcoded_configuration() -> None:
    policy, evidence = load_policy(), load_evidence()
    configs = list(candidate_configs(policy))
    assert len(configs) == 48
    assert len({digest(c) for c in configs}) == 48
    report = make_proposal(policy, evidence, set())
    assert report["status"] == "NEW_RESEARCH_PROPOSAL"
    assert report["search_space_count"] == 48
    assert report["may_score"] is False
    assert report["may_promote"] is False
    assert report["may_release"] is False
    new, = report["new_proposals"]
    assert new["config"] in configs
    assert new["executor"] == "REVIEW_AND_REGISTER_PINNED_EXECUTOR"
    assert new["basis"]["split"] == "development"
    assert new["hypothesis_only"] is True


def test_development_failure_profile_changes_next_generated_hypothesis() -> None:
    policy, evidence = load_policy(), load_evidence()
    first = make_proposal(policy, evidence, set())["new_proposals"][0]["config"]
    changed = copy.deepcopy(evidence)
    changed["failure_counts"] = {
        "supported_route_miss": 0,
        "unsupported_false_accept": 54,
        "wrong_operation": 60,
        "supported_false_refusal": 0,
    }
    second = make_proposal(policy, changed, set())["new_proposals"][0]["config"]
    assert first != second
    assert second["no_fit"] == "explicit_negative_veto"
    assert second["operation_filter"] == "advisory_contrastive"


def test_bot_proposal_receipt_is_idempotent_and_pending_budget_pauses() -> None:
    policy, evidence = load_policy(), load_evidence()
    first = make_proposal(policy, evidence, set())
    body = issue_comment(first)
    assert "PROPOSED, NOT RUN" in body
    comments = [[{"user": {"login": "github-actions[bot]"}, "body": body}]]
    ids = proposals_from_comments(comments)
    assert ids == {first["new_proposals"][0]["config_sha256"]}
    second = make_proposal(policy, evidence, ids)
    assert second["new_proposals"][0]["config_sha256"] not in ids
    other = second["new_proposals"][0]["config_sha256"]
    paused = make_proposal(policy, evidence, ids | {other})
    assert paused["status"] == "PAUSED_UNMEASURED_PROPOSALS"
    assert paused["new_proposals"] == []
    with pytest.raises(ValueError):
        issue_comment(paused)


def test_human_receipt_does_not_suppress_generator() -> None:
    doc = {"config_sha256": "0" * 64, "status": "PROPOSED_UNMEASURED", "issue": 1412}
    content = MARKER + json.dumps(doc) + END
    assert proposals_from_comments(
        [{"user": {"login": "an-untrusted-user"}, "body": content}]
    ) == set()


@pytest.mark.parametrize("value", [
    {"config_sha256": "0" * 64, "status": "SCORED", "issue": 1412},
    {"config_sha256": "0" * 64, "status": "PROPOSED_UNMEASURED", "issue": 1346},
    {"config_sha256": "not-a-digest", "status": "PROPOSED_UNMEASURED", "issue": 1412},
    {"config_sha256": "0" * 64, "status": "PROPOSED_UNMEASURED", "issue": True},
])
def test_forged_bot_authority_fails_closed(value: dict) -> None:
    content = MARKER + json.dumps(value) + END
    with pytest.raises(ValueError):
        proposals_from_comments(
            [{"user": {"login": "github-actions[bot]"}, "body": content}]
        )


@pytest.mark.parametrize("field,value", [
    ("execution", "allow_model_execution"),
    ("qualification", "dev_counts_as_independent"),
    ("max_pending_proposals", 100),
    ("targets", {}),
])
def test_escalated_policy_rejected(tmp_path, field: str, value: object) -> None:
    policy = copy.deepcopy(load_policy())
    policy[field] = value
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy))
    with pytest.raises(ValueError):
        load_policy(path)


@pytest.mark.parametrize("field,value", [
    ("split", "heldout"),
    ("independent_qualification", True),
    ("source", "https://example.com/untrusted"),
    ("run_ids", [True]),
    ("failure_counts", {"supported_route_miss": -1}),
])
def test_invalid_evidence_rejected(tmp_path, field: str, value: object) -> None:
    seed = copy.deepcopy(load_evidence())
    seed[field] = value
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(seed))
    with pytest.raises(ValueError):
        load_evidence(path)


def test_evidence_never_certifies_product_target_or_release() -> None:
    p = load_policy()
    e = load_evidence()
    e["failure_counts"] = {k: 0 for k in e["failure_counts"]}
    report = make_proposal(p, e, set())
    assert report["status"] == "NEW_RESEARCH_PROPOSAL"
    assert report["may_score"] is False
    assert report["may_promote"] is False
    assert report["may_release"] is False
