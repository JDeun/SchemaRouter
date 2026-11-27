"""No-model guards for the public historical-plan agreement pilot."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts import research_original_paper_public_model_pilot as pilot


def test_fixed_public_fixture_pilot_has_one_case_per_original_category() -> None:
    fixture = pilot._load_fixture()
    cases = pilot._cohort(fixture["cases"], "pilot")
    assert len(fixture["cases"]) == 110
    assert len(cases) == len({case["category"] for case in cases}) == 9
    assert [case["query_id"] for case in cases] == [
        next(
            row["query_id"] for row in fixture["cases"]
            if row["category"] == case["category"]
        )
        for case in cases
    ]


def test_archived_agreement_counts_tool_specific_fields_and_empty_cases() -> None:
    actual = [{"tool": "a", "fields": ["x", "y"]}]
    archived = [{"tool": "a", "fields": ["x"]}, {"tool": "b", "fields": ["y"]}]
    score = pilot._agreement(actual, archived)
    assert score["archived_tool_set_exact"] == 0.0
    assert score["archived_field_set_exact"] == 0.0
    assert score["archived_field_f1"] == 0.5
    assert pilot._agreement([], [])["archived_field_f1"] == 1.0
    assert pilot._agreement([], archived)["archived_field_f1"] == 0.0


@pytest.mark.parametrize("overflow", [False, True])
async def test_pilot_sends_only_raw_query_and_preserves_failed_generation(
    monkeypatch, overflow,
) -> None:
    case = {
        "query_id": "x", "query": "query text", "category": "fixture",
        "intent": "hidden reference intent", "concepts": ["reference concept"],
        "archived_calls": [{"tool": "reference", "fields": ["answer"]}],
    }
    measured = SimpleNamespace(calls=[], stage="understand")

    async def compile_stub(session, intents, rank, actor, model, raw):
        assert raw == {"query_id": "x", "query": "query text"}
        model.calls.append({
            "stage": "understand", "input_tokens": 10,
            "output_tokens": 0 if overflow else 4,
            "context_overflow": overflow, "latency_s": 0.1,
        })
        return {"selected_tools": []}, {
            "status": "ModelAnalysisError", "executed_provider_calls": 0,
        }

    monkeypatch.setattr(pilot, "_current_plan", compile_stub)
    row = await pilot._case(None, None, None, None, measured, case)
    assert row["inference_observed"] is (not overflow)
    assert row["agreement"]["archived_field_recall"] == 0.0
    assert row["executed_provider_calls"] == 0
