from schemarouter import DecisionPolicy


def test_decision_policy_is_off_by_default() -> None:
    policy = DecisionPolicy()
    assert policy.enabled is False
    assert policy.candidate_selection_enabled is False
    assert policy.candidate_recall_on_empty_enabled is False
    assert policy.recall_on_empty is False
    assert policy.candidate_abstention == "deterministic"
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
