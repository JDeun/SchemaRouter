"""Offline integrity tests for the prospective multilingual CPU evaluation."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.evaluate_multilingual_embedding_cpu_dev import (
    aggregate,
    load_development_corpus,
    percentile,
)

CORPUS = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/multilingual-embedding-cpu-dev-20261015.json"
)


def test_prospective_corpus_is_disjoint_by_id_and_label_explicit() -> None:
    corpus, digest = load_development_corpus(CORPUS)
    assert len(digest) == 64
    assert corpus["surface"] == "prospective_development_only"
    assert corpus["validation_or_holdout_claim_allowed"] is False
    assert len(corpus["catalog"]) == 13
    assert len(corpus["cases"]) == 84
    assert len(set(case["id"] for case in corpus["cases"])) == 84
    assert {case["language"] for case in corpus["cases"]} == {
        "en", "ko", "ja", "es", "de", "mixed",
    }
    for language in corpus["languages"]:
        cases = [case for case in corpus["cases"] if case["language"] == language]
        assert sum(case["kind"] == "supported" for case in cases) == 8
        assert sum(case["kind"] == "unsupported" for case in cases) == 6


def test_corpus_integrity_fails_closed_on_false_ground_truth(tmp_path: Path) -> None:
    corpus, _ = load_development_corpus(CORPUS)
    corrupted = copy.deepcopy(corpus)
    corrupted["cases"][0]["expected_route"] = "not_registered.execute"
    path = tmp_path / "corrupted.json"
    path.write_text(json.dumps(corrupted), encoding="utf-8")
    with pytest.raises(ValueError, match="registered route"):
        load_development_corpus(path)


def test_corpus_cannot_claim_blind_validation(tmp_path: Path) -> None:
    corpus, _ = load_development_corpus(CORPUS)
    corpus["validation_or_holdout_claim_allowed"] = True
    path = tmp_path / "untrusted.json"
    path.write_text(json.dumps(corpus), encoding="utf-8")
    with pytest.raises(ValueError, match="holdout"):
        load_development_corpus(path)


def test_supported_and_unsupported_denominators_are_disjoint() -> None:
    rows = [
        {"language": "ko", "kind": "supported", "hit_at_1": True,
         "hit_at_5": True, "top_similarity": 0.85, "latency_ms": 10.0},
        {"language": "ko", "kind": "supported", "hit_at_1": False,
         "hit_at_5": True, "top_similarity": 0.65, "latency_ms": 20.0},
        {"language": "ko", "kind": "unsupported", "hit_at_1": None,
         "hit_at_5": None, "top_similarity": 0.83, "latency_ms": 40.0},
    ]
    summary = aggregate(rows, [0.8])["overall"]
    assert summary["supported"] == 2
    assert summary["unsupported"] == 1
    assert summary["recall_at_1"] == 0.5
    assert summary["recall_at_5"] == 1.0
    diagnostics = summary["threshold_diagnostics"]["0.8"]
    assert diagnostics["unsupported_false_match_rate"] == 1.0
    assert diagnostics["supported_false_refusal_rate"] == 0.5
    assert diagnostics["supported_wrong_route_accepted_rate"] == 0.0
    assert percentile([1.0, 11.0], 95) == pytest.approx(10.5)
