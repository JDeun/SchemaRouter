from __future__ import annotations

from typing import Literal

from pydantic import Field

from .models import StrictModel

CapabilityEligibilityCode = Literal[
    "eligible",
    "missing_required_state",
    "semantic_mismatch",
    "type_or_unit_incompatible",
    "method_unhealthy",
    "contract_drifted",
    "policy_denied",
    "privacy_constraint",
    "locality_constraint",
    "cost_constraint",
    "unsupported_or_unknown",
]


class CapabilityEligibilityReason(StrictModel):
    code: CapabilityEligibilityCode
    detail: str = ""
    children: list[CapabilityEligibilityReason] = Field(default_factory=list)


class CapabilityEligibilityExplanation(StrictModel):
    capability_id: str
    eligible: bool
    reasons: list[CapabilityEligibilityReason] = Field(default_factory=list)


def explain_capability_eligibility(
    capability_id: str,
    *,
    visible: bool,
    reasons: list[CapabilityEligibilityReason] | None = None,
) -> CapabilityEligibilityExplanation | None:
    """Build a structured explanation only for a host-visible capability.

    Returning None for invisible capabilities is the non-disclosure boundary:
    callers cannot distinguish policy denial from non-existence through this API.
    """

    if not visible:
        return None

    items = list(reasons or [])
    if not items:
        items = [CapabilityEligibilityReason(code="eligible")]
    eligible = all(item.code == "eligible" for item in items)
    return CapabilityEligibilityExplanation(
        capability_id=capability_id,
        eligible=eligible,
        reasons=items,
    )
