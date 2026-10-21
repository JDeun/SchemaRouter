"""No-network, no-model controls for paired E1 bookkeeping; NOT scored agent E2."""
from __future__ import annotations

import json
from typing import Any

import pytest

from scripts import research_qwen_verified_continuation_paired_e1 as study


class FakeGenerator:
    def generate(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "text": "non-scored synthetic response",
            "input_tokens": 90,
            "tool_tokens": 20,
            "output_tokens": 10,
            "latency_ms": 2.0,
            "context_overflow": False,
        }


@pytest.mark.asyncio
async def test_original_and_opt_in_are_paired_without_e2_or_source_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, int, int]] = []

    async def synthetic_evaluate(
        agent: Any, _client: Any, *, language: str, city: str, country: str,
        menu_mode: str, transport_retry_budget: int,
        evidence_reprompt_budget: int,
    ) -> dict[str, Any]:
        del city, country
        assert menu_mode == "state_ready"
        assert transport_retry_budget == 1
        calls.append((language, evidence_reprompt_budget, transport_retry_budget))
        agent.generate([], [])
        # Only a scripted opt-in English episode succeeds in this bookkeeping test.
        success = language == "en" and evidence_reprompt_budget == 1
        row = {
            "language": language,
            "independent_e2_qualified": False,
            "model_turns": 1,
            "full_task_complete": success,
            "strict_final_answer_correct": success,
            "model_generated_two_step_complete": success,
            "real_geocoding_calls": 1,
            "real_forecast_calls": int(success),
            "real_geocoding_http_attempts": 1,
            "real_forecast_http_attempts": int(success),
            "termination_reason": "completed_final" if success else "premature_final",
            "trusted_failure_stage": None,
            "trusted_transport_error_kind": None,
            "trusted_final_validation_failure_kind": None,
            "model_generation_ms": 2.0,
        }
        if evidence_reprompt_budget:
            row["host_evidence_reprompts"] = 1
        return row

    monkeypatch.setattr(study, "evaluate_one", synthetic_evaluate)
    report = await study.compare(FakeGenerator(), object())
    assert calls == [
        ("en", 0, 1), ("en", 1, 1),
        ("ko", 1, 1), ("ko", 0, 1),
        ("ja", 0, 1), ("ja", 1, 1),
    ]
    assert report["paired_case_count"] == 3
    assert report["by_arm"]["original"]["strict_full_task_passes"] == 0
    assert report["by_arm"]["one_verified_reminder"]["strict_full_task_passes"] == 1
    assert report["by_arm"]["original"]["host_evidence_reprompts"] == 0
    assert report["by_arm"]["one_verified_reminder"]["host_evidence_reprompts"] == 3
    assert report["by_arm"]["original"]["token_totals"] == {
        "input_tokens": 270, "tool_tokens": 60, "output_tokens": 30,
    }
    assert report["independent_e2_qualified"] is False
    assert report["product_default_changed"] is False
    assert report["release_qualified"] is False
    serialized = json.dumps(report, ensure_ascii=False)
    assert "non-scored synthetic response" not in serialized
    assert "latitude" not in serialized and "longitude" not in serialized


@pytest.mark.asyncio
async def test_fail_closed_on_invalid_study_budget_before_evaluation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    async def forbidden_evaluate(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        calls.append(1)
        raise AssertionError("should not call source")

    monkeypatch.setattr(study, "evaluate_one", forbidden_evaluate)
    for invalid in (0, 2, True, 1.0, None):
        with pytest.raises(ValueError, match="fixed preregistered retry"):
            await study.compare(
                FakeGenerator(), object(), transport_retry_budget=invalid,
            )
    assert not calls


def test_model_cost_cannot_silently_count_missing_or_malformed_tokens() -> None:
    class Bad:
        def __init__(self, usage: Any) -> None:
            self.usage = usage

        def generate(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return self.usage

    for invalid in (
        {"input_tokens": 100, "tool_tokens": 3},
        {"input_tokens": True, "tool_tokens": 0, "output_tokens": 0},
        {"input_tokens": 10, "tool_tokens": 11, "output_tokens": 0},
        {"input_tokens": -1, "tool_tokens": 0, "output_tokens": 0},
    ):
        with pytest.raises(ValueError):
            study.MeteredAgent(Bad(invalid)).generate([], [])


def test_reject_fabricated_full_task_completion_and_control_contamination() -> None:
    meter = study.MeteredAgent(FakeGenerator())
    meter.generate([], [])
    row = {
        "language": "en",
        "independent_e2_qualified": False,
        "model_turns": 1,
        "full_task_complete": True,
        "strict_final_answer_correct": False,
        "model_generated_two_step_complete": False,
        "real_geocoding_calls": 0,
        "real_forecast_calls": 0,
    }
    with pytest.raises(ValueError, match="unverified strict"):
        study._checked_public_row(
            row, meter, 1.0, language="en", arm="original",
        )
    row.update({
        "full_task_complete": False,
        "host_evidence_reprompts": 1,
        "real_geocoding_http_attempts": 0,
        "real_forecast_http_attempts": 0,
    })
    with pytest.raises(ValueError, match="original control arm changed"):
        study._checked_public_row(
            row, meter, 1.0, language="en", arm="original",
        )
