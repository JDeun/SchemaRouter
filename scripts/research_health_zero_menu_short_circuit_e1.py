"""E1 opt-in host preflight: never ask an LLM to invent an outage refusal.

The original principal-scoped model menu is authoritative for presentation
ONLY, never for execution. A 0-route state is resolved by the trusted host,
not inferred by the Qwen model. No real provider calls or default changes.
"""
from __future__ import annotations

import asyncio
from typing import Any

from schemarouter import PolicyViolationError, PrincipalContext, SchemaRouter
from scripts.research_live_health_model_menu_e1 import (
    capture_health_scoped_model_menu,
)
from scripts.research_real_qwen_bound_two_step_e0 import parse_one_model_action

REFUSAL_LITERAL = "REQUEST_MORE_TOOLS"


def _host_receipt(
    status: str, *,
    offered: int, model_invoked: bool, discard: bool,
    proposed: str, terminal: str | None,
) -> dict[str, Any]:
    if status not in (
        "temporary_unavailable", "inputs_missing", "needs_revalidation",
        "proposal_only", "unexecutable_proposal", "terminal_no_tool",
    ):
        raise ValueError("invalid public host preflight status")
    if terminal not in (None, REFUSAL_LITERAL):
        raise ValueError("host may emit only bounded refusal literal")
    return {
        "status": status,
        "terminal_text": terminal,
        "model_invoked": model_invoked,
        "model_output_discarded": discard,
        "offered_tool_count": offered,
        "proposed_action_class": proposed,
        "executed_tool_calls": 0,
        "provider_http_requests": 0,
        "semantic_no_fit_established": False,
        "real_provider_success_qualified": False,
        "independent_e2_qualified": False,
        "production_default_changed": False,
    }


async def run_strict_health_gated_model_turn(
    agent: Any,
    router: SchemaRouter,
    *,
    query: str,
    principal: PrincipalContext,
    host_request_inputs: dict[str, Any],
    system_prompt: str,
    prior_public_observation: dict[str, Any] | None = None,
    executed_route_ids: tuple[str, ...] = (),
    max_probe_age_seconds: float = 60.0,
) -> dict[str, Any]:
    """Host-owned strict preflight, then optional ONE model proposal.

    A model proposal is never executable authority. The host emits the exact
    old fixed refusal literal on UNAVAILABLE, while the sideband status keeps
    temporary service failure distinct from semantic unsupported/no-fit.
    """
    if (
        not callable(getattr(agent, "generate", None))
        or type(query) is not str or not query.strip()
        or type(system_prompt) is not str or not system_prompt.strip()
        or not isinstance(principal, PrincipalContext)
        or type(host_request_inputs) is not dict
    ):
        raise ValueError("trusted agent, principal and bounded host request required")
    menu = capture_health_scoped_model_menu(
        router, query, principal=principal,
        host_request_inputs=host_request_inputs,
        prior_public_observation=prior_public_observation,
        executed_route_ids=executed_route_ids,
        max_probe_age_seconds=max_probe_age_seconds,
    )
    if not menu.definitions:
        if menu.route_ids or menu.status not in (
            "temporary_unavailable", "inputs_missing",
        ):
            raise ValueError("no tool definitions with inconsistent menu status")
        # CRITICAL: do not call the LLM with an empty catalog and hope it
        # emits the host's strict refusal protocol. We have a host-level
        # operational status independent of any model language.
        menu.assert_current()
        return _host_receipt(
            menu.status, offered=0, model_invoked=False, discard=False,
            proposed="not_invoked_no_viable_route",
            terminal=REFUSAL_LITERAL,
        )
    if menu.status != "ready" or not menu.route_ids:
        raise ValueError("invalid offered tool contract")
    menu.assert_current()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]
    # Keep event loop/monitor active while CPU generation is in progress.
    result = await asyncio.to_thread(
        agent.generate, messages, list(menu.definitions),
    )
    try:
        # A failed/forged/stale source or newly unhealthy route discards
        # the entire model proposal, never forwards its tool name/arguments.
        menu.assert_current()
    except PolicyViolationError:
        return _host_receipt(
            "needs_revalidation", offered=len(menu.route_ids),
            model_invoked=True, discard=True,
            proposed="not_scored_stale_source_or_health",
            terminal=REFUSAL_LITERAL,
        )
    if type(result) is not dict or type(result.get("text")) is not str:
        return _host_receipt(
            "unexecutable_proposal", offered=len(menu.route_ids),
            model_invoked=True, discard=True,
            proposed="invalid_model_envelope", terminal=REFUSAL_LITERAL,
        )
    try:
        kind, candidate = parse_one_model_action(result["text"])
    except (ValueError, TypeError, OverflowError):
        classification = "invalid_format"
    else:
        if kind == "final":
            classification = (
                "exact_model_refusal" if candidate == REFUSAL_LITERAL
                else "nonstandard_model_terminal"
            )
        elif (
            kind == "tool" and type(candidate) is dict
            and candidate.get("route") in menu.route_ids
        ):
            classification = "visible_tool_proposal"
        else:
            classification = "hidden_or_unknown_tool_proposal"
    if classification == "visible_tool_proposal":
        return _host_receipt(
            "proposal_only", offered=len(menu.route_ids),
            model_invoked=True, discard=False,
            proposed=classification, terminal=None,
        )
    if classification in ("exact_model_refusal", "nonstandard_model_terminal"):
        return _host_receipt(
            "terminal_no_tool", offered=len(menu.route_ids),
            model_invoked=True, discard=False,
            proposed=classification, terminal=REFUSAL_LITERAL,
        )
    return _host_receipt(
        "unexecutable_proposal", offered=len(menu.route_ids),
        model_invoked=True, discard=True,
        proposed=classification, terminal=REFUSAL_LITERAL,
    )
