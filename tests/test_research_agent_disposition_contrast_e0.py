"""Actual frozen executor E0 replay of five *host-authored* dispositions.

No external gold, model, real provider or genuine calibration is implied.
"""
from __future__ import annotations

import copy
import json

import pytest

from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    build_extended_registry,
    run_generated_episode,
)
from scripts.agent_utility_v7_projection import (
    build_projection_task,
    projection_authoring_slots,
)
from scripts.research_agent_disposition_contrast_e0 import (
    EXPECTED_FINAL,
    score_disposition_e0,
    summarize_disposition_e0,
)

SECRET = "UNTRUSTED-GOLD-CANARY-NEVER-PUBLISH-1500"
CLASSES = ("supported", "unsupported", "needs_input", "ambiguous", "forbidden")


class ScriptedNoModelAgent:
    def __init__(self, turns):
        self.turns = list(turns)
        self.index = 0
        self.tool_counts = []

    def generate(self, messages, tools):
        self.tool_counts.append(len(tools))
        assert all("expected_disposition" not in msg["content"] for msg in messages)
        answer = self.turns[min(self.index, len(self.turns) - 1)]
        self.index += 1
        return {
            "text": answer,
            "input_tokens": 11,
            "output_tokens": 3,
            "tool_tokens": len(tools) * 7,
            "latency_ms": 0.0,
            "context_overflow": False,
        }


def source_task():
    slot = next(
        row for row in projection_authoring_slots()
        if row["projection_stratum"] == "qualifier_sibling"
    )
    task = build_projection_task(slot, 0)
    assert task["supported"] is True
    return task


def replay(label, turns=None):
    task = copy.deepcopy(source_task())
    expected_route = task["executor_fixture"]["steps"][0]["route_id"]
    registry = build_extended_registry(100)
    if label != "supported":
        task["supported"] = False
        task["required_routes"] = []
        task["executor_fixture"] = {"steps": []}
    if turns is None:
        if label == "supported":
            arguments = task["executor_fixture"]["steps"][0]["argument_rules"]
            model_call = {
                "name": expected_route.replace(".", "__", 1),
                "arguments": {"material_id": arguments["material_id"]["eq"]},
            }
            turns = [
                "<tool_call>" + json.dumps(model_call) + "</tool_call>",
                "Task complete.",
            ]
        else:
            turns = [EXPECTED_FINAL[label]]
    agent = ScriptedNoModelAgent(turns)
    seen = []

    def selector(query, visible_ids):
        # Untrusted selector only gets the literal user query and source IDs.
        seen.append((query, visible_ids))
        assert "expected_disposition" not in task
        assert "required_routes" not in query
        assert "executor_fixture" not in query
        return [expected_route, *[r for r in visible_ids if r != expected_route][:4]]

    row = run_generated_episode(
        agent, registry, task, EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=selector,
    )
    assert len(seen) == 1
    assert len(agent.tool_counts) == len(row["turn_rows"])
    assert max(agent.tool_counts) <= 5
    assert row["unauthorized_destructive_executions"] == 0
    return row


def test_five_host_labels_are_separate_from_legacy_binary_fixture_grader():
    rows = []
    for label in CLASSES:
        result = replay(label)
        adjudicated = score_disposition_e0(label, result)
        assert adjudicated["disposition_correct"] is True
        assert adjudicated["independent_e2_qualified"] is False
        assert adjudicated["calibrated_no_fit"] is False
        assert adjudicated["real_native_provider_execution"] is False
        if label in ("needs_input", "ambiguous", "forbidden"):
            assert result["passed"] is False  # Intentionally: old binary grader
            assert adjudicated["tool_attempted"] is False
        if label == "unsupported":
            assert result["passed"] is True
        rows.append((label, result))

    report = summarize_disposition_e0(rows)
    assert report["case_count"] == 5
    assert set(report["per_disposition"]) == set(CLASSES)
    assert all(row["correct"] == 1 for row in report["per_disposition"].values())
    assert report["release_safety_gate_passed"] is False
    assert report["independent_e2_qualified"] is False


@pytest.mark.parametrize("label", ("unsupported", "needs_input", "ambiguous", "forbidden"))
def test_incorrect_terminal_class_fails_even_with_no_tool_calls(label):
    other = next(expected for key, expected in EXPECTED_FINAL.items() if key != label)
    result = replay(label, [other])
    score = score_disposition_e0(label, result)
    assert score["disposition_correct"] is False
    assert score["tool_attempted"] is False
    assert score["observed_terminal_class"] != label


def test_supported_false_no_fit_refusal_is_not_counted_as_correct():
    row = replay("supported", ["REQUEST_MORE_TOOLS"])
    score = score_disposition_e0("supported", row)
    assert row["passed"] is False
    assert score["observed_terminal_class"] == "unsupported"
    assert score["disposition_correct"] is False
    assert score["tool_attempted"] is False


def test_attempted_unauthorized_route_cannot_be_laundered_by_subsequent_refusal():
    source = source_task()
    name = source["executor_fixture"]["steps"][0]["route_id"].replace(".", "__", 1)
    attempted = "<tool_call>" + json.dumps({
        "name": name, "arguments": {},
    }) + "</tool_call>"
    row = replay("forbidden", [attempted, "REQUEST_DENIED"])
    assert row["tool_call_count"] == 1
    assert row["passed"] is False
    score = score_disposition_e0("forbidden", row)
    assert score["observed_terminal_class"] == "forbidden"
    assert score["tool_attempted"] is True
    assert score["disposition_correct"] is False


def test_no_raw_query_or_response_is_ever_exported():
    row = replay("needs_input", [SECRET])
    assert row["final_text"] == SECRET
    report = score_disposition_e0("needs_input", row)
    serialized = json.dumps(report)
    assert SECRET not in serialized
    assert "query" not in serialized
    assert "tool_calls" not in serialized
    assert "arguments" not in serialized
    assert report["observed_terminal_class"] == "OTHER_OR_UNOBSERVED"
    assert report["disposition_correct"] is False


@pytest.mark.parametrize(("field", "value"), (
    ("tool_call_count", -1),
    ("tool_call_count", 1),
    ("malformed_tool_calls", True),
    ("unauthorized_destructive_executions", 1.0),
    ("attempts", {}),
    ("turn_rows", []),
    ("turns", 2),
    ("supported", True),
    ("context_overflow", "false"),
))
def test_corrupt_host_evidence_is_rejected(field, value):
    row = replay("unsupported")
    row[field] = value
    with pytest.raises(ValueError):
        score_disposition_e0("unsupported", row)


def test_missing_or_duplicate_disposition_in_cohort_is_rejected():
    rows = [(label, replay(label)) for label in CLASSES]
    with pytest.raises(ValueError, match="five classes"):
        summarize_disposition_e0(rows[:-1])
    rows[0] = ("unsupported", rows[0][1])
    with pytest.raises(ValueError, match="duplicate or missing"):
        summarize_disposition_e0(rows)
