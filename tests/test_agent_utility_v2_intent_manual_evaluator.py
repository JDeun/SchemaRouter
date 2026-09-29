from __future__ import annotations

from pathlib import Path

import scripts.evaluate_agent_utility_v2_intent_manual as intent_eval
import scripts.evaluate_agent_utility_v2_representation as base_eval
from scripts.generate_agent_utility_v2_dev import freeze_dev
from scripts.generate_agent_utility_v2_intent_manual import generate_all


def test_intent_conditions_score_without_opening_confirmation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    freeze_dir = tmp_path / "freeze"
    intent_dir = tmp_path / "intent"
    freeze_dev(freeze_dir)
    generate_all(freeze_dir, intent_dir)

    monkeypatch.setattr(base_eval, "CATALOG_SIZES", (100,))
    monkeypatch.setattr(intent_eval, "CATALOG_SIZES", (100,))

    result = intent_eval.evaluate(freeze_dir, intent_dir)

    assert result["confirmation_state"] == "sealed_not_generated_not_scored"
    assert result["conditions_blocked"] == {}
    assert result["conditions_scored"] == [
        "DESCRIPTION-ONLY",
        "RAW-SPEC",
        "TYPED-MULTIFIELD",
        "INTENT-MANUAL",
        "TYPED+INTENT",
    ]
    assert set(result["catalog_sizes"]["100"]) == {
        "DESCRIPTION-ONLY",
        "RAW-SPEC",
        "TYPED-MULTIFIELD",
        "INTENT-MANUAL",
        "TYPED+INTENT",
    }

    for condition in ("INTENT-MANUAL", "TYPED+INTENT"):
        metrics = result["catalog_sizes"]["100"][condition]
        assert metrics["aggregate"]["rows"] == 360
        assert metrics["aggregate"]["supported_rows"] == 300
        assert metrics["aggregate"]["unsupported_rows"] == 60
        assert metrics["index_bytes"] > 0
        assert metrics["index_build_seconds"] >= 0

    assert set(result["dev_gates_descriptive"]) == {
        "TYPED-MULTIFIELD",
        "INTENT-MANUAL",
        "TYPED+INTENT",
    }
    assert set(result["promotion_ready_on_dev"]) == {
        "TYPED-MULTIFIELD",
        "INTENT-MANUAL",
        "TYPED+INTENT",
    }
    assert all(
        gate["confirmation_claim_allowed"] is False
        for gate in result["dev_gates_descriptive"].values()
    )


def test_combined_fusion_is_component_level() -> None:
    ranking_a = [
        ("a", 3.0),
        ("b", 2.0),
        ("c", 1.0),
    ]
    ranking_b = [
        ("c", 4.0),
        ("b", 2.0),
        ("a", 0.0),
    ]

    fused = intent_eval.IntentRetriever._fuse((ranking_a, ranking_b))
    scores = dict(fused)

    assert scores["c"] == (
        1.0 / (intent_eval.RRF_K + 3)
        + 1.0 / (intent_eval.RRF_K + 1)
    )
    assert scores["b"] == (
        1.0 / (intent_eval.RRF_K + 2)
        + 1.0 / (intent_eval.RRF_K + 2)
    )
    assert scores["a"] == 1.0 / (intent_eval.RRF_K + 1)
