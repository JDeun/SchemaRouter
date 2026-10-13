"""No-gold regressions for the unreviewed domain-scoped review queue."""

from __future__ import annotations

import copy
import json

import pytest

from scripts.inventory_safeact_v1_public_tools import PINNED_REVISION
from scripts.prepare_safeact_v1_review_queue import build_review_queue


def _listing() -> dict:
    return {
        "case_count": 131,
        "tasks": [
            {
                "case_id": f"SAB-V1-{index:03d}",
                "protocol": "v1",
                "expected_action": "hidden_wrong_target",
                "gold_decision": "ALLOW",
            }
            for index in range(1, 132)
        ],
    }


def _inventory() -> dict:
    return {
        "kind": "safeact_v1_public_tool_filename_inventory_only",
        "upstream_revision": PINNED_REVISION,
        "human_reviewed": False,
        "independently_authored_contracts": False,
        "scored_experiment": False,
        "policy_candidates_are_contracts": False,
        "forbidden_sources_read": False,
        "tools": [
            {
                "domain": domain,
                "tool_name": "reply_send",
                "source_path": f"templates/{domain}/tools/reply_send.py",
                "source_sha256": "a" * 64,
                "gold_hint": "must_not_copy",
            }
            for domain in ("customer_policy_qa", "legal_finance_advice")
        ],
        "public_policy_candidates": [{
            "domain": "customer_policy_qa",
            "source_path": (
                "templates/customer_policy_qa/world/policies/refunds.md"
            ),
            "source_sha256": "b" * 64,
        }],
    }


def test_same_named_tools_are_separate_unapproved_domain_candidates() -> None:
    result = build_review_queue(_listing(), _inventory())
    assert len(result["case_coverage"]) == 131
    assert set(result["case_coverage"].values()) == {None}
    assert len(result["public_tool_candidates"]) == 2
    assert result["action_contracts"] == []
    assert result["human_policy_author_reviewed"] is False
    assert result["independent_reviewer_approved"] is False
    assert result["scored_run_authorized"] is False
    assert result["model_calls"] == 0
    assert {x["domain"] for x in result["public_tool_candidates"]} == {
        "customer_policy_qa", "legal_finance_advice"
    }
    encoded = json.dumps(result)
    for forbidden in ("hidden_wrong_target", "gold_decision", "must_not_copy"):
        assert forbidden not in encoded


@pytest.mark.parametrize("field", ["human_reviewed", "scored_experiment"])
def test_approved_looking_source_inventory_is_refused(field: str) -> None:
    inventory = _inventory()
    inventory[field] = True
    with pytest.raises(ValueError, match="untrusted"):
        build_review_queue(_listing(), inventory)


def test_forbidden_path_and_duplicate_scope_fail_closed() -> None:
    inventory = _inventory()
    inventory["tools"][0]["source_path"] = "env/case_manifest.json"
    with pytest.raises(ValueError, match="non-public tool"):
        build_review_queue(_listing(), inventory)
    duplicate = _inventory()
    duplicate["tools"].append(copy.deepcopy(duplicate["tools"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        build_review_queue(_listing(), duplicate)


def test_policy_cannot_escape_public_domain_directory() -> None:
    inventory = _inventory()
    inventory["public_policy_candidates"][0][
        "source_path"
    ] = "templates/legal_finance_advice/world/policies/refunds.md"
    with pytest.raises(ValueError, match="non-public policy"):
        build_review_queue(_listing(), inventory)


def test_wrong_case_count_is_rejected() -> None:
    listing = _listing()
    listing["tasks"] = listing["tasks"][:-1]
    with pytest.raises(ValueError, match="131"):
        build_review_queue(listing, _inventory())
