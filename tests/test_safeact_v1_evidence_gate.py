from __future__ import annotations

import pytest

from examples.external_validation.safeact_v1.evidence_gate import (
    ActionContract,
    EvidenceGate,
    Observation,
)


def _gate() -> EvidenceGate:
    return EvidenceGate(ActionContract(
        action="refund_issue",
        required_observations=(("charge_read", "C2", frozenset({"amount", "owner"})),),
    ))


def test_missing_observation_blocks_without_invoking_executor() -> None:
    gate = _gate()
    calls = []
    try:
        gate.dispatch("refund_issue", {"charge_id": "C2"}, lambda *args: calls.append(args))
    except PermissionError:
        pass
    else:
        raise AssertionError("missing evidence was not blocked")
    assert not calls


def test_wrong_entity_cannot_satisfy_contract() -> None:
    gate = _gate()
    gate.observe(Observation("charge_read", "C1", frozenset({"amount", "owner"})))
    assert not gate.check("refund_issue").allowed


def test_partial_fields_cannot_satisfy_contract() -> None:
    gate = _gate()
    gate.observe(Observation("charge_read", "C2", frozenset({"amount"})))
    assert not gate.check("refund_issue").allowed


def test_successful_observation_enables_dispatch() -> None:
    gate = _gate()
    gate.observe(Observation("charge_read", "C2", frozenset({"amount", "owner"})))
    assert gate.dispatch("refund_issue", {"charge_id": "C2"}, lambda name, args: (name, args)) == (
        "refund_issue", {"charge_id": "C2"}
    )


def test_failed_observation_does_not_count() -> None:
    gate = _gate()
    gate.observe(Observation("charge_read", "C2", frozenset({"amount", "owner"}), successful=False))
    assert not gate.check("refund_issue").allowed


def test_wrong_action_blocks() -> None:
    gate = _gate()
    gate.observe(Observation("charge_read", "C2", frozenset({"amount", "owner"})))
    assert gate.check("delete_charge").missing == ("action_mismatch",)

def test_evidence_for_one_record_cannot_authorize_another_target() -> None:
    gate = EvidenceGate(
        ActionContract(
            action="refund_issue",
            required_observations=(("charge_read", "C2", frozenset({"owner"})),),
            argument_bindings=(("charge_id", "C2"),),
        )
    )
    gate.observe(Observation("charge_read", "C2", frozenset({"owner"})))
    calls: list[object] = []
    with pytest.raises(PermissionError, match="argument_binding_mismatch"):
        gate.dispatch("refund_issue", {"charge_id": "C1"}, lambda *args: calls.append(args))
    assert calls == []
    assert not gate.check("refund_issue").allowed
    assert not gate.check("refund_issue", {}).allowed
    assert gate.check("refund_issue", {"charge_id": "C2"}).allowed


def test_action_binding_must_name_a_declared_observation() -> None:
    with pytest.raises(ValueError, match="argument binding"):
        EvidenceGate(
            ActionContract(
                action="refund_issue",
                required_observations=(("charge_read", "C2", frozenset({"owner"})),),
                argument_bindings=(("charge_id", "C1"),),
            )
        )


def test_dynamic_action_bound_record_only_accepts_observed_target() -> None:
    gate = EvidenceGate(
        ActionContract(
            action="refund_issue",
            required_observations=(
                ("charge_read", "$action.charge_id", frozenset({"owner"})),
            ),
        )
    )
    gate.observe(Observation("charge_read", "C2", frozenset({"owner"})))
    assert gate.check("refund_issue", {"charge_id": "C2"}).allowed
    assert not gate.check("refund_issue", {"charge_id": "C1"}).allowed
    assert not gate.check("refund_issue", {}).allowed
    assert not gate.check("refund_issue", {"charge_id": 42}).allowed


@pytest.mark.parametrize("reference", ["$action.", "$action.a-b", "$action.a.b"])
def test_invalid_dynamic_argument_name_fails_closed(reference: str) -> None:
    with pytest.raises(ValueError, match="malformed action-bound"):
        EvidenceGate(
            ActionContract(
                action="refund_issue",
                required_observations=(
                    ("charge_read", reference, frozenset({"owner"})),
                ),
            )
        )


def test_reviewed_value_comparisons_deny_invalid_refund_amount() -> None:
    from examples.external_validation.safeact_v1.evidence_gate import ValueCondition

    gate = EvidenceGate(ActionContract(
        action="refund_issue",
        required_observations=((
            "charge_read", "$action.charge_id",
            frozenset({"amount", "payment_method"}),
        ),),
        value_conditions=(
            ValueCondition(
                "charge_read", "$action.charge_id", "amount",
                "lte", "action_argument", "refund_amount",
            ),
            ValueCondition(
                "charge_read", "$action.charge_id", "payment_method",
                "eq", "action_argument", "payment_method",
            ),
        ),
    ))
    gate.observe(Observation(
        "charge_read", "C2", frozenset({"amount", "payment_method"}),
        values=(("amount", 50), ("payment_method", "card-A")),
    ))
    assert gate.check("refund_issue", {
        "charge_id": "C2", "refund_amount": 30, "payment_method": "card-A",
    }).allowed
    assert not gate.check("refund_issue", {
        "charge_id": "C2", "refund_amount": 70, "payment_method": "card-A",
    }).allowed
    assert not gate.check("refund_issue", {
        "charge_id": "C2", "refund_amount": 30, "payment_method": "card-B",
    }).allowed


