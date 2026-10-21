"""No-model K5 native source scale invariants, separate from actual E5 scoring."""
from __future__ import annotations

import copy

import pytest

from schemarouter import ToolSpec
from schemarouter.decisions import (
    CallableDecisionBackend,
    DecisionOption,
    DecisionRequest,
)
from schemarouter.errors import PlanningError
from scripts.evaluate_authorized_e5_scale_500_cpu_dev import (
    CORPUS,
    E5_PROFILE_STAGE_FIELDS,
    PRINCIPAL,
    PROFILED_STAGE_FIELDS,
    SIZES,
    _ProfiledBackend,
    _summary,
    aggregate_e5_substages,
    build_scaled_authorized_router,
    native_route_id,
    paired_retrieval_error_attribution,
    run_scaled_retrieval_dev,
)
from scripts.evaluate_multilingual_embedding_cpu_dev import load_development_corpus
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_authorized_fixed5_decision_bridge import _visible_fingerprints


def fake_backend(request):
    """A deliberately unmeasured deterministic no-model backend."""
    return {"selections": [
        {"option_id": opt.id}
        for opt in request.options[:request.max_selections]
    ]}


def test_source_native_inventory_is_exactly_nested_at_each_scale():
    corpus, _ = load_development_corpus(CORPUS)
    base = {item["id"] for item in corpus["catalog"]}
    prior = set()
    for size in SIZES:
        router, digest = build_scaled_authorized_router(corpus, size)
        assert len(digest) == 64
        routes = {
            f"{tool.name}.{endpoint.name}"
            for tool in router.registry.tools()
            for endpoint in tool.endpoints
        }
        assert len(routes) == size
        assert base <= routes
        assert prior <= routes
        assert all(
            endpoint.read_only and not endpoint.destructive
            for tool in router.registry.tools() for endpoint in tool.endpoints
        )
        prior = routes


def test_offline_scaled_smoke_checks_real_authority_without_claiming_e5():
    corpus, digest = load_development_corpus(CORPUS)
    out = run_scaled_retrieval_dev(
        corpus, digest, CallableDecisionBackend(fake_backend),
        sizes=SIZES, case_limit=1,
    )
    assert out["catalog_sizes"] == list(SIZES)
    assert out["fixed_k"] == 5
    assert out["real_model_routing_measured"] is False
    assert out["independent_e2_qualified"] is False
    assert out["agent_task_success_measured"] is False
    assert out["calibrated_no_fit"] is False
    assert out["publication_gate_passed"] is False
    assert out["full_84_case_evaluation"] is False
    assert out["evidence_tier"] == "UNATTESTED_BACKEND_RETRIEVAL_DEV_ONLY"
    for size in SIZES:
        item = out["results"][str(size)]
        assert item["e5_substage_profile_ms"] == {"smoke_only_not_scored": True}
        assert item["registered_native_routes"] == size
        assert item["cases_scored"] == 1
        for arm in out["candidate_arm_ids"]:
            assert item["arms"][arm] == {
                "smoke_only_not_scored": True,
                "cases_exercised": 1,
            }


@pytest.mark.parametrize("id", (
    "dev_stress.marine.lookup", "dev_stress.audio_recordings.read",
))
def test_native_route_identifier_preserves_typed_tool_identity(id):
    out = native_route_id(id)
    assert out.count(".") == 1
    assert out.startswith("dev_stress_")


@pytest.mark.parametrize("bad", (
    "dev_stress", "dev_stress.marine", "other.marine.lookup",
    "dev_stress.marine.lookup.extra", "dev_stress..lookup", "dev_stress.marine.",
))
def test_malformed_generated_source_ids_are_fail_closed(bad):
    with pytest.raises(ValueError, match="research distractor"):
        native_route_id(bad)


def test_never_score_altered_dev_gold_or_unpinned_corpus():
    corpus, digest = load_development_corpus(CORPUS)
    altered = copy.deepcopy(corpus)
    altered["cases"][0]["expected_route"] = "dev_stress_marine.lookup"
    with pytest.raises(ValueError, match="unverified or altered DEV corpus"):
        run_scaled_retrieval_dev(
            altered, digest, CallableDecisionBackend(fake_backend),
            sizes=(13,), case_limit=1,
        )
    with pytest.raises(ValueError, match="unverified or altered DEV corpus"):
        run_scaled_retrieval_dev(
            corpus, "0" * 64, CallableDecisionBackend(fake_backend),
            sizes=(13,), case_limit=1,
        )


