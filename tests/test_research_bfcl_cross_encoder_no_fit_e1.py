"""Synthetic negative controls for source-pinned BFCL cross-encoder E1."""

from __future__ import annotations

import json
import math

import pytest

from scripts.research_bfcl_cross_encoder_no_fit_e1 import (
    BINS,
    MAX_TOTAL_PAIRS,
    STUDY,
    menu_bin,
    run,
    score_one,
    stats,
)


def _function(name: str, description: str = "Description") -> dict:
    return {"name": name, "description": description, "parameters": {"properties": {}}}


def _record(kind: str, number: int, menu: list[dict]) -> dict:
    return {
        "id": f"{kind}_{number}",
        "question": [[{"role": "system", "content": "hidden source preface"},
                      {"role": "user", "content": "Find scientific papers"}]],
        "function": menu,
    }


PAPER = _function("paper_search", "Search original scientific articles")
UNSUPPORTED = _function("bank_transfer", "Transfer funds to a recipient")


class FakeCrossEncoder:
    def __init__(self) -> None:
        self.observed: list[list[tuple[str, str]]] = []

    def predict(self, pairs, batch_size=16, show_progress_bar=False):
        assert batch_size == 16 and show_progress_bar is False
        self.observed.append(pairs)
        return [0.9 if "paper_search" in description else 0.2
                for _, description in pairs]


def _sources() -> tuple[dict, dict]:
    old = {
        "irrelevance": [_record("irrelevance", i, [UNSUPPORTED])
                        for i in range(240)],
    }
    live = {
        "live_relevance": [
            _record("live_relevance", i, [UNSUPPORTED, PAPER])
            for i in range(16)
        ],
        "live_irrelevance": [
            _record("live_irrelevance", i, [] if i < 4 else [UNSUPPORTED])
            for i in range(884)
        ],
    }
    return old, live


@pytest.mark.parametrize(("size", "expected"), [
    (1, "1"), (2, "2-4"), (4, "2-4"),
    (5, "5-12"), (12, "5-12"), (13, "13+"), (500, "13+"),
])
def test_menu_bins_are_predeclared(size: int, expected: str) -> None:
    assert menu_bin(size) == expected
    assert tuple(BINS) == ("1", "2-4", "5-12", "13+")


def test_empty_menu_is_only_structural_no_call() -> None:
    model = FakeCrossEncoder()
    assert score_one(_record("live_irrelevance", 0, []), model) == (None, 0, 0.0)
    assert model.observed == []
    with pytest.raises(ValueError, match="nonempty"):
        menu_bin(0)


def test_model_only_reads_last_user_and_offered_function_docs() -> None:
    model = FakeCrossEncoder()
    score, width, seconds = score_one(
        _record("live_relevance", 0, [UNSUPPORTED, PAPER]), model,
    )
    assert score == 0.9 and width == 2 and seconds >= 0
    assert len(model.observed) == 1
    assert all(query == "Find scientific papers" for query, _ in model.observed[0])
    assert "hidden source preface" not in json.dumps(model.observed)


def test_nonfinite_scores_cannot_enter_cutoff() -> None:
    class Nonfinite:
        def predict(self, pairs, **kwargs):
            return [float("nan")] * len(pairs)

    with pytest.raises(ValueError, match="nonfinite"):
        score_one(_record("irrelevance", 1, [PAPER]), Nonfinite())


def test_model_length_drift_is_rejected() -> None:
    class WrongLength:
        def predict(self, pairs, **kwargs):
            return []

    with pytest.raises(ValueError, match="result length"):
        score_one(_record("irrelevance", 1, [PAPER]), WrongLength())


def test_frozen_odd_negative_cutoff_and_live_false_accept_denominators() -> None:
    old, live = _sources()
    model = FakeCrossEncoder()
    result = run(old, live, model)
    assert result["study"] == STUDY
    assert result["split"] == {
        "calibrate_publisher_irrelevance_odd_ids": 120,
        "calibrate_false_accepted": 0,
        "calibrate_budget_false_accepted": 12,
        "live_supported": 16,
        "live_unsupported_scored": 880,
        "live_unsupported_empty_menu_safe_excluded": 4,
    }
    assert result["calibration_max_score_threshold"] > 0.2
    assert result["live"]["supported"]["accepted"] == 16
    assert result["live"]["supported"]["false_refused"] == 0
    assert result["live"]["unsupported"]["false_accepted"] == 0
    assert result["live"]["original_menu_size_bins"]["1"]["unsupported"]["total"] == 880
    assert result["cpu_inference"]["offered_function_pairs_scored"] == 120 + 32 + 880
    assert len(model.observed) == 120 + 16 + 880
    assert not result["heldout_independent_e2"]
    assert not result["release_qualified"]
    assert not result["default_product_changed"]
    assert result["public_model_training_contamination_possible"]
    assert "hidden source preface" not in json.dumps(result)
    assert "Find scientific papers" not in json.dumps(result)


def test_live_relevance_denominator_drift_is_rejected() -> None:
    old, live = _sources()
    live["live_relevance"].pop()
    with pytest.raises(ValueError, match="cardinality"):
        run(old, live, FakeCrossEncoder())


def test_calibration_with_empty_or_missing_odd_negative_is_rejected() -> None:
    old, live = _sources()
    old["irrelevance"][1]["function"] = []
    with pytest.raises(ValueError, match="empty offered menu"):
        run(old, live, FakeCrossEncoder())


def test_e1_calibration_is_not_live_selected() -> None:
    assert stats([0.2, 0.8], math.nextafter(0.2, math.inf), supported=True) == {
        "total": 2, "accepted": 1, "refused": 1, "false_refused": 1,
    }
    assert stats([0.2, 0.8], math.nextafter(0.2, math.inf), supported=False) == {
        "total": 2, "accepted": 1, "refused": 1, "false_accepted": 1,
    }
    assert MAX_TOTAL_PAIRS == 100_000