def test_missing_or_contradictory_value_cannot_satisfy_predicate() -> None:
    from examples.external_validation.safeact_v1.evidence_gate import ValueCondition

    gate = EvidenceGate(ActionContract(
        "refund_issue", (("charge_read", "C2", frozenset({"amount"})),),
        value_conditions=(ValueCondition(
            "charge_read", "C2", "amount", "lte",
            "action_argument", "refund_amount",
        ),),
    ))
    args = {"refund_amount": 20}
    gate.observe(Observation("charge_read", "C2", frozenset({"amount"})))
    assert not gate.check("refund_issue", args).allowed
    gate.observe(Observation(
        "charge_read", "C2", frozenset({"amount"}), values=(("amount", 30),),
    ))
    # A different trusted result for the same field is ambiguous, not "OR".
    gate.observe(Observation(
        "charge_read", "C2", frozenset({"amount"}), values=(("amount", 10),),
    ))
    assert not gate.check("refund_issue", args).allowed


@pytest.mark.parametrize("actual", [True, False, float("nan"), "NaN"])
def test_invalid_numeric_types_and_nonfinite_are_not_comparable(actual: object) -> None:
    from examples.external_validation.safeact_v1.evidence_gate import ValueCondition

    gate = EvidenceGate(ActionContract(
        "refund_issue", (("charge_read", "C2", frozenset({"amount"})),),
        value_conditions=(ValueCondition(
            "charge_read", "C2", "amount", "lte",
            "action_argument", "refund_amount",
        ),),
    ))
    gate.observe(Observation(
        "charge_read", "C2", frozenset({"amount"}), values=(("amount", actual),),
    ))
    assert not gate.check("refund_issue", {"refund_amount": 1}).allowed


def test_unanchored_policy_value_predicate_fails_closed() -> None:
    from examples.external_validation.safeact_v1.evidence_gate import ValueCondition

    with pytest.raises(ValueError, match="declared observation"):
        EvidenceGate(ActionContract(
            "refund_issue", (("charge_read", "C2", frozenset({"owner"})),),
            value_conditions=(ValueCondition(
                "charge_read", "C2", "amount", "lte",
                "action_argument", "refund_amount",
            ),),
        ))



@pytest.mark.parametrize("value", ["30", "3e1", True, [30], {"number": 30}])
def test_numeric_policy_does_not_coerce_untrusted_action_types(value: object) -> None:
    """A text or structured model argument must not become a number by parsing."""
    from examples.external_validation.safeact_v1.evidence_gate import ValueCondition

    gate = EvidenceGate(ActionContract(
        action="refund_issue",
        required_observations=(("charge_read", "C2", frozenset({"amount"})),),
        value_conditions=(ValueCondition(
            "charge_read", "C2", "amount", "lte",
            "action_argument", "refund_amount",
        ),),
    ))
    gate.observe(Observation(
        "charge_read", "C2", frozenset({"amount"}), values=(("amount", 50),),
    ))
    assert not gate.check("refund_issue", {"refund_amount": value}).allowed
    assert gate.check("refund_issue", {"refund_amount": 30}).allowed
    assert gate.check("refund_issue", {"refund_amount": 30.0}).allowed


@pytest.mark.parametrize("candidate", [
    float("inf"), float("-inf"), float("nan"), [20], {"amount": 20},
])
def test_equality_policy_never_accepts_nonfinite_or_structured_values(
    candidate: object,
) -> None:
    from examples.external_validation.safeact_v1.evidence_gate import ValueCondition

    gate = EvidenceGate(ActionContract(
        action="refund_issue",
        required_observations=(("charge_read", "C2", frozenset({"amount"})),),
        value_conditions=(ValueCondition(
            "charge_read", "C2", "amount", "eq",
            "action_argument", "refund_amount",
        ),),
    ))
    gate.observe(Observation(
        "charge_read", "C2", frozenset({"amount"}),
        values=(("amount", candidate),),
    ))
    assert not gate.check("refund_issue", {"refund_amount": candidate}).allowed
    assert gate.check("refund_issue", {"refund_amount": 20}).allowed is False


def test_typed_boolean_equality_is_not_numeric_one() -> None:
    from examples.external_validation.safeact_v1.evidence_gate import ValueCondition

    gate = EvidenceGate(ActionContract(
        action="refund_issue",
        required_observations=(("charge_read", "C2", frozenset({"approved"})),),
        value_conditions=(ValueCondition(
            "charge_read", "C2", "approved", "eq", "literal", True,
        ),),
    ))
    gate.observe(Observation(
        "charge_read", "C2", frozenset({"approved"}),
        values=(("approved", 1),),
    ))
    assert not gate.check("refund_issue").allowed



@pytest.mark.parametrize("literal", ["30", True, False])
def test_nonnumeric_order_policy_literal_rejected_during_authoring(
    literal: object,
) -> None:
    from examples.external_validation.safeact_v1.evidence_gate import ValueCondition

    with pytest.raises(ValueError, match="malformed independent value condition"):
        EvidenceGate(ActionContract(
            action="refund_issue",
            required_observations=(
                ("charge_read", "C2", frozenset({"amount"})),
            ),
            value_conditions=(ValueCondition(
                "charge_read", "C2", "amount",
                "lte", "literal", literal,
            ),),
        ))
