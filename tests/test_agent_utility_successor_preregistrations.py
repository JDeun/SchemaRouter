from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTIVE = ROOT / "benchmarks" / "agent-utility-v5-adaptive-shortlist-preregistration.json"
CORRECTIVE = ROOT / "benchmarks" / "agent-utility-v6-corrective-reretrieval-preregistration.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_adaptive_shortlist_protocol_is_independent_and_scale_invariant() -> None:
    data = _load(ADAPTIVE)

    assert data["issue"] == 430
    assert data["status"] == "preregistered_before_dev_corpus_generation_or_scoring"
    assert data["score_semantics"]["absolute_score_thresholds_allowed"] is False
    assert "max(abs(score_i), abs(score_{i+1}), 1e-9)" in data["score_semantics"]["formula"]

    independence = data["independence"]
    assert all(value is False for value in independence.values())

    assert data["development_surface"]["unique_semantic_tasks"] == 240
    assert len(data["development_surface"]["task_strata"]) == 8
    assert len(data["development_surface"]["languages"]) == 6
    assert data["development_surface"]["tasks_per_stratum_language_cell"] == 5
    assert 8 * 6 * 5 == 240

    assert data["confirmation_surface"]["unique_semantic_tasks"] == 240
    assert data["confirmation_surface"]["sealed_until_one_policy_selected"] is True
    assert data["confirmation_surface"]["tuning_eligible"] is False


def test_adaptive_shortlist_policy_selection_is_finite_and_frozen() -> None:
    data = _load(ADAPTIVE)
    policies = data["candidate_policies"]

    assert [row["id"] for row in policies["controls"]] == [
        "FIXED-3",
        "FIXED-5",
        "FIXED-10",
    ]
    assert [row["id"] for row in policies["adaptive"]] == [
        "REL-GAP-005",
        "REL-GAP-010",
        "REL-GAP-020",
        "MAX-GAP-010",
    ]
    assert policies["learned_policy_allowed"] is False

    selection = data["dev_selection"]
    assert selection["select_exactly_one_policy"] is True
    assert selection["no_post_selection_retuning"] is True

    inclusion = data["heldout_432_inclusion"]
    assert (\n        inclusion["allowed_only_if_confirmation_gate_passes_before_432_content_generation"] is True\n    )
    assert inclusion["cannot_add_after_any_432_task_content_is_generated"] is True
    assert inclusion["cannot_add_after_any_432_score_is_opened"] is True


def test_corrective_reretrieval_uses_observable_state_only() -> None:
    data = _load(CORRECTIVE)

    assert data["issue"] == 431
    assert data["run_authorization"]["b2_terminal_required"] is True
    assert data["run_authorization"]["current_authorized_to_run"] is False

    state = data["state_contract"]
    assert state["free_text_tool_output_injected_into_retrieval"] is False
    assert state["execution_authority_unchanged"] is True
    assert "future_required_route_id" in state["forbidden_fields"]
    assert "gold_next_route_id" in state["forbidden_fields"]
    assert "oracle_task_graph" in state["forbidden_fields"]
    assert "SchemaRouter rank score" in state["forbidden_fields"]
    assert "SchemaRouter rank position" in state["forbidden_fields"]

    assert "observation_semantic_ids" in state["allowed_fields"]
    assert "observation_units" in state["allowed_fields"]
    assert "stable_observed_identifiers" in state["allowed_fields"]


def test_corrective_reretrieval_surface_and_budget_are_frozen() -> None:
    data = _load(CORRECTIVE)
    surface = data["surface"]

    assert surface["unique_semantic_tasks"] == 180
    assert len(surface["task_strata"]) == 5
    assert len(surface["languages"]) == 6
    assert surface["tasks_per_stratum_language_cell"] == 6
    assert 5 * 6 * 6 == 180

    assert data["conditions"] == [
        "SR-5-STATIC",
        "SR-PROGRESSIVE-STATIC",
        "SR-5-STATE-AWARE",
        "FULL",
        "ORACLE",
    ]
    assert data["candidate_budget"]["state_aware_per_retrieval_max"] == 5
    assert data["candidate_budget"]["maximum_retrieval_refreshes_per_episode"] == 5

    governance = data["governance"]
    assert governance["same_downstream_agent_as_terminal_b2_required"] is True
    assert governance["no_rule_tuning_from_b2_failures"] is True
    assert governance["no_hidden_ground_truth_in_state"] is True
    assert governance["no_execution_authority_from_retrieval"] is True
