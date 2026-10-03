from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import Field, model_validator

from .capability_constraints import OperationalConstraintResult
from .capability_eligibility import (
    CapabilityEligibilityExplanation,
    CapabilityEligibilityReason,
)
from .capability_fallback import CapabilityFallbackEligibility
from .capability_lineage import CapabilityLineage
from .capability_negotiation import CapabilityNegotiationCandidate
from .execution_state import StateEligibility
from .models import StrictModel

CapabilityDecisionDisposition = Literal[
    "candidate",
    "selected",
    "excluded",
    "fallback",
]
CapabilityRetrievalDisposition = Literal[
    "retrieved",
    "not_retrieved",
    "unknown",
]
CapabilityHealthDisposition = Literal["healthy", "unhealthy", "unknown"]
CapabilityDriftDisposition = Literal["current", "drifted", "unknown"]
CapabilityPolicyDisposition = Literal["allowed", "denied", "unknown"]

CapabilityDecisionStage = Literal[
    "retrieval",
    "eligibility",
    "state",
    "health",
    "drift",
    "policy",
    "operational",
    "negotiation",
    "fallback",
    "lineage",
]


class CapabilityDecisionReason(StrictModel):
    stage: CapabilityDecisionStage
    code: str
    detail: str = ""
    children: tuple[CapabilityDecisionReason, ...] = ()


class CapabilityDecisionCandidateInput(StrictModel):
    """Host-visible candidate decision inputs.

    visible=False is accepted only as an input suppression signal. Invisible
    capability identifiers never appear in the resulting trace.
    """

    capability_id: str
    visible: bool = True
    final_disposition: CapabilityDecisionDisposition = "candidate"
    retrieval: CapabilityRetrievalDisposition = "unknown"
    health: CapabilityHealthDisposition = "unknown"
    drift: CapabilityDriftDisposition = "unknown"
    policy: CapabilityPolicyDisposition = "unknown"
    eligibility: CapabilityEligibilityExplanation | None = None
    state: StateEligibility | None = None
    operational: OperationalConstraintResult | None = None
    negotiation: CapabilityNegotiationCandidate | None = None
    fallback: CapabilityFallbackEligibility | None = None

    @model_validator(mode="after")
    def validate_identity(self) -> CapabilityDecisionCandidateInput:
        if not self.capability_id.strip():
            raise ValueError("capability_id must be non-empty")
        if (
            self.eligibility is not None
            and self.eligibility.capability_id != self.capability_id
        ):
            raise ValueError("eligibility capability_id does not match decision candidate")
        if (
            self.negotiation is not None
            and self.negotiation.capability_id != self.capability_id
        ):
            raise ValueError("negotiation capability_id does not match decision candidate")
        return self


class CapabilityDecisionCandidate(StrictModel):
    capability_id: str
    final_disposition: CapabilityDecisionDisposition
    retrieval: CapabilityRetrievalDisposition
    health: CapabilityHealthDisposition
    drift: CapabilityDriftDisposition
    policy: CapabilityPolicyDisposition
    eligibility: CapabilityEligibilityExplanation | None = None
    state: StateEligibility | None = None
    operational: OperationalConstraintResult | None = None
    negotiation: CapabilityNegotiationCandidate | None = None
    fallback: CapabilityFallbackEligibility | None = None
    reasons: tuple[CapabilityDecisionReason, ...] = ()


class CapabilityDecisionTrace(StrictModel):
    trace_id: str
    snapshot_id: str | None = None
    registry_version: int | None = Field(default=None, ge=0)
    candidates: tuple[CapabilityDecisionCandidate, ...] = ()
    lineage: CapabilityLineage | None = None


def _eligibility_reason(
    reason: CapabilityEligibilityReason,
) -> CapabilityDecisionReason:
    return CapabilityDecisionReason(
        stage="eligibility",
        code=reason.code,
        detail=reason.detail,
        children=tuple(
            _eligibility_reason(child)
            for child in reason.children
        ),
    )


def _candidate_reasons(
    item: CapabilityDecisionCandidateInput,
) -> tuple[CapabilityDecisionReason, ...]:
    reasons: list[CapabilityDecisionReason] = []

    if item.retrieval == "not_retrieved":
        reasons.append(
            CapabilityDecisionReason(
                stage="retrieval",
                code="not_retrieved",
            )
        )

    if item.eligibility is not None:
        reasons.extend(_eligibility_reason(reason) for reason in item.eligibility.reasons)

    if item.state is not None and not item.state.eligible:
        reasons.extend(
            CapabilityDecisionReason(
                stage="state",
                code=reason.code,
                detail=reason.detail,
            )
            for reason in item.state.reasons
        )

    if item.health == "unhealthy":
        reasons.append(
            CapabilityDecisionReason(
                stage="health",
                code="method_unhealthy",
            )
        )

    if item.drift == "drifted":
        reasons.append(
            CapabilityDecisionReason(
                stage="drift",
                code="contract_drifted",
            )
        )

    if item.policy == "denied":
        reasons.append(
            CapabilityDecisionReason(
                stage="policy",
                code="policy_denied",
            )
        )

    if item.operational is not None:
        reasons.extend(
            CapabilityDecisionReason(
                stage="operational",
                code=reason.code,
                detail=reason.detail,
            )
            for reason in item.operational.reasons
            if reason.code != "eligible"
        )

    if item.negotiation is not None and item.negotiation.status not in {
        "exact",
        "compatible",
        "convertible",
    }:
        if item.negotiation.reasons:
            reasons.extend(
                CapabilityDecisionReason(
                    stage="negotiation",
                    code=item.negotiation.status,
                    detail=detail,
                )
                for detail in item.negotiation.reasons
            )
        else:
            reasons.append(
                CapabilityDecisionReason(
                    stage="negotiation",
                    code=item.negotiation.status,
                )
            )

    if item.fallback is not None and not item.fallback.eligible:
        reasons.extend(
            CapabilityDecisionReason(
                stage="fallback",
                code=reason,
            )
            for reason in item.fallback.reasons
            if reason != "eligible"
        )

    return tuple(reasons)


