"""Public BFCL menu-size source-negative tail: scoped exploratory only."""
from __future__ import annotations

import json

import pytest

from scripts.research_bfcl_pair_fit_live_transfer_e1 import (
    familywise_negative_tail_accept,
)


def _fn(name: str, description: str) -> dict:
    return {
        "name": name, "description": description,
        "parameters": {"type": "dict", "properties": {
            "query": {"type": "string", "description": "Query text"},
        }},
    }


GOOD = _fn("paper_search", "Search original scientific papers by keyword")
BAD = _fn("bank_transfer", "Transfer money to a bank account")


def _training() -> dict:
    return {
        "multiple": [
            {"id": f"multiple_{i}",
             "question": [[{"role": "user", "content": "Search scientific papers"}]],
             "function": [BAD, GOOD]}
            for i in range(200)
        ],
        "irrelevance": [
            {"id": f"irrelevance_{i}",
             "question": [[{"role": "user", "content": "Translate this audio"}]],
             "function": [BAD]}
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
             "function": [] if i < 4 else [BAD]}
            for i in range(24)
        ],
    }


def fake_encode(texts: list[str]) -> list[list[float]]:
    return [
        [1.0, 0.0] if txt.startswith("query:") else [0.8, 0.6]
        for txt in texts
    ]


NEGATIVE_120 = [i / 120.0 for i in range(120)]


def test_finite_original_calibration_resolution_prevents_big_menu_extrapolation():
    assert familywise_negative_tail_accept([1.0], NEGATIVE_120)
    assert familywise_negative_tail_accept([1.0] * 12, NEGATIVE_120)
    assert not familywise_negative_tail_accept([1.0] * 13, NEGATIVE_120)
    assert not familywise_negative_tail_accept([1.0] * 37, NEGATIVE_120)


def test_candidate_tail_and_ties_account_for_each_nonfit_comparison():
    assert not familywise_negative_tail_accept([0.5], NEGATIVE_120)
    assert not familywise_negative_tail_accept([0.9] * 8, NEGATIVE_120)
    assert familywise_negative_tail_accept([1.0] * 4, NEGATIVE_120)
    assert not familywise_negative_tail_accept(
        [0.8],
        [0.8] * 120,
    )


@pytest.mark.parametrize("candidates,negatives", (
    ([], NEGATIVE_120),
    ([float("nan")], NEGATIVE_120),
    ([True], NEGATIVE_120),
    ([1.0] * 501, NEGATIVE_120),
    ([1.0], NEGATIVE_120[:119]),
    ([1.0], [float("inf")] * 120),
))
def test_reject_invalid_or_unsupported_source_calibration(candidates, negatives):
    with pytest.raises(ValueError, match="invalid source-pinned"):
        familywise_negative_tail_accept(candidates, negatives)


def test_original_bfcl_source_e5_scorer_unchanged_without_optin():
    pytest.importorskip("sklearn", reason="research-only classifier dependency")
    from scripts.research_bfcl_pair_fit_live_transfer_e1 import run

    old = run(_training(), _live(), fake_encode)
    trial = run(_training(), _live(), fake_encode, menu_familywise=True)
    assert old["live_category_evaluation"]["e5_raw_cosine"] == (
        trial["live_category_evaluation"]["e5_raw_cosine"]
    )
    assert old["live_category_evaluation"]["trained_pair_fit"] == (
        trial["live_category_evaluation"]["trained_pair_fit"]
    )
    assert "menu_familywise_diagnostic" not in old["live_category_evaluation"]
    extra = trial["live_category_evaluation"]["menu_familywise_diagnostic"]
    assert extra["supported_total"] == 16
    assert extra["unsupported_total"] == 20
    assert extra["supported_admitted"] + extra["supported_false_refused"] == 16
    assert extra["unsupported_false_accepted"] + extra[
        "unsupported_correctly_refused"
    ] == 20
    assert extra["external_independent_e2_qualified"] is False
    assert extra["source"] == (
        "original_odd_id_hash_selected_single_negative_pair_Bonferroni"
    )
    assert extra["calibration_unit"] == "one_function_per_original_negative_request"
    assert extra["negative_calibration_requests"] == 120
    assert not trial["production_threshold_calibrated"]
    assert not trial["release_qualified"]
    dumped = json.dumps(trial, ensure_ascii=False)
    assert "Search scientific papers" not in dumped
    assert "Translate this audio" not in dumped
