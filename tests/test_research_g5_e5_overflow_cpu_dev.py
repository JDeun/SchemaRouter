"""24-source typed G5 E0 contract before any CPU model download."""
from __future__ import annotations

import json

import pytest

from schemarouter import AuthorizationPolicy, AuthorizationRule
from schemarouter.decisions import EmbeddingDecisionBackend
from scripts.research_g5_e5_overflow_cpu_dev import (
    ACCOUNT_QUERY_CARRIER,
    ACTOR,
    OOD,
    QUERIES,
    SERVICE_NAMES,
    K,
    UnscoredE5ScoreObserver,
    _source,
    run,
)


def test_synthetic_native_source_real_g5_24_edges_and_no_gold_model_input():
    router, graph, group = _source()
    assert len(SERVICE_NAMES) == 24
    assert len(QUERIES) == 9
    assert len(OOD) == 3
    assert len(set(SERVICE_NAMES)) == 24
    assert graph.field_index.indexed_route_count == 25
    assert graph.native_consumer_count == 24
    assert graph.native_root_count == 1
    assert len(graph.graph.edges) == 24
    for route in (f"service_{service}.read" for service in SERVICE_NAMES):
        assert graph.graph.predecessors(route) == ("customer_directory.read",)
    assert group.required_fields[0].semantic_id == "service.status"
    assert not router.registry.get("service_refund").endpoint("read").destructive


def test_no_model_e0_requires_unsupported_nonempty_not_calibrated_no_fit():
    report = run()
    assert report["schema_version"] == 1
    assert report["evidence_tier"] == "E0_NO_MODEL_G5_OVERFLOW_SYNTHETIC_DEV_ONLY"
    assert report["synthetic_service_paths"] == 24
    assert report["required_typed_one_hop_edges"] == 24
    assert report["k"] == K
    assert report["languages"] == ("en", "ko", "ja")
    assert report["supported_case_count"] == 27
    assert report["ood_case_count"] == 3
    assert not report["real_model_routing_measured"]
    assert not report["independent_e2_qualified"]
    assert not report["independent_publisher_gold"]
    assert not report["calibrated_no_fit"]
    assert not report["agent_task_success_measured"]
    assert not report["product_default_promoted"]
    assert report["whole_lookup_latency_ms"] is None
    assert report["paired_first5_to_e5"] is None
    for lang in ("en", "ko", "ja"):
        assert report["per_language"][lang]["supported_count"] == len(QUERIES)
        assert report["per_language"][lang]["e5_recall_count"] is None
        assert report["per_language"][lang]["ood_nonempty_e5_count"] is None
        assert report["per_language"][lang]["ood_nonempty_first5_count"] == 1
    # The reporter must never serialize task queries or an expected route.
    rendered = json.dumps(report, ensure_ascii=False)
    assert "expected_route" not in rendered
    assert all(query not in rendered for _, *texts in QUERIES for query in texts)
    assert all(query not in rendered for _, query in OOD)


def test_current_principal_denial_is_enforced_before_any_research_ranking():
    router, graph, group = _source()
    # Freeze explicit deny while preserving exact typed graph edges.
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="customer_directory.read",
            roles_any=("reader",),
        ),),
    )
    from schemarouter.field_group_retrieval import NativeDeclaredFieldGroup

    demand = NativeDeclaredFieldGroup(
        aliases=("refund request status",),
        required_fields=group.required_fields,
        source_type=group.source_type,
        license=group.license,
    )
    result = graph.lookup(
        router, "refund request status", principal=ACTOR, group=demand,
        _research_ranker=lambda *_: pytest.fail("no authorized candidates"),
    )
    assert result.status == "no_proven_hit"
    assert not result.candidates
    assert result.qualified_path_count == 0


def test_injected_embedding_never_attests_pinned_real_e5_or_calibrated_no_fit():
    """The backend cannot declare itself pinned via Python library `run`."""

    def injected_vectors(texts):
        # Completely fake in-memory vectors, NOT real multilingual E5.
        return [
            [1.0, 0.0],
            *([1.0, float(index) / 15.0]
              for index in range(len(texts) - 1)),
        ]

    report = run(EmbeddingDecisionBackend(injected_vectors))
    assert report["evidence_tier"] == (
        "E0_INJECTED_G5_DECISION_BACKEND_DEV_NOT_ATTESTED"
    )
    assert report["real_model_routing_measured"] is False
    assert report["calibrated_no_fit"] is False
    assert report["independent_e2_qualified"] is False
    assert report["agent_task_success_measured"] is False
    assert report["product_default_promoted"] is False
    assert report["supported_case_count"] == 27
    assert report["ood_case_count"] == 3
    assert report["per_language"]["ko"]["e5_recall_count"] is not None
    scores = report["e5_score_diagnostic_unscored"]
    assert scores["evidence_tier"] == "UNSCORED_PUBLIC_SYNTHETIC_DEV_SCORE_ONLY"
    assert scores["observed_model_calls"] == 30
    assert scores["no_fit_threshold_selected"] is False
    assert scores["probabilities_calibrated"] is False
    assert scores["independent_publisher_evidence"] is False
    assert "NOT a top-versus-sixth" in scores[
        "meaning_of_top_to_kth_span"
    ]
    for label, count in (("supported", 9), ("unsupported", 1)):
        for lang in ("en", "ko", "ja"):
            group = scores["by_stratum_language"][label][lang]
            assert group["count"] == count
            for metric in ("top_cosine", "kth_cosine", "top_to_kth_span"):
                summary = group[metric]
                assert summary["min"] <= summary["p50"] <= summary["max"]
                assert summary["min"] <= summary["p95"] <= summary["max"]
    exported = json.dumps(report, ensure_ascii=False)
    assert "expected_route" not in exported
    assert "executor_fixture" not in exported
    assert all(query not in exported for _, *queries in QUERIES for query in queries)
    assert all(query not in exported for _lang, query in OOD)


