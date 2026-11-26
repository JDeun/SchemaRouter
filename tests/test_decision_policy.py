import inspect

import pytest

import schemarouter
from schemarouter import InMemoryRegistry, SchemaPlanner
from scripts.research_legacy_decision_policy import DecisionPolicy


def test_decision_policy_is_off_by_default() -> None:
    policy = DecisionPolicy()
    assert policy.enabled is False
    assert policy.candidate_selection_enabled is False
    assert policy.candidate_recall_on_empty_enabled is False
    assert policy.recall_on_empty is False
    assert policy.candidate_abstention == "inherit"
    assert policy.candidate_abstention_mode == "deterministic"
    assert policy.fallback == "deterministic"


def test_each_decision_surface_is_independently_switchable() -> None:
    policy = DecisionPolicy(enabled=True, endpoint_selection=True)
    assert policy.candidate_selection_enabled is True
    assert policy.field_selection_enabled is False
    assert policy.evidence_sufficiency_enabled is False
    assert policy.reserved_surfaces_enabled is False
    assert policy.tool_selection is False
    assert policy.field_selection is False
    assert policy.evidence_sufficiency is False


def test_field_selection_has_independent_bounded_switch() -> None:
    policy = DecisionPolicy(enabled=True, field_selection=True)
    assert policy.candidate_selection_enabled is False
    assert policy.field_selection_enabled is True
    assert policy.evidence_sufficiency_enabled is False
    assert policy.reserved_surfaces_enabled is False


def test_evidence_sufficiency_has_independent_bounded_switch() -> None:
    policy = DecisionPolicy(enabled=True, evidence_sufficiency=True)
    assert policy.evidence_sufficiency_enabled is True
    assert policy.reserved_surfaces_enabled is False


def test_master_switch_overrides_feature_switches() -> None:
    policy = DecisionPolicy(
        enabled=False,
        endpoint_selection=True,
        tool_selection=True,
        field_selection=True,
        evidence_sufficiency=True,
    )
    assert policy.candidate_selection_enabled is False
    assert policy.field_selection_enabled is False
    assert policy.evidence_sufficiency_enabled is False
    assert policy.reserved_surfaces_enabled is False



def test_recall_on_empty_requires_enabled_candidate_selection() -> None:
    disabled = DecisionPolicy(recall_on_empty=True)
    master_off = DecisionPolicy(
        enabled=False,
        endpoint_selection=True,
        recall_on_empty=True,
    )
    enabled = DecisionPolicy(
        enabled=True,
        endpoint_selection=True,
        recall_on_empty=True,
    )

    assert disabled.candidate_recall_on_empty_enabled is False
    assert master_off.candidate_recall_on_empty_enabled is False
    assert enabled.candidate_recall_on_empty_enabled is True



def test_recall_on_empty_is_visible_in_policy_serialization() -> None:
    policy = DecisionPolicy(
        enabled=True,
        endpoint_selection=True,
        recall_on_empty=True,
    )

    document = policy.model_dump(mode="json")

    assert document["recall_on_empty"] is True
    assert policy.candidate_recall_on_empty_enabled is True



def test_candidate_abstention_is_independent_from_provider_error_fallback() -> None:
    policy = DecisionPolicy(
        enabled=True,
        endpoint_selection=True,
        candidate_abstention="no_route",
        fallback="deterministic",
    )

    assert policy.candidate_abstention == "no_route"
    assert policy.fallback == "deterministic"



def test_inherited_candidate_abstention_preserves_error_fallback_semantics() -> None:
    policy = DecisionPolicy(
        enabled=True,
        endpoint_selection=True,
        fallback="error",
    )

    assert policy.candidate_abstention == "inherit"
    assert policy.candidate_abstention_mode == "error"


def test_installed_planner_no_longer_accepts_decision_policy_or_backend() -> None:
    assert not hasattr(schemarouter, "DecisionPolicy")
    assert not hasattr(schemarouter, "DecisionFallback")
    parameters = inspect.signature(SchemaPlanner).parameters
    assert "decision_policy" not in parameters
    assert "decision_backend" not in parameters
    planner = SchemaPlanner(InMemoryRegistry())
    assert not hasattr(planner, "decision_policy")
    assert not hasattr(planner, "decision_backend")
    with pytest.raises(TypeError, match="decision_policy"):
        SchemaPlanner(InMemoryRegistry(), decision_policy=DecisionPolicy(enabled=True))
