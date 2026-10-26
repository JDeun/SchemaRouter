"""Opt-in A7 stage metering around the unchanged source-scoped A5 episode.

This is not paired independent E2. Understand usage is provider-reported when
the host adapter supplies it; absence of a receipt never becomes zero tokens.
"""
from __future__ import annotations

import inspect
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from schemarouter.concept_retrieval import NativeConceptCatalog
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.paper_understood_direct_plan import PaperIntentRegistry
from scripts.agent_utility_generated_common import GeneratedEpisodeAgent
from scripts.research_authorized_agent_tool_surface import AuthorizedAgentToolSurface
from scripts.research_paper_refusal_eval_e0 import Decision
from scripts.research_paper_scoped_agent_episode_e0 import (
    run_paper_scoped_agent_episode_e0,
)

MAX_PROVIDER_REPORTED_TOKENS = 10_000_000


@dataclass(frozen=True)
class PaperProviderUsageResponse:
    """Host model adapter's answer and separately observed usage counters.

    These counts are not inferred from model-produced structured hints.
    Original provider metering must still be independently audited in E2.
    """

    response: dict[str, Any] | str
    input_tokens: int
    output_tokens: int


PaperMeteredModel = Callable[
    [dict[str, Any]],
    dict[str, Any] | str | PaperProviderUsageResponse
    | Awaitable[dict[str, Any] | str | PaperProviderUsageResponse],
]


@dataclass(frozen=True)
class PaperStageMeasurement:
    """Sanitized mechanical timing and *reported* token counters only."""

    understand_called: bool
    understand_model_callback_wall_latency_ms: float | None
    understand_request_utf8_bytes: int | None
    understand_input_tokens_provider_reported: int | None
    understand_output_tokens_provider_reported: int | None
    agent_input_tokens_reported: int
    agent_output_tokens_reported: int
    agent_tool_schema_tokens_reported: int
    agent_tool_schema_utf8_bytes_exposed: int
    agent_wall_latency_ms: float
    total_wall_latency_ms: float
    independent_e2_qualified: bool = False


@dataclass(frozen=True)
class PaperMeteredAgentEpisode:
    decision: Decision
    episode: dict[str, Any]
    measurement: PaperStageMeasurement


def _provider_token_count(value: Any) -> int:
    if (
        type(value) is not int
        or not 0 <= value <= MAX_PROVIDER_REPORTED_TOKENS
    ):
        raise ValueError("invalid provider-reported paper model usage")
    return value


async def run_paper_measured_agent_episode_e0(
    model: PaperMeteredModel,
    agent: GeneratedEpisodeAgent,
    *,
    view: AuthorizedAgentToolSurface,
    task: dict[str, Any],
    catalog: NativeConceptCatalog,
    intent_registry: PaperIntentRegistry,
    index: NativeSchemaGraphIndex,
    model_visible_intent_ids: tuple[str, ...],
    model_visible_concept_ids: tuple[str, ...],
) -> PaperMeteredAgentEpisode:
    """Meter the original A5 pipeline once; do not create a second agent.

    The pre-model stage's wall clock is locally observed; tokens are `None`
    unless the caller's provider API explicitly returns a metering receipt.
    Agent counts remain separate from the unchanged fixed5 agent's counters.
    """
    started = time.perf_counter_ns()
    callback_count = 0
    callback_wall_ms: float | None = None
    understand_request_bytes: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    agent_schema_bytes = 0

    def canonical_bytes(value: Any) -> int:
        """Count canonical JSON bytes, never confuse them with token usage."""
        return len(json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8"))

    class SchemaMeteredAgent:
        def generate(
            self, messages: list[dict[str, str]], tools: list[dict[str, Any]],
        ) -> dict[str, Any]:
            nonlocal agent_schema_bytes
            agent_schema_bytes += canonical_bytes(tools)
            return agent.generate(messages, tools)

    async def timed_model(payload: dict[str, Any]) -> dict[str, Any] | str:
        nonlocal callback_count, callback_wall_ms, understand_request_bytes
        nonlocal input_tokens, output_tokens
        if callback_count:
            raise ValueError("repeated paper Understand model callback")
        callback_count += 1
        understand_request_bytes = canonical_bytes(payload)
        model_started = time.perf_counter_ns()
        result = model(payload)
        if inspect.isawaitable(result):
            result = await result
        callback_wall_ms = (time.perf_counter_ns() - model_started) / 1_000_000
        if isinstance(result, PaperProviderUsageResponse):
            input_tokens = _provider_token_count(result.input_tokens)
            output_tokens = _provider_token_count(result.output_tokens)
            return result.response
        return result

    decision, episode = await run_paper_scoped_agent_episode_e0(
        timed_model, SchemaMeteredAgent(), view=view, task=task, catalog=catalog,
        intent_registry=intent_registry, index=index,
        model_visible_intent_ids=model_visible_intent_ids,
        model_visible_concept_ids=model_visible_concept_ids,
    )
    # The original A5 adapter's source check executes before it returns.
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
    measurement = PaperStageMeasurement(
        understand_called=callback_count == 1,
        understand_model_callback_wall_latency_ms=callback_wall_ms,
        understand_request_utf8_bytes=understand_request_bytes,
        understand_input_tokens_provider_reported=input_tokens,
        understand_output_tokens_provider_reported=output_tokens,
        agent_input_tokens_reported=int(episode["input_tokens"]),
        agent_output_tokens_reported=int(episode["output_tokens"]),
        agent_tool_schema_tokens_reported=int(episode["tool_schema_tokens"]),
        agent_tool_schema_utf8_bytes_exposed=agent_schema_bytes,
        agent_wall_latency_ms=float(episode["episode_wall_latency_ms"]),
        total_wall_latency_ms=elapsed_ms,
    )
    return PaperMeteredAgentEpisode(decision, episode, measurement)