def _trace_digest(
    *,
    snapshot_id: str | None,
    registry_version: int | None,
    candidates: tuple[CapabilityDecisionCandidate, ...],
    lineage: CapabilityLineage | None,
) -> str:
    payload = {
        "snapshot_id": snapshot_id,
        "registry_version": registry_version,
        "candidates": [
            item.model_dump(mode="json")
            for item in candidates
        ],
        "lineage": (
            lineage.model_dump(mode="json")
            if lineage is not None
            else None
        ),
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()


def build_capability_decision_trace(
    candidates: list[CapabilityDecisionCandidateInput],
    *,
    snapshot_id: str | None = None,
    registry_version: int | None = None,
    lineage: CapabilityLineage | None = None,
    enabled: bool = True,
) -> CapabilityDecisionTrace | None:
    """Aggregate already-computed host-visible decision results.

    This function is intentionally not a policy engine. It never changes candidate
    eligibility, routing order, fallback authority, or execution authority.
    """

    if not enabled:
        return None

    visible: list[CapabilityDecisionCandidate] = []
    seen: set[str] = set()
    for item in sorted(
        (candidate for candidate in candidates if candidate.visible),
        key=lambda candidate: candidate.capability_id,
    ):
        if item.capability_id in seen:
            raise ValueError("decision trace capability IDs must be unique")
        seen.add(item.capability_id)
        visible.append(
            CapabilityDecisionCandidate(
                capability_id=item.capability_id,
                final_disposition=item.final_disposition,
                retrieval=item.retrieval,
                health=item.health,
                drift=item.drift,
                policy=item.policy,
                eligibility=item.eligibility,
                state=item.state,
                operational=item.operational,
                negotiation=item.negotiation,
                fallback=item.fallback,
                reasons=_candidate_reasons(item),
            )
        )

    candidate_items = tuple(visible)
    return CapabilityDecisionTrace(
        trace_id=_trace_digest(
            snapshot_id=snapshot_id,
            registry_version=registry_version,
            candidates=candidate_items,
            lineage=lineage,
        ),
        snapshot_id=snapshot_id,
        registry_version=registry_version,
        candidates=candidate_items,
        lineage=lineage,
    )


def render_capability_decision_trace(
    trace: CapabilityDecisionTrace,
    *,
    detailed: bool = False,
) -> dict[str, object]:
    """Render a privacy-safe compact or detailed inspection document."""

    candidates: list[dict[str, object]] = []
    for item in trace.candidates:
        rendered: dict[str, object] = {
            "capability_id": item.capability_id,
            "final_disposition": item.final_disposition,
            "retrieval": item.retrieval,
            "health": item.health,
            "drift": item.drift,
            "policy": item.policy,
            "reasons": [
                reason.model_dump(mode="json")
                for reason in item.reasons
            ],
        }
        if detailed:
            rendered.update(
                {
                    "eligibility": (
                        item.eligibility.model_dump(mode="json")
                        if item.eligibility is not None
                        else None
                    ),
                    "state": (
                        item.state.model_dump(mode="json")
                        if item.state is not None
                        else None
                    ),
                    "operational": (
                        item.operational.model_dump(mode="json")
                        if item.operational is not None
                        else None
                    ),
                    "negotiation": (
                        item.negotiation.model_dump(mode="json")
                        if item.negotiation is not None
                        else None
                    ),
                    "fallback": (
                        item.fallback.model_dump(mode="json")
                        if item.fallback is not None
                        else None
                    ),
                }
            )
        candidates.append(rendered)

    return {
        "trace_id": trace.trace_id,
        "snapshot_id": trace.snapshot_id,
        "registry_version": trace.registry_version,
        "candidates": candidates,
        "lineage": (
            trace.lineage.model_dump(mode="json")
            if detailed and trace.lineage is not None
            else (
                {
                    "lineage_id": trace.lineage.lineage_id,
                    "selected": trace.lineage.selected.route_id,
                    "actual": trace.lineage.actual.route_id,
                }
                if trace.lineage is not None
                else None
            )
        ),
    }
