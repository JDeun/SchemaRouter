from schemarouter.capability_contracts import CapabilityFieldContract, CapabilityPrecondition
from schemarouter.execution_state import (
    ObservedStateField,
    TypedExecutionState,
    evaluate_preconditions,
)


def test_exists_precondition_uses_observable_typed_state() -> None:
    state = TypedExecutionState(
        observed_fields=[
            ObservedStateField(
                contract=CapabilityFieldContract(semantic_id="resource.material_id"),
                stable_identifier="mp-149",
            )
        ]
    )

    result = evaluate_preconditions(
        [CapabilityPrecondition(semantic_id="resource.material_id")],
        state,
    )

    assert result.eligible


def test_duplicate_observations_make_preconditions_order_independent() -> None:
    condition = CapabilityPrecondition(
        semantic_id="sample_id",
        operator="equals",
        value="target",
    )
    observations = [
        ObservedStateField(
            contract=CapabilityFieldContract(semantic_id="sample_id"),
            stable_identifier="other",
        ),
        ObservedStateField(
            contract=CapabilityFieldContract(
                semantic_id="sample_id",
                qualifiers={"source": "preferred"},
            ),
            stable_identifier="target",
        ),
    ]

    forward = evaluate_preconditions(
        [condition],
        TypedExecutionState(observed_fields=observations),
    )
    reverse = evaluate_preconditions(
        [condition],
        TypedExecutionState(
            observed_fields=list(reversed(observations)),
        ),
    )

    assert forward.status == "eligible"
    assert reverse.status == "eligible"


def test_duplicate_observations_fail_deterministically_when_none_match() -> None:
    condition = CapabilityPrecondition(
        semantic_id="sample_id",
        operator="contains",
        value="target",
    )
    observations = [
        ObservedStateField(
            contract=CapabilityFieldContract(semantic_id="sample_id"),
            stable_identifier=None,
        ),
        ObservedStateField(
            contract=CapabilityFieldContract(semantic_id="sample_id"),
            stable_identifier="other",
        ),
    ]

    forward = evaluate_preconditions(
        [condition],
        TypedExecutionState(observed_fields=observations),
    )
    reverse = evaluate_preconditions(
        [condition],
        TypedExecutionState(
            observed_fields=list(reversed(observations)),
        ),
    )

    assert forward == reverse
    assert forward.status == "precondition_failed"


def test_value_precondition_fails_closed_without_observable_value() -> None:
    state = TypedExecutionState(
        observed_fields=[
            ObservedStateField(
                contract=CapabilityFieldContract(semantic_id="auth.scope"),
            )
        ]
    )

    result = evaluate_preconditions(
        [
            CapabilityPrecondition(
                semantic_id="auth.scope",
                operator="contains",
                value="materials.read",
            )
        ],
        state,
    )

    assert result.status == "precondition_failed"


def test_value_precondition_can_use_explicit_stable_identifier() -> None:
    state = TypedExecutionState(
        observed_fields=[
            ObservedStateField(
                contract=CapabilityFieldContract(semantic_id="auth.scope"),
                stable_identifier="materials.read materials.summary",
            )
        ]
    )

    result = evaluate_preconditions(
        [
            CapabilityPrecondition(
                semantic_id="auth.scope",
                operator="contains",
                value="materials.read",
            )
        ],
        state,
    )

    assert result.eligible
