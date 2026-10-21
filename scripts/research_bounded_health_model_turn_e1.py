"""E1 opt-in host request deadline and single-flight guard for health-scoped LLM.

Timeout means the CALLER stops waiting, not that an already-running Python
thread/CPU model was forcibly terminated. The still-running task is quarantined
and another model turn on this controller is refused until it actually ends.
No model-selected operation is executed; no source or product default changed.
"""
from __future__ import annotations

import asyncio
import math
from threading import Event
from typing import Any

from schemarouter import PrincipalContext, SchemaRouter
from scripts.research_health_zero_menu_short_circuit_e1 import (
    REFUSAL_LITERAL,
    run_strict_health_gated_model_turn,
)


class _GenerationStartWitness:
    """Thread-safe, host-only proof the model delegate actually began."""

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate
        self.started = Event()

    def generate(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]],
    ) -> Any:
        self.started.set()
        return self._delegate.generate(messages, tools)


def _quarantined_receipt(
    status: str, *, invoked: bool,
) -> dict[str, Any]:
    if status not in ("model_busy", "generation_timeout", "generation_error"):
        raise ValueError("invalid sanitized model deadline state")
    return {
        "status": status,
        "terminal_text": REFUSAL_LITERAL,
        "model_invoked": invoked,
        "model_output_discarded": True,
        "offered_tool_count": None,  # never falsely claim a measured zero
        "proposed_action_class": "not_scored_model_deadline",
        "executed_tool_calls": 0,
        "provider_http_requests": 0,
        "semantic_no_fit_established": False,
        "real_provider_success_qualified": False,
        "independent_e2_qualified": False,
        "production_default_changed": False,
    }


class BoundedHealthModelTurnE1:
    """One model, one router, at most one ongoing model-generation host turn.

    The application must retain this object for the whole model session.
    Isolation is PER CONTROLLER, not a global process-wide Qwen mutex.
    """

    def __init__(
        self, agent: Any, router: SchemaRouter, *,
        model_deadline_seconds: float,
    ) -> None:
        if (
            not callable(getattr(agent, "generate", None))
            or not isinstance(router, SchemaRouter)
            or type(model_deadline_seconds) not in (float, int)
            or not math.isfinite(model_deadline_seconds)
            or not 0.01 <= model_deadline_seconds <= 60.0
        ):
            raise ValueError("trusted model/router and finite deadline required")
        self._agent = agent
        self._router = router
        self._deadline = float(model_deadline_seconds)
        self._active: asyncio.Task[dict[str, Any]] | None = None
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._closed = False

    @property
    def busy(self) -> bool:
        return self._active is not None and not self._active.done()

    def close(self) -> None:
        """Stop admitting turns; cannot force-kill a running CPU model thread."""
        self._closed = True

    def _consume_late_result(
        self, completed: asyncio.Task[dict[str, Any]],
    ) -> None:
        # A timed-out task is intentionally NOT cancelled: late text and
        # arguments are discarded, and the task exception is retrieved
        # without exposing model/source details or "Task exception" logs.
        try:
            completed.result()
        except BaseException:
            pass
        if self._active is completed:
            self._active = None

    async def run(
        self, *,
        query: str,
        principal: PrincipalContext,
        host_request_inputs: dict[str, Any],
        system_prompt: str,
        prior_public_observation: dict[str, Any] | None = None,
        executed_route_ids: tuple[str, ...] = (),
        max_probe_age_seconds: float = 60.0,
    ) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        if self._event_loop is None:
            self._event_loop = loop
        if loop is not self._event_loop or self._closed:
            raise RuntimeError("model controller closed or used across event loops")
        if (
            type(query) is not str or not query.strip()
            or type(system_prompt) is not str or not system_prompt.strip()
            or not isinstance(principal, PrincipalContext)
            or type(host_request_inputs) is not dict
        ):
            raise ValueError("trusted host model turn input required")
        if self.busy:
            return _quarantined_receipt("model_busy", invoked=False)
        # Synchronous assignment BEFORE the first await prevents another
        # coroutine on the same loop from entering a second CPU generation.
        started = _GenerationStartWitness(self._agent)
        task = asyncio.create_task(run_strict_health_gated_model_turn(
            started, self._router, query=query, principal=principal,
            host_request_inputs=host_request_inputs,
            system_prompt=system_prompt,
            prior_public_observation=prior_public_observation,
            executed_route_ids=executed_route_ids,
            max_probe_age_seconds=max_probe_age_seconds,
        ))
        self._active = task
        task.add_done_callback(self._consume_late_result)
        try:
            # Shield preserves the thread and its outstanding quarantine
            # on request deadline expiry or cancellation of THIS waiter.
            return await asyncio.wait_for(
                asyncio.shield(task), timeout=self._deadline,
            )
        except asyncio.TimeoutError:
            return _quarantined_receipt(
                "generation_timeout", invoked=started.started.is_set(),
            )
        except asyncio.CancelledError:
            # The original calling coroutine may be cancelled by a client
            # disconnect, while the CPU thread still runs; retain quarantine.
            raise
        except Exception:
            return _quarantined_receipt(
                "generation_error", invoked=started.started.is_set(),
            )
