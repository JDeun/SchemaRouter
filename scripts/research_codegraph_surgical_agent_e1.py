"""Opt-in E1: model-driven schema disclosure, then original scoped calls.

There is no new native executor or product-visible action. The reserved
``research__request_scoped_source_schema`` operation materializes definitions
only, and the model must separately choose every real read-only operation.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from schemarouter.errors import PolicyViolationError
from scripts.research_codegraph_action_shape_e1 import structural_action_label
from scripts.research_codegraph_scoped_materializer import (
    SurgicalEpisode,
    materialize_scoped_original_schemas,
)
from scripts.research_real_qwen_bound_two_step_e0 import (
    TOOL_CALL,
    _parse_strict_model_json,
    _strip_one_chatml_marker,
    parse_one_model_action,
)
from scripts.research_scoped_host_invocation import execute_scoped_host_call

SCHEMA_REQUEST_NAME = "research__request_scoped_source_schema"
MAX_TURNS = 5

_SCHEMA_REQUEST_TOOL: dict[str, Any] = {
    "name": SCHEMA_REQUEST_NAME,
    "description": (
        "Request current original tool definitions for one or more route IDs "
        "explicitly selected in the verified graph reference. "
        "This never executes a provider operation."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "route_ids": {
                "type": "array", "minItems": 1, "maxItems": 5,
                "uniqueItems": True, "items": {"type": "string"},
            },
        },
        "required": ["route_ids"],
        "additionalProperties": False,
    },
}

# Model-only protocol condition. It is never used by routing, gold,
# authorization, original executor, source bindings or the strict parser.
SINGLE_STEP_PROTOCOL_E1 = (
    "For each turn emit exactly ONE action, never a batch or two tool_call "
    "blocks. For a tool call output precisely one JSON object enclosed by "
    "<tool_call> and </tool_call>, with keys 'name' and 'arguments'. "
    "The name must match exactly one offered native tool. "
    "Never output two or more tool_call blocks in the same turn. "
    "Do not invent names or call tools that were not offered. Wait for " 
    "the host's real "
    "tool observation before considering any dependent call. "
    "A final JSON answer is allowed only after the verified native "
    "operations are complete. Never infer tool results or arguments."
)

_SYSTEM_PROMPT = (
    "The graph reference contains only authorization-scoped path references; "
    "it is not a tool schema or an execution grant. "
    "First call research__request_scoped_source_schema using a JSON array "
    "of explicitly listed route IDs. Wait for the original tool definitions. "
    "Then choose each real tool call yourself, one per turn, using only "
    "trusted inputs and verified public observations from previous tool calls. "
    "Never invent route IDs, source data or tool results. "
    "Answer only after completing a verified source path."
)


@dataclass(frozen=True, slots=True)
class SurgicalHostContext:
    """Trusted host-only task inputs and source final oracle (never model args)."""

    trusted_route_inputs: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    required_output_fields: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    final_response_instruction: str = ""
    validate_final: Callable[[str, Mapping[str, Any]], bool] | None = field(
        default=None, repr=False,
    )


def _parse_action(text: str) -> tuple[str, Any]:
    """Allow a strict list argument ONLY for the reserved research action.

    All actual native provider operations still pass through the untouched
    ``parse_one_model_action`` scalar-only grammar and host invoker.
    """
    raw = _strip_one_chatml_marker(text)
    match = TOOL_CALL.fullmatch(raw)
    if match is not None:
        payload = _parse_strict_model_json(match.group(1))
        if type(payload) is dict and payload.get("name") == SCHEMA_REQUEST_NAME:
            if (
                set(payload) != {"name", "arguments"}
                or type(payload["arguments"]) is not dict
                or set(payload["arguments"]) != {"route_ids"}
                or type(payload["arguments"]["route_ids"]) is not list
                or not 1 <= len(payload["arguments"]["route_ids"]) <= 5
                or any(type(value) is not str for value in payload["arguments"]["route_ids"])
            ):
                raise ValueError("invalid research schema request")
            return "schema", payload["arguments"]["route_ids"]
    return parse_one_model_action(text)


def _model_token_receipt(generated: dict[str, Any]) -> tuple[int, int, int] | None:
    keys = ("input_tokens", "tool_tokens", "output_tokens")
    if (
        any(type(generated.get(key)) is not int or generated[key] < 0 for key in keys)
        or generated["tool_tokens"] > generated["input_tokens"]
    ):
        return None
    return generated["input_tokens"], generated["tool_tokens"], generated["output_tokens"]


def _append_observation(
    messages: list[dict[str, str]], action_text: str, observation: dict[str, Any],
) -> None:
    messages.append({"role": "assistant", "content": action_text})
    messages.append({
        "role": "tool",
        "content": "<tool_response>\n" + json.dumps(
            observation, ensure_ascii=False, sort_keys=True, allow_nan=False,
        ) + "\n</tool_response>",
    })


def _expected_arguments(
    episode: SurgicalEpisode,
    executed_routes: list[str],
    observations: dict[str, dict[str, Any]],
    route_id: str,
    context: SurgicalHostContext,
) -> dict[str, Any] | None:
    """Derive allowed arguments solely from trusted inputs and observed binds."""
    prefix = (*executed_routes, route_id)
    active_paths = [
        path for path in episode.selection.route_sets
        if path.route_ids[:len(prefix)] == prefix
    ]
    if not active_paths:
        return None
    known = dict(context.trusted_route_inputs.get(route_id, {}))
    if len(prefix) > 1:
        # All still-possible paths must agree on the source binding; no
        # ambiguous alternative is silently resolved using model arguments.
        constraints = {path.parameter_bindings for path in active_paths}
        if len(constraints) != 1:
            return None
        predecessor = executed_routes[0]
        prior = observations.get(predecessor)
        if prior is None:
            return None
        for target_parameter, producer_field in next(iter(constraints)):
            if producer_field not in prior:
                return None
            value = prior[producer_field]
            if target_parameter in known and known[target_parameter] != value:
                return None
            known[target_parameter] = value
    return known


async def run_surgical_model_episode(
    agent: Any,
    *,
    episode: SurgicalEpisode,
    host_context: SurgicalHostContext,
    max_turns: int = MAX_TURNS,
    diagnose_model_actions: bool = False,
    experimental_single_step_prompt: bool = False,
) -> dict[str, Any]:
    """Measure schema requests and actual original invocations separately.

    Returned data is category/count evidence, with no source observations,
    private model messages, arguments, principals or original definitions.
    """
    if not callable(getattr(agent, "generate", None)):
        raise ValueError("model generator required")
    if type(diagnose_model_actions) is not bool:
        raise ValueError("research diagnostics flag must be boolean")
    if type(experimental_single_step_prompt) is not bool:
        raise ValueError("single-step prompt experiment must be boolean")
    if type(host_context) is not SurgicalHostContext:
        raise ValueError("trusted surgical host context required")
    if type(host_context.final_response_instruction) is not str:
        raise ValueError("trusted final response instruction must be a string")
    if type(max_turns) is not int or not 1 <= max_turns <= 8:
        raise ValueError("bounded surgical research turn budget required")
    initial_reference = episode.public_reference
    messages = [
        {"role": "system", "content": (
            _SYSTEM_PROMPT + "\n" + host_context.final_response_instruction
            + ("\n" + SINGLE_STEP_PROTOCOL_E1
               if experimental_single_step_prompt else "")
        )},
        {"role": "user", "content": episode.original_query + "\n" + json.dumps(
            initial_reference, ensure_ascii=False, sort_keys=True, allow_nan=False,
        )},
    ]
    materialized_ids: list[str] = []
    definitions: list[dict[str, Any]] = []
    observations: dict[str, dict[str, Any]] = {}
    executed_routes: list[str] = []
    schema_requests = 0
    source_attempts = 0
    source_calls = 0
    model_turns = 0
    reason = "turn_limit"
    full_task_correct = False
    all_receipts = True
    input_tokens = tool_tokens = output_tokens = 0
    model_latency_ms = 0.0
    action_shape_labels: list[str] = []

    for _ in range(max_turns):
        try:
            # Changes in authority, principal or producer output visibility
            # abort before model generation or another original tool call.
            _ = episode.public_reference
        except PolicyViolationError:
            reason = "authorization_changed"
            break
        offered = [_SCHEMA_REQUEST_TOOL] if not materialized_ids else definitions
        model_turns += 1
        generated = agent.generate(messages, offered)
        try:
            _ = episode.public_reference
        except PolicyViolationError:
            reason = "authorization_changed"
            break
        if (
            type(generated) is not dict
            or type(generated.get("text")) is not str
            or type(generated.get("context_overflow")) is not bool
            or type(generated.get("latency_ms")) not in (int, float)
            or not math.isfinite(float(generated["latency_ms"]))
            or float(generated["latency_ms"]) < 0
        ):
            reason = "invalid_model_envelope"
            all_receipts = False
            break
        if diagnose_model_actions:
            action_shape_labels.append(structural_action_label(
                generated["text"],
                offered_names=tuple(item["name"] for item in offered),
                after_schema=bool(materialized_ids),
                native_calls=source_calls,
            ))
        receipt = _model_token_receipt(generated)
        if receipt is None:
            all_receipts = False
        else:
            input_tokens += receipt[0]
            tool_tokens += receipt[1]
            output_tokens += receipt[2]
        model_latency_ms += float(generated["latency_ms"])
        if generated["context_overflow"]:
            reason = "context_overflow"
            break
        try:
            kind, value = _parse_action(generated["text"])
        except (ValueError, TypeError, OverflowError):
            reason = "malformed_call"
            break

        if kind == "final":
            completed_paths = [
                path for path in episode.selection.route_sets
                if path.route_ids == tuple(executed_routes)
            ]
            if not completed_paths or not observations:
                reason = "premature_final"
            else:
                reason = "completed_final"
                validator = host_context.validate_final
                if validator is not None:
                    try:
                        full_task_correct = (
                            validator(value, observations[executed_routes[-1]]) is True
                        )
                    except (KeyError, TypeError, ValueError, OverflowError):
                        full_task_correct = False
            break

        if kind == "schema":
            if materialized_ids:
                reason = "unoffered_or_repeated_schema_request"
                break
            try:
                _, definitions = materialize_scoped_original_schemas(episode, value)
            except (PolicyViolationError, ValueError):
                reason = "schema_request_denied"
                break
            materialized_ids = list(value)
            schema_requests += 1
            _append_observation(messages, generated["text"], {
                "status": "ok", "tool_definitions": definitions,
            })
            continue

        route_id, arguments = value["route"], value["arguments"]
        if route_id not in materialized_ids:
            reason = "unoffered_native_route"
            break
        expected = _expected_arguments(
            episode, executed_routes, observations, route_id, host_context,
        )
        if expected is None or arguments != expected:
            reason = "unbound_source_arguments"
            break
        try:
            # Materialization rechecks original G5/source/permission each time.
            view, _ = materialize_scoped_original_schemas(episode, materialized_ids)
            source_attempts += 1
            observation = await execute_scoped_host_call(
                view, selected_route_ids=materialized_ids, route_id=route_id,
                arguments=arguments,
                host_required_output_fields=host_context.required_output_fields.get(
                    route_id, (),
                ),
            )
        except (PolicyViolationError, ValueError, RuntimeError):
            reason = "native_host_call_denied"
            break
        if observation.get("status") != "ok":
            reason = "non_ok_observation"
            break
        source_calls += 1
        executed_routes.append(route_id)
        observations[route_id] = observation
        _append_observation(messages, generated["text"], observation)

    return {
        "evidence_tier": "E1_RESEARCH_SCOPED_PROTOCOL",
        "model_turns": model_turns,
        "schema_requests": schema_requests,
        "source_call_attempts": source_attempts,
        "actual_source_calls": source_calls,
        "termination_reason": reason,
        "full_task_correct": full_task_correct,
        "model_input_tokens": input_tokens if all_receipts else None,
        "tool_schema_tokens": tool_tokens if all_receipts else None,
        "model_output_tokens": output_tokens if all_receipts else None,
        "total_model_tokens": input_tokens + output_tokens if all_receipts else None,
        "model_latency_ms": model_latency_ms,
        "real_external_native_provider_execution": False,
        "independent_e2_qualified": False,
        "model_default_promoted": False,
        "release_safety_gate_passed": False,
        **({
            "action_structure_labels": action_shape_labels,
        } if diagnose_model_actions else {}),
    }
