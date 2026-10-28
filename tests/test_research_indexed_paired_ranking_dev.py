"""#1560 direct-index paired DEV: same synthetic cases, scorer-only gold."""
from __future__ import annotations

import math

import pytest

from schemarouter.decisions import (
    CallableDecisionBackend,
    DecisionResult,
    DecisionSelection,
)
from scripts.research_indexed_paired_ranking_dev import (
    ARMS,
    _cases,
    _rank_score,
    _tokens,
    build_direct_source,
    lexical_five,
    run_paired_dev,
)


def test_direct_24_route_source_and_original_frozen_30_cases():
    router, index = build_direct_source()
    assert index.indexed_route_count == 24
    assert len(index.postings["service.status"]) == 24
    assert len(router.registry.keys()) == 24
    cases = _cases("task_only")
    assert len(cases) == 30
    assert len([c for c in cases if c[2] is not None]) == 27
    assert len([c for c in cases if c[2] is None]) == 3
    assert set(lang for lang, _, _ in cases) == {"en", "ko", "ja"}
    assert "acct_demo_7" not in str(cases)
    carrier = _cases("account_carrier")
    assert len(carrier) == len(cases)
    assert all(before[0] == after[0] and before[2] == after[2]
               for before, after in zip(cases, carrier, strict=True))


def test_indexed_no_model_dev_reports_explicit_27_supported_and_3_ood():
    report = run_paired_dev()
    assert report["route_count"] == 24
    assert report["supported_case_count"] == 27
    assert report["ood_case_count"] == 3
    assert report["case_count"] == 30
    assert report["arms"] == ARMS[:2]
    assert report["evidence_tier"] == "E0_NO_MODEL_INDEXED_SYNTHETIC_DEV_ONLY"
    assert report["model_used"] is False
    assert report["real_model_runtime_attested"] is False
    assert report["independent_publisher_gold"] is False
    assert report["agent_task_success_measured"] is False
    assert report["calibrated_no_fit"] is False
    assert report["product_default_changed"] is False
    assert report["paired_lexical5_to_backend"] is None
    for arm in ARMS[:2]:
        for lang in ("en", "ko", "ja"):
            summary = report["per_language"][arm][lang]
            assert summary["supported"] == 9
            assert summary["ood_nonempty_shortlist_count"] == 1
            for metric in ("recall_at_5", "mrr_at_5", "ndcg_at_5"):
                assert 0 <= summary[metric] <= 1
                assert math.isfinite(summary[metric])
    # Source names are English only. The lexical baseline is NOT translated
    # and cannot learn its way into a positive by observing offline gold.
    assert report["per_language"]["lexical5"]["en"]["recall_at_5"] == 1.0
    assert report["per_language"]["lexical5"]["ko"]["recall_at_5"] == 1 / 9
    assert report["per_language"]["lexical5"]["ja"]["recall_at_5"] == 1 / 9
    for arm in ("unranked", "first5", "lexical5"):
        assert report["latency_ms"][arm]["p50"] >= 0
        assert report["latency_ms"][arm]["p99"] >= report["latency_ms"][arm]["p50"]


def test_injected_backend_is_scored_without_access_to_gold_or_registry():
    requests = []

    def select_fixed_source(request):
        requests.append(request)
        assert set(request.context) == {
            "type", "independent_quality_evidence",
            "executable_authority", "calibrated_no_fit",
        }
        assert request.context["executable_authority"] is False
        assert request.context["independent_quality_evidence"] is False
        assert all(option.metadata == {} for option in request.options)
        assert all(option.description == "" for option in request.options)
        assert len(request.options) == 24
        ids = [i for i, option in enumerate(request.options)
               if option.label == "service_refund.read"]
        assert len(ids) == 1
        chosen = (ids[0], *(i for i in range(24) if i != ids[0]))[:5]
        return DecisionResult(selections=[
            DecisionSelection(option_id=request.options[i].id)
            for i in chosen
        ])

    report = run_paired_dev(CallableDecisionBackend(select_fixed_source))
    assert len(requests) == 30
    assert report["arms"] == ARMS
    assert report["model_used"] is True
    assert report["real_model_runtime_attested"] is False
    assert report["evidence_tier"].startswith("E0_INJECTED_")
    assert report["per_language"]["e5_5"]["en"]["supported"] == 9
    assert report["per_language"]["e5_5"]["en"]["recall_at_5"] == 2 / 9
    assert report["per_language"]["e5_5"]["ko"]["recall_at_5"] == 2 / 9
    assert report["per_language"]["e5_5"]["ja"]["recall_at_5"] == 2 / 9
    assert report["paired_lexical5_to_backend"]["rescued"] == 2
    assert report["paired_lexical5_to_backend"]["regressed"] == 7


def test_lexical_ranker_uses_only_bounded_visible_route_tokens():
    router, index = build_direct_source()
    from schemarouter.native_semantic_index import IndexedNativeFieldCandidate

    paths = tuple(
        IndexedNativeFieldCandidate(
            route_id=r,
            tool_fingerprint="test-pinned",
            endpoint_fingerprint="test-pinned",
            required_output_fields=("status",),
        )
        for r in index.postings["service.status"]
    )
    chosen = lexical_five("refund request status", paths, 5)
    assert paths[chosen[0]].route_id == "service_refund.read"
    assert _tokens("SERVICE_refund.read") == {"service", "refund", "read"}
    assert set(chosen) <= set(range(24))
    with pytest.raises(ValueError, match="cohort"):
        lexical_five("refund", paths, 3)
    # No registry reads or invocations are available inside the callback.
    assert len(router.registry.keys()) == 24


@pytest.mark.parametrize(
    ("selected", "rank", "mrr", "ndcg"),
    [
        (("a", "b", "c", "d", "e"), "c", 1 / 3, 1 / math.log2(4)),
        (("a", "b", "c", "d", "e"), "z", 0.0, 0.0),
    ],
)
def test_offline_scoring_respects_true_position_and_absent_relevance(
    selected, rank, mrr, ndcg,
):
    result = _rank_score(selected, rank)
    assert result["recall_at_5"] == float(rank in selected)
    assert result["mrr_at_5"] == pytest.approx(mrr)
    assert result["ndcg_at_5"] == pytest.approx(ndcg)


def test_invalid_backend_or_query_variant_never_produces_scored_report():
    from schemarouter.errors import PolicyViolationError

    backend = CallableDecisionBackend(
        lambda request: DecisionResult(selections=[
            DecisionSelection(option_id="unapproved-service.read"),
        ]),
    )
    with pytest.raises(PolicyViolationError, match="indexed research ranking failed"):
        run_paired_dev(backend)
    with pytest.raises(ValueError, match="frozen"):
        run_paired_dev(query_variant="invented")
    with pytest.raises(ValueError, match="boolean"):
        run_paired_dev(omit_identical_descriptions=1)


def test_original_query_carrier_perturbation_preserves_synthetic_gold():
    original = run_paired_dev()
    carrier = run_paired_dev(query_variant="account_carrier")
    assert carrier["source_snapshot_id"] == original["source_snapshot_id"]
    assert carrier["query_variant"] == "account_carrier"
    assert carrier["route_count"] == original["route_count"]
    assert carrier["supported_case_count"] == original["supported_case_count"]
    assert carrier["independent_publisher_gold"] is False
