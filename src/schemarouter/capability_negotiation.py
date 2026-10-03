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

NegotiationStatus = Literal[
    "exact",
    "compatible",
    "convertible",
    "incompatible",
    "unknown",
    "policy_denied",
    "unavailable",
]


class CapabilityNegotiationRequest(StrictModel):
    required_outputs: list[CapabilityFieldContract] = Field(default_factory=list)
    allowed_capability_ids: set[str] | None = None


class CapabilityNegotiationCandidate(StrictModel):
    capability_id: str
    status: NegotiationStatus
    reasons: tuple[str, ...] = ()


class CapabilityNegotiationResult(StrictModel):
    candidates: list[CapabilityNegotiationCandidate] = Field(default_factory=list)


def _match_required_output(
    required: CapabilityFieldContract,
    offered: list[CapabilityFieldContract],
    context: CompatibilityContext | None,
) -> tuple[NegotiationStatus, str]:
    matches = [
        field
        for field in offered
        if field.semantic_id == required.semantic_id
        or (
            context is not None
            and context.semantics_equivalent(field.semantic_id, required.semantic_id)
        )
    ]
    if not matches:
        return "incompatible", f"missing semantic output {required.semantic_id}"

    outcomes = [compare_capability_fields(field, required, context=context) for field in matches]
    order = {"exact": 0, "compatible": 1, "convertible": 2, "unknown": 3, "incompatible": 4}
    best = min(outcomes, key=lambda item: order[item.status])
    return best.status, "; ".join(reason.detail for reason in best.reasons)


def negotiate_capabilities(
    request: CapabilityNegotiationRequest,
    capabilities: list[CapabilityContract],
    *,
    authorized_capability_ids: set[str] | None = None,
    unavailable_capability_ids: set[str] | None = None,
    context: CompatibilityContext | None = None,
) -> CapabilityNegotiationResult:
    """Match host requirements to declared contracts without widening authority."""

    unavailable = unavailable_capability_ids or set()
    results: list[CapabilityNegotiationCandidate] = []
    for capability in sorted(capabilities, key=lambda item: item.capability_id):
        capability_id = capability.capability_id
        if (
            request.allowed_capability_ids is not None
            and capability_id not in request.allowed_capability_ids
        ):
            results.append(CapabilityNegotiationCandidate(
                capability_id=capability_id,
                status="policy_denied",
                reasons=("outside request allow-set",),
            ))
            continue
        if authorized_capability_ids is not None and capability_id not in authorized_capability_ids:
            results.append(CapabilityNegotiationCandidate(
                capability_id=capability_id,
                status="policy_denied",
                reasons=("outside host authorization",),
            ))
            continue
        if capability_id in unavailable:
            results.append(CapabilityNegotiationCandidate(
                capability_id=capability_id,
                status="unavailable",
                reasons=("capability unavailable",),
            ))
            continue

        matches = [
            _match_required_output(required, capability.produces, context)
            for required in request.required_outputs
        ]
        if not matches:
            status: NegotiationStatus = "exact"
            reasons: tuple[str, ...] = ()
        else:
            rank = {"exact": 0, "compatible": 1, "convertible": 2, "unknown": 3, "incompatible": 4}
            status = max((item[0] for item in matches), key=lambda item: rank[item])
            reasons = tuple(item[1] for item in matches if item[1])
        results.append(CapabilityNegotiationCandidate(
            capability_id=capability_id,
            status=status,
            reasons=reasons,
        ))
    return CapabilityNegotiationResult(candidates=results)
