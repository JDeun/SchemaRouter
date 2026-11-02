"""E0 direct-index test: compare original overflow and scoped first-K baseline."""
from __future__ import annotations

import pytest

from schemarouter.decisions import CallableDecisionBackend
from scripts.research_indexed_direct_e5_paired_dev import (
    LANGUAGES,
    _percentile,
    run,
)


def test_public_synthetic_direct_index_benchmark_has_fixed_roster_and_gold_is_scored_later():
    report = run()
    assert report["evidence_tier"] == "E0_NO_MODEL_FIRST_FIVE_PUBLIC_SYNTHETIC_DEV_ONLY"
    assert report["source_route_count"] == 25
    assert report["eligible_complete_candidates"] == 24
    assert report["supported_cases"] == 27
    assert report["ood_cases"] == 3
    assert report["k"] == 5
    assert report["real_model_routing_measured"] is False
    assert report["independent_publisher_gold"] is False
    assert report["calibrated_no_fit"] is False
    assert report["agent_task_success_measured"] is False
    assert report["product_default_promoted"] is False
    assert report["languages"] == LANGUAGES
    assert report["total_lookup_calls_measured"] == 30
    assert sum(r["supported_count"] for r in report["by_language"].values()) == 27
    assert sum(r["ood_count"] for r in report["by_language"].values()) == 3
    assert sum(r["hits_at_5"] for r in report["by_language"].values()) == (
        report["scorer_only_hits_at_5"]
    )
    assert 0 <= report["supported_recall_at_5"] <= 1
    assert 0 <= report["latency_ms_p50"] <= report["latency_ms_p95"]
    assert report["latency_ms_p95"] <= report["latency_ms_p99"]


def test_actual_injected_decision_backend_runs_with_only_scoped_options():
    calls = []

    def choose(request):
        calls.append(request)
        assert len(request.options) == 24
        assert request.max_selections == 5
        assert request.context["executable_authority"] is False
        assert "fingerprint" not in request.model_dump_json()
        assert all(not option.metadata for option in request.options)
        # This deterministic scoring arm is deliberately not called a model.
        return {"selections": [
            {"option_id": option.id}
            for option in request.options[-5:]
        ]}

    report = run(CallableDecisionBackend(choose))
    assert report["evidence_tier"] == "E0_INJECTED_DECISION_BACKEND_PUBLIC_SYNTHETIC_DEV_ONLY"
    assert report["real_model_routing_measured"] is False
    assert len(calls) == 30
    assert report["supported_cases"] == 27
    assert report["ood_cases"] == 3
    assert all(report["by_language"][lang]["ood_nonempty"] == 1 for lang in LANGUAGES)


def test_abstaining_backend_does_not_fake_supported_success_or_no_fit():
    def abstain(_request):
        return {"abstained": True}

    with pytest.raises(ValueError, match="invalid ranked Top-K5"):
        run(CallableDecisionBackend(abstain))


def test_percentile_fixed_interpolation():
    assert _percentile([], 0.95) == 0
    assert _percentile([10.0], 0.95) == 10.0
    assert _percentile([0.0, 100.0], 0.95) == pytest.approx(95.0)
