"""E1 comparison runner contract: mock does not constitute actual CPU evidence."""
from __future__ import annotations

import json
from typing import Any

import pytest

from scripts import research_qwen_state_ready_open_meteo_e1 as study


@pytest.mark.asyncio
async def test_pairs_exact_same_live_tasks_and_never_claims_independent_e2(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[tuple[str, str]] = []

    async def fake_evaluate(
        agent: Any, client: Any, *, language: str,
        city: str, country: str, menu_mode: str,
        transport_retry_budget: int,
    ) -> dict[str, Any]:
        del agent, client, city, country
        assert transport_retry_budget == 0
        calls.append((language, menu_mode))
        return {
            "language": language,
            "independent_e2_qualified": False,
            "full_task_complete": False,
            "strict_final_answer_correct": False,
            "model_generated_two_step_complete": False,
            "real_geocoding_calls": 0,
            "real_forecast_calls": 0,
            "real_geocoding_http_attempts": 0,
            "real_forecast_http_attempts": 0,
            "termination_reason": "host_or_native_source_denied",
            "trusted_failure_stage": "geocode_http_transport_failure",
            "model_turns": 1,
            "model_generation_ms": 2.0,
        }

    monkeypatch.setattr(study, "evaluate_one", fake_evaluate)
    result = await study.compare(
        type("Agent", (), {"generate": lambda *_a, **_k: None})(),
        object(),
    )
    assert calls == [
        ("en", "all_visible"), ("en", "state_ready"),
        ("ko", "state_ready"), ("ko", "all_visible"),
        ("ja", "all_visible"), ("ja", "state_ready"),
    ]
    assert result["study"] == study.EVIDENCE
    assert result["case_count_per_arm"] == 3
    assert result["independent_e2_qualified"] is False
    assert result["default_product_modified"] is False
    assert result["release_qualified"] is False
    assert set(result["by_arm"]) == set(study.ARMS)
    assert all(
        row["completed_strict_real_provider_tasks"] == 0
        for row in result["by_arm"].values()
    )
    serialized = json.dumps(result, ensure_ascii=False)
    assert "latitude" not in serialized and "longitude" not in serialized


@pytest.mark.asyncio
async def test_reject_forged_strict_final_oracle_from_fake_agent(
    monkeypatch: pytest.MonkeyPatch,
):
    async def false_success(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "language": "en",
            "independent_e2_qualified": False,
            "full_task_complete": True,
            "strict_final_answer_correct": False,
            "model_generated_two_step_complete": False,
            "real_geocoding_calls": 0,
            "real_forecast_calls": 0,
        }

    monkeypatch.setattr(study, "evaluate_one", false_success)
    with pytest.raises(ValueError, match="unsupported real task completion"):
        await study.compare(
            type("Agent", (), {"generate": lambda *_a, **_k: None})(),
            object(),
        )
