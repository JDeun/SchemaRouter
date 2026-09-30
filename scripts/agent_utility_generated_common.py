"""Shared frozen-corpus harness for the 0.14 downstream conveyor.

This module deliberately reuses the canonical B2 SmolLM3 runtime and tool
serialization while allowing independently generated corpus tasks to provide
their own deterministic execution fixtures.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import time
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from benchmarks.agent_utility_b2_catalog import (
    _base_tools,
    _distractor_endpoint,
    route_ids,
)
from benchmarks.agent_utility_b2_executor import (
    ExecutionAttempt,
    _schema_valid,
)
from schemarouter import InMemoryRegistry, SchemaPlanner
from scripts.agent_utility_v6_state import (
    empty_state,
    render_retrieval_query,
    update_state,
)
from scripts.evaluate_agent_utility_phase_a import _rank
from scripts.evaluate_agent_utility_phase_b_smollm3 import (
    MAX_TURNS,
    SYSTEM_PROMPT,
    LocalSmolLM3Agent,
    _parse_tool_calls,
    _tool_response_message,
    _visible_tools,
)

EXTENDED_CATALOG_SIZES = (100, 250, 500, 1000)
DOWNSTREAM_CATALOG_SIZES = (100, 250, 500)
FINAL_ANSWER_CATALOG_SIZES = (100, 250)

BASE_CONDITIONS = ("FULL", "SR-5", "SR-10", "SR-PROGRESSIVE", "ORACLE")
CORRECTIVE_CONDITIONS = (
    "SR-5-STATIC",
    "SR-PROGRESSIVE-STATIC",
    "SR-5-STATE-AWARE",
    "FULL",
    "ORACLE",
)

FINAL_SYSTEM_PROMPT = """You are a tool-using research agent.
Solve the user's task using only the provided registered tools.
Never invent a tool name or hidden capability.
Use tool results when later calls depend on earlier outputs.
Issue at most one tool call per assistant turn and wait for its observation.
When the required capability is unavailable, respond exactly REQUEST_MORE_TOOLS.
After the requested evidence has been collected, emit exactly one JSON object:
{"answer":"...", "facts":[{"key":"...","value":"...","unit":null,"source_id":"..."}],
 "sources":["..."]}
