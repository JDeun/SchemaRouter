"""Cross-stage, no-model E0 failure matrix through the ORIGINAL #1477 agent loop.

These cases run the existing FrozenCorpusExecutor; they do not attest a model,
independently authored tasks, private gold, provider invocation or real E2.
"""
from __future__ import annotations

import json
from typing import Any

from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    build_extended_registry,
    run_generated_episode,
)
from scripts.agent_utility_v7_projection import (
    build_projection_task,
    projection_authoring_slots,
)
from scripts.research_agent_stage_evidence_e0 import (
    observed_stages,
    sanitized_e0_jsonl,
)


class ScriptedAgent:
    def __init__(self, outputs: list[str]):
        self.outputs = outputs
        self.calls = 0
        self.max_tools = 0

    def generate(
        self, messages: list[dict[str, str]], tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        del messages
        self.max_tools = max(self.max_tools, len(tools))
        result = self.outputs[min(self.calls, len(self.outputs) - 1)]
        self.calls += 1
        return {
            "text": result,
            "input_tokens": 20,
            "tool_tokens": 8,
            "output_tokens": 12,
            "latency_ms": 0.0,
            "context_overflow": False,
        }


def _task(kind: str = "qualifier_sibling") -> dict[str, Any]:
    slot = next(
        item for item in projection_authoring_slots()
        if item["projection_stratum"] == kind
    )
    return build_projection_task(slot, 1 if kind == "multi_step_provenance" else 0)


def _call(route: str, arguments: dict[str, Any]) -> str:
    return "<tool_call>" + json.dumps({
        "name": route.replace(".", "__", 1), "arguments": arguments,
    }) + "</tool_call>"


def _run(
    task: dict[str, Any], outputs: list[str], chosen: list[str],
) -> tuple[dict[str, Any], ScriptedAgent]:
    agent = ScriptedAgent(outputs)
    registry = build_extended_registry(100)
    row = run_generated_episode(
        agent, registry, task, EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=lambda query, ids: (
            chosen if query == task["query"] and set(chosen).issubset(ids) else []
        ),
    )
    assert row["condition"] == EXPERIMENTAL_FIXED5_CONDITION
    assert row["candidate_history"] == [sorted(chosen)]
    assert row["initial_candidate_count"] <= 5
    assert agent.max_tools <= 5
    assert row["unauthorized_destructive_executions"] == 0
    return row, agent


def _safe_wrong_route(task: dict[str, Any]) -> str:
    registry = build_extended_registry(100)
    expected = {step["route_id"] for step in task["executor_fixture"]["steps"]}
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            name = f"{tool.key}.{endpoint.name}"
            if (
                name not in expected
                and not endpoint.destructive
                and not any(parameter.required for parameter in endpoint.parameters)
                and not endpoint.input_schema.get("required")
            ):
                return name
    raise AssertionError("fixed fixture has no safe zero-argument wrong-operation route")


def test_supported_false_refusal_is_not_counted_as_successful_no_fit():
    task = _task()
    route = task["executor_fixture"]["steps"][0]["route_id"]
    row, agent = _run(task, ["REQUEST_MORE_TOOLS"], [route])
    assert agent.calls == 1
    assert row["initial_required_route_miss"] is False
    assert row["passed"] is False
    assert row["tool_call_count"] == 0
    assert row["task_complete"] is False
    assert observed_stages(row) == [
        "agent_final_before_task_completion",
        "supported_no_fit_refusal_observed",
    ]


def test_unsupported_false_accept_is_not_approved_or_called_independent_e2():
    task = _task()
    route = task["executor_fixture"]["steps"][0]["route_id"]
    task["supported"] = False
    task["required_routes"] = []
    task["executor_fixture"] = {"steps": []}
    row, _ = _run(
        task,
        [_call(route, {"material_id": "UNSUPPORTED"}), "Done."],
        [route],
    )
    assert row["task_complete"] is False
    assert row["passed"] is False
    assert row["unauthorized_destructive_executions"] == 0
    assert "unsupported_tool_executed" in observed_stages(row)


def test_missing_required_input_is_schema_failure_not_route_recall_failure():
    task = _task()
    route = task["executor_fixture"]["steps"][0]["route_id"]
    row, _ = _run(task, [_call(route, {}), "Done."], [route])
    assert row["passed"] is False
    assert row["initial_required_route_miss"] is False
    assert row["attempts"][0]["schema_valid"] is False
    assert row["required_routes_advanced"] == 0
    assert "input_schema_rejection_observed" in observed_stages(row)


def test_safe_wrong_operation_cannot_advance_a_supported_task():
    task = _task()
    expected = task["executor_fixture"]["steps"][0]["route_id"]
    wrong = _safe_wrong_route(task)
    row, _ = _run(task, [_call(wrong, {}), "Done."], [expected, wrong])
    assert row["passed"] is False
    assert row["initial_required_route_miss"] is False
    assert row["attempts"][0]["schema_valid"] is True
    assert row["attempts"][0]["expected_at_step"] is False
    assert row["required_routes_advanced"] == 0
    assert "wrong_operation_attempt_observed" in observed_stages(row)


def test_two_step_wrong_state_identifier_stops_before_source_step_two():
    task = _task("multi_step_provenance")
    first, second = task["executor_fixture"]["steps"]
    first_id = first["argument_rules"]["material_id"]["eq"]
    row, _ = _run(task, [
        _call(first["route_id"], {"material_id": first_id}),
        _call(second["route_id"], {"artifact_id": "WRONG-UNOBSERVED-ARTIFACT"}),
        "Done.",
    ], [first["route_id"], second["route_id"]])
    assert row["passed"] is False
    assert row["required_routes_advanced"] == 1
    assert row["tool_call_count"] == 2
    assert row["attempts"][1]["schema_valid"] is True
    assert row["attempts"][1]["semantic_valid"] is False
    assert row["attempts"][1]["expected_at_step"] is True
    assert "task_argument_mismatch_observed" in observed_stages(row)


def test_after_execution_stage_trace_redacts_raw_model_and_gold():
    task = _task()
    route = task["executor_fixture"]["steps"][0]["route_id"]
    secret = "PRIVATE_QUERY_OR_MODEL_CANARY"
    task["query"] = task["query"] + " " + secret
    row, _ = _run(task, [_call(route, {}), secret], [route])
    serialized = sanitized_e0_jsonl(
        row,
        source_revision="a" * 40,
        source_sha256="b" * 64,
        task_identity=str(task["semantic_task_id"]),
        hmac_key=b"this-is-a-private-hmac-test-key",
        seed=20261021,
    )
    public = json.loads(serialized)
    assert secret not in serialized
    assert task["query"] not in serialized
    assert "arguments" not in serialized
    assert "required_routes" not in serialized
    assert "input_schema_rejection_observed" in public["observed_stages"]
    assert public["independent_e2_qualified"] is False
