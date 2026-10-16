"""No-model E0 boundary tests for one opt-in future integrated agent comparator.

These do not certify ranking accuracy, independent task authorship, or host
permission. They verify the original agent executor can exercise a bounded,
source-registered new route selector without modifying frozen conditions.
"""
from __future__ import annotations

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


class ScriptedAgent:
    def __init__(self, turns: list[str]) -> None:
        self.turns = turns
        self.index = 0
        self.visible_tool_counts: list[int] = []

    def generate(self, messages, tools):
        del messages
        self.visible_tool_counts.append(len(tools))
        text = self.turns[min(self.index, len(self.turns) - 1)]
        self.index += 1
        return {
            "text": text,
            "input_tokens": 9,
            "tool_tokens": 6,
            "output_tokens": 4,
            "latency_ms": 0.0,
            "context_overflow": False,
        }


def task():
    slot = next(
        item for item in projection_authoring_slots()
        if item["projection_stratum"] == "qualifier_sibling"
    )
    return build_projection_task(slot, 0)


def transcript(source_task):
    step = source_task["executor_fixture"]["steps"][0]
    payload = {
        "name": step["route_id"].replace(".", "__", 1),
        "arguments": {
            "material_id": step["argument_rules"]["material_id"]["eq"],
        },
    }
    return [
        "<tool_call>" + json.dumps(payload) + "</tool_call>",
        "Done.",
    ]


def test_one_step_end_to_end_supported_task_uses_new_fixed_five_exposure():
    source_task = task()
    expected = source_task["executor_fixture"]["steps"][0]["route_id"]
    seen = []

    def choose(query: str, route_names: tuple[str, ...]) -> list[str]:
        seen.append((query, route_names))
        assert query == source_task["query"]
        assert len(route_names) == 100
        assert expected in route_names
        return [expected, *[route for route in route_names if route != expected][:4]]

    agent = ScriptedAgent(transcript(source_task))
    result = run_generated_episode(
        agent, build_extended_registry(100), source_task,
        EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=choose,
    )
    assert len(seen) == 1
    assert result["passed"] is True
    assert result["task_complete"] is True
    assert result["initial_candidate_count"] == 5
    assert result["candidate_condition"] == EXPERIMENTAL_FIXED5_CONDITION
    assert result["unauthorized_destructive_executions"] == 0
    assert result["required_route_call_coverage"] == 1.0
    assert max(agent.visible_tool_counts) == 5
    assert result["tool_call_count"] == 1


def test_missing_required_route_is_an_observed_agent_failure_not_repaired():
    source_task = task()
    expected = source_task["executor_fixture"]["steps"][0]["route_id"]
    agent = ScriptedAgent(transcript(source_task))
    row = run_generated_episode(
        agent, build_extended_registry(100), source_task,
        EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=lambda _query, ids: [
            route for route in ids if route != expected
        ][:5],
    )
    assert row["initial_required_route_miss"] is True
    assert row["passed"] is False
    assert row["required_route_call_coverage"] == 0
    assert row["tool_call_count"] == 1
    assert row["attempts"][0]["error"] == "unavailable_tool"


def test_unsupported_request_can_make_safe_no_call_not_calibrated_no_fit():
    source_task = task()
    source_task["supported"] = False
    source_task["required_routes"] = []
    source_task["executor_fixture"] = {"steps": []}
    agent = ScriptedAgent(["REQUEST_MORE_TOOLS"])
    row = run_generated_episode(
        agent, build_extended_registry(100), source_task,
        EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=lambda _query, _ids: [],
    )
    assert row["passed"] is True
    assert row["tool_call_count"] == 0
    assert row["initial_candidate_count"] == 0
    assert row["unauthorized_destructive_executions"] == 0
    # Synthetic no-call correctness is not evidence that a model knows no-fit.


@pytest.mark.parametrize("choice", (
    ["unknown.endpoint"],
    ["a", "a"],
    ["a", "b", "c", "d", "e", "f"],
    "a",
    [None],
))
def test_forgeries_duplicates_over_budget_and_wrong_shape_are_rejected(choice):
    registry = build_extended_registry(100)
    ids = sorted(
        f"{tool.key}.{ep.name}"
        for tool in registry.tools() for ep in tool.endpoints
    )
    if isinstance(choice, list):
        choice = [ids[int(letter == "b") % len(ids)] if letter in ("a", "b")
                  else (ids[0] if letter in ("c", "d", "e", "f") else letter)
                  for letter in choice]
    with pytest.raises(ValueError, match="invalid experimental source-native"):
        run_generated_episode(
            ScriptedAgent(["REQUEST_MORE_TOOLS"]),
            registry, task(), EXPERIMENTAL_FIXED5_CONDITION,
            experimental_candidate_selector=lambda _query, _ids: choice,
        )


def test_selector_may_not_mutate_source_catalog():
    registry = build_extended_registry(100)

    def change_catalog(query, routes):
        del query
        registry.update_many([])  # may not increment a version; add real route
        from benchmarks.agent_utility_b2_catalog import _distractor_endpoint
        registry.register(_distractor_endpoint(999999))
        return list(routes[:5])

    with pytest.raises(ValueError, match="experimental source changed"):
        run_generated_episode(
            ScriptedAgent(["REQUEST_MORE_TOOLS"]),
            registry, task(), EXPERIMENTAL_FIXED5_CONDITION,
            experimental_candidate_selector=change_catalog,
        )


def test_frozen_conditions_cannot_use_new_hook_or_be_replaced_by_it():
    registry = build_extended_registry(100)
    callback = lambda _query, ids: list(ids[:5])
    for condition in ("FULL", "SR-5", "SR-10", "SR-PROGRESSIVE", "ORACLE"):
        with pytest.raises(ValueError, match="isolated fixed5"):
            run_generated_episode(
                ScriptedAgent(["REQUEST_MORE_TOOLS"]),
                registry, task(), condition,
                experimental_candidate_selector=callback,
            )
    with pytest.raises(ValueError, match="requires explicit selector"):
        run_generated_episode(
            ScriptedAgent(["REQUEST_MORE_TOOLS"]),
            registry, task(), EXPERIMENTAL_FIXED5_CONDITION,
        )
    with pytest.raises(ValueError, match="isolated fixed5"):
        run_generated_episode(
            ScriptedAgent(["REQUEST_MORE_TOOLS"]),
            registry, task(), EXPERIMENTAL_FIXED5_CONDITION,
            candidate_condition="ORACLE",
            experimental_candidate_selector=callback,
        )
