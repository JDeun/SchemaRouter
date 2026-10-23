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


@pytest.mark.parametrize("language", ("en", "ko", "ja"))
@pytest.mark.asyncio
async def test_documented_noncommercial_source_proves_complete_native_g5_join(
    language: str,
) -> None:
    """Original provider docs, not case answer gold, own both typed coordinate inputs."""
    async with httpx.AsyncClient(transport=_fixture_transport([])) as client:
        router, _, _ = build_live_router(client, documented_noncommercial_e1=True)
        selector = study._qualified_g5_selector(
            router, study.USER_REQUESTS[language],
            catalog=study.documented_open_meteo_e1_catalog(),
            approved_host_roots=frozenset({study.ROUTES[0]}),
        )
    assert selector is not None
    assert tuple(selector(study.USER_REQUESTS[language], study.ROUTES)) == study.ROUTES
    assert selector.last_status == "complete"
    assert router.authorization_policy is not None
    assert all("Non-Commercial" in (tool.license or "") for tool in router.registry.tools())


@pytest.mark.asyncio
async def test_documented_noncommercial_source_graph_agent_completes_two_real_calls() -> None:
    seen: list[str] = []

    class SourceReadyAgent(ScriptedAgent):
        def generate(self, messages, tools):
            # G5 truthfully offers only the source-ready route at each turn.
            expected = (("open_meteo_geocoding__search",),
                        ("open_meteo_weather__current",), ())
            assert tuple(t["name"] for t in tools) == expected[self.calls]
            self.history_roles.append([row["role"] for row in messages])
            position = self.calls
            self.calls += 1
            return {"text": self.text[position], "input_tokens": 64,
                    "tool_tokens": 25, "output_tokens": 30,
                    "latency_ms": 0.0, "context_overflow": False}

    agent = SourceReadyAgent([FIRST, SECOND, FINAL])
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        row = await study.evaluate_one(
            agent, client, language=LANGUAGE, city=CITY, country=COUNTRY,
            menu_mode="concept_graph_optin", documented_noncommercial_e1=True,
            host_concept_catalog=study.documented_open_meteo_e1_catalog(),
            approved_host_roots=frozenset({study.ROUTES[0]}),
        )
    assert row["full_task_complete"] is True
    assert row["strict_final_answer_correct"] is True
    assert row["real_geocoding_calls"] == row["real_forecast_calls"] == 1
    assert seen == ["/v1/search", "/v1/forecast"]


@pytest.mark.asyncio
async def test_documented_noncommercial_source_still_requires_explicit_host_review() -> None:
    """Documented metadata alone must not silently enable the research arm."""
    seen: list[str] = []
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        row = await study.evaluate_one(
            ScriptedAgent([FIRST, SECOND, FINAL]), client,
            language=LANGUAGE, city=CITY, country=COUNTRY,
            menu_mode="concept_graph_optin", documented_noncommercial_e1=True,
        )
    assert row["status"] == "BLOCKED_SOURCE_SEMANTICS"
    assert seen == []


@pytest.mark.asyncio
async def test_documented_scalar_graph_view_cannot_bypass_original_source_bounds() -> None:
    """Graph's type-only proof view must keep source range/enum checking host-side."""
    seen: list[str] = []
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        _, geocode, weather = build_live_router(client, documented_noncommercial_e1=True)
        with pytest.raises(ValueError, match="source argument"):
            await geocode("search", {
                "name": "Seoul", "language": "invalid", "country_code": "KR",
            })
        with pytest.raises(ValueError, match="source argument"):
            await weather("current", {"latitude": 91.0, "longitude": 127.0})
    assert seen == []


@pytest.mark.asyncio
async def test_documented_g5_preflight_requires_model_without_source_calls() -> None:
    seen: list[str] = []
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        row = await study.compare_graph_native_e1(
            None, client,
            documented_noncommercial_e1=True,
            host_concept_catalog=study.documented_open_meteo_e1_catalog(),
            approved_host_roots=frozenset({study.ROUTES[0]}),
        )
    assert row["status"] == "BLOCKED_MODEL_RUNTIME"
    assert row["task_success_rate"] is None
    assert seen == []