def test_observer_fails_closed_when_embedding_backend_forges_score_metadata(
    monkeypatch,
):
    from schemarouter.decisions import (
        DecisionOption,
        DecisionRequest,
        DecisionResult,
    )

    backend = EmbeddingDecisionBackend(lambda texts: [
        [1.0, 0.0] for _ in texts
    ])
    request = DecisionRequest(
        query="task", max_selections=5,
        options=[DecisionOption(id=str(i)) for i in range(6)],
    )
    real = backend.decide(request)
    assert isinstance(real, DecisionResult)
    assert real.metadata["provider"] == "embedding-similarity"
    score = real.model_copy(
        update={"metadata": {
            **real.metadata, "top_similarity": float("nan"),
        }}
    )
    monkeypatch.setattr(backend, "decide", lambda _req: score)
    observer = UnscoredE5ScoreObserver(backend)
    with pytest.raises(ValueError, match="uncalibrated observation"):
        observer.decide(request)
    assert observer.observed == []


def test_frozen_account_carrier_no_model_preserves_original_source_scope():
    task = run()
    carrier = run(query_variant="account_carrier")
    assert task["query_variant"] == "task_only"
    assert carrier["query_variant"] == "account_carrier"
    assert task["native_source_index_snapshot_id"] == (
        carrier["native_source_index_snapshot_id"]
    )
    assert carrier["synthetic_service_paths"] == 24
    assert carrier["supported_case_count"] == 27
    assert carrier["ood_case_count"] == 3
    assert carrier["e5_score_diagnostic_unscored"] is None
    assert carrier["real_model_routing_measured"] is False
    assert carrier["independent_e2_qualified"] is False
    assert carrier["calibrated_no_fit"] is False
    with pytest.raises(ValueError, match="only frozen"):
        run(query_variant="translate_to_english_using_gold")


def test_query_carrier_applied_uniformly_to_all_supported_not_ood():
    from schemarouter.decisions import CallableDecisionBackend

    captured: list[str] = []

    def selector(request):
        captured.append(request.query)
        return {"selections": [
            {"option_id": option.id}
            for option in request.options[:request.max_selections]
        ]}

    backend = CallableDecisionBackend(selector)
    r = run(backend, query_variant="account_carrier")
    assert r["evidence_tier"] == (
        "E0_INJECTED_G5_DECISION_BACKEND_DEV_NOT_ATTESTED"
    )
    assert r["real_model_routing_measured"] is False
    assert r["supported_case_count"] == 27
    assert r["ood_case_count"] == 3
    assert len(captured) == 30
    assert all(query.endswith(ACCOUNT_QUERY_CARRIER) for query in captured[:27])
    assert all(ACCOUNT_QUERY_CARRIER not in query for query in captured[27:])
    assert not any(
        "service_" in query for query in captured
    )  # no scorer-only native route gold
    exported = json.dumps(r, ensure_ascii=False)
    assert ACCOUNT_QUERY_CARRIER not in exported
    assert all(query not in exported for query in captured)
    assert r["calibrated_no_fit"] is False
    assert r["product_default_promoted"] is False


def test_identical_source_description_omission_is_opt_in_and_never_scores():
    from schemarouter.decisions import CallableDecisionBackend

    legacy = []
    shortened = []

    def full_model(request):
        legacy.append(tuple((opt.label, opt.description) for opt in request.options))
        return {"selections": [
            {"option_id": option.id} for option in request.options[:5]
        ]}

    def short_model(request):
        shortened.append(
            tuple((opt.label, opt.description) for opt in request.options)
        )
        return {"selections": [
            {"option_id": option.id} for option in request.options[:5]
        ]}

    baseline = run(CallableDecisionBackend(full_model))
    omitted = run(
        CallableDecisionBackend(short_model),
        query_variant="account_carrier",
        omit_identical_descriptions=True,
    )
    assert baseline["identical_descriptions_omitted"] is False
    assert omitted["identical_descriptions_omitted"] is True
    assert omitted["query_variant"] == "account_carrier"
    assert len(legacy) == len(shortened) == 30
    assert all(len(optset) == 24 for optset in [*legacy, *shortened])
    for a, b in zip(legacy, shortened, strict=True):
        assert [label for label, _ in a] == [label for label, _ in b]
        assert all(description for _label, description in a)
        assert all(description == "" for _label, description in b)
    assert omitted["per_language"] == baseline["per_language"]
    assert omitted["native_source_index_snapshot_id"] == (
        baseline["native_source_index_snapshot_id"]
    )
    assert omitted["e5_score_diagnostic_unscored"] is None
    assert omitted["independent_e2_qualified"] is False
    assert omitted["real_model_routing_measured"] is False
    assert omitted["calibrated_no_fit"] is False
    assert omitted["product_default_promoted"] is False
    for invalid in (None, 0, 1, "yes"):
        with pytest.raises(ValueError, match="exact bool"):
            run(omit_identical_descriptions=invalid)
