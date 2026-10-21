"""Exact-pinned negative E1 provenance checks; never retrospective performance claims."""
from __future__ import annotations

import copy
import json

import pytest

from scripts.verify_research_qwen_e1_negative import SOURCE, verify


def _data():
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def test_archived_actual_provider_result_is_negative_and_bounded():
    data = _data()
    checked = verify(data)
    assert checked["decision"] == "VALID_NEGATIVE_NO_STRICT_TASK_PASS_UPLIFT"
    assert checked["independent_e2_qualified"] is False
    assert checked["arms"]["original"] == {
        "strict_tasks_passed": 0, "http_attempts": 6,
        "model_turns": 8, "host_reminders": 0,
    }
    assert checked["arms"]["one_verified_reminder"] == {
        "strict_tasks_passed": 0, "http_attempts": 6,
        "model_turns": 7, "host_reminders": 1,
    }
    serialized = json.dumps(checked, ensure_ascii=False)
    assert "latitude" not in serialized
    assert "temperature_2m" not in serialized
    assert "observed_at" not in serialized


@pytest.mark.parametrize(("section", "key", "value"), (
    ("run", "artifact_zip_sha256", "0" * 64),
    ("run", "report_json_sha256", "0" * 64),
    ("run", "workflow_run_id", True),
    ("runtime", "model_revision", "unreviewed"),
    ("study", "total_http_attempt_ceiling", 100),
    ("gates", "independent_e2_qualified", True),
    ("gates", "release_qualified", True),
    ("original", "strict_tasks_passed", 1),
    ("original", "host_reminders", 1),
    ("candidate", "strict_tasks_passed", 3),
    ("candidate", "model_turns", 99),
    ("candidate", "tool_tokens", 999999),
    ("candidate", "model_generation_ms", float("nan")),
))
def test_reject_fake_provenance_unsafe_upgrade_or_inconsistent_aggregates(
    section, key, value,
):
    data = _data()
    if section == "original":
        row = data["by_arm"]["original"]
    elif section == "candidate":
        row = data["by_arm"]["one_verified_reminder"]
    else:
        row = data[section]
    row[key] = value
    with pytest.raises(ValueError):
        verify(data)


def test_reject_model_output_or_source_value_in_allowlisted_trace():
    data = _data()
    row = data["by_arm"]["original"]["by_language"]["en"]
    row["raw_model_text"] = "PRIVATE_PROMPT_CANARY"
    with pytest.raises(ValueError, match="unallowlisted row"):
        verify(data)
    assert "PRIVATE_PROMPT_CANARY" not in json.dumps(verify(_data()))


def test_reject_missing_or_duplicated_task_cohort():
    data = _data()
    del data["by_arm"]["one_verified_reminder"]["by_language"]["ko"]
    with pytest.raises(ValueError, match="incomplete paired"):
        verify(data)
    data = _data()
    data["by_arm"]["original"]["by_language"]["fr"] = copy.deepcopy(
        data["by_arm"]["original"]["by_language"]["en"]
    )
    with pytest.raises(ValueError, match="incomplete paired"):
        verify(data)


def test_reject_fake_recovered_second_tool_or_ineligible_reminder():
    data = _data()
    data["by_arm"]["one_verified_reminder"]["by_language"]["en"]["forecasts"] = 1
    with pytest.raises(ValueError):
        verify(data)
    data = _data()
    data["by_arm"]["one_verified_reminder"]["by_language"]["ko"]["host_reminders"] = 1
    with pytest.raises(ValueError):
        verify(data)


def test_reject_transport_timeout_masked_as_model_improvement():
    data = _data()
    row = data["by_arm"]["one_verified_reminder"]["by_language"]["ko"]
    row["transport_failure"] = None
    with pytest.raises(ValueError):
        verify(data)