@pytest.mark.asyncio
async def test_paired_g5_reports_actual_model_token_envelopes_per_arm() -> None:
    """Model-reported schema and input tokens belong to each arm, not to gold."""
    seen: list[str] = []

    class TokenAgent:
        def generate(self, messages, tools):
            del messages, tools
            return {
                "text": "REQUEST_MORE_TOOLS", "input_tokens": 64,
                "tool_tokens": 25, "output_tokens": 30,
                "latency_ms": 0.0, "context_overflow": False,
            }

    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        result = await study.compare_graph_native_e1(
            TokenAgent(), client, documented_noncommercial_e1=True,
            host_concept_catalog=study.documented_open_meteo_e1_catalog(),
            approved_host_roots=frozenset({study.ROUTES[0]}),
        )
    assert result["status"] == "E1_MEASURED_DEV_NOT_E2"
    assert len(result["outcomes"]) == 9
    for row in result["outcomes"]:
        assert row["model_input_tokens"] == 64 * row["model_turns"]
        assert row["tool_schema_tokens"] == 25 * row["model_turns"]
        assert row["model_output_tokens"] == 30 * row["model_turns"]
        assert row["token_accounting_complete"] is True
    assert seen == []


@pytest.mark.asyncio
async def test_paired_g5_never_fabricates_zero_tokens_from_missing_metrics() -> None:
    """Model stubs lacking tokenizer receipts must not imply free inference."""
    class MissingTokensAgent:
        def generate(self, messages, tools):
            del messages, tools
            return {
                "text": "REQUEST_MORE_TOOLS", "latency_ms": 0.0,
                "context_overflow": False,
            }

    seen: list[str] = []
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        result = await study.compare_graph_native_e1(
            MissingTokensAgent(), client, documented_noncommercial_e1=True,
            host_concept_catalog=study.documented_open_meteo_e1_catalog(),
            approved_host_roots=frozenset({study.ROUTES[0]}),
        )
    assert result["status"] == "E1_MEASURED_DEV_NOT_E2"
    assert len(result["outcomes"]) == 9
    for row in result["outcomes"]:
        assert row["token_accounting_complete"] is False
        assert row["model_input_tokens"] is None
        assert row["tool_schema_tokens"] is None
        assert row["model_output_tokens"] is None
    assert seen == []


@pytest.mark.asyncio
async def test_paired_g5_live_source_transport_failure_is_incomparable(monkeypatch) -> None:
    """HTTP availability variation is not evidence for an agent's routing quality."""
    async def source_failure(agent, client, *, language, menu_mode, **kwargs):
        del agent, client, kwargs
        return {
            "language": language, "full_task_complete": False,
            "trusted_failure_stage": (
                "geocode_http_transport_failure"
                if (language, menu_mode) == ("ko", "concept_graph_optin")
                else None
            ),
        }

    monkeypatch.setattr(study, "evaluate_one", source_failure)
    class QualifiedAgent:
        def generate(self, messages, tools):
            raise AssertionError("the injected evaluator owns this case")

    async with httpx.AsyncClient(transport=_fixture_transport([])) as client:
        result = await study.compare_graph_native_e1(
            QualifiedAgent(), client, documented_noncommercial_e1=True,
            host_concept_catalog=study.documented_open_meteo_e1_catalog(),
            approved_host_roots=frozenset({study.ROUTES[0]}),
        )
    assert result["status"] == "INCOMPARABLE_SOURCE_FAILURE"
    assert result["task_success_rate"] is None
    assert len(result["outcomes"]) == 9
    assert sum(
        row["trusted_failure_stage"] == "geocode_http_transport_failure"
        for row in result["outcomes"]
    ) == 1


