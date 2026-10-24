"""E0 synthetic direct field-index DEV against original scoped registry."""
from __future__ import annotations

import json

import pytest

from schemarouter.decisions import CallableDecisionBackend
from scripts.research_indexed_e5_overflow_cpu_dev import (
    ACTOR,
    K,
    OOD,
    QUERIES,
    SERVICE_NAMES,
    _source,
    run,
)


def test_direct_field_index_uses_native_source_tools_no_execution():
    router, index, group = _source()
    assert len(SERVICE_NAMES) == 24
    assert len(QUERIES) == 9
    assert len(OOD) == 3
    assert index.indexed_route_count == 24
    assert set(index.postings["service.status"]) == {
        f"service_{name}.read" for name in SERVICE_NAMES
    }
    for name in SERVICE_NAMES:
        route = router.registry.get(f"service_{name}").endpoint("read")
        assert route.read_only is True
        assert not route.parameters
        assert not route.input_schema
    query = "invoicing status test"
    qualified = index.lookup(
        router, query, principal=ACTOR,
        group=group.model_copy(update={"aliases": (query,)}),
        input_free_only=True,
    )
    assert qualified.status == "over_k_unranked"
    assert qualified.qualified_count == 24


def test_no_model_validation_discloses_no_pseudo_gold_or_quality_claims():
    report = run()
    assert report["schema_version"] == 1
    assert report["evidence_tier"] == "E0_NO_MODEL_DIRECT_INDEX_SYNTHETIC_DEV_ONLY"
    assert report["source_snapshot_id"]
    assert report["synthetic_service_paths"] == 24
    assert report["indexed_route_count"] == 24
    assert report["supported_case_count"] == 27
    assert report["ood_case_count"] == 3
    assert report["languages"] == ("en", "ko", "ja")
    assert report["k"] == K
    assert report["real_model_routing_measured"] is False
    assert report["independent_publisher_gold"] is False
    assert report["independent_e2_qualified"] is False
    assert report["agent_task_success_measured"] is False
    assert report["calibrated_no_fit"] is False
    assert report["product_default_promoted"] is False
    assert report["paired_first5_to_model"] is None
    assert report["model_input_output_tokens"] is None
    assert set(report["whole_lookup_latency_ms"]) == {"unranked", "first5"}
    for lang in ("en", "ko", "ja"):
        scored = report["per_language"][lang]
        assert scored["supported_count"] == 9
        assert scored["model_recall_count"] is None
        assert scored["ood_nonempty_first5_count"] == 1
    rendered = json.dumps(report, ensure_ascii=False)
    assert "expected_route" not in rendered
    for _service, en, ko, ja in QUERIES:
        assert en not in rendered
        assert ko not in rendered
        assert ja not in rendered
    for _lang, text in OOD:
        assert text not in rendered


def test_injected_model_measures_only_public_synthetic_ranking():
    seen = []

    def answer(request):
        seen.append(request)
        assert len(request.options) == 24
        assert all(option.description == "required output=status"
                   for option in request.options)
        assert all(option.metadata == {} for option in request.options)
        assert request.context["independent_quality_evidence"] is False
        assert request.context["executable_authority"] is False
        return {"selections": [
            {"option_id": option.id} for option in request.options[-5:]
        ]}

    report = run(CallableDecisionBackend(answer))
    assert len(seen) == 30
    assert report["evidence_tier"] == "E0_INJECTED_DIRECT_INDEX_DECISION_DEV_NOT_ATTESTED"
    assert report["real_model_routing_measured"] is False
    assert report["independent_publisher_gold"] is False
    assert report["model_input_output_tokens"] is None
    assert report["paired_first5_to_model"] is not None
    assert set(report["whole_lookup_latency_ms"]) == {"unranked", "first5", "model"}
    assert sum(
        report["per_language"][lang]["model_recall_count"] for lang in ("en", "ko", "ja")
    ) <= 27
    for lang in ("en", "ko", "ja"):
        assert report["per_language"][lang]["ood_nonempty_model_count"] == 1
    exposed = str([item.model_dump(mode="python") for item in seen])
    assert "expected_route" not in exposed
    assert "independent_publisher_gold" not in exposed
    assert "source_snapshot_id" not in exposed


def test_no_unapproved_tool_or_model_for_ranker_selection(monkeypatch):
    router, index, group = _source()
    forbidden = {"called": False}

    def fail_execution(*args, **kwargs):
        forbidden["called"] = True
        pytest.fail("research decision may never execute native tools")

    monkeypatch.setattr(router, "execute", fail_execution)
    index.lookup(
        router, "synthetic case status", group=group, principal=ACTOR,
        input_free_only=True,
    )
    assert forbidden["called"] is False
