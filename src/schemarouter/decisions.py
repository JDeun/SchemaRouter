from __future__ import annotations

import inspect
import math
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .errors import PlanningError


class _DecisionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class DecisionOption(_DecisionModel):
    """One locally authorized choice exposed to a decision backend."""

    id: str = Field(min_length=1)
    label: str = ""
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionRequest(_DecisionModel):
    """A bounded choice request.

    Option IDs are the only authoritative values. Descriptions and metadata are
    untrusted context and cannot grant execution authority.
    """

    query: str
    options: list[DecisionOption] = Field(min_length=1)
    max_selections: int = Field(default=1, ge=1)
    context: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_bounds(self) -> DecisionRequest:
        ids = [option.id for option in self.options]
        if len(ids) != len(set(ids)):
            raise ValueError("decision option IDs must be unique")
        if self.max_selections > len(self.options):
            raise ValueError("max_selections cannot exceed the option count")
        return self


class DecisionSelection(_DecisionModel):
    option_id: str = Field(min_length=1)
    score: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_finite_score(self) -> DecisionSelection:
        if self.score is not None and not math.isfinite(self.score):
            raise ValueError("decision scores must be finite")
        return self


class DecisionResult(_DecisionModel):
    selections: list[DecisionSelection] = Field(default_factory=list)
    abstained: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_abstention(self) -> DecisionResult:
        if self.abstained and self.selections:
            raise ValueError("an abstaining decision cannot contain selections")
        return self


class DecisionBackend(Protocol):
    def decide(
        self,
        request: DecisionRequest,
    ) -> DecisionResult | Awaitable[DecisionResult]: ...


DecisionCallable = Callable[
    [DecisionRequest],
    DecisionResult | dict[str, Any] | Awaitable[DecisionResult | dict[str, Any]],
]


def validate_decision(request: DecisionRequest, result: DecisionResult) -> DecisionResult:
    """Fail closed if a backend returns anything outside the offered choice set."""

    allowed = {option.id for option in request.options}
    selected = [selection.option_id for selection in result.selections]

    if len(selected) != len(set(selected)):
        raise PlanningError("decision backend returned duplicate option IDs")
    unknown = sorted(set(selected) - allowed)
    if unknown:
        raise PlanningError(
            "decision backend returned unknown option IDs: " + ", ".join(unknown)
        )
    if len(selected) > request.max_selections:
        raise PlanningError("decision backend exceeded max_selections")
    return result


class CallableDecisionBackend:
    """Provider-neutral adapter for hosted or local bounded-decision models."""

    def __init__(self, model: DecisionCallable) -> None:
        self.model = model

    def decide(
        self,
        request: DecisionRequest,
    ) -> DecisionResult | Awaitable[DecisionResult]:
        raw = self.model(request)
        if inspect.isawaitable(raw):

            async def resolve() -> DecisionResult:
                value = await raw
                result = (
                    value
                    if isinstance(value, DecisionResult)
                    else DecisionResult.model_validate(value)
                )
                return validate_decision(request, result)

            return resolve()

        result = raw if isinstance(raw, DecisionResult) else DecisionResult.model_validate(raw)
        return validate_decision(request, result)


class FirstOptionDecisionBackend:
    """Deterministic reference backend for tests and integration examples."""

    def decide(self, request: DecisionRequest) -> DecisionResult:
        return DecisionResult(
            selections=[DecisionSelection(option_id=request.options[0].id, score=1.0)]
        )


def choose_sync(
    backend: DecisionBackend,
    request: DecisionRequest,
) -> DecisionResult:
    result = backend.decide(request)
    if inspect.isawaitable(result):
        if inspect.iscoroutine(result):
            result.close()
        raise PlanningError("the configured decision backend is asynchronous; use an async path")
    return validate_decision(request, result)


async def choose_async(
    backend: DecisionBackend,
    request: DecisionRequest,
) -> DecisionResult:
    result = backend.decide(request)
    if inspect.isawaitable(result):
        result = await result
    return validate_decision(request, result)
