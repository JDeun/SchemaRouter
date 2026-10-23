"""Qwen17 research wrapper metadata and local K5 denominator, no model download."""
from __future__ import annotations

import pytest

from scripts import research_codegraph_qwen17_local_e1 as study


@pytest.mark.asyncio
async def test_qwen17_wrapper_refuses_unpinned_or_scripted_model():
    with pytest.raises(TypeError, match="pinned Qwen3-1.7B"):
        await study.evaluate_candidate(object(), language="en")


@pytest.mark.asyncio
async def test_qwen17_wrapper_preserves_four_arm_local_tier_and_checkpoint(monkeypatch):
    passed = []

    async def source_run(agent, *, language, condition, catalog_size):
        passed.append((language, condition, catalog_size))
        arms = ("all_visible", "lexical_k5", "concept_graph_optin", "surgical_g5_e1")
        return {
            "status": "E1_MEASURED_LOCAL_FOUR_ARM_NOT_E2",
            "source_route_count": 4,
            "arms": arms,
            "outcomes": [
                {"condition": arm, "model_turns": 1, "full_task_complete": False}
                for arm in arms
            ],
            "qualified_task_denominator": {"all_visible": 1, "lexical_k5": 1,
                                           "concept_graph_optin": 1, "surgical_g5_e1": 1},
            "task_success_rate": {"all_visible": 0.0, "lexical_k5": 0.0,
                                  "concept_graph_optin": 0.0, "surgical_g5_e1": 0.0},
        }

    monkeypatch.setattr(study, "run_local_multiroute_codegraph_e1", source_run)
    # No weights downloaded: identity/class gate only.
    instance = object.__new__(study.LocalQwen17BRealAgent)
    report = await study.evaluate_candidate(instance, language="ko")
    assert passed == [("ko", "joined", 4)]
    assert report["model_id"] == "Qwen/Qwen3-1.7B"
    assert report["model_revision"] == study.REVISION
    assert report["baseline_model_id"] != report["model_id"]
    assert report["checkpoint_only_model_intervention"] is True
    assert report.get("original_provider_e1", False) is False
    assert report["real_external_provider_observed"] is False
    assert report["independent_e2_qualified"] is False
    assert report["release_qualified"] is False
    assert report["task_success_rate"]["surgical_g5_e1"] == 0.0


@pytest.mark.asyncio
async def test_qwen17_wrapper_rejects_incomparable_full_cohort(monkeypatch):
    async def bad(*_args, **_kwargs):
        return {"status": "INCOMPARABLE_FULL_MENU_CAP", "source_route_count": 12,
                "outcomes": ()}

    monkeypatch.setattr(study, "run_local_multiroute_codegraph_e1", bad)
    instance = object.__new__(study.LocalQwen17BRealAgent)
    with pytest.raises(ValueError, match="comparable K5"):
        await study.evaluate_candidate(instance, language="en")
