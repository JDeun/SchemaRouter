"""Tamper tests and threshold-impossibility counterexamples, no model download."""
from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.audit_multilingual_score_overlap_dev import (
    EXPECTED_CORPUS,
    EXPECTED_SEED,
    LANGUAGES,
    MODELS,
    SIZES,
    audit_reports,
)


def _fixture() -> tuple[dict, dict]:
    provenance = {
        "source_repository": "JDeun/SchemaRouter",
        "source_run_id": 38729631022,
        "head_sha": "bc448804d7205ffb4deb4853db6225a4755bb72d",
        "independent_confirmation": False,
    }
    rows = []
    for lang in LANGUAGES:
        for kind, count in (("supported", 8), ("unsupported", 6)):
            for i in range(count):
                positive = kind == "supported"
                gold = "catalog.id0" if positive else None
                ranked = [f"catalog.id{k}" for k in range(10)]
                rows.append({
                    "case_id": f"{lang}.{kind}.{i}",
                    "kind": kind, "language": lang,
                    "expected_route": gold,
                    "top_1": ranked[0], "top_5": ranked[:5],
                    "top_10": ranked,
                    "hit_at_1": True if positive else None,
                    "hit_at_5": True if positive else None,
                    "hit_at_10": True if positive else None,
                    "top_similarity": 0.40 if positive else 0.80,
                    "latency_ms": 1.0,
                })
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
    return reports, provenance


def test_score_overlap_rejected_as_perfect_threshold_claim() -> None:
    models, provenance = _fixture()
    result = audit_reports(models, provenance=provenance)
    assert result["scope"]["may_release"] is False
    assert result["scope"]["scalar_threshold_fitted"] is False
    for model in MODELS:
        for size in SIZES:
            row = result["models"][model][size]
            assert row["supported"] == 48
            assert row["unsupported"] == 36
            assert row["top1_correct"] == 48
            assert row["perfect_scalar_threshold_possible"] is False
            assert row["unsupported_above_weakest_supported"] == 36
            assert not row["lost_top1_since_13"]


@pytest.mark.parametrize("mutation", (
    "missing_scale", "duplicate_task", "unsupported_gold",
    "rank_forgery", "fake_model", "fake_independent",
    "mismatched_gold", "forged_top5", "bad_score",
    "catalog_mismatch", "altered_corpus",
))
def test_tampered_source_reports_rejected(mutation: str) -> None:
    reports, provenance = _fixture()
    row = reports["minilm"]["results"]["500"]["rows"][0]
    if mutation == "missing_scale":
        del reports["minilm"]["results"]["250"]
    elif mutation == "duplicate_task":
        reports["minilm"]["results"]["500"]["rows"][1]["case_id"] = row["case_id"]
    elif mutation == "unsupported_gold":
        row["expected_route"] = None
    elif mutation == "rank_forgery":
        row["top_10"][1] = row["top_10"][0]
    elif mutation == "fake_model":
        reports["minilm"]["model_id"] = "fake/faster-model"
    elif mutation == "fake_independent":
        provenance["independent_confirmation"] = True
    elif mutation == "mismatched_gold":
        row["expected_route"] = "catalog.id1"
    elif mutation == "forged_top5":
        row["hit_at_5"] = False
    elif mutation == "bad_score":
        row["top_similarity"] = float("nan")
    elif mutation == "catalog_mismatch":
        reports["e5-small"]["results"]["500"]["catalog_sha256"] = "a" * 64
    elif mutation == "altered_corpus":
        reports["e5-small"]["corpus_sha256"] = "b" * 64
    with pytest.raises(ValueError):
        audit_reports(reports, provenance=provenance)


def test_top1_degradation_cases_remain_visible() -> None:
    reports, provenance = _fixture()
    for model in MODELS:
        row = reports[model]["results"]["500"]["rows"][0]
        row["top_1"] = "catalog.id1"
        row["top_10"][0] = "catalog.id1"
        row["top_10"][1] = "catalog.id0"
        row["top_5"] = row["top_10"][:5]
        row["hit_at_1"] = False
    report = audit_reports(reports, provenance=provenance)
    for model in MODELS:
        row = report["models"][model]["500"]
        assert row["top1_correct"] == 47
        assert row["top5_correct"] == 48
        assert row["lost_top1_since_13"] == ["en.supported.0"]
