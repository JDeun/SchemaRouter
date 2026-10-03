from __future__ import annotations

from typing import Literal

from pydantic import Field

from .models import StrictModel

ExecutionLocality = Literal["local", "remote"]
OperationalConstraintCode = Literal[
    "eligible",
    "latency_constraint",
    "cost_constraint",
    "locality_constraint",
    "residency_constraint",
    "privacy_constraint",
    "network_constraint",
    "metadata_unknown",
]


class CapabilityOperationalMetadata(StrictModel):
    estimated_latency_ms: float | None = Field(default=None, ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    locality: ExecutionLocality | None = None
    region: str | None = None
    privacy_class: str | None = None
    network_required: bool | None = None


class HostCapabilityConstraints(StrictModel):
    max_latency_ms: float | None = Field(default=None, ge=0)
    max_cost: float | None = Field(default=None, ge=0)
    allowed_localities: set[ExecutionLocality] | None = None
    allowed_regions: set[str] | None = None
    allowed_privacy_classes: set[str] | None = None
    network_allowed: bool | None = None
    prefer_local: bool = False
    prefer_lower_latency: bool = False
    prefer_lower_cost: bool = False


class OperationalConstraintReason(StrictModel):
    code: OperationalConstraintCode
    detail: str = ""


class OperationalConstraintResult(StrictModel):
    eligible: bool
    preference_score: float = 0.0
    reasons: list[OperationalConstraintReason] = Field(default_factory=list)


def evaluate_operational_constraints(
    metadata: CapabilityOperationalMetadata,
    constraints: HostCapabilityConstraints,
) -> OperationalConstraintResult:
    """Apply host-declared hard filters and deterministic soft preferences."""

    reasons: list[OperationalConstraintReason] = []

    def unknown(detail: str) -> None:
        reasons.append(OperationalConstraintReason(code="metadata_unknown", detail=detail))

    if constraints.max_latency_ms is not None:
        if metadata.estimated_latency_ms is None:
            unknown("latency metadata is required by the host constraint")
        elif metadata.estimated_latency_ms > constraints.max_latency_ms:
            reasons.append(OperationalConstraintReason(code="latency_constraint"))

    if constraints.max_cost is not None:
        if metadata.estimated_cost is None:
            unknown("cost metadata is required by the host constraint")
        elif metadata.estimated_cost > constraints.max_cost:
            reasons.append(OperationalConstraintReason(code="cost_constraint"))

    if constraints.allowed_localities is not None:
        if metadata.locality is None:
            unknown("locality metadata is required by the host constraint")
        elif metadata.locality not in constraints.allowed_localities:
            reasons.append(OperationalConstraintReason(code="locality_constraint"))

    if constraints.allowed_regions is not None:
        if metadata.region is None:
            unknown("region metadata is required by the host constraint")
        elif metadata.region not in constraints.allowed_regions:
            reasons.append(OperationalConstraintReason(code="residency_constraint"))

    if constraints.allowed_privacy_classes is not None:
        if metadata.privacy_class is None:
            unknown("privacy metadata is required by the host constraint")
        elif metadata.privacy_class not in constraints.allowed_privacy_classes:
            reasons.append(OperationalConstraintReason(code="privacy_constraint"))

    if constraints.network_allowed is not None:
        if metadata.network_required is None:
            unknown("network metadata is required by the host constraint")
        elif metadata.network_required and not constraints.network_allowed:
            reasons.append(OperationalConstraintReason(code="network_constraint"))

    eligible = not reasons
    score = 0.0
    if eligible:
        if constraints.prefer_local and metadata.locality == "local":
            score += 1.0
        if constraints.prefer_lower_latency and metadata.estimated_latency_ms is not None:
            score += 1.0 / (1.0 + metadata.estimated_latency_ms)
        if constraints.prefer_lower_cost and metadata.estimated_cost is not None:
            score += 1.0 / (1.0 + metadata.estimated_cost)
        reasons.append(OperationalConstraintReason(code="eligible"))

    return OperationalConstraintResult(
        eligible=eligible,
        preference_score=score,
        reasons=reasons,
    )