@pytest.mark.parametrize("sizes", ((0,), (100, 100), [100], (False,)))
def test_scale_cannot_be_duplicated_forged_or_outside_predeclared_catalog(sizes):
    corpus, digest = load_development_corpus(CORPUS)
    with pytest.raises(ValueError, match="unverified or altered DEV corpus"):
        run_scaled_retrieval_dev(
            corpus, digest, CallableDecisionBackend(fake_backend),
            sizes=sizes, case_limit=1,
        )


def test_invalid_task_limit_rejected_without_backend_exposure():
    corpus, digest = load_development_corpus(CORPUS)
    for bad in (0, True, -1, 85):
        with pytest.raises(ValueError, match="smoke case bound"):
            run_scaled_retrieval_dev(
                corpus, digest, CallableDecisionBackend(fake_backend),
                sizes=(13,), case_limit=bad,
            )


def test_untrusted_model_option_id_still_cannot_appear_in_native_shortlist():
    corpus, digest = load_development_corpus(CORPUS)
    with pytest.raises((PlanningError, ValueError)):
        run_scaled_retrieval_dev(
            corpus, digest,
            CallableDecisionBackend(
                lambda request: {
                    "selections": [{"option_id": "foreign-not-registered"}],
                }
            ),
            sizes=(13,), case_limit=1,
        )


def test_profiling_wrapper_is_output_transparent_and_never_accepts_gold():
    backend = _ProfiledBackend(CallableDecisionBackend(fake_backend))
    request = DecisionRequest(
        query="Korean multilingual DEV no model",
        options=[DecisionOption(id="native:0", label="safe.read")],
        max_selections=1,
    )
    result = backend.decide(request)
    assert [s.option_id for s in result.selections] == ["native:0"]
    assert backend.calls == 1
    assert type(backend.elapsed_ns) is int
    assert backend.elapsed_ns >= 0


def test_profile_aggregates_stage_p95_without_raw_query_or_labels():
    corpus, _ = load_development_corpus(CORPUS)
    rows = [
        {
            "kind": case["kind"],
            "language": case["language"],
            "hit_at_1": True if case["kind"] == "supported" else None,
            "hit_at_5": True if case["kind"] == "supported" else None,
            "nonempty_unsupported": case["kind"] == "unsupported",
            "selection_latency_ms": 4.0,
            "source_capture_latency_ms": 12.0,
            "backend_decision_latency_ms": 2.0,
            "nonbackend_selection_latency_ms": 2.0,
            "source_capture_plus_selection_latency_ms": 16.0,
        }
        for case in corpus["cases"]
    ]
    result = _summary(rows)
    assert set(result["stage_latency_ms"]) == set(PROFILED_STAGE_FIELDS)
    assert result["supported_recall_at_5"] == 1
    assert result["stage_latency_ms"]["source_capture_latency_ms"]["p95"] == 12.0
    assert result["stage_latency_ms"]["backend_decision_latency_ms"]["p99"] == 2.0
    assert result["stage_latency_ms"]["nonbackend_selection_latency_ms"]["p50"] == 2.0
    assert result["stage_latency_ms"]["source_capture_plus_selection_latency_ms"]["p95"] == 16.0
    assert "query" not in str(result)
    assert "expected_route" not in str(result)


def test_invalid_profile_telemetry_is_fail_closed():
    corpus, _ = load_development_corpus(CORPUS)
    rows = []
    for case in corpus["cases"]:
        rows.append({
            "kind": case["kind"],
            "language": case["language"],
            "hit_at_1": True if case["kind"] == "supported" else None,
            "hit_at_5": True if case["kind"] == "supported" else None,
            "nonempty_unsupported": case["kind"] == "unsupported",
            "selection_latency_ms": 0.1,
            **{name: 0.1 for name in PROFILED_STAGE_FIELDS},
        })
    for corrupt in (-1.0, float("nan"), float("inf"), "fake"):
        rows[0]["backend_decision_latency_ms"] = corrupt
        with pytest.raises(ValueError, match="measured CPU latency stage"):
            _summary(rows)


