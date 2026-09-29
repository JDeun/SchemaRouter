from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "benchmarks" / "agent-utility-v2-representation-preregistration.json"


def _load() -> dict:
    return json.loads(PREREG.read_text(encoding="utf-8"))


def test_representation_ablation_identity_is_frozen() -> None:
    data = _load()
    assert data["issue"] == 434
    assert data["parent_issue"] == 417
    assert data["status"] == "preregistered_before_corpus_generation_or_scoring"
    assert data["independence"]["b1_rows_tuning_eligible"] is False
    assert data["independence"]["heldout_issue_432_rows_tuning_eligible"] is False
    assert data["independence"]["fresh_disjoint_surface_required"] is True


def test_representation_ablation_surfaces_and_clusters_are_frozen() -> None:
    data = _load()
    surface = data["task_surface"]
    assert surface["development"] == {
        "unique_semantic_tasks": 60,
        "language_renderings_per_task": 6,
        "total_rows": 360,
        "tuning_eligible": True,
    }
    assert surface["confirmation"] == {
        "unique_semantic_tasks": 120,
        "language_renderings_per_task": 6,
        "total_rows": 720,
        "tuning_eligible": False,
    }
    assert surface["languages"] == ["en", "ko", "es", "ja", "de", "mixed"]
    assert surface["catalog_endpoint_counts"] == [100, 250, 500, 1000]
    assert surface["inference_cluster_unit"] == "semantic_task_id"
    assert surface["catalog_repeat_is_independent_sample"] is False
    assert len(surface["required_strata"]) == 12


def test_representation_ablation_conditions_and_budgets_are_frozen() -> None:
    data = _load()
    assert list(data["conditions"]) == [
        "DESCRIPTION-ONLY",
        "RAW-SPEC",
        "TYPED-MULTIFIELD",
        "INTENT-MANUAL",
        "TYPED+INTENT",
    ]
    assert data["k_values"] == [1, 3, 5, 10]
    assert data["conditions"]["TYPED-MULTIFIELD"]["field_fusion"] == {
        "method": "reciprocal_rank_fusion",
        "rrf_k": 60,
    }
    assert data["conditions"]["INTENT-MANUAL"]["evaluation_queries_allowed"] is False
    assert data["conditions"]["INTENT-MANUAL"]["gold_labels_allowed"] is False
    assert data["conditions"]["INTENT-MANUAL"]["b1_failure_rows_allowed"] is False


def test_representation_ablation_governance_prevents_posthoc_repair() -> None:
    data = _load()
    governance = data["governance"]
    assert governance["no_weight_tuning_from_confirmation"] is True
    assert governance["no_condition_removal_after_confirmation_open"] is True
    assert governance["no_query_removal_after_scoring"] is True
    assert governance["no_manual_generation_from_eval_queries"] is True
    assert governance["no_retrofit_into_b1"] is True
    assert (
        governance["no_claim_about_end_to_end_agent_utility_from_this_retrieval_ablation_alone"]
        is True
    )
