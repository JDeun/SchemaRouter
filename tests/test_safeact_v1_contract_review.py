"""Prevent evaluator/gold fields from entering V1 authoring worksheets."""

import json

import pytest

from scripts.prepare_safeact_v1_contract_review import review_worksheet


def _listing() -> dict:
    return {
        "case_count": 131,
        "tasks": [
            {
                "protocol": "v1",
                "case_id": f"SAB-V1-{i:03d}",
                "gold_decision": "ALLOW",
                "hidden_case_spec_sha256": "confidential",
                "evaluator_requirements": {"owner": "hidden"},
                "private_data": {"should_not_copy": True},
            }
            for i in range(1, 132)
        ],
    }


def test_public_ids_only_never_copy_private_task_fields() -> None:
    worksheet = review_worksheet(_listing())
    assert len(worksheet["case_coverage"]) == 131
    assert set(worksheet["case_coverage"].values()) == {None}
    assert worksheet["contracts"] == []
    assert worksheet["scored_run_authorized"] is False
    serialized = json.dumps(worksheet)
    for forbidden in ("gold_decision", "confidential", "should_not_copy", "ALLOW"):
        assert forbidden not in serialized


def test_rejects_duplicates_and_non_v1_tasks() -> None:
    data = _listing()
    data["tasks"][0]["case_id"] = data["tasks"][1]["case_id"]
    with pytest.raises(ValueError, match="duplicate"):
        review_worksheet(data)
    data = _listing()
    data["tasks"][0]["protocol"] = "v2"
    with pytest.raises(ValueError, match="non-V1"):
        review_worksheet(data)


def test_rejects_incomplete_or_forged_case_ids() -> None:
    data = _listing()
    data["tasks"].pop()
    with pytest.raises(ValueError, match="131"):
        review_worksheet(data)
    data = _listing()
    data["tasks"][0]["case_id"] = "../private/labels.json"
    with pytest.raises(ValueError, match="invalid public case ID"):
        review_worksheet(data)
