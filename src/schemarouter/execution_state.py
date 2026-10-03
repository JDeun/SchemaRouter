from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .capability_contracts import CapabilityFieldContract, compare_capability_fields
from .models import StrictModel

ExecutionStatus = Literal["success", "failure", "partial", "unknown"]
EligibilityStatus = Literal["eligible", "missing_required_state", "incompatible_state"]


class ObservedStateField(StrictModel):
    """Typed state observed by the host from prior execution."""

    contract: CapabilityFieldContract
    stable_identifier: str | None = None


class TypedExecutionState(StrictModel):
    """Observable execution state supplied by an external host runtime."""

    original_request_ref: str | None = None
    completed_route_ids: tuple[str, ...] = ()
    observed_fields: list[ObservedStateField] = Field(default_factory=list)
    last_status: ExecutionStatus = "unknown"
    error_class: str | None = None
    task_incomplete: bool = False

    @model_validator(mode="after")
    def validate_state(self) -> TypedExecutionState:
        if len(set(self.completed_route_ids)) != len(self.completed_route_ids):
            raise ValueError("completed_route_ids must not contain duplicates")
        return self


class StateEligibilityReason(StrictModel):
    code: Literal["missing_required_state", "incompatible_state"]
    semantic_id: str
    detail: str


class StateEligibility(StrictModel):
    status: EligibilityStatus
    reasons: list[StateEligibilityReason] = Field(default_factory=list)

    @property
    def eligible(self) -> bool:
        return self.status == "eligible"


def evaluate_state_eligibility(
    requirements: list[CapabilityFieldContract],
    state: TypedExecutionState,
) -> StateEligibility:
    """Evaluate typed state only; never plan or execute a capability."""

    reasons: list[StateEligibilityReason] = []
    for required in requirements:
        same_semantic = [
            observed.contract
            for observed in state.observed_fields
            if observed.contract.semantic_id == required.semantic_id
        ]
        if not same_semantic:
            reasons.append(StateEligibilityReason(
                code="missing_required_state",
                semantic_id=required.semantic_id,
                detail="required semantic state has not been observed",
            ))
            continue

        comparisons = [
            compare_capability_fields(required, observed)
            for observed in same_semantic
        ]
        if not any(result.satisfies for result in comparisons):
            reasons.append(StateEligibilityReason(
                code="incompatible_state",
                semantic_id=required.semantic_id,
                detail="observed state does not satisfy the required typed contract",
            ))

    if any(reason.code == "incompatible_state" for reason in reasons):
        return StateEligibility(status="incompatible_state", reasons=reasons)
    if reasons:
        return StateEligibility(status="missing_required_state", reasons=reasons)
    return StateEligibility(status="eligible")
