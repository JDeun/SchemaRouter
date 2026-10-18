"""Synthetic invariants only; official BFCL publisher bytes are tested in CPU CI."""
from __future__ import annotations

import hashlib
import json

import pytest

from scripts.research_bfcl_pair_fit_live_transfer_e1 import (
    _reject_duplicate_pairs,
    fixed_fpr_cutoff,
    git_blob,
    pair_features,
    parse_task,
    run,
    stats,
)
from schemarouter import E5CachedEmbedder


def _function(name: str, description: str) -> dict:
    return {
        "name": name, "description": description,
        "parameters": {"type": "dict", "properties": {
            "query": {"type": "string", "description": "Query text"},
        }},
    }


GOOD = _function("paper_search", "Search original scientific papers by keyword")
BAD = _function("bank_transfer", "Transfer money to a bank account")


def _training() -> dict:
    return {
        "multiple": [
            {
                "id": f"multiple_{i}",
                "question": [[{"role": "user", "content": "Search scientific papers"}]],
                "function": [BAD, GOOD],
            }
            for i in range(200)
        ],
        "irrelevance": [
            {
                "id": f"irrelevance_{i}",
                "question": [[{"role": "user", "content": "Translate this audio"}]],
                "function": [BAD],
            }
            for i in range(240)
        ],
        "gold": [
            {"id": f"multiple_{i}", "ground_truth": [{GOOD["name"]: {}}]}
            for i in range(200)
        ],
    }


def _live() -> dict:
    return {
        "live_relevance": [
            {"id": f"live_relevance_{i}-0-0",
             "question": [[{"role": "user", "content": "Search scientific papers"}]],
             "function": [BAD, GOOD]}
            for i in range(16)
        ],
        "live_irrelevance": [
            {"id": f"live_irrelevance_{i}-0-0",
             "question": [[{"role": "user", "content": "Translate this audio"}]],
             "function": [BAD]}
            for i in range(24)
        ],
    }


def fake_encode(texts: list[str]) -> list[list[float]]:
    return [
        [1.0, 0.0] if txt.startswith("query:") else [0.8, 0.6]
        for txt in texts
    ]


def test_git_blob_and_strict_duplicate_keys() -> None:
    assert git_blob(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
    value = b"source"
    assert git_blob(value) == hashlib.sha1(
        b"blob 6\0" + value,
    ).hexdigest()
    assert _reject_duplicate_pairs([("a", 1), ("b", 2)]) == {"a": 1, "b": 2}
    with pytest.raises(ValueError, match="repeated source"):
        _reject_duplicate_pairs([("a", 1), ("a", 0)])


@pytest.mark.parametrize("scores", [
    [], [1.0], [float("nan")] * 120, [float("inf")] * 120,
])
def test_calibration_needs_120_finite_negatives(scores: list[float]) -> None:
    with pytest.raises(ValueError):
        fixed_fpr_cutoff(scores)


def test_cutoff_does_not_calibrate_on_live_evaluation() -> None:
    values = [float(i) / 120 for i in range(120)]
    cutoff = fixed_fpr_cutoff(values)
    assert sum(x >= cutoff for x in values) <= 12
    rows = stats([0.0] * 100, values, cutoff)
    assert rows["supported_false_refused"] == 100
    assert rows["unsupported_false_accepted"] <= 12


def test_model_only_reads_original_query_and_offered_function_descriptions() -> None:
    q, funcs = parse_task({
        "question": [[{"role": "user", "content": "Search scientific papers"}]],
        "function": [GOOD, BAD],
    })
    assert len(pair_features(q, funcs, E5CachedEmbedder(fake_encode))) == 2
    with pytest.raises(ValueError):
        parse_task({
            "question": [[{"role": "user", "content": "Search scientific papers"}]],
            "function": [GOOD, GOOD],
        })


def test_pair_fit_training_and_live_evaluation_do_not_mix_denominators() -> None:
    result = run(_training(), _live(), fake_encode)
    assert result["train_even"] == {
        "supported": 100, "irrelevant": 120, "individual_pairs": 320,
    }
    assert result["calibrate_odd"] == {"supported": 100, "irrelevant": 120}
    evidence = result["live_category_evaluation"]
    assert evidence["supported"] == 16
    assert evidence["irrelevant"] == 24
    for arm in ("e5_raw_cosine", "trained_pair_fit"):
        assert evidence[arm]["live"]["supported_total"] == 16
        assert evidence[arm]["live"]["unsupported_total"] == 24
    assert result["actual_provider_calls"] is False
    assert result["independently_authored_private_e2"] is False
    assert result["default_product_changed"] is False
    assert "Translate this audio" not in json.dumps(result)
