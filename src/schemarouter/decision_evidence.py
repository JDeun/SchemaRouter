from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .decisions import (
    DecisionEvidence,
    DecisionRequest,
    DecisionResult,
    DecisionSelection,
    validate_decision,
)
from .errors import PlanningError

EvidenceUnknownPolicy = Literal["abstain", "reject"]
EvidenceProjectionState = Literal["accept", "reject", "unknown"]


class EvidenceRequirement(BaseModel):
    """One independently evaluated decision-evidence requirement.

    Numeric thresholds are meaningful only within the declared score kind.
    Requirements never average or compare scores across different score kinds.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str = Field(min_length=1)
    source: str | None = None
    score_kind: str | None = None
    min_score: float | None = None
    on_unknown: EvidenceUnknownPolicy = "abstain"

    @model_validator(mode="after")
    def validate_requirement(self) -> EvidenceRequirement:
        if not self.kind.strip():
            raise ValueError("evidence requirement kind must contain non-whitespace text")
        if self.source is not None and not self.source.strip():
            raise ValueError("evidence requirement source must contain non-whitespace text")
        if self.score_kind is not None and not self.score_kind.strip():
            raise ValueError("evidence requirement score_kind must contain non-whitespace text")
        if self.min_score is not None:
            if not math.isfinite(self.min_score):
                raise ValueError("evidence requirement min_score must be finite")
            if self.score_kind is None:
                raise ValueError(
                    "numeric evidence requirement min_score requires score_kind"
                )
        return self


class EvidenceProjector:
    """Project typed bounded evidence without cross-kind score arithmetic.

    The projector can only return option IDs that were already present in the
    DecisionRequest. Missing evidence remains unknown; it is never converted
    into a numeric zero.
    """

    def __init__(self, requirements: Iterable[EvidenceRequirement]) -> None:
        self.requirements = tuple(requirements)
        if not self.requirements:
            raise ValueError("at least one evidence requirement is required")

        selectors = [
            (item.kind, item.source, item.score_kind)
            for item in self.requirements
        ]
        if len(selectors) != len(set(selectors)):
            raise ValueError("duplicate evidence requirement selectors are not allowed")

    @staticmethod
    def _matches_requirement(
        item: DecisionEvidence,
        requirement: EvidenceRequirement,
        *,
        option_id: str,
    ) -> bool:
        if item.option_id != option_id:
            return False
        if item.kind != requirement.kind:
            return False
        if requirement.source is not None and item.source != requirement.source:
            return False
        if (
            requirement.score_kind is not None
            and item.score_kind != requirement.score_kind
        ):
            return False
        return True

    @staticmethod
    def _unknown_state(requirement: EvidenceRequirement) -> EvidenceProjectionState:
        return "reject" if requirement.on_unknown == "reject" else "unknown"

    def _evaluate_requirement(
        self,
        *,
        option_id: str,
        evidence: list[DecisionEvidence],
        requirement: EvidenceRequirement,
    ) -> tuple[EvidenceProjectionState, dict[str, object]]:
        matches = [
            item
            for item in evidence
            if self._matches_requirement(
                item,
                requirement,
                option_id=option_id,
            )
        ]
        selector = {
            "kind": requirement.kind,
            "source": requirement.source,
            "score_kind": requirement.score_kind,
            "min_score": requirement.min_score,
            "on_unknown": requirement.on_unknown,
        }
        if not matches:
            state = self._unknown_state(requirement)
            return state, {
                **selector,
                "state": state,
                "reason": "missing_evidence",
            }
        if len(matches) > 1:
            raise PlanningError(
                "evidence projection found multiple observations for one "
                f"requirement and option {option_id!r}"
            )

        item = matches[0]
        if item.state == "unknown":
            state = self._unknown_state(requirement)
            return state, {
                **selector,
                "state": state,
                "reason": "unknown_evidence",
            }
        if item.state == "no_match":
            return "reject", {
                **selector,
                "state": "reject",
                "reason": "explicit_no_match",
                "score": item.score,
            }

        if requirement.min_score is not None:
            if item.score is None:
                state = self._unknown_state(requirement)
                return state, {
                    **selector,
                    "state": state,
                    "reason": "missing_numeric_score",
                }
            if item.score < requirement.min_score:
                return "reject", {
                    **selector,
                    "state": "reject",
                    "reason": "below_min_score",
                    "score": item.score,
                }

        return "accept", {
            **selector,
            "state": "accept",
            "reason": "matched",
            "score": item.score,
        }

    def project(
        self,
        request: DecisionRequest,
        evidence: Iterable[DecisionEvidence],
    ) -> DecisionResult:
        evidence_list = list(evidence)
        validate_decision(
            request,
            DecisionResult(
                abstained=True,
                evidence=evidence_list,
                metadata={"reason": "evidence_projection_precheck"},
            ),
        )

        per_option: dict[str, dict[str, object]] = {}
        accepted: list[str] = []
        has_unknown = False

        for option in request.options:
            traces: list[dict[str, object]] = []
            states: list[EvidenceProjectionState] = []
            for requirement in self.requirements:
                state, trace = self._evaluate_requirement(
                    option_id=option.id,
                    evidence=evidence_list,
                    requirement=requirement,
                )
                states.append(state)
                traces.append(trace)

            if "reject" in states:
                state: EvidenceProjectionState = "reject"
            elif "unknown" in states:
                state = "unknown"
                has_unknown = True
            else:
                state = "accept"
                accepted.append(option.id)

            per_option[option.id] = {
                "state": state,
                "requirements": traces,
            }

        metadata: dict[str, object] = {
            "provider": "typed-evidence-projection",
            "requirement_count": len(self.requirements),
            "per_option": per_option,
        }

        if not accepted:
            reason = "evidence_unknown" if has_unknown else "evidence_rejected"
            return validate_decision(
                request,
                DecisionResult(
                    abstained=True,
                    evidence=evidence_list,
                    metadata={**metadata, "reason": reason},
                ),
            )

        if len(accepted) > request.max_selections:
            return validate_decision(
                request,
                DecisionResult(
                    abstained=True,
                    evidence=evidence_list,
                    metadata={
                        **metadata,
                        "reason": "ambiguous_evidence_projection",
                        "accepted_option_ids": accepted,
                    },
                ),
            )

        return validate_decision(
            request,
            DecisionResult(
                selections=[
                    DecisionSelection(option_id=option_id)
                    for option_id in accepted
                ],
                evidence=evidence_list,
                metadata={
                    **metadata,
                    "accepted_option_ids": accepted,
                },
            ),
        )
