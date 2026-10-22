"""Native-source E1 arm must decline unattested inputs without fake results."""

from __future__ import annotations

import json

import httpx
import pytest
from test_native_concept_graph_vertical_slice import _catalog
from test_research_real_qwen_open_meteo_two_hop_e1 import (
    CITY,
    COUNTRY,
    FINAL,
    FIRST,
    LANGUAGE,
    SECOND,
    ScriptedAgent,
    _fixture_transport,
)

from schemarouter import EndpointSpec, ToolSpec
from scripts import research_real_qwen_open_meteo_two_hop_e1 as study
from scripts.research_open_meteo_live_two_hop_e1 import build_live_router


@pytest.mark.asyncio
async def test_unattested_live_open_meteo_g5_never_fabricates_join() -> None:
    seen: list[str] = []
    agent = ScriptedAgent([FIRST, SECOND, FINAL])
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        router, _, _ = build_live_router(client)
        assert router.authorization_policy is None
        assert any(tool.license is None for tool in router.registry.tools())
        result = await study.evaluate_one(
            agent, client, language=LANGUAGE, city=CITY, country=COUNTRY,
            menu_mode="concept_graph_optin",
        )
    assert result["status"] == "BLOCKED_SOURCE_SEMANTICS"
    assert result["full_task_complete"] is None
    assert result["real_geocoding_http_attempts"] == 0
    assert result["real_forecast_http_attempts"] == 0
    assert seen == [] and agent.calls == 0


@pytest.mark.asyncio
async def test_graph_e1_requires_verified_geocoding_before_weather() -> None:
    seen: list[str] = []
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        row = await study.evaluate_one(
            ScriptedAgent([SECOND]), client,
            language=LANGUAGE, city=CITY, country=COUNTRY,
            menu_mode="all_visible",
        )
    assert row["full_task_complete"] is False
    assert row["real_forecast_http_attempts"] == 0
    assert seen == []


@pytest.mark.asyncio
async def test_graph_e1_scoped_selection_never_calls_host() -> None:
    seen: list[str] = []
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        result = await study.compare_graph_native_e1(ScriptedAgent([FIRST]), client)
    assert result["status"] == "BLOCKED_SOURCE_SEMANTICS"
    assert result["task_success_rate"] is None
    assert result["arms"] == ("all_visible", "lexical_k5", "concept_graph_optin")
    assert seen == []


@pytest.mark.asyncio
async def test_host_reviewed_catalog_and_roots_reach_pair_preflight(monkeypatch) -> None:
    """Future qualified source intake is injectable; not a permanent block."""
    catalog = _catalog()
    roots = frozenset({"open_meteo_geocoding.search"})
    observed = []

    async def capture(agent, client, *, host_concept_catalog=None, approved_host_roots=frozenset()):
        del agent, client
        observed.append((host_concept_catalog, approved_host_roots))
        return {"status": "BLOCKED_SOURCE_SEMANTICS"}

    monkeypatch.setattr(study, "compare_graph_native_e1", capture)
    row = await study.real_cpu_graph_compare(
        host_concept_catalog=catalog, approved_host_roots=roots,
    )
    assert row["status"] == "BLOCKED_SOURCE_SEMANTICS"
    assert observed == [(catalog, roots)]


@pytest.mark.asyncio
async def test_paired_native_graph_source_drift_is_not_scored(monkeypatch) -> None:
    original = study.build_live_router
    count = 0

    def changed(client, *, transport_retry_budget=0):
        nonlocal count
        count += 1
        router, geo, weather = original(client, transport_retry_budget=transport_retry_budget)
        if count == 2:
            router.add_tool(ToolSpec(name="unexpected_revision", endpoints=[
                EndpointSpec(name="read", read_only=True),
            ]))
        return router, geo, weather

    monkeypatch.setattr(study, "build_live_router", changed)
    seen: list[str] = []
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        result = await study.compare_graph_native_e1(ScriptedAgent([FIRST]), client)
    assert result["status"] == "INCOMPARABLE_SOURCE_DRIFT"
    assert result["task_success_rate"] is None
    assert seen == []


@pytest.mark.asyncio
async def test_graph_e1_false_final_not_scored_as_pass() -> None:
    seen: list[str] = []
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        row = await study.evaluate_one(
            ScriptedAgent([FIRST, SECOND, json.dumps({
                "temperature_2m": 100., "unit": "°C",
                "observed_at": "2026-10-18T10:00",
            })]), client, language=LANGUAGE, city=CITY, country=COUNTRY,
        )
    assert row["real_forecast_calls"] == 1
    assert row["strict_final_answer_correct"] is False
    assert row["full_task_complete"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(("language", "city", "country"), (
    ("en", "Seoul", "KR"), ("ko", "서울특별시", "KR"),
    ("ja", "東京都", "JP"),
))
async def test_graph_e1_en_ko_ja_same_source_and_k(language, city, country) -> None:
    # An unattested source is blocked identically in every declared language.
    seen: list[str] = []
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        row = await study.evaluate_one(
            ScriptedAgent([FIRST]), client, language=language, city=city,
            country=country, menu_mode="concept_graph_optin",
        )
    assert row["status"] == "BLOCKED_SOURCE_SEMANTICS"
    assert row["requested_k"] == 5
    assert row["model_turns"] == 0
    assert seen == []


@pytest.mark.asyncio
async def test_legacy_e1_output_unchanged() -> None:
    seen: list[str] = []
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        row = await study.evaluate_one(
            ScriptedAgent([FIRST, SECOND, FINAL]), client,
            language=LANGUAGE, city=CITY, country=COUNTRY,
        )
    assert row["full_task_complete"] is True
    assert "status" not in row
    assert "requested_k" not in row
    assert seen == ["/v1/search", "/v1/forecast"]
