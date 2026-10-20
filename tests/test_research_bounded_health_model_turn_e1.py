"""No-network bounded host turn: deadlines never authorize a late proposal."""
from __future__ import annotations

import asyncio
import json
from threading import Event

import httpx
import pytest

from schemarouter import PrincipalContext
from scripts.research_bounded_health_model_turn_e1 import (
    BoundedHealthModelTurnE1,
)
from scripts.research_live_health_model_menu_e1 import (
    GEO,
    build_health_aware_router,
)

ACTOR = PrincipalContext(subject="bounded-reader-e1", roles=("reader",))
INPUTS = {"name": "Seoul", "language": "en", "country_code": "KR"}
QUERY = "Current weather in Seoul"
SYSTEM = "Call only exposed read-only tools"
VISIBLE = (
    '<tool_call>{"name":"open_meteo_geocoding__search",'
    '"arguments":{"name":"Seoul","language":"en","country_code":"KR"}}'
    "</tool_call>"
)


def no_network(request: httpx.Request) -> httpx.Response:
    raise AssertionError("an E1 model proposal must not execute provider GET")


async def _invoke(controller):
    return await controller.run(
        query=QUERY, principal=ACTOR, host_request_inputs=INPUTS,
        system_prompt=SYSTEM,
    )


class BlockingModel:
    def __init__(self):
        self.started = Event()
        self.release = Event()
        self.calls = 0

    def generate(self, messages, tools):
        self.calls += 1
        self.started.set()
        assert len(messages) == 2
        assert len(tools) == 1
        if not self.release.wait(timeout=3):
            raise RuntimeError("PRIVATE_BLOCKED_MODEL_CANARY")
        return {"text": VISIBLE}


class InstantModel:
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools):
        self.calls += 1
        return {"text": VISIBLE}


class BrokenModel:
    def generate(self, messages, tools):
        raise RuntimeError("PRIVATE_GENERATION_EXCEPTION_CANARY")


async def _router(client, *, healthy=True):
    router = build_health_aware_router(
        client, trusted_health_probes={GEO: lambda: healthy},
    )
    await router.check_health_once()
    return router


@pytest.mark.asyncio
async def test_unknown_or_down_provider_short_circuits_without_model_generation():
    async with httpx.AsyncClient(transport=httpx.MockTransport(no_network)) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={},
        )
        agent = InstantModel()
        guard = BoundedHealthModelTurnE1(
            agent, router, model_deadline_seconds=0.05,
        )
        for _ in range(3):
            receipt = await _invoke(guard)
            assert receipt["status"] == "temporary_unavailable"
            assert receipt["model_invoked"] is False
            assert receipt["terminal_text"] == "REQUEST_MORE_TOOLS"
            assert receipt["executed_tool_calls"] == 0
        assert agent.calls == 0
        guard.close()
        await router.aclose()


@pytest.mark.asyncio
async def test_timed_out_cpu_thread_stays_quarantined_until_real_completion():
    async with httpx.AsyncClient(transport=httpx.MockTransport(no_network)) as client:
        router = await _router(client)
        agent = BlockingModel()
        guard = BoundedHealthModelTurnE1(
            agent, router, model_deadline_seconds=0.05,
        )
        first = await _invoke(guard)
        assert first["status"] == "generation_timeout"
        assert first["model_invoked"] is True
        assert first["model_output_discarded"] is True
        assert first["offered_tool_count"] is None
        assert first["terminal_text"] == "REQUEST_MORE_TOOLS"
        assert first["semantic_no_fit_established"] is False
        assert first["executed_tool_calls"] == 0
        assert guard.busy
        busy = await _invoke(guard)
        assert busy["status"] == "model_busy"
        assert busy["model_invoked"] is False
        assert agent.calls == 1  # never start a second concurrent Qwen call
        agent.release.set()
        for _ in range(100):
            if not guard.busy:
                break
            await asyncio.sleep(0.01)
        assert not guard.busy
        # Late first result was ignored. Only NEW authorized proposal is
        # returned on a NEW host request once the CPU worker actually ended.
        after = await _invoke(guard)
        assert after["status"] == "proposal_only"
        assert after["terminal_text"] is None
        assert agent.calls == 2
        assert "PRIVATE_" not in json.dumps(first)
        assert "PRIVATE_" not in json.dumps(after)
        guard.close()
        await router.aclose()


@pytest.mark.asyncio
async def test_waiter_cancellation_does_not_cancel_background_model_thread():
    async with httpx.AsyncClient(transport=httpx.MockTransport(no_network)) as client:
        router = await _router(client)
        agent = BlockingModel()
        guard = BoundedHealthModelTurnE1(
            agent, router, model_deadline_seconds=0.5,
        )
        pending = asyncio.create_task(_invoke(guard))
        try:
            assert await asyncio.to_thread(agent.started.wait, 1)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            assert guard.busy
            assert (await _invoke(guard))["status"] == "model_busy"
            assert agent.calls == 1
        finally:
            agent.release.set()
        for _ in range(100):
            if not guard.busy:
                break
            await asyncio.sleep(0.01)
        assert not guard.busy
        guard.close()
        await router.aclose()


@pytest.mark.asyncio
async def test_model_exception_is_sanitized_and_slot_released():
    async with httpx.AsyncClient(transport=httpx.MockTransport(no_network)) as client:
        router = await _router(client)
        guard = BoundedHealthModelTurnE1(
            BrokenModel(), router, model_deadline_seconds=0.25,
        )
        receipt = await _invoke(guard)
        assert receipt["status"] == "generation_error"
        assert receipt["model_output_discarded"] is True
        assert receipt["executed_tool_calls"] == 0
        assert receipt["provider_http_requests"] == 0
        assert "PRIVATE_" not in json.dumps(receipt)
        await router.aclose()


@pytest.mark.asyncio
async def test_two_simultaneous_host_calls_admit_one_model_generation():
    async with httpx.AsyncClient(transport=httpx.MockTransport(no_network)) as client:
        router = await _router(client)
        agent = BlockingModel()
        guard = BoundedHealthModelTurnE1(
            agent, router, model_deadline_seconds=0.05,
        )
        one, two = await asyncio.gather(_invoke(guard), _invoke(guard))
        assert {one["status"], two["status"]} == {
            "generation_timeout", "model_busy",
        }
        assert agent.calls == 1
        agent.release.set()
        for _ in range(100):
            if not guard.busy:
                break
            await asyncio.sleep(0.01)
        assert not guard.busy
        guard.close()
        await router.aclose()


@pytest.mark.parametrize("bad", (0, -1, True, float("nan"), float("inf"), 61))
def test_deadline_is_finite_bounded_and_not_boolean(bad):
    with pytest.raises(ValueError, match="finite deadline"):
        BoundedHealthModelTurnE1(
            InstantModel(), object(), model_deadline_seconds=bad,
        )


@pytest.mark.asyncio
async def test_closed_guard_refuses_new_requests_without_running_model():
    async with httpx.AsyncClient(transport=httpx.MockTransport(no_network)) as client:
        router = await _router(client)
        agent = InstantModel()
        guard = BoundedHealthModelTurnE1(
            agent, router, model_deadline_seconds=0.25,
        )
        guard.close()
        with pytest.raises(RuntimeError, match="closed"):
            await _invoke(guard)
        assert agent.calls == 0
        await router.aclose()
