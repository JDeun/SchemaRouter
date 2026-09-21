from schemarouter import DecisionPolicy


def test_decision_policy_is_off_by_default() -> None:
    policy = DecisionPolicy()
    assert policy.enabled is False
    assert policy.candidate_selection_enabled is False
    assert policy.fallback == "deterministic"


def test_each_decision_surface_is_independently_switchable() -> None:
    policy = DecisionPolicy(enabled=True, endpoint_selection=True)
    assert policy.candidate_selection_enabled is True
    assert policy.tool_selection is False
    assert policy.field_selection is False
    assert policy.evidence_sufficiency is False


def test_master_switch_overrides_feature_switches() -> None:
    policy = DecisionPolicy(enabled=False, endpoint_selection=True, tool_selection=True)
    assert policy.candidate_selection_enabled is False
