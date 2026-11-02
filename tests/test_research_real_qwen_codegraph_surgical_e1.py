"""Four-arm original Open-Meteo E1 checks (scripted model, mocked HTTP)."""

from __future__ import annotations

import httpx
import pytest
from test_research_real_qwen_open_meteo_two_hop_e1 import (
    CITY,
    COUNTRY,
    FINAL,
    FIRST,
    LANGUAGE,
    SECOND,
    _fixture_transport,
)

from scripts import research_real_qwen_open_meteo_two_hop_e1 as study

SCHEMA_REQUEST = (
    '<tool_call>{"name":"research__request_scoped_source_schema",'
    '"arguments":{"route_ids":["open_meteo_geocoding.search",'
    '"open_meteo_weather.current"]}}</tool_call>'
)


class SchemaAwareAgent:
    def __init__(self, *, complete=False, with_tokens=True):
        self.complete = complete
        self.with_tokens = with_tokens
        self.menus = []

    def generate(self, messages, tools):
        menu = tuple(tool["name"] for tool in tools)
        self.menus.append(menu)
        calls = sum("<tool_call>" in item["content"] for item in messages)
        if self.complete and menu == ("research__request_scoped_source_schema",):
            action = SCHEMA_REQUEST
        elif self.complete and calls == 1 and menu == (
            "open_meteo_geocoding__search", "open_meteo_weather__current",
        ):
            action = FIRST
        elif self.complete and calls == 2:
            action = SECOND
        elif self.complete and calls == 3:
            action = FINAL
        else:
            action = "REQUEST_MORE_TOOLS"
        result = {"text": action, "latency_ms": 2.0, "context_overflow": False}
        if self.with_tokens:
            result.update(input_tokens=41, tool_tokens=7, output_tokens=13)
        return result


def _qualified_kwargs():
    return {
        "documented_noncommercial_e1": True,
        "host_concept_catalog": study.documented_open_meteo_e1_catalog(),
        "approved_host_roots": frozenset({study.ROUTES[0]}),
    }


@pytest.mark.asyncio
async def test_four_arm_requires_same_tasks_principal_source_and_k():
    seen = []
    agent = SchemaAwareAgent()
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        result = await study.compare_codegraph_surgical_e1(
            agent, client, **_qualified_kwargs(),
        )
    assert result["arms"] == (
        "all_visible", "lexical_k5", "concept_graph_optin", "surgical_g5_e1",
    )
    assert len(result["outcomes"]) == 12
    assert result["requested_k"] == result["max_model_turns"] == 5
    assert set(row["language"] for row in result["outcomes"]) == {"en", "ko", "ja"}
    assert all(row["original_provider_e1"] for row in result["outcomes"])
    assert all(row["actual_source_calls"] == 0 for row in result["outcomes"])
    assert seen == []


@pytest.mark.asyncio
async def test_surgical_arm_never_preinvokes_provider_or_fabricates_geo_coordinates():
    seen = []
    agent = SchemaAwareAgent(complete=True)
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        row = await study._evaluate_surgical_one(
            agent, client, language=LANGUAGE, city=CITY, country=COUNTRY,
            **_qualified_kwargs(),
        )
    assert row["full_task_complete"] is True
    assert row["schema_requests"] == 1
    assert row["actual_source_calls"] == 2
    assert seen == ["/v1/search", "/v1/forecast"]
    assert agent.menus[0] == ("research__request_scoped_source_schema",)
    assert agent.menus[1] == (
        "open_meteo_geocoding__search", "open_meteo_weather__current",
    )
    assert row["model_turns"] == 4
    assert row["total_model_tokens"] == 4 * (41 + 13)


@pytest.mark.asyncio
async def test_surgical_arm_rejects_forged_coordinates_before_second_http():
    seen = []

    class ForgedCoordinates(SchemaAwareAgent):
        def generate(self, messages, tools):
            response = super().generate(messages, tools)
            if "open_meteo_weather__current" in (
                tool["name"] for tool in tools
            ) and sum("<tool_call>" in row["content"] for row in messages) == 2:
                response["text"] = SECOND.replace("37.56", "37.98")
            return response

    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        row = await study._evaluate_surgical_one(
            ForgedCoordinates(complete=True), client,
            language=LANGUAGE, city=CITY, country=COUNTRY,
            **_qualified_kwargs(),
        )
    assert row["termination_reason"] == "unbound_source_arguments"
    assert row["actual_source_calls"] == 1
    assert row["real_forecast_http_attempts"] == 0
    assert seen == ["/v1/search"]


