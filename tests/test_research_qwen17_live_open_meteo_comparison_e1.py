"""No-model invariant tests; only CPU workflow validates actual Qwen3-1.7B."""
from __future__ import annotations

import json

import httpx
import pytest

from scripts.research_qwen17_live_open_meteo_comparison_e1 import (
    BASELINE_REAL_RUN,
    MODEL_ID,
    REVISION,
    compare_model,
)


def test_exact_checkpoint_and_baseline_are_frozen() -> None:
    assert MODEL_ID == "Qwen/Qwen3-1.7B"
    assert REVISION == "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"
    assert BASELINE_REAL_RUN.endswith("/39089681858")


@pytest.mark.asyncio
async def test_reuse_existing_evaluator_without_extra_executed_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import research_qwen17_live_open_meteo_comparison_e1 as module

    called = []
    class Stub:
        pass

    async def unchanged_evaluator(agent, client):
        called.append((agent, client))
        return {
            "case_count": 3,
            "total_real_source_calls": 3,
            "total_real_http_attempts": 4,
            "model_generated_full_task_successes": 1,
            "outcomes": [
                {"language": "en", "real_geocoding_calls": 1,
                 "real_forecast_calls": 0, "real_geocoding_http_attempts": 1,
                 "real_forecast_http_attempts": 0, "full_task_complete": False},
                {"language": "ko", "real_geocoding_calls": 1,
                 "real_forecast_calls": 1, "real_geocoding_http_attempts": 1,
                 "real_forecast_http_attempts": 1, "full_task_complete": True},
                {"language": "ja", "real_geocoding_calls": 0,
                 "real_forecast_calls": 0, "real_geocoding_http_attempts": 1,
                 "real_forecast_http_attempts": 0, "full_task_complete": False},
            ],
        }

    monkeypatch.setattr(module, "evaluate", unchanged_evaluator)
    agent = Stub()
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda _: (_ for _ in ()).throw(AssertionError("unexpected network"))
    )) as client:
        result = await compare_model(agent, client)
    assert called == [(agent, client)]
    assert result["baseline"]["baseline_full_task_successes"] == 1
    assert result["model_generated_full_task_successes"] == 1
    assert result["total_real_http_attempts"] == 4
    assert result["real_provider_observed"] is True
    assert result["candidate_only_checkpoint_changed"] is True
    assert result["independent_e2_qualified"] is False
    assert result["released_or_promoted"] is False
    assert "Seoul" not in json.dumps(result)


@pytest.mark.asyncio
async def test_mismatched_native_call_count_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import research_qwen17_live_open_meteo_comparison_e1 as module

    async def invalid(*_a):
        return {"case_count": 3, "total_real_source_calls": 2,
                "total_real_http_attempts": 1,
                "outcomes": [{"real_geocoding_calls": 1,
                              "real_forecast_calls": 0,
                              "real_geocoding_http_attempts": 1,
                              "real_forecast_http_attempts": 0}]}

    monkeypatch.setattr(module, "evaluate", invalid)
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError, match="denominator drift"):
            await compare_model(object(), client)