def test_existing_13_route_mock_scores_preserved_with_inference_profile():
    corpus, digest = load_development_corpus(CORPUS)
    output = run_scaled_retrieval_dev(
        corpus, digest, CallableDecisionBackend(fake_backend),
        sizes=(13,),
    )
    assert output["real_model_routing_measured"] is False
    assert output["independent_e2_qualified"] is False
    assert output["full_84_case_evaluation"] is True
    assert output["candidate_arm_ids"] == [
        "lexical_k5", "e5_k5", "hybrid_rrf60_k5",
    ]
    details = output["results"]["13"]["e5_substage_profile_ms"]
    assert set(details) == set(E5_PROFILE_STAGE_FIELDS)
    assert details["choose_sync_ms"]["p95"] >= (
        details["choose_sync_nonbackend_ms"]["p95"]
    )
    assert details["source_validation_ms"]["p95"] >= 0
    assert "expected_route" not in str(details)
    for arm in output["candidate_arm_ids"]:
        result = output["results"]["13"]["arms"][arm]
        assert result["supported"] == 48
        assert result["unsupported"] == 36
        assert set(result["stage_latency_ms"]) == set(PROFILED_STAGE_FIELDS)
        for stats in result["stage_latency_ms"].values():
            assert stats["p50"] >= 0
            assert stats["p95"] >= stats["p50"]
            assert stats["p99"] >= stats["p95"]
    assert output["results"]["13"]["arms"]["lexical_k5"]["stage_latency_ms"][
        "backend_decision_latency_ms"
    ]["p95"] == 0
    assert output["results"]["13"]["arms"]["e5_k5"]["stage_latency_ms"][
        "backend_decision_latency_ms"
    ]["p95"] > 0


def _paired_fixture():
    corpus, _ = load_development_corpus(CORPUS)
    rows = {arm: [] for arm in ("lexical_k5", "e5_k5", "hybrid_rrf60_k5")}
    per_language_supported = {}
    for case_ordinal, case in enumerate(corpus["cases"]):
        lang = case["language"]
        if case["kind"] == "supported":
            index = per_language_supported.get(lang, 0)
            per_language_supported[lang] = index + 1
            outcomes = {
                "lexical_k5": (index in (0, 1, 2), index in (0, 1, 2, 3, 4)),
                "e5_k5": (index in (1, 2, 3, 4, 5), index in (1, 2, 3, 4, 5, 6)),
                "hybrid_rrf60_k5": (index in (0, 1, 2, 3), index in (0, 1, 2, 3, 4, 5)),
            }
        else:
            outcomes = {arm: (None, None) for arm in rows}
        for arm, (at1, at5) in outcomes.items():
            rows[arm].append({
                "case_ordinal": case_ordinal,
                "case_id": case["id"],
                "kind": case["kind"],
                "language": lang,
                "hit_at_1": at1,
                "hit_at_5": at5,
                "nonempty_unsupported": case["kind"] == "unsupported",
            })
    return rows


def test_paired_error_attribution_reports_language_rescues_and_regressions():
    paired = paired_retrieval_error_attribution(_paired_fixture())
    assert set(paired) == {
        "lexical_k5_vs_e5_k5",
        "lexical_k5_vs_hybrid_rrf60_k5",
    }
    for lang in ("en", "ko", "ja", "es", "de", "mixed"):
        row = paired["lexical_k5_vs_e5_k5"][lang]
        assert (row["supported"], row["unsupported"]) == (8, 6)
        assert row["at_1"] == {
            "lexical_hits": 3, "candidate_hits": 5, "rescued": 3,
            "regressed": 1, "both_hit": 2, "neither_hit": 2,
        }
        assert row["at_5"] == {
            "lexical_hits": 5, "candidate_hits": 6, "rescued": 2,
            "regressed": 1, "both_hit": 4, "neither_hit": 1,
        }
        assert row["unsupported_nonempty_both"] == 6
        assert row["unsupported_newly_nonempty"] == 0
        assert row["unsupported_newly_empty"] == 0
    total = paired["lexical_k5_vs_e5_k5"]["all"]
    assert total["at_5"]["rescued"] == 12
    assert total["at_5"]["regressed"] == 6
    assert total["supported"] == 48
    assert total["unsupported"] == 36
    assert "query" not in str(paired)
    assert "expected_route" not in str(paired)


