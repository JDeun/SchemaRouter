"""Official V1 routing-only arm executes the actual typed registry boundary."""

import copy
from types import SimpleNamespace

import pytest

from examples.external_validation.safeact_v1 import official_routing_hook as hook


def _scenario() -> dict:
    return {
        "env_id": "customer_policy_qa",
        "candidate_action": {
            "tool": "refund_issue",
            "args": {"charge_id": "C2"},
            "action_properties": {},
        },
    }


def _record(tool: str = "refund_issue", arguments=None) -> dict:
    return {
        "events": [
            {
                "type": "INFO_CALL",
                "tool": "charge_read",
                "arguments": {"charge_id": "C2"},
            },
            {
                "type": "CONSEQUENTIAL_CALL",
                "tool": tool,
                "arguments": arguments if arguments is not None else {"charge_id": "C2"},
            },
        ],
        "metadata": {},
    }


def test_valid_public_candidate_route_is_preserved() -> None:
    original = _record()
    result = hook.route_public_v1_record(
        original, scenario=_scenario(), case_id="SAB-V1-001"
    )
    assert result["events"] == original["events"]
    assert original["metadata"] == {}
    marker = result["metadata"]["schemarouter_intervention"]
    assert marker["kind"] == "schemarouter_typed_route"
    assert marker["authorized_action_dispatches"] == 1
    assert marker["denied_action_attempts"] == 0
    assert len(marker["typed_tool_fingerprint"]) == 64
    assert marker["evaluator_data_used"] is False


def test_mismatched_target_is_rejected_without_touching_info() -> None:
    result = hook.route_public_v1_record(
        _record("delete_account"), scenario=_scenario(), case_id="SAB-V1-001"
    )
    assert len(result["events"]) == 1
    assert result["events"][0]["type"] == "INFO_CALL"
    marker = result["metadata"]["schemarouter_intervention"]
    assert marker["model_action_attempts"] == 1
    assert marker["denied_action_attempts"] == 1
    assert marker["authorized_action_dispatches"] == 0


def test_missing_tool_and_multi_action_fail_closed() -> None:
    s = copy.deepcopy(_scenario())
    del s["candidate_action"]
    with pytest.raises(ValueError, match="candidate"):
        hook.route_public_v1_record(_record(), scenario=s, case_id="SAB-V1-001")
    broken = _record()
    broken["events"].append(copy.deepcopy(broken["events"][-1]))
    with pytest.raises(ValueError, match="multiple"):
        hook.route_public_v1_record(broken, scenario=_scenario(), case_id="SAB-V1-001")


def test_missing_or_malformed_action_arguments_denied() -> None:
    record = _record()
    record["events"][-1]["arguments"] = "not-an-object"
    outcome = hook.route_public_v1_record(
        record, scenario=_scenario(), case_id="SAB-V1-001"
    )
    assert outcome["metadata"]["schemarouter_intervention"]["denied_action_attempts"] == 1


def test_upstream_normalizer_remains_the_source_of_all_info_events() -> None:
    def normalized(*_args):
        return _record()

    official = SimpleNamespace(normalize_v1=normalized)
    hook.install_v1_routing(official, case_id="SAB-V1-001")
    rec = official.normalize_v1(_scenario(), {}, [], "codex", "fixed", "", None)
    assert rec["events"][0]["type"] == "INFO_CALL"
    assert rec["metadata"]["schemarouter_intervention"]["kind"] == (
        "schemarouter_typed_route"
    )


def test_routing_ablation_does_not_claim_real_action_execution() -> None:
    result = route_public_v1_record(
        {
            "events": [{
                "type": "CONSEQUENTIAL_CALL", "tool": "refund_issue",
                "arguments": {"charge_id": "C2"},
            }],
            "metadata": {},
        },
        scenario={
            "candidate_action": {"tool": "refund_issue", "args": {"charge_id": "C2"}}
        },
        case_id="SAB-V1-001",
    )
    marker = result["metadata"]["schemarouter_intervention"]
    assert marker["action_effect_boundary"] == "normalized_record_only"
    assert marker["physical_action_execution_observed"] is False
