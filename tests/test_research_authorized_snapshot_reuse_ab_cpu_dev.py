"""Same-run no-model paired source reuse controls; never a speedup claim."""
from __future__ import annotations

import copy

import pytest

from schemarouter.decisions import CallableDecisionBackend
from schemarouter.errors import PlanningError
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import CORPUS
from scripts.evaluate_multilingual_embedding_cpu_dev import load_development_corpus
from scripts.research_authorized_snapshot_reuse_ab_cpu_dev import (
    PAIR,
    paired_source_reuse_dev,
)


def fixed_backend(request):
    return {"selections": [
        {"option_id": option.id}
        for option in request.options[:request.max_selections]
    ]}


def test_mock_scoped_reuse_ab_preserves_ids_and_never_claims_real_cpu_success():
    corpus, digest = load_development_corpus(CORPUS)
    report = paired_source_reuse_dev(
        corpus, digest, CallableDecisionBackend(fixed_backend),
        case_limit=2,
    )
    assert report["catalog_size"] == 500
    assert report["fixed_k"] == 5
    assert report["case_count"] == 2
    assert report["arms"] == list(PAIR)
    assert report["all_paired_decisions_identical"] is True
    assert report["full_84_case_evaluation"] is False
    assert report["latency_summary"] is None
    assert report["paired_delta_summary"] is None
    assert report["evidence_tier"] == "UNATTESTED_BACKEND_PAIRED_LATENCY_DEV_ONLY"
    assert report["real_model_routing_measured"] is False
    assert report["independent_e2_qualified"] is False
    assert report["agent_task_success_measured"] is False
    assert report["publication_gate_passed"] is False
    assert report["calibrated_no_fit"] is False
    assert report["product_default_promoted"] is False


def test_paired_comparison_rejects_mutated_task_and_digest():
    corpus, digest = load_development_corpus(CORPUS)
    tampered = copy.deepcopy(corpus)
    tampered["cases"][0]["query"] = "changed after declared DEV split"
    with pytest.raises(ValueError, match="source hash/contents drift"):
        paired_source_reuse_dev(
            tampered, digest, CallableDecisionBackend(fixed_backend),
            case_limit=1,
        )
    with pytest.raises(ValueError, match="source hash/contents drift"):
        paired_source_reuse_dev(
            corpus, "f" * 64, CallableDecisionBackend(fixed_backend),
            case_limit=1,
        )


@pytest.mark.parametrize("limit", (0, True, 85, -1))
def test_no_forged_or_partial_completed_paired_case_count(limit):
    corpus, digest = load_development_corpus(CORPUS)
    with pytest.raises(ValueError, match="paired smoke task bound"):
        paired_source_reuse_dev(
            corpus, digest, CallableDecisionBackend(fixed_backend),
            case_limit=limit,
        )


def test_foreign_model_tool_ids_cannot_be_measured_or_selected():
    corpus, digest = load_development_corpus(CORPUS)
    with pytest.raises((PlanningError, ValueError)):
        paired_source_reuse_dev(
            corpus, digest,
            CallableDecisionBackend(
                lambda _: {"selections": [{"option_id": "foreign:fake"}]},
            ),
            case_limit=1,
        )