@pytest.mark.parametrize("corrupt", (
    "reordered", "wrong_ordinal", "same_language_swap", "incomplete",
    "unsupported_type", "bad_kind", "extra_arm",
))
def test_paired_error_attribution_refuses_misaligned_or_invalid_rows(corrupt):
    rows = _paired_fixture()
    if corrupt == "reordered":
        rows["e5_k5"][0]["language"] = "another-language"
    elif corrupt == "wrong_ordinal":
        rows["e5_k5"][0]["case_ordinal"] = 1
    elif corrupt == "same_language_swap":
        # Ordinals, language and kind remain identical: only true IDs differ.
        indices = [
            i for i, row in enumerate(rows["e5_k5"])
            if row["language"] == "en" and row["kind"] == "supported"
        ]
        a, b = indices[:2]
        rows["e5_k5"][a]["case_id"], rows["e5_k5"][b]["case_id"] = (
            rows["e5_k5"][b]["case_id"], rows["e5_k5"][a]["case_id"],
        )
    elif corrupt == "incomplete":
        rows["e5_k5"].pop()
    elif corrupt == "unsupported_type":
        next(row for row in rows["hybrid_rrf60_k5"]
             if row["kind"] == "unsupported")["hit_at_5"] = False
    elif corrupt == "bad_kind":
        rows["e5_k5"][0]["kind"] = "other"
    else:
        rows["unexpected"] = rows["e5_k5"]
    with pytest.raises(ValueError, match="paired"):
        paired_retrieval_error_attribution(rows)


def test_model_mock_full_still_labels_attribution_unattested():
    corpus, digest = load_development_corpus(CORPUS)
    result = run_scaled_retrieval_dev(
        corpus, digest, CallableDecisionBackend(fake_backend), sizes=(13,),
    )
    paired = result["results"]["13"]["paired_attribution"]
    assert paired["lexical_k5_vs_e5_k5"]["all"]["supported"] == 48
    assert result["real_model_routing_measured"] is False
    assert result["evidence_tier"] == "UNATTESTED_BACKEND_RETRIEVAL_DEV_ONLY"
    smoke = run_scaled_retrieval_dev(
        corpus, digest, CallableDecisionBackend(fake_backend),
        sizes=(13,), case_limit=1,
    )
    assert smoke["results"]["13"]["paired_attribution"] == {
        "smoke_only_not_scored": True,
    }


def test_e5_substage_aggregation_rejects_partial_forged_and_nonfinite_rows():
    valid = [
        {
            **{key: float(index + 1)
               for index, key in enumerate(E5_PROFILE_STAGE_FIELDS)},
            "choose_sync_ms": 10.0,
            "choose_sync_nonbackend_ms": 1.0,
        }
        for _ in range(84)
    ]
    assert aggregate_e5_substages(valid)["source_validation_ms"]["p95"] > 0
    with pytest.raises(ValueError, match="84 original"):
        aggregate_e5_substages(valid[:-1])
    for change in ("missing", "extra", "negative", "nan", "invalid_choice"):
        corrupted = copy.deepcopy(valid)
        if change == "missing":
            corrupted[0].pop("source_validation_ms")
        elif change == "extra":
            corrupted[0]["case_id"] = "should-never-leak"
        elif change == "negative":
            corrupted[0]["bridge_prevalidation_ms"] = -1.0
        elif change == "nan":
            corrupted[0]["request_materialization_ms"] = float("nan")
        else:
            corrupted[0]["choose_sync_nonbackend_ms"] = 999.0
        with pytest.raises(ValueError, match="E5"):
            aggregate_e5_substages(corrupted)


@pytest.mark.parametrize("size", SIZES)
def test_fingerprint_snapshot_scan_matches_original_and_hashes_each_tool_once(
    size, monkeypatch,
):
    corpus, _ = load_development_corpus(CORPUS)
    router, _ = build_scaled_authorized_router(corpus, size)
    query = corpus["cases"][0]["query"]
    view = capture_authorized_agent_tool_surface(
        router, query, principal=PRINCIPAL,
    )
    visible = set(view.visible_route_ids)
    original: dict[str, tuple[str, str]] = {}
    for tool in router.registry.tools():
        for endpoint in tool.endpoints:
            route = f"{tool.key}.{endpoint.name}"
            if route in visible:
                original[route] = (tool.fingerprint, endpoint.fingerprint)

    expected_tools = sum(
        any(f"{tool.key}.{endpoint.name}" in visible for endpoint in tool.endpoints)
        for tool in router.registry.tools()
    )
    full_fingerprint = ToolSpec.fingerprint.fget
    assert full_fingerprint is not None
    calls = 0

    def counted_fingerprint(tool):
        nonlocal calls
        calls += 1
        return full_fingerprint(tool)

    with monkeypatch.context() as scoped:
        scoped.setattr(ToolSpec, "fingerprint", property(counted_fingerprint))
        current = _visible_fingerprints(view)
    assert current == original
    assert set(current) == visible
    assert calls == expected_tools
    view.assert_source_unchanged()