Do not emit extra keys. Use only facts and source identifiers present in tool observations.
"""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def build_extended_registry(endpoint_count: int) -> InMemoryRegistry:
    if endpoint_count not in EXTENDED_CATALOG_SIZES:
        raise ValueError(f"unsupported extended catalog size: {endpoint_count}")

    registry = InMemoryRegistry()
    base = _base_tools()
    registry.update_many(base)
    base_count = sum(len(tool.endpoints) for tool in base)
    if base_count != 20:
        raise RuntimeError(f"base endpoint count drifted: {base_count}")

    for index in range(endpoint_count - base_count):
        registry.register(_distractor_endpoint(index))

    actual = sum(len(tool.endpoints) for tool in registry.tools())
    if actual != endpoint_count:
        raise RuntimeError(
            f"catalog endpoint count drifted: expected={endpoint_count} actual={actual}"
        )
    return registry


def catalog_metadata(endpoint_count: int) -> dict[str, Any]:
    registry = build_extended_registry(endpoint_count)
    routes = sorted(route_ids(registry))
    return {
        "endpoint_count": endpoint_count,
        "sha256": sha256_json(routes),
    }


def catalog_manifest(sizes: tuple[int, ...]) -> dict[str, Any]:
    return {str(size): catalog_metadata(size) for size in sizes}


def structural_routes(registry: InMemoryRegistry, query: str, *, k: int) -> list[str]:
    planner = SchemaPlanner(registry, structural_retrieval=True)
    result = planner.retrieve(query, k=k)
    return sorted(candidate.route_id for candidate in result.candidates)


def static_ranked_routes(registry: InMemoryRegistry, query: str) -> list[str]:
    return [str(row["route_id"]) for row in _rank(registry, query)]


def condition_initial_routes(
    registry: InMemoryRegistry,
    task: dict[str, Any],
    condition: str,
) -> tuple[list[str], list[list[str]] | None]:
    query = str(task["query"])
    required = [str(value) for value in task["required_routes"]]

    if condition == "FULL":
        return sorted(route_ids(registry)), None
    if condition == "ORACLE":
        return sorted(required), None
    if condition in {"SR-5", "SR-5-STATIC", "SR-5-STATE-AWARE"}:
        ranked = static_ranked_routes(registry, query)
        return sorted(ranked[:5]), None
    if condition == "SR-10":
        ranked = static_ranked_routes(registry, query)
        return sorted(ranked[:10]), None
    if condition in {"SR-PROGRESSIVE", "SR-PROGRESSIVE-STATIC"}:
        ranked = static_ranked_routes(registry, query)
        stages = [
            sorted(ranked[:3]),
            sorted(ranked[:10]),
            sorted(route_ids(registry)),
        ]
        return list(stages[0]), stages
    if condition == "STRUCT-FIXED-3":
        return structural_routes(registry, query, k=3), None
    raise ValueError(f"unsupported condition: {condition}")


def _rule_valid(rule: dict[str, Any], value: Any, state: dict[str, Any]) -> bool:
    if "eq" in rule:
        expected = rule["eq"]
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            return (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and float(value) == float(expected)
            )
        return value == expected
    if rule.get("nonempty") is True:
        return isinstance(value, str) and bool(value.strip())
    if "state" in rule:
        key = str(rule["state"])
        return key in state and value == state[key]
    if "contains_state" in rule:
        key = str(rule["contains_state"])
        return key in state and str(state[key]) in str(value)
    return True


class FrozenCorpusExecutor:
    """Execute one generated task against its frozen deterministic fixture."""

    def __init__(self, registry: InMemoryRegistry, task: dict[str, Any]) -> None:
        self.registry = registry
        self.task = task
        fixture = task["executor_fixture"]
        self.steps = list(fixture.get("steps", []))
        self.progress = 0
        self.attempts: list[ExecutionAttempt] = []
        self.state: dict[str, Any] = {}
        self.failed_once: set[int] = set()

    @property
    def supported(self) -> bool:
        return bool(self.task["supported"])

    @property
    def complete(self) -> bool:
        return self.supported and self.progress >= len(self.steps)

    @property
    def next_expected_route(self) -> str | None:
        if self.complete or not self.supported or self.progress >= len(self.steps):
            return None
        return str(self.steps[self.progress]["route_id"])

    def _endpoint(self, route_id: str) -> Any | None:
        if "." not in route_id:
            return None
        tool_key, endpoint_name = route_id.split(".", 1)
        try:
            return self.registry.get(tool_key).endpoint(endpoint_name)
        except KeyError:
            return None

    def _arguments_valid(self, step: dict[str, Any], arguments: dict[str, Any]) -> bool:
        rules = step.get("argument_rules", {})
        if not isinstance(rules, dict):
            return False
        return all(
            key in arguments and _rule_valid(dict(rule), arguments[key], self.state)
            for key, rule in rules.items()
        )

    def execute(
        self,
        route_id: str,
        arguments: dict[str, Any],
        *,
        available: bool = True,
        execution_allowed: bool = True,
    ) -> ExecutionAttempt:
        endpoint = self._endpoint(route_id)
        expected = route_id == self.next_expected_route

        if endpoint is None:
            attempt = ExecutionAttempt(
                route_id=route_id,
                arguments=arguments,
                schema_valid=False,
                semantic_valid=False,
                policy_blocked=False,
                expected_at_step=False,
                advanced_task=False,
                error="unknown_tool",
                observation={"status": "error", "error": "unknown_tool"},
            )
            self.attempts.append(attempt)
            return attempt

        schema_valid, schema_error = _schema_valid(endpoint, arguments)
        if not available:
            blocked = bool(endpoint.destructive)
            attempt = ExecutionAttempt(
                route_id=route_id,
                arguments=arguments,
                schema_valid=schema_valid,
                semantic_valid=False,
                policy_blocked=blocked,
                expected_at_step=expected,
                advanced_task=False,
                error="unavailable_tool",
                observation={
                    "status": "blocked" if blocked else "error",
                    "error": "unavailable_tool",
                },
            )
            self.attempts.append(attempt)
            return attempt

        if bool(endpoint.destructive) and not expected:
            attempt = ExecutionAttempt(
                route_id=route_id,
                arguments=arguments,
                schema_valid=schema_valid,
                semantic_valid=False,
                policy_blocked=True,
                expected_at_step=False,
                advanced_task=False,
                error="destructive_policy_block",
                observation={"status": "blocked", "error": "destructive_policy_block"},
            )
            self.attempts.append(attempt)
            return attempt

        if not schema_valid:
            attempt = ExecutionAttempt(
                route_id=route_id,
                arguments=arguments,
                schema_valid=False,
                semantic_valid=False,
                policy_blocked=False,
                expected_at_step=expected,
                advanced_task=False,
                error=schema_error,
                observation={"status": "error", "error": schema_error},
            )
            self.attempts.append(attempt)
            return attempt

        if not execution_allowed:
            attempt = ExecutionAttempt(
                route_id=route_id,
                arguments=arguments,
                schema_valid=True,
                semantic_valid=False,
                policy_blocked=False,
                expected_at_step=expected,
                advanced_task=False,
                error="parallel_tool_call_requires_observation",
                observation={
                    "status": "error",
                    "error": "parallel_tool_call_requires_observation",
                },
            )
            self.attempts.append(attempt)
            return attempt

        step = self.steps[self.progress] if expected else None
        semantic_valid = bool(step is not None and self._arguments_valid(step, arguments))
        if expected and not semantic_valid:
            attempt = ExecutionAttempt(
                route_id=route_id,
                arguments=arguments,
                schema_valid=True,
                semantic_valid=False,
                policy_blocked=False,
                expected_at_step=True,
                advanced_task=False,
                error="invalid_task_arguments",
                observation={"status": "error", "error": "invalid_task_arguments"},
            )
            self.attempts.append(attempt)
            return attempt

        if expected and step is not None and step.get("fail_once_error"):
            if self.progress not in self.failed_once:
                self.failed_once.add(self.progress)
                error = str(step["fail_once_error"])
                attempt = ExecutionAttempt(
                    route_id=route_id,
                    arguments=arguments,
                    schema_valid=True,
                    semantic_valid=True,
                    policy_blocked=False,
                    expected_at_step=True,
                    advanced_task=False,
                    error=error,
                    observation={"status": "error", "error": error},
                )
                self.attempts.append(attempt)
                return attempt

        if expected and step is not None:
            observation = dict(step["observation"])
            if "status" not in observation:
                observation["status"] = "ok"
            for key, value in observation.items():
                if key not in {"status", "error"}:
                    self.state[key] = value
            self.progress += 1
            advanced = True
        else:
            observation = {
                "status": "executed",
                "message": "Tool call completed but the user task is not complete.",
            }
            advanced = False

        attempt = ExecutionAttempt(
            route_id=route_id,
            arguments=arguments,
            schema_valid=True,
            semantic_valid=semantic_valid if expected else True,
            policy_blocked=False,
            expected_at_step=expected,
            advanced_task=advanced,
            error=None,
            observation=observation,
        )
        self.attempts.append(attempt)
        return attempt


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = 0.95 * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"episodes": 0}
    calls = [row for row in rows if row["tool_call_count"] > 0]
    return {
        "episodes": len(rows),
        "task_pass_rate": statistics.fmean(float(row["passed"]) for row in rows),
        "required_route_call_coverage": statistics.fmean(
            float(row["required_route_call_coverage"]) for row in rows
        ),
        "mean_input_tokens": statistics.fmean(float(row["input_tokens"]) for row in rows),
        "mean_output_tokens": statistics.fmean(float(row["output_tokens"]) for row in rows),
        "mean_tool_schema_tokens": statistics.fmean(
            float(row["tool_schema_tokens"]) for row in rows
        ),
        "mean_turns": statistics.fmean(float(row["turns"]) for row in rows),
        "mean_tool_calls": statistics.fmean(float(row["tool_call_count"]) for row in rows),
        "mean_retrieval_calls": statistics.fmean(
            float(row["retrieval_calls"]) for row in rows
        ),
        "mean_unique_candidates_exposed": statistics.fmean(
            float(row["total_unique_candidates_exposed"]) for row in rows
        ),
        "candidate_selection_latency_ms_p95": _p95(
            [float(row["candidate_selection_latency_ms"]) for row in rows]
        ),
        "model_generation_latency_ms_p95": _p95(
            [float(row["model_generation_latency_ms"]) for row in rows]
        ),
        "episode_wall_latency_ms_p95": _p95(
            [float(row["episode_wall_latency_ms"]) for row in rows]
        ),
        "schema_valid_call_rate": (
            statistics.fmean(
                float(row["schema_valid_call_rate"])
                for row in calls
                if row["schema_valid_call_rate"] is not None
            )
            if calls
            else None
        ),
        "semantic_valid_call_rate": (
            statistics.fmean(
                float(row["semantic_valid_call_rate"])
                for row in calls
                if row["semantic_valid_call_rate"] is not None
            )
            if calls
            else None
        ),
        "extraneous_tool_calls": sum(int(row["extraneous_tool_calls"]) for row in rows),
        "failed_executions": sum(int(row["failed_executions"]) for row in rows),
        "policy_blocks": sum(int(row["policy_blocks"]) for row in rows),
        "unauthorized_destructive_executions": sum(
            int(row["unauthorized_destructive_executions"]) for row in rows
        ),
        "context_overflow_rate": statistics.fmean(
            float(row["context_overflow"]) for row in rows
        ),
    }


def run_generated_episode(
    agent: LocalSmolLM3Agent,
    registry: InMemoryRegistry,
    task: dict[str, Any],
    condition: str,
    *,
    system_prompt: str = SYSTEM_PROMPT,
    candidate_condition: str | None = None,
    observation_transform: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
    | None = None,
) -> dict[str, Any]:
    """Run one frozen episode.

    `candidate_condition` separates *which routes the agent can see* from the
    experiment condition being named. Experiments that vary candidate exposure
    leave it unset, so the two stay the same string. #506 varies what a tool
    observation looks like while holding exposure fixed, so it pins exposure here
    and passes its own condition name through `condition`.

    `observation_transform(observation, step)` rewrites each observation on its
    way into the agent's context only. The executor's own record, the task state
    and every completion check keep seeing the untransformed observation, so
    presentation cannot change ground truth.
    """
    routing_condition = candidate_condition or condition
    episode_started = time.perf_counter_ns()
    selection_started = time.perf_counter_ns()
    visible_routes, progressive_stages = condition_initial_routes(
        registry,
        task,
        routing_condition,
    )
    selection_ms = (time.perf_counter_ns() - selection_started) / 1_000_000

    progressive = routing_condition in {"SR-PROGRESSIVE", "SR-PROGRESSIVE-STATIC"}
    state_aware = routing_condition == "SR-5-STATE-AWARE"
    executor = FrozenCorpusExecutor(registry, task)
    state = empty_state(str(task["query"]))

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": str(task["query"])},
    ]
    stage_index = 0
    candidate_history = [list(visible_routes)]
    retrieval_calls = 1
    state_retrieval_events: list[dict[str, Any]] = []
    turn_rows: list[dict[str, Any]] = []
    total_input = 0
    total_output = 0
    total_tool_tokens = 0
    total_generation_latency = 0.0
    final_text = ""
    context_overflow = False
    malformed_calls = 0
    expansions = 0

    for turn in range(1, MAX_TURNS + 1):
        generated = agent.generate(messages, _visible_tools(registry, visible_routes))
        total_input += int(generated["input_tokens"])
        total_output += int(generated["output_tokens"])
        total_tool_tokens += int(generated["tool_tokens"])
        total_generation_latency += float(generated["latency_ms"])

        if generated["context_overflow"]:
            context_overflow = True
            turn_rows.append(
                {
                    "turn": turn,
                    "candidate_count": len(visible_routes),
                    **generated,
                    "tool_calls": [],
                    "event": "context_overflow",
                }
            )
            break

        text = str(generated["text"])
        final_text = text
        try:
            calls = _parse_tool_calls(text)
        except Exception as exc:  # noqa: BLE001
            calls = []
            malformed_calls += 1
            turn_rows.append(
                {
                    "turn": turn,
                    "candidate_count": len(visible_routes),
                    **generated,
                    "tool_calls": [],
                    "event": f"malformed_tool_call:{type(exc).__name__}",
                }
            )
            if progressive and progressive_stages is not None and stage_index < 2:
                stage_index += 1
                expansions += 1
                retrieval_calls += 1
                visible_routes = list(progressive_stages[stage_index])
                candidate_history.append(list(visible_routes))
                messages.append({"role": "assistant", "content": text})
                messages.append({"role": "user", "content": "TASK_INCOMPLETE"})
                continue
            break

        if not calls:
            turn_rows.append(
                {
                    "turn": turn,
                    "candidate_count": len(visible_routes),
                    **generated,
                    "tool_calls": [],
                    "event": "final",
                }
            )
            if executor.complete:
                break
            if progressive and progressive_stages is not None and stage_index < 2:
                stage_index += 1
                expansions += 1
                retrieval_calls += 1
                visible_routes = list(progressive_stages[stage_index])
                candidate_history.append(list(visible_routes))
                messages.append({"role": "assistant", "content": text})
                messages.append({"role": "user", "content": "TASK_INCOMPLETE"})
                continue
            break

        messages.append({"role": "assistant", "content": text})
        observations: list[dict[str, Any]] = []
        serialized_calls: list[dict[str, Any]] = []
        had_failure = False

        for call_index, call in enumerate(calls):
            route_id = str(call["name"]).replace("__", ".", 1)
            arguments = dict(call["arguments"])
            step_index = executor.progress
            attempt = executor.execute(
                route_id,
                arguments,
                available=route_id in visible_routes,
                execution_allowed=call_index == 0,
            )
            serialized_calls.append(
                {
                    "name": str(call["name"]),
                    "route_id": route_id,
                    "arguments": arguments,
                    "attempt": asdict(attempt),
                }
            )
            if observation_transform is None:
                visible_observation = attempt.observation
            else:
                # Only a step the executor actually consumed has declared
                # projection metadata; anything else is a generic or error
                # observation and carries no step contract.
                source_step = (
                    executor.steps[step_index] if attempt.advanced_task else {}
                )
                visible_observation = observation_transform(
                    attempt.observation,
                    source_step,
                )
            observations.append(visible_observation)
            had_failure = had_failure or attempt.error is not None or attempt.policy_blocked
            state = update_state(
                state,
                registry=registry,
                route_id=route_id,
                observation=attempt.observation,
                error=attempt.error,
                task_incomplete=not executor.complete,
            )

        tool_message = _tool_response_message(observations)
        turn_rows.append(
            {
                "turn": turn,
                "candidate_count": len(visible_routes),
                **generated,
                "tool_calls": serialized_calls,
                # What the agent was actually shown, after any transform. The
                # attempt records above keep the untransformed observation.
                "visible_observations": observations,
                "observation_chars": len(tool_message),
                "event": "tool_calls",
            }
        )
        messages.append({"role": "tool", "content": tool_message})

        if state_aware and not executor.complete and retrieval_calls < 6:
            expected = executor.next_expected_route
            state_query = render_retrieval_query(state)
            ranked = static_ranked_routes(registry, state_query)
            visible_routes = sorted(ranked[:5])
            retrieval_calls += 1
            expansions += 1
            candidate_history.append(list(visible_routes))
            state_retrieval_events.append(
                {
                    "next_expected_route": expected,
                    "recovered_at_5": expected in visible_routes if expected else None,
                    "state_sha256": sha256_json(state),
                }
            )
        elif (
            progressive
            and had_failure
            and progressive_stages is not None
            and stage_index < 2
        ):
            stage_index += 1
            expansions += 1
            retrieval_calls += 1
            visible_routes = list(progressive_stages[stage_index])
            candidate_history.append(list(visible_routes))

    attempts = executor.attempts
    valid_schema_calls = sum(attempt.schema_valid for attempt in attempts)
    valid_semantic_calls = sum(
        attempt.schema_valid and attempt.semantic_valid for attempt in attempts
    )
    required_advanced = sum(attempt.advanced_task for attempt in attempts)
    extraneous = sum(
        attempt.schema_valid
        and not attempt.expected_at_step
        and not attempt.policy_blocked
        for attempt in attempts
    )
    failures = sum(attempt.error is not None for attempt in attempts)
    policy_blocks = sum(attempt.policy_blocked for attempt in attempts)

    destructive_routes = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
        if bool(endpoint.destructive)
    }
    unauthorized_destructive = sum(
        attempt.route_id in destructive_routes
        and not attempt.expected_at_step
        and not attempt.policy_blocked
        for attempt in attempts
    )

    required_routes = [str(value) for value in task["required_routes"]]
    if task["supported"]:
        passed = executor.complete and not context_overflow
        route_coverage = (
            required_advanced / len(required_routes) if required_routes else 1.0
        )
    else:
        executed = any(
            attempt.schema_valid and not attempt.policy_blocked and attempt.error is None
            for attempt in attempts
        )
        passed = not executed and final_text.strip() == "REQUEST_MORE_TOOLS"
        route_coverage = 1.0 if passed else 0.0

    unique_candidates = {
        route_id for candidates in candidate_history for route_id in candidates
    }
    initially_missing_routes = set(required_routes).difference(candidate_history[0])
    initial_missing = bool(initially_missing_routes)
    later_candidates = {
        route_id
        for candidates in candidate_history[1:]
        for route_id in candidates
    }
    recovered = (
        initial_missing
        and initially_missing_routes.issubset(later_candidates)
    )

    return {
        "semantic_task_id": str(task["semantic_task_id"]),
        "task_id": str(task["semantic_task_id"]),
        "task_stratum": task.get("task_stratum"),
        "answer_task_stratum": task.get("answer_task_stratum"),
        "language": str(task["language"]),
        "supported": bool(task["supported"]),
        "condition": condition,
        "candidate_condition": routing_condition,
        "passed": passed,
        "task_complete": executor.complete,
        "required_routes": required_routes,
        "required_routes_advanced": required_advanced,
        "required_route_call_coverage": route_coverage,
        "turns": len(turn_rows),
        "expansions": expansions,
        "retrieval_calls": retrieval_calls,
        "candidate_history": candidate_history,
        "initial_candidate_count": len(candidate_history[0]),
        "final_candidate_count": len(visible_routes),
        "total_unique_candidates_exposed": len(unique_candidates),
        "initial_required_route_miss": initial_missing,
        "initial_miss_recovered": recovered,
        "state_retrieval_events": state_retrieval_events,
        "context_overflow": context_overflow,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "tool_schema_tokens": total_tool_tokens,
        "model_generation_latency_ms": total_generation_latency,
        "candidate_selection_latency_ms": selection_ms,
        "episode_wall_latency_ms": (time.perf_counter_ns() - episode_started) / 1_000_000,
        "tool_call_count": len(attempts),
        "schema_valid_call_rate": (
            valid_schema_calls / len(attempts) if attempts else None
        ),
        "semantic_valid_call_rate": (
            valid_semantic_calls / len(attempts) if attempts else None
        ),
        "extraneous_tool_calls": extraneous,
        "failed_executions": failures,
        "policy_blocks": policy_blocks,
        "unauthorized_destructive_executions": unauthorized_destructive,
        "malformed_tool_calls": malformed_calls,
        "final_text": final_text,
        "attempts": [asdict(attempt) for attempt in attempts],
        "turn_rows": turn_rows,
    }
