"""Pair whole-selector latency on one frozen authorized native source, no model."""
from __future__ import annotations

import json

import pytest

from schemarouter.decisions import CallableDecisionBackend
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import CORPUS
from scripts.evaluate_multilingual_embedding_cpu_dev import (
    load_development_corpus,
)
from scripts.research_authorized_fingerprint_selector_paired_e5_cpu_dev import (
    ARMS,
    paired_fingerprint_selector_dev,
)


def _first_five(request):
    return {"selections": [
        {"option_id": option.id}
        for option in request.options[:request.max_selections]
    ]}


def test_no_model_paired_selection_has_exact_same_choices_and_not_scored():
    corpus, digest = load_development_corpus(CORPUS)
    seen = []

    def backend(request):
        seen.append(request.model_dump_json())
        return _first_five(request)

    result = paired_fingerprint_selector_dev(
        corpus, digest, CallableDecisionBackend(backend), case_limit=2,
    )
    assert result["case_count"] == 2
    assert result["arms"] == list(ARMS)
    assert result["registered_native_routes"] == 500
    assert result["all_exact_order_status_bytes_identical"]
    assert not result["real_model_routing_measured"]
    assert not result["independent_e2_qualified"]
    assert not result["agent_task_success_measured"]
    assert not result["calibrated_no_fit"]
    assert not result["product_default_promoted"]
    assert not result["full_84_case_evaluation"]
    assert result["selector_including_constructor_latency_ms"] is None
    assert result["shared_authorized_source_capture_latency_ms"] is None
    assert result["shared_capture_plus_selector_latency_ms"] is None
    assert result["paired_delta_summary"] is None
    assert len(seen) == 4
    assert seen[0] == seen[1]
    assert seen[2] == seen[3]
    published = json.dumps(result)
    assert "expected_route" not in published
    assert "case_id" not in published
    assert corpus["cases"][0]["query"] not in published


def test_pair_refuses_changed_native_ranking_from_untrusted_backend():
    corpus, digest = load_development_corpus(CORPUS)
    calls = 0

    def changed(request):
        nonlocal calls
        calls += 1
        options = request.options[:request.max_selections]
        if calls % 2 == 0:
            options = options[::-1]
        return {"selections": [{"option_id": opt.id} for opt in options]}

    with pytest.raises(ValueError, match="model ranking drift"):
        paired_fingerprint_selector_dev(
            corpus, digest, CallableDecisionBackend(changed), case_limit=1,
        )


def test_pair_rejects_modified_source_and_invalid_smoke_sizes():
    corpus, digest = load_development_corpus(CORPUS)
    for invalid in (0, True, -1, 85):
        with pytest.raises(ValueError, match="smoke limit"):
            paired_fingerprint_selector_dev(
                corpus, digest, CallableDecisionBackend(_first_five),
                case_limit=invalid,
            )
    with pytest.raises(ValueError, match="unverified frozen"):
        paired_fingerprint_selector_dev(
            corpus, "0" * 64, CallableDecisionBackend(_first_five),
            case_limit=1,
        )
