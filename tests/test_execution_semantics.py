from schemarouter.capability_contracts import (
    CapabilityContract,
    CapabilityEffects,
    CapabilityPrecondition,
)


def test_execution_semantics_round_trip_without_execution_behavior() -> None:
    contract = CapabilityContract(
        capability_id="materials.update",
        effects=CapabilityEffects(
            kind="write",
            idempotent="false",
            compensatable="unknown",
        ),
        preconditions=[
            CapabilityPrecondition(
                semantic_id="auth.scope",
                operator="contains",
                value="materials.write",
            )
        ],
    )

    restored = CapabilityContract.model_validate(contract.model_dump())

    assert restored == contract
    assert restored.effects is not None
    assert restored.effects.kind == "write"


def test_execution_semantics_are_optional_for_backward_compatibility() -> None:
    contract = CapabilityContract(capability_id="arxiv.search")

    assert contract.effects is None
    assert contract.preconditions == []
