"""Opt-in E1: stage-restricted source-attested original tool disclosure.

Research harness only. No invented executor, schema request, route/argument repair,
or changes to the product's authorization, parser, and execution paths.
"""
from __future__ import annotations

import math
from typing import Any

from schemarouter.errors import PolicyViolationError
from scripts.research_codegraph_scoped_materializer import (
    SurgicalEpisode,
    materialize_scoped_original_schemas,
)
from scripts.research_codegraph_surgical_agent_e1 import (
    MAX_TURNS,
    SINGLE_STEP_PROTOCOL_E1,
    SurgicalHostContext,
    _append_observation,
    _expected_arguments,
    _model_token_receipt,
)
from scripts.research_real_qwen_bound_two_step_e0 import parse_one_model_action
from scripts.research_scoped_host_invocation import execute_scoped_host_call

FRONTIER_ARM = "graph_frontier_g5_e1"
FRONTIER_CUED_ARM = "graph_frontier_cued_e1"
FRONTIER_VERIFIED_CONTINUATION_CUE_E1 = (
    "The host has returned a verified original read-only observation. "
    "The dependency path is not yet complete. Continue with exactly one "
    "currently offered read-only operation per turn, using only parameters "
    "available from actual verified observations. Do not invent arguments, "
    "or answer finally before the source dependency path is complete."
)
FRONTIER_PROMPT_E1 = (
    "Complete the user task with real original read-only source operations. "
    "The host offers only operations authorized at the current dependency step. "
    "Choose exactly one currently offered operation and its required arguments; "
    "wait for a genuine source observation before taking a dependent action. "
    "When no operation remains, produce the final JSON answer. "
    "Never invent observed values, output an early final, or request schemas."
)


def _frontier_route_ids(
    episode: SurgicalEpisode, executed_routes: tuple[str, ...],
) -> list[str]:
    """All attested next routes for an exact executed prefix, without guessing."""
    if type(episode) is not SurgicalEpisode or type(executed_routes) is not tuple:
        raise ValueError("original graph episode and tuple prefix required")
    if any(type(route) is not str for route in executed_routes):
        raise ValueError("invalid route prefix")
    paths = [
        path for path in episode.selection.route_sets
        if path.route_ids[:len(executed_routes)] == executed_routes
    ]
    if not paths:
        return []
    result = list(dict.fromkeys(
        path.route_ids[len(executed_routes)]
        for path in paths if len(path.route_ids) > len(executed_routes)
    ))
    if len(result) > 5:
        raise ValueError("frontier exceeds strict K5")
    return result


