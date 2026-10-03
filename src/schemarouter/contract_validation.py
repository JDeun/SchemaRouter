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

ValidationStatus = Literal["valid", "missing", "incompatible", "convertible", "unknown"]


class ContractObservation(StrictModel):
    contract: CapabilityFieldContract


class ContractValidationItem(StrictModel):
    semantic_id: str
    status: ValidationStatus
    detail: str


class ContractValidationResult(StrictModel):
    status: ValidationStatus
    items: list[ContractValidationItem] = Field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.status in {"valid", "convertible"}


def validate_contract_fields(
    required: list[CapabilityFieldContract],
    observed: list[ContractObservation],
    *,
    context: CompatibilityContext | None = None,
) -> ContractValidationResult:
    """Validate typed observations against declared fields without repairing values."""

    items: list[ContractValidationItem] = []
    for requirement in required:
        candidates = [
            compare_capability_fields(requirement, item.contract, context=context)
            for item in observed
            if (
                item.contract.semantic_id == requirement.semantic_id
                or (
                    context is not None
                    and context.semantics_equivalent(
                        requirement.semantic_id,
                        item.contract.semantic_id,
                    )
                )
            )
        ]
        satisfying = [item for item in candidates if item.satisfies]
        if satisfying:
            best = min(
                satisfying,
                key=lambda item: {"exact": 0, "compatible": 1, "convertible": 2}[item.status],
            )
            status: ValidationStatus = (
                "convertible" if best.status == "convertible" else "valid"
            )
            items.append(ContractValidationItem(
                semantic_id=requirement.semantic_id,
                status=status,
                detail="declared typed observation satisfies the contract",
            ))
            continue
        if any(item.status == "unknown" for item in candidates):
            items.append(ContractValidationItem(
                semantic_id=requirement.semantic_id,
                status="unknown",
                detail="available metadata cannot prove contract satisfaction",
            ))
        elif candidates:
            items.append(ContractValidationItem(
                semantic_id=requirement.semantic_id,
                status="incompatible",
                detail="typed observation is incompatible with the declared contract",
            ))
        else:
            items.append(ContractValidationItem(
                semantic_id=requirement.semantic_id,
                status="missing",
                detail="required semantic field was not observed",
            ))

    statuses = {item.status for item in items}
    if "incompatible" in statuses:
        status = "incompatible"
    elif "missing" in statuses:
        status = "missing"
    elif "unknown" in statuses:
        status = "unknown"
    elif "convertible" in statuses:
        status = "convertible"
    else:
        status = "valid"
    return ContractValidationResult(status=status, items=items)


def validate_capability_input(
    capability: CapabilityContract,
    observations: list[ContractObservation],
    *,
    context: CompatibilityContext | None = None,
) -> ContractValidationResult:
    return validate_contract_fields(capability.requires, observations, context=context)


def validate_capability_output(
    capability: CapabilityContract,
    observations: list[ContractObservation],
    *,
    context: CompatibilityContext | None = None,
) -> ContractValidationResult:
    return validate_contract_fields(capability.produces, observations, context=context)