@pytest.mark.asyncio
async def test_surgical_arm_real_http_failure_keeps_source_failure_stage():
    seen = []

    def fail(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        raise httpx.ConnectError("private transport error", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
        row = await study._evaluate_surgical_one(
            SchemaAwareAgent(complete=True), client,
            language=LANGUAGE, city=CITY, country=COUNTRY,
            **_qualified_kwargs(),
        )
    assert row["full_task_complete"] is False
    assert row["trusted_failure_stage"] == "geocode_http_transport_failure"
    assert row["real_geocoding_http_attempts"] == 1
    assert row["real_forecast_http_attempts"] == 0
    assert seen == ["/v1/search"]
    assert "private transport error" not in str(row)


@pytest.mark.asyncio
async def test_four_arm_source_failure_has_null_denominator_and_tokens(monkeypatch):
    async def fail_source(_agent, _client, *, language, menu_mode, **kwargs):
        del kwargs
        return {
            "language": language, "full_task_complete": False,
            "actual_source_calls": 0,
            "trusted_failure_stage": "geocode_http_transport_failure"
            if (language, menu_mode) == ("ko", "lexical_k5") else None,
        }

    async def fail_surgical(_agent, _client, *, language, **kwargs):
        del kwargs
        return {
            "language": language, "full_task_complete": False,
            "actual_source_calls": 0, "trusted_failure_stage": None,
            "model_input_tokens": None, "tool_schema_tokens": None,
            "model_output_tokens": None, "total_model_tokens": None,
        }

    monkeypatch.setattr(study, "evaluate_one", fail_source)
    monkeypatch.setattr(study, "_evaluate_surgical_one", fail_surgical, raising=False)
    async with httpx.AsyncClient(transport=_fixture_transport([])) as client:
        result = await study.compare_codegraph_surgical_e1(
            SchemaAwareAgent(), client, **_qualified_kwargs(),
        )
    assert result["status"] == "INCOMPARABLE_SOURCE_FAILURE"
    assert result["task_success_rate"] is None
    assert result["qualified_task_denominator"] is None
    assert len(result["outcomes"]) == 12
    assert next(row for row in result["outcomes"]
                if row["condition"] == "surgical_g5_e1")["model_input_tokens"] is None


@pytest.mark.asyncio
async def test_model_runtime_unavailable_is_blocked_not_zero_success():
    seen = []
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        result = await study.compare_codegraph_surgical_e1(
            None, client, **_qualified_kwargs(),
        )
    assert result["status"] == "BLOCKED_MODEL_RUNTIME"
    assert result["task_success_rate"] is None
    assert result["qualified_task_denominator"] is None
    assert result["outcomes"] == ()
    assert seen == []


@pytest.mark.asyncio
async def test_each_meta_request_and_followup_turn_counts_actual_tool_tokens():
    seen = []

    class RequestThenStop(SchemaAwareAgent):
        def generate(self, messages, tools):
            response = super().generate(messages, tools)
            if tuple(tool["name"] for tool in tools) == (
                "research__request_scoped_source_schema",
            ):
                response["text"] = SCHEMA_REQUEST
            return response

    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        row = await study._evaluate_surgical_one(
            RequestThenStop(), client,
            language=LANGUAGE, city=CITY, country=COUNTRY,
            **_qualified_kwargs(),
        )
        missing = await study._evaluate_surgical_one(
            SchemaAwareAgent(with_tokens=False), client,
            language=LANGUAGE, city=CITY, country=COUNTRY,
            **_qualified_kwargs(),
        )
    assert row["model_turns"] == 2
    assert row["schema_requests"] == 1
    assert row["model_input_tokens"] == 82
    assert row["tool_schema_tokens"] == 14
    assert row["model_output_tokens"] == 26
    assert row["actual_source_calls"] == 0
    assert missing["model_input_tokens"] is None
    assert missing["total_model_tokens"] is None
    assert seen == []


@pytest.mark.asyncio
async def test_original_three_arm_comparison_remains_unchanged():
    seen = []
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        row = await study.compare_graph_native_e1(
            SchemaAwareAgent(), client, **_qualified_kwargs(),
        )
    assert row["arms"] == study.G5_COMPARISON_ARMS
    assert len(row["outcomes"]) == 9
    assert "surgical_g5_e1" not in row["arms"]
    assert seen == []