@pytest.mark.asyncio
async def test_paired_robustness_cohort_uses_identical_bounded_budgets(monkeypatch) -> None:
    """Reliability intervention is arm-neutral; do not quietly reward one router."""
    calls: list[tuple[str, str, int, int]] = []

    async def observe(agent, client, *, language, menu_mode,
                      transport_retry_budget=0, evidence_reprompt_budget=0, **kwargs):
        del agent, client, kwargs
        calls.append((language, menu_mode, transport_retry_budget,
                      evidence_reprompt_budget))
        return {
            "language": language, "full_task_complete": False,
            "trusted_failure_stage": None, "model_turns": 1,
            "termination_reason": "premature_final",
        }

    monkeypatch.setattr(study, "evaluate_one", observe)

    class QualifiedAgent:
        def generate(self, messages, tools):
            raise AssertionError("test stub owns the episode")

    async with httpx.AsyncClient(transport=_fixture_transport([])) as client:
        row = await study.compare_graph_native_e1(
            QualifiedAgent(), client, documented_noncommercial_e1=True,
            host_concept_catalog=study.documented_open_meteo_e1_catalog(),
            approved_host_roots=frozenset({study.ROUTES[0]}),
            transport_retry_budget=1, evidence_reprompt_budget=1,
        )
    assert row["status"] == "E1_MEASURED_DEV_NOT_E2"
    assert row["transport_retry_budget"] == 1
    assert row["evidence_reprompt_budget"] == 1
    assert len(calls) == 9
    assert {(retry, reprompt) for _, _, retry, reprompt in calls} == {(1, 1)}
    assert {language for language, _, _, _ in calls} == {"en", "ko", "ja"}
    assert {arm for _, arm, _, _ in calls} == set(study.G5_COMPARISON_ARMS)


@pytest.mark.asyncio
async def test_robustness_uses_actual_idempotent_retry_and_verified_followup() -> None:
    """No host auto-call: Qwen surrogate must still choose the weather operation."""
    requests: list[str] = []
    baseline = _fixture_transport(requests)
    first_search = True

    def flaky_search(request: httpx.Request) -> httpx.Response:
        nonlocal first_search
        if request.url.path == "/v1/search" and first_search:
            first_search = False
            requests.append(request.url.path)
            raise httpx.ConnectTimeout("synthetic first-attempt outage", request=request)
        return baseline.handle_request(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(flaky_search)) as client:
        row = await study.evaluate_one(
            ScriptedAgent([FIRST, "REQUEST_MORE_TOOLS", SECOND, FINAL]), client,
            language=LANGUAGE, city=CITY, country=COUNTRY,
            transport_retry_budget=1, evidence_reprompt_budget=1,
        )
    assert row["full_task_complete"] is True
    assert row["real_geocoding_http_attempts"] == 2
    assert row["real_geocoding_calls"] == 1
    assert row["real_forecast_http_attempts"] == 1
    assert row["real_forecast_calls"] == 1
    assert row["host_evidence_reprompts"] == 1
    assert row["model_turns"] == 4
    assert requests == ["/v1/search", "/v1/search", "/v1/forecast"]


@pytest.mark.asyncio
async def test_paired_robustness_budget_rejects_out_of_bounds_before_source(monkeypatch) -> None:
    def forbidden_router(*args, **kwargs):
        raise AssertionError("invalid research budgets must fail before source")

    monkeypatch.setattr(study, "build_live_router", forbidden_router)
    async with httpx.AsyncClient(transport=_fixture_transport([])) as client:
        for retry, reprompt in ((2, 0), (0, 2), (True, 0), (0, -1)):
            with pytest.raises(ValueError, match="budget"):
                await study.compare_graph_native_e1(
                    ScriptedAgent([FIRST]), client,
                    transport_retry_budget=retry, evidence_reprompt_budget=reprompt,
                )


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
