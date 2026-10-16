"""Counterfactual oracle labels are a diagnostic, never trusted inference."""
from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.audit_multilingual_score_overlap_dev import (
    EXPECTED_CORPUS,
    EXPECTED_SEED,
    LANGUAGES,
    MODELS,
    SIZES,
)
from scripts.research_operation_oracle_recoverability_dev import (
    BASE_OPERATION,
    CASE_INTENT,
    compatible_top10,
    declared_route_operation,
    evaluate,
)


def fixture() -> tuple[dict, dict]:
    rows = []
    for lang in LANGUAGES:
        for family in CASE_INTENT:
            supported = family in {
                "materials.search", "papers.search", "weather.current",
                "inventory.lookup", "flights.search",
                "finance.convert_currency", "calendar.list_events",
                "maps.directions",
            }
            gold = family if supported else None
            alternatives = [key for key in BASE_OPERATION if key != gold]
            ranks = ([gold] if gold is not None else []) + alternatives
            ranks = ranks[:10]
            if gold == "maps.directions":
                ranks.remove(gold)
                ranks.insert(1, gold)
            rows.append({
                "case_id": f"{'supported' if supported else 'unsupported'}-"
                           f"{lang}-{family}",
                "kind": "supported" if supported else "unsupported",
                "language": lang, "expected_route": gold,
                "top_1": ranks[0], "top_5": ranks[:5],
                "top_10": ranks, "top_similarity": 0.53,
                "latency_ms": 1.0,
                "hit_at_1": (ranks[0] == gold) if supported else None,
                "hit_at_5": (gold in ranks[:5]) if supported else None,
                "hit_at_10": (gold in ranks) if supported else None,
            })
    assert len(rows) == 84
    reports = {}
    for model, model_id in MODELS.items():
        reports[model] = {
            "model_key": model, "model_id": model_id,
            "corpus_sha256": EXPECTED_CORPUS,
            "generator_seed": EXPECTED_SEED,
            "nested_sizes": [13, 100, 250, 500],
            "surface": "synthetic_stress_development_only",
            "independent_validation": False,
            "true_registered_catalog": False,
            "agent_or_execution_success": False,
            "frozen_0_14_evidence_modified": False,
            "results": {
                size: {
                    "catalog_sha256": f"{int(size):064x}",
                    "generated_distractors": int(size) - 13,
                    "rows": deepcopy(rows),
                } for size in SIZES
            },
        }
    return reports, {
        "source_repository": "JDeun/SchemaRouter",
        "source_run_id": 38729631022,
        "head_sha": "bc448804d7205ffb4deb4853db6225a4755bb72d",
        "independent_confirmation": False,
    }


def test_no_gold_or_query_text_can_grant_operation_fit() -> None:
    assert declared_route_operation("maps.directions") == "directions"
    assert declared_route_operation("dev_stress.museums.routes") == "lookup"
    assert declared_route_operation("finance.exchange_history") == "history"
    assert declared_route_operation("user.injected.delete_all") is None
    assert compatible_top10([
        "dev_stress.museums.routes", "maps.directions",
    ], "directions") == ["maps.directions"]
    assert compatible_top10(["maps.directions"], None) == []
    assert compatible_top10(["maps.directions"], "other") == []


def test_oracle_recovers_some_wrong_first_routes_not_missing_top10() -> None:
    reports, provenance = fixture()
    out = evaluate(reports, provenance)
    assert out["cases_actual"] == 672
    assert out["limitations"]["classifier_accuracy_measured"] is False
    assert out["limitations"]["may_select_default_or_release"] is False
    for model in MODELS:
        for size in SIZES:
            cell = out["summary"][model][size]
            assert cell["supported"] == 48
            assert cell["unsupported"] == 36
            assert cell["oracle_operation_top1_correct"] >= (
                cell["raw_model_top1_correct"]
            )
            assert cell["unsupported_false_accept_with_oracle"] == 0
            assert cell["oracle_operation_top1_correct"] <= (
                cell["model_top10_recoverable"]
            )


@pytest.mark.parametrize("mode", (
    "missing_model", "fake_gold", "duplicate_case", "false_hit",
    "independent", "forgot_scale",
))
def test_counterfactual_fails_closed_on_tampered_source(mode: str) -> None:
    reports, provenance = fixture()
    rows = reports["minilm"]["results"]["500"]["rows"]
    if mode == "missing_model":
        del reports["e5-small"]
    elif mode == "fake_gold":
        rows[0]["expected_route"] = "missing.injected"
    elif mode == "duplicate_case":
        rows[1]["case_id"] = rows[0]["case_id"]
    elif mode == "false_hit":
        rows[0]["hit_at_1"] = False
    elif mode == "independent":
        provenance["independent_confirmation"] = True
    elif mode == "forgot_scale":
        del reports["minilm"]["results"]["250"]
    with pytest.raises(ValueError):
        evaluate(reports, provenance)


def test_a_missing_top10_target_cannot_be_rescued() -> None:
    reports, provenance = fixture()
    for model in MODELS:
        for size in SIZES:
            rows = reports[model]["results"][size]["rows"]
            paper = next(
                r for r in rows
                if r["case_id"] == "supported-ko-papers.search"
            )
            gold = paper["expected_route"]
            ranks = [key for key in BASE_OPERATION if key != gold][:10]
            paper.update({
                "top_1": ranks[0], "top_5": ranks[:5], "top_10": ranks,
                "hit_at_1": False, "hit_at_5": False, "hit_at_10": False,
            })
    out = evaluate(reports, provenance)
    for model in MODELS:
        stats = out["summary"][model]["500"]
        assert stats["model_top10_recoverable"] == 47
        assert stats["oracle_operation_top1_correct"] <= 47
