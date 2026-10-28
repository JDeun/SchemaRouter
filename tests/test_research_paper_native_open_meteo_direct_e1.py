"""Real original native Open-Meteo invoker, bounded at HTTP MockTransport."""

from __future__ import annotations

import json

import httpx
import pytest


@pytest.mark.asyncio
async def test_a5_direct_native_bridge_reaches_original_open_meteo_http_invoker():
    from scripts.research_paper_native_open_meteo_direct_e1 import (
        run_native_open_meteo_direct_e1,
    )

    requests = []

    def source_http(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.host == "geocoding-api.open-meteo.com"
        assert request.url.path == "/v1/search"
        assert request.url.params["name"] == "Seoul"
        assert request.url.params["language"] == "en"
        assert request.url.params["countryCode"] == "KR"
        return httpx.Response(200, json={"results": [{
            "id": 1835848, "country_code": "KR",
            "latitude": 37.56, "longitude": 126.98,
        }]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(source_http)) as client:
        report = await run_native_open_meteo_direct_e1(client)

    assert len(requests) == 1
    assert report["native_invocations"] == 1
    assert report["source_http_attempts"] == 1
    assert report["host_bound_tool_calls"] == 1
    assert report["provider_result_contract_matched"] is True
    assert report["model_selected_calls"] == 0
    assert report["independent_e2"] is False
    assert "37.56" not in json.dumps(report)
    assert "126.98" not in json.dumps(report)


@pytest.mark.asyncio
async def test_http_source_failure_never_emits_native_success_receipt():
    from scripts.research_paper_native_open_meteo_direct_e1 import (
        run_native_open_meteo_direct_e1,
    )

    requests = []

    def source_http(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(503, json={"raw_secret": "NEVER_LOG_THIS"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(source_http)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await run_native_open_meteo_direct_e1(client)
    assert len(requests) == 1
