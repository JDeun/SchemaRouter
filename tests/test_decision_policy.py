from schemarouter import DecisionPolicy


def test_decision_policy_is_off_by_default() -> None:
    policy = DecisionPolicy()
    assert policy.enabled is False
    assert policy.candidate_selection_enabled is False
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
