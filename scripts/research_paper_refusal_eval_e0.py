"""Opt-in E0 scoped refusal evaluation; no global capability absence inference."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

Gold = Literal["supported", "unsupported", "unresolved"]
Decision = Literal["offer", "abstain", "request_arguments", "request_observation"]
Language = Literal["ko", "en", "ja"]

@dataclass(frozen=True)
class Case:
    case_id: str
    language: Language
    gold: Gold
    decision: Decision
    source_verified: bool

@dataclass(frozen=True)
class Metrics:
    supported: int
    unsupported: int
    unresolved: int
    false_refusal: int
    false_accept: int
    supported_deferred: int
    unsupported_deferred: int
    false_refusal_rate: float | None
    false_accept_rate: float | None

def decision_from_plan_status(status: str) -> Decision:
    """Map a proved planning receipt, not a model assertion, to evaluation outcome."""
    if status == "ready":
        return "offer"
    if status == "requires_arguments":
        return "request_arguments"
    if status == "requires_observation":
        return "request_observation"
    if status in ("no_proven_hit", "over_k_unranked", "budget_unsatisfied", "ambiguous_paths"):
        return "abstain"
    raise ValueError("unknown or unverified paper plan status")

def evaluate(cases: tuple[Case, ...]) -> dict[str, Metrics]:
    """Only independent source-verified gold contributes to error denominators."""
    if type(cases) is not tuple or not 1 <= len(cases) <= 10000:
        raise ValueError("bounded immutable evaluation cases required")
    seen: set[str] = set()
    for case in cases:
        if (type(case) is not Case or type(case.case_id) is not str
            or not 1 <= len(case.case_id) <= 100 or case.case_id in seen):
            raise ValueError("invalid or duplicate case identifier")
        seen.add(case.case_id)
        if (case.language not in ("ko", "en", "ja")
            or case.gold not in ("supported", "unsupported", "unresolved")
            or case.decision not in ("offer", "abstain", "request_arguments", "request_observation")
            or type(case.source_verified) is not bool
            or (case.gold != "unresolved" and not case.source_verified)):
            raise ValueError("independent source verification required for resolved gold")
    result: dict[str, Metrics] = {}
    for language in ("ko", "en", "ja", "all"):
        subset = [c for c in cases if language == "all" or c.language == language]
        supported = sum(c.gold == "supported" for c in subset)
        unsupported = sum(c.gold == "unsupported" for c in subset)
        unresolved = sum(c.gold == "unresolved" for c in subset)
        fr = sum(c.gold == "supported" and c.decision == "abstain" for c in subset)
        fa = sum(c.gold == "unsupported" and c.decision == "offer" for c in subset)
        sd = sum(c.gold == "supported" and c.decision in ("request_arguments", "request_observation") for c in subset)
        ud = sum(c.gold == "unsupported" and c.decision in ("request_arguments", "request_observation") for c in subset)
        result[language] = Metrics(supported, unsupported, unresolved, fr, fa, sd, ud,
                                   fr / supported if supported else None,
                                   fa / unsupported if unsupported else None)
    return result
