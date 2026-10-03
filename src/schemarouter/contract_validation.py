from __future__ import annotations

from typing import Literal

from pydantic import Field

from .capability_contracts import (
    CapabilityContract,
    CapabilityFieldContract,
    CompatibilityContext,
    compare_capability_fields,
)
from .models import StrictModel

ContractValidationStatus = Literal[
    "valid",
    "missing",
    "incompatible",
    "coercible",
    "unverifiable",
]


class CapabilityObservation(StrictModel):
    """Typed field observation supplied by a host runtime."""

    contract: CapabilityFieldContract


class ContractFieldValidation(StrictModel):
    semantic_id: str
    status: ContractValidationStatus
    detail: str


class CapabilityContractValidation(StrictModel):
    """Machine-readable contract validation without execution authority."""

    status: ContractValidationStatus
    fields: list[ContractFieldValidation] = Field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.status in {"valid", "coercible"}


def validate_capability_inputs(
    capability: CapabilityContract,
    observations: list[CapabilityObservation],
    *,
    context: CompatibilityContext | None = None,
) -> CapabilityContractValidation:
    """Validate host-owned inputs against a capability's declared requirements."""

    return _validate_fields(capability.requires, observations, context=context)


def validate_capability_outputs(
    capability: CapabilityContract,
    observations: list[CapabilityObservation],
    *,
    context: CompatibilityContext | None = None,
) -> CapabilityContractValidation:
    """Validate host-observed outputs against a capability's declared productions."""

    return _validate_fields(capability.produces, observations, context=context)


def _validate_fields(
    expected_fields: list[CapabilityFieldContract],
    observations: list[CapabilityObservation],
    *,
    context: CompatibilityContext | None,
) -> CapabilityContractValidation:
    if not expected_fields:
        return CapabilityContractValidation(status="valid")

    fields: list[ContractFieldValidation] = []
    for expected in expected_fields:
        candidates = [
            compare_capability_fields(expected, observed.contract, context=context)
            for observed in observations
            if (
                observed.contract.semantic_id == expected.semantic_id
                or (
                    context is not None
                    and context.semantics_equivalent(
                        expected.semantic_id,
                        observed.contract.semantic_id,
                    )
                )
            )
        ]
        if not candidates:
            fields.append(ContractFieldValidation(
                semantic_id=expected.semantic_id,
                status="missing",
                detail="required typed field was not observed",
            ))
            continue

        compatible = [candidate for candidate in candidates if candidate.satisfies]
        if compatible:
            best = min(
                compatible,
                key=lambda candidate: {
                    "exact": 0,
                    "compatible": 1,
                    "convertible": 2,
                }[candidate.status],
            )
            status: ContractValidationStatus = (
                "coercible" if best.status == "convertible" else "valid"
            )
            fields.append(ContractFieldValidation(
                semantic_id=expected.semantic_id,
                status=status,
                detail=(
                    "declared safe conversion is required"
                    if status == "coercible"
                    else "observed field satisfies the declared contract"
                ),
            ))
            continue

        if any(candidate.status == "unknown" for candidate in candidates):
            fields.append(ContractFieldValidation(
                semantic_id=expected.semantic_id,
                status="unverifiable",
                detail="declared metadata is insufficient to prove compatibility",
            ))
            continue

        fields.append(ContractFieldValidation(
            semantic_id=expected.semantic_id,
            status="incompatible",
            detail="observed field conflicts with the declared contract",
        ))

    return CapabilityContractValidation(
        status=_overall_status(fields),
        fields=fields,
    )


def _overall_status(fields: list[ContractFieldValidation]) -> ContractValidationStatus:
    statuses = {field.status for field in fields}
    if "incompatible" in statuses:
        return "incompatible"
    if "missing" in statuses:
        return "missing"
    if "unverifiable" in statuses:
        return "unverifiable"
    if "coercible" in statuses:
        return "coercible"
    return "valid"
