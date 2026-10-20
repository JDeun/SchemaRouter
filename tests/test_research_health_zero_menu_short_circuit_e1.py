"""Host-only strict temporary-unavailable response (no model/no provider)."""
from __future__ import annotations

import json

import httpx
import pytest

from schemarouter import PrincipalContext
from scripts.research_health_zero_menu_short_circuit_e1 import (
    REFUSAL_LITERAL,
    run_strict_health_gated_model_turn,
)
from scripts.research_live_health_model_menu_e1 import (
    GEO,
    build_health_aware_router,
)

ACTOR = PrincipalContext(subject="e1-readable", roles=("reader",))
INPUTS = {"name": "Seoul", "language": "en", "country_code": "KR"}
QUERY = "Show current Celsius in Seoul"
SYSTEM = "Use only source-authorized tools. If unable, reply REQUEST_MORE_TOOLS."
GOOD_TOOL = (
    '<tool_call>{"name":"open_meteo_geocoding__search",'
    '"arguments":{"name":"Seoul","country_code":"KR","language":"en"}}'
    "</tool_call>"
)
HIDDEN_TOOL = (
    '<tool_call>{"name":"open_meteo_weather__current",'
    '"arguments":{"latitude":37.56,"longitude":126.98}}</tool_call>'
)


class RecordingAgent:
    def __init__(self, response: str, on_generate=None):
        self.response = response
        self.calls = 0
        self.names = []
        self.on_generate = on_generate

    def generate(self, messages, tools):
        self.calls += 1
        self.names.append(tuple(item["name"] for item in tools))
        assert len(messages) == 2
        if self.on_generate is not None:
            self.on_generate()
        return {"text": self.response}


async def run(router, agent, *, request_inputs=None):
    return await run_strict_health_gated_model_turn(
        agent, router, query=QUERY, principal=ACTOR,
        host_request_inputs=INPUTS if request_inputs is None else request_inputs,
        system_prompt=SYSTEM,
    )


def deny_external_requests(request: httpx.Request) -> httpx.Response:
    raise AssertionError("cannot make business GET in health model preflight")


@pytest.mark.asyncio
async def test_host_returns_exact_unavailable_without_generating_model_text():
    healthy = {"ok": False}

    async def probe() -> bool:
        return healthy["ok"]

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(deny_external_requests),
    ) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={GEO: probe},
        )
        agent = RecordingAgent("I cannot do that.")
        await router.check_health_once()
        no_route = await run(router, agent)
        assert no_route["status"] == "temporary_unavailable"
        assert no_route["terminal_text"] == REFUSAL_LITERAL
        assert no_route["model_invoked"] is False
        assert no_route["proposed_action_class"] == "not_invoked_no_viable_route"
        assert no_route["semantic_no_fit_established"] is False
        assert no_route["executed_tool_calls"] == 0
        assert no_route["provider_http_requests"] == 0
        assert agent.calls == 0

        healthy["ok"] = True
        await router.check_health_once()
        restored = await run(router, RecordingAgent(GOOD_TOOL))
        assert restored["status"] == "proposal_only"
        assert restored["proposed_action_class"] == "visible_tool_proposal"
        assert restored["offered_tool_count"] == 1
        assert restored["terminal_text"] is None
        await router.aclose()


@pytest.mark.asyncio
async def test_unknown_no_probe_remains_unavailable_and_no_model_invocation():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(deny_external_requests),
    ) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={},
        )
        agent = RecordingAgent(GOOD_TOOL)
        assert (await run(router, agent))["status"] == "temporary_unavailable"
        assert agent.calls == 0
        await router.aclose()


@pytest.mark.asyncio
async def test_host_does_not_make_semantic_no_fit_claim_on_missing_inputs():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(deny_external_requests),
    ) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={GEO: lambda: True},
        )
        await router.check_health_once()
        agent = RecordingAgent(GOOD_TOOL)
        receipt = await run(router, agent, request_inputs={})
        assert receipt["status"] == "inputs_missing"
        assert receipt["terminal_text"] == REFUSAL_LITERAL
        assert receipt["semantic_no_fit_established"] is False
        assert agent.calls == 0
        await router.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(("response", "expected_status", "classification"), (
    (HIDDEN_TOOL, "unexecutable_proposal", "hidden_or_unknown_tool_proposal"),
    ("not-JSON", "terminal_no_tool", "nonstandard_model_terminal"),
    ("REQUEST_MORE_TOOLS<|im_end|>", "terminal_no_tool", "exact_model_refusal"),
    ("<tool_call>broken", "unexecutable_proposal", "invalid_format"),
))
async def test_model_proposal_cannot_bypass_host_source_authority(
    response, expected_status, classification,
):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(deny_external_requests),
    ) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={GEO: lambda: True},
        )
        await router.check_health_once()
        agent = RecordingAgent(response)
        receipt = await run(router, agent)
        assert agent.calls == 1
        assert agent.names == [("open_meteo_geocoding__search",)]
        assert receipt["status"] == expected_status
        assert receipt["proposed_action_class"] == classification
        assert receipt["executed_tool_calls"] == 0
        assert receipt["provider_http_requests"] == 0
        assert receipt["independent_e2_qualified"] is False
        assert "Seoul" not in json.dumps(receipt)
        await router.aclose()


@pytest.mark.asyncio
async def test_new_cooldown_during_generation_disposes_of_model_tool_proposal():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(deny_external_requests),
    ) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={GEO: lambda: True},
        )
        await router.check_health_once()
        agent = RecordingAgent(
            GOOD_TOOL,
            on_generate=lambda: router.mark_access_unavailable(
                "open_meteo_geocoding", "search",
            ),
        )
        receipt = await run(router, agent)
        assert agent.calls == 1
        assert receipt["status"] == "needs_revalidation"
        assert receipt["model_output_discarded"] is True
        assert receipt["terminal_text"] == REFUSAL_LITERAL
        assert receipt["executed_tool_calls"] == 0
        assert receipt["provider_http_requests"] == 0
        await router.aclose()


@pytest.mark.asyncio
async def test_unhealthy_to_healthy_to_unhealthy_is_deterministic_across_requests():
    state = {"ok": True}

    async def probe() -> bool:
        return state["ok"]

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(deny_external_requests),
    ) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={GEO: probe},
        )
        agent = RecordingAgent(GOOD_TOOL)
        for ok in (True, False, False, True, False):
            state["ok"] = ok
            await router.check_health_once()
            result = await run(router, agent)
            assert result["status"] == (
                "proposal_only" if ok else "temporary_unavailable"
            )
            assert result["terminal_text"] == (
                None if ok else REFUSAL_LITERAL
            )
        assert agent.calls == 2
        await router.aclose()


@pytest.mark.asyncio
async def test_invalid_host_input_aborts_before_any_model_or_provider():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(deny_external_requests),
    ) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={GEO: lambda: True},
        )
        agent = RecordingAgent(GOOD_TOOL)
        with pytest.raises(ValueError, match="trusted agent"):
            await run_strict_health_gated_model_turn(
                agent, router, query="", principal=ACTOR,
                host_request_inputs=INPUTS, system_prompt=SYSTEM,
            )
        assert agent.calls == 0
        await router.aclose()
