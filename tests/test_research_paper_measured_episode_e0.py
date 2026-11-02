"""E0-only A7 timing/usage accounting against the original A5 episode."""
from __future__ import annotations

import json
from dataclasses import asdict

import pytest
from test_research_paper_scoped_agent_real_e0 import (
    CATALOG,
    INTENTS,
    QUERY,
    Agent,
    model_result,
    source,
)

from schemarouter import (
    AuthorizationPolicy,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    PolicyViolationError,
    PrincipalContext,
)
from schemarouter.errors import ModelAnalysisError
from scripts import research_paper_measured_episode_e0 as measured_module
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_paper_measured_episode_e0 import (
    PaperProviderUsageResponse,
    run_paper_measured_agent_episode_e0,
)


def inputs(view, index, *, supported=True):
    return {
        "view": view,
        "task": {
            "semantic_task_id": "a7-development-synthetic",
            "query": QUERY, "language": "en", "supported": supported,
            "required_routes": ["complete.read"] if supported else [],
            "executor_fixture": {"steps": [{
                "route_id": "complete.read", "argument_rules": {},
                "observation": {"status": "ok", "status_value": "open"},
            }]} if supported else {"steps": []},
        },
        "catalog": CATALOG, "intent_registry": INTENTS, "index": index,
        "model_visible_intent_ids": ("case.lookup",),
        "model_visible_concept_ids": ("case.status",),
    }


@pytest.mark.asyncio
async def test_measured_understand_provider_counts_are_separate_from_original_agent():
    view, index = source()
    seen = []

    class RecordingAgent(Agent):
        def __init__(self):
            super().__init__()
            self.offered_tools = []

        def generate(self, messages, tools):
            self.offered_tools.append(tools)
            return super().generate(messages, tools)

    agent = RecordingAgent()

    async def metered_model(payload):
        seen.append(payload)
        return PaperProviderUsageResponse(
            response=model_result(), input_tokens=41, output_tokens=7,
        )

    result = await run_paper_measured_agent_episode_e0(
        metered_model, agent, **inputs(view, index),
    )
    report = asdict(result.measurement)
    assert result.decision == "offer"
    assert result.episode["passed"] is True
    assert len(seen) == 1
    assert report["understand_called"] is True
    assert report["understand_input_tokens_provider_reported"] == 41
    assert report["understand_output_tokens_provider_reported"] == 7
    assert report["understand_model_callback_wall_latency_ms"] >= 0
    def serialized(obj):
        return json.dumps(
            obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    assert report["understand_request_utf8_bytes"] == len(serialized(seen[0]))
    assert report["agent_input_tokens_reported"] == result.episode["input_tokens"]
    assert report["agent_output_tokens_reported"] == result.episode["output_tokens"]
    assert report["agent_tool_schema_tokens_reported"] == result.episode["tool_schema_tokens"]
    assert len(agent.offered_tools) == 2
    assert report["agent_tool_schema_utf8_bytes_exposed"] == sum(
        len(serialized(tool_definitions)) for tool_definitions in agent.offered_tools
    )
    assert report["total_wall_latency_ms"] >= report["understand_model_callback_wall_latency_ms"]
    assert "query" not in report and "response" not in report
    assert report["independent_e2_qualified"] is False


@pytest.mark.asyncio
async def test_absent_provider_token_receipt_is_unknown_not_fabricated_zero():
    view, index = source()
    result = await run_paper_measured_agent_episode_e0(
        lambda payload: model_result(), Agent(), **inputs(view, index),
    )
    report = asdict(result.measurement)
    assert report["understand_called"] is True
    assert report["understand_input_tokens_provider_reported"] is None
    assert report["understand_request_utf8_bytes"] > 0
    assert report["understand_output_tokens_provider_reported"] is None
    assert report["agent_input_tokens_reported"] > 0


@pytest.mark.asyncio
async def test_empty_source_does_not_call_model_and_reports_no_model_usage():
    original, _ = source()
    router = original.router
    router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    view = capture_authorized_agent_tool_surface(
        router, QUERY, principal=PrincipalContext(subject="synthetic"),
    )
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))

    def forbidden(payload):
        raise AssertionError("empty source must not invoke model")

    class ForbiddenAgent:
        def generate(self, messages, tools):
            raise AssertionError("empty source must not invoke agent")

    result = await run_paper_measured_agent_episode_e0(
        forbidden, ForbiddenAgent(), **inputs(view, index, supported=False),
    )
    report = asdict(result.measurement)
    assert result.decision == "abstain"
    assert result.episode["host_empty_menu_terminal"] is True
    assert report["understand_called"] is False
    assert report["understand_model_callback_wall_latency_ms"] is None
    assert report["understand_input_tokens_provider_reported"] is None
    assert report["understand_request_utf8_bytes"] is None
    assert report["agent_tool_schema_utf8_bytes_exposed"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [
    (True, 3), (-1, 3), (4, 1.5), (10**9, 2), (None, 2),
])
async def test_malformed_provider_usage_fails_before_agent_execution(bad):
    view, index = source()

    class ForbiddenAgent:
        def generate(self, messages, tools):
            raise AssertionError("invalid provider usage must not reach agent")

    with pytest.raises(ModelAnalysisError, match="paper scoped model understanding failed"):
        await run_paper_measured_agent_episode_e0(
            lambda payload: PaperProviderUsageResponse(
                response=model_result(), input_tokens=bad[0], output_tokens=bad[1],
            ),
            ForbiddenAgent(), **inputs(view, index),
        )


@pytest.mark.asyncio
async def test_source_drift_through_model_still_rejects_all_measurements():
    view, index = source()

    def mutate(payload):
        view.router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return PaperProviderUsageResponse(model_result(), 10, 3)

    with pytest.raises(PolicyViolationError):
        await run_paper_measured_agent_episode_e0(
            mutate, Agent(), **inputs(view, index),
        )


@pytest.mark.asyncio
async def test_original_model_cannot_be_called_twice_by_a_regressed_a5_adapter(monkeypatch):
    view, index = source()
    invocations = []

    async def broken_double_callback(wrapped_model, agent, **kwargs):
        await wrapped_model({"original_only": "one"})
        await wrapped_model({"original_only": "two"})
        raise AssertionError("repeated callback should have been refused")

    monkeypatch.setattr(
        measured_module, "run_paper_scoped_agent_episode_e0",
        broken_double_callback,
    )

    def model(payload):
        invocations.append(payload)
        return model_result()

    with pytest.raises(ValueError, match="repeated paper Understand"):
        await run_paper_measured_agent_episode_e0(
            model, Agent(), **inputs(view, index),
        )
    assert len(invocations) == 1


@pytest.mark.asyncio
async def test_failed_scoped_model_does_not_yield_partial_measurement():
    view, index = source()

    class ForbiddenAgent:
        def generate(self, messages, tools):
            raise AssertionError("failed model cannot invoke agent")

    def failed_model(payload):
        raise RuntimeError("provider secret or raw model failure")

    with pytest.raises(ModelAnalysisError, match="paper scoped model understanding failed"):
        await run_paper_measured_agent_episode_e0(
            failed_model, ForbiddenAgent(), **inputs(view, index),
        )
