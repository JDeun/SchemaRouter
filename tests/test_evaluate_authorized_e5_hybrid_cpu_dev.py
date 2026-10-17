"""No-model DEV integrity checks for the separate real-E5 Actions runner."""
from __future__ import annotations

import copy

import pytest

from schemarouter.decisions import CallableDecisionBackend
from schemarouter.errors import PlanningError
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import (
    ARMS,
    CORPUS,
    MODEL_REVISION,
    build_source_router,
    run_three_arm_dev,
)
from scripts.evaluate_multilingual_embedding_cpu_dev import load_development_corpus


def rank_offered_options(request):
    """Fixed mock choice: never based on gold, not a real model score."""
    return {"selections": [
        {"option_id": option.id}
        for option in request.options[:request.max_selections]
    ]}


def test_real_e5_runner_reuses_prospective_multilingual_corpus_and_source():
    corpus, digest = load_development_corpus(CORPUS)
    router = build_source_router(corpus)
    assert sum(len(t.endpoints) for t in router.registry.tools()) == 13
    assert len(MODEL_REVISION) == 40
    assert len(set(ARMS)) == 3
    # This is a mock DecisionBackend: even if the mock scores highly,
    # publication and agent-success flags may NEVER become true.
    report = run_three_arm_dev(corpus, digest, CallableDecisionBackend(rank_offered_options))
    assert report["case_count"] == 84
    assert report["source_corpus_sha256"] == digest
    assert report["fixed_k"] == 5
    assert report["arms"] == list(ARMS)
    assert report["evidence_tier"] == "UNATTESTED_BACKEND_RETRIEVAL_DEV_ONLY"
    assert report["real_model_routing_measured"] is False
    assert report["agent_task_success_measured"] is False
    assert report["independent_e2_qualified"] is False
    assert report["calibrated_no_fit"] is False
    assert report["publication_gate_passed"] is False
    assert report["product_default_promoted"] is False
    for arm, stats in report["results"].items():
        assert stats["supported"] == 48
        assert stats["unsupported"] == 36
        assert 0 <= stats["supported_recall_at_1"] <= 1
        assert 0 <= stats["supported_recall_at_5"] <= 1
        assert stats["unsupported_nonempty_candidate_rate"] == 1.0
        assert set(stats["languages"]) == set(corpus["languages"])
        for language, values in stats["languages"].items():
            assert values["supported"] == 8, (arm, language)
            assert values["unsupported"] == 6, (arm, language)


def test_cannot_use_mutated_gold_or_claim_unfrozen_input_digest():
    corpus, digest = load_development_corpus(CORPUS)
    altered = copy.deepcopy(corpus)
    altered["cases"][0]["query"] = "Changed to a post-hoc tuned query"
    with pytest.raises(ValueError, match="DEV source/content digest"):
        run_three_arm_dev(altered, digest, CallableDecisionBackend(rank_offered_options))
    with pytest.raises(ValueError, match="DEV source/content digest"):
        run_three_arm_dev(corpus, "0" * 64, CallableDecisionBackend(rank_offered_options))


def test_cannot_register_unbounded_or_forged_native_source():
    corpus, digest = load_development_corpus(CORPUS)
    altered = copy.deepcopy(corpus)
    altered["catalog"][0]["id"] = "forged"
    with pytest.raises(ValueError, match="source-native route"):
        build_source_router(altered)
    altered = copy.deepcopy(corpus)
    altered["catalog"][0]["id"] = altered["catalog"][1]["id"]
    with pytest.raises(ValueError, match="duplicate source-native route"):
        build_source_router(altered)
    altered = copy.deepcopy(corpus)
    altered["catalog"][0]["description"] = ""
    with pytest.raises(ValueError, match="source-native route"):
        build_source_router(altered)


def test_backend_forgery_cannot_escape_authorized_source():
    corpus, digest = load_development_corpus(CORPUS)
    with pytest.raises((PlanningError, ValueError)):
        run_three_arm_dev(
            corpus, digest,
            CallableDecisionBackend(lambda _: {
                "selections": [{"option_id": "forged:unauthorized"}],
            }),
        )
