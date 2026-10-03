from __future__ import annotations

from typing import Literal

from pydantic import Field

from .contract_validation import CapabilityContractValidation
from .execution_state import StateEligibility
from .models import StrictModel

FallbackEligibilityReason = Literal[
    "eligible",
    "policy_denied",
    "method_unhealthy",
    "contract_missing",
    "contract_incompatible",
    "contract_unverifiable",
    "contract_drifted",
    "state_ineligible",
    "not_retrieved",
]


class CapabilityFallbackEligibility(StrictModel):
    eligible: bool
    reasons: list[FallbackEligibilityReason] = Field(default_factory=list)


def evaluate_fallback_eligibility(
    *,
    authorized: bool,
    healthy: bool,
    retrieved: bool = True,
    contract_validation: CapabilityContractValidation | None = None,
    contract_drifted: bool = False,
    state_eligibility: StateEligibility | None = None,
) -> CapabilityFallbackEligibility:
    """Compose host policy, health, contract, state, and retrieval eligibility.

    The result only describes whether an already host-visible candidate can remain
    in a fallback set. It never executes a route or widens host authorization.
    """

    reasons: list[FallbackEligibilityReason] = []
    if not authorized:
        reasons.append("policy_denied")
    if not healthy:
        reasons.append("method_unhealthy")
    if contract_drifted:
        reasons.append("contract_drifted")
    if contract_validation is not None:
        if contract_validation.status == "missing":
            reasons.append("contract_missing")
        elif contract_validation.status == "incompatible":
            reasons.append("contract_incompatible")
        elif contract_validation.status == "unverifiable":
            reasons.append("contract_unverifiable")
    if state_eligibility is not None and not state_eligibility.eligible:
        reasons.append("state_ineligible")
    if not retrieved:
        reasons.append("not_retrieved")

    if reasons:
        return CapabilityFallbackEligibility(eligible=False, reasons=reasons)
    return CapabilityFallbackEligibility(eligible=True, reasons=["eligible"])