async def run_graph_frontier_model_episode(
    agent: Any,
    *,
    episode: SurgicalEpisode,
    host_context: SurgicalHostContext,
    max_turns: int = MAX_TURNS,
    diagnose_model_actions: bool = False,
    experimental_verified_continuation: bool = False,
) -> dict[str, Any]:
    """Model chooses original calls; host limits offer to attested next steps.

    Returns only safe counts/labels, never model text, source arguments, or data.
    """
    if not callable(getattr(agent, "generate", None)):
        raise ValueError("model generator required")
    if type(host_context) is not SurgicalHostContext:
        raise ValueError("trusted host context required")
    if type(host_context.final_response_instruction) is not str:
        raise ValueError("invalid host final instruction")
    if type(max_turns) is not int or max_turns != MAX_TURNS:
        raise ValueError("frontier E1 requires pinned five-turn budget")
    if type(diagnose_model_actions) is not bool:
        raise ValueError("diagnostics flag must be boolean")
    if type(experimental_verified_continuation) is not bool:
        raise ValueError("verified continuation flag must be boolean")
    # Fail before generation on absent or stale original authorization.
    _ = episode.public_reference
    if not episode.selection.route_sets or any(
        len(path.route_ids) != 2 for path in episode.selection.route_sets
    ):
        raise ValueError("frontier E1 requires only attested two-hop paths")

    messages = [
        {"role": "system", "content": (
            FRONTIER_PROMPT_E1 + "\n" + SINGLE_STEP_PROTOCOL_E1
            + "\n" + host_context.final_response_instruction
        )},
        {"role": "user", "content": episode.original_query},
    ]
    executed: list[str] = []
    observations: dict[str, dict[str, Any]] = {}
    source_attempts = source_calls = model_turns = 0
    input_tokens = output_tokens = tool_tokens = 0
    latency_ms = 0.0
    all_receipts = True
    frontier_sizes: list[int] = []
    structure_labels: list[str] = []
    continuation_cues = 0
    reason = "turn_limit"
    correct = False

    for _ in range(max_turns):
        try:
            _ = episode.public_reference
            offered_routes = _frontier_route_ids(episode, tuple(executed))
            if offered_routes:
                _, offered = materialize_scoped_original_schemas(
                    episode, offered_routes,
                )
            else:
                # The final-answer turn cannot execute any additional tool.
                offered = []
        except (PolicyViolationError, ValueError, AttributeError, TypeError):
            reason = "authorization_changed"
            break

        frontier_sizes.append(len(offered))
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
            or generated["latency_ms"] < 0
        ):
            reason = "invalid_model_envelope"
            all_receipts = False
            break
        if diagnose_model_actions:
            from scripts.research_codegraph_action_shape_e1 import structural_action_label

            structure_labels.append(structural_action_label(
                generated["text"],
                offered_names=tuple(item["name"] for item in offered),
                after_schema=False,
                native_calls=source_calls,
            ))
        receipt = _model_token_receipt(generated)
        if receipt is None:
            all_receipts = False
        else:
            input_tokens += receipt[0]
            tool_tokens += receipt[1]
            output_tokens += receipt[2]
        latency_ms += float(generated["latency_ms"])
        if generated["context_overflow"]:
            reason = "context_overflow"
            break
        try:
            kind, value = parse_one_model_action(generated["text"])
        except (ValueError, TypeError, OverflowError):
            reason = "malformed_call"
            break
        if kind == "final":
            complete = any(
                path.route_ids == tuple(executed)
                for path in episode.selection.route_sets
            )
            if not complete or not observations:
                reason = "premature_final"
            else:
                reason = "completed_final"
                validator = host_context.validate_final
                if validator is not None:
                    try:
                        correct = (
                            validator(value, observations[executed[-1]]) is True
                        )
                    except (KeyError, TypeError, ValueError, OverflowError):
                        correct = False
            break
        if kind != "tool":
            reason = "malformed_call"
            break
        route_id, arguments = value["route"], value["arguments"]
        if route_id not in offered_routes:
            reason = "unoffered_native_route"
            break
        expected = _expected_arguments(
            episode, executed, observations, route_id, host_context,
        )
        if expected is None or arguments != expected:
            reason = "unbound_source_arguments"
            break
        try:
            _ = episode.public_reference
            view, _ = materialize_scoped_original_schemas(
                episode, offered_routes,
            )
            source_attempts += 1
            observation = await execute_scoped_host_call(
                view, selected_route_ids=offered_routes, route_id=route_id,
                arguments=arguments,
                host_required_output_fields=host_context.required_output_fields.get(
                    route_id, (),
                ),
            )
            _ = episode.public_reference
        except (PolicyViolationError, ValueError, RuntimeError):
            reason = "native_host_call_denied"
            break
        if observation.get("status") != "ok":
            reason = "non_ok_observation"
            break
        source_calls += 1
        executed.append(route_id)
        observations[route_id] = observation
        _append_observation(messages, generated["text"], observation)
        if experimental_verified_continuation and source_calls == 1 and (
            _frontier_route_ids(episode, tuple(executed))
        ):
            # Actual verified first callback is the ONLY model cue trigger.
            # No next-route ID, argument, hidden field, gold or new grant.
            messages.append({
                "role": "user", "content": FRONTIER_VERIFIED_CONTINUATION_CUE_E1,
            })
            continuation_cues += 1

    return {
        "evidence_tier": "E1_RESEARCH_SCOPED_FRONTIER",
        "model_turns": model_turns,
        "schema_requests": 0,
        "source_call_attempts": source_attempts,
        "actual_source_calls": source_calls,
        "frontier_sizes": frontier_sizes,
        **({"verified_continuation_cues": continuation_cues}
           if experimental_verified_continuation else {}),
        "termination_reason": reason,
        "full_task_correct": correct,
        "model_input_tokens": input_tokens if all_receipts else None,
        "tool_schema_tokens": tool_tokens if all_receipts else None,
        "model_output_tokens": output_tokens if all_receipts else None,
        "total_model_tokens": input_tokens + output_tokens if all_receipts else None,
        "model_latency_ms": latency_ms,
        "real_external_native_provider_execution": False,
        "independent_e2_qualified": False,
        "model_default_promoted": False,
        "release_safety_gate_passed": False,
        **({"action_structure_labels": structure_labels} if diagnose_model_actions else {}),
    }
