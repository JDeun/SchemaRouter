from __future__ import annotations

from collections.abc import Awaitable, Callable, Hashable, Set
from dataclasses import dataclass
from typing import Generic, TypeVar

ContextT = TypeVar("ContextT")
CandidateT = TypeVar("CandidateT")
CoverageT = TypeVar("CoverageT", bound=Hashable)


@dataclass(frozen=True, slots=True)
class CandidatePipelineResult(Generic[CandidateT, CoverageT]):
    """Immutable output of the ordered candidate-selection stage pipeline."""

    all_candidates: tuple[CandidateT, ...]
    candidates: tuple[CandidateT, ...]
    required_coverage: frozenset[CoverageT]
    warnings: tuple[str, ...]


def run_candidate_pipeline_sync(
    *,
    context: ContextT,
    recall: Callable[[ContextT], list[CandidateT]],
    augment: Callable[
        [ContextT, list[CandidateT]],
        tuple[list[CandidateT], list[str]],
    ],
    coverage: Callable[[ContextT, list[CandidateT]], Set[CoverageT]],
    capability_fit: Callable[
        [ContextT, list[CandidateT]],
        tuple[list[CandidateT], list[str]],
    ],
    operation_fit: Callable[
        [ContextT, list[CandidateT]],
        tuple[list[CandidateT], list[str]],
    ],
    disambiguate: Callable[
        [ContextT, list[CandidateT]],
        tuple[list[CandidateT], list[str]],
    ],
    decide: Callable[
        [ContextT, list[CandidateT]],
        tuple[list[CandidateT], list[str]],
    ],
    order: Callable[[ContextT, list[CandidateT]], list[CandidateT]],
) -> CandidatePipelineResult[CandidateT, CoverageT]:
    """Run the deterministic candidate pipeline in its explicit policy order."""

    lexical_candidates = recall(context)
    all_candidates, recall_warnings = augment(context, lexical_candidates)
    required_coverage = coverage(context, all_candidates)
    fit_candidates, fit_warnings = capability_fit(context, all_candidates)
    operation_candidates, operation_warnings = operation_fit(
        context,
        fit_candidates,
    )
    disambiguated_candidates, disambiguation_warnings = disambiguate(
        context,
        operation_candidates,
    )
    selected_candidates, decision_warnings = decide(
        context,
        disambiguated_candidates,
    )
    ordered_candidates = order(context, selected_candidates)

    return CandidatePipelineResult(
        all_candidates=tuple(all_candidates),
        candidates=tuple(ordered_candidates),
        required_coverage=frozenset(required_coverage),
        warnings=tuple(
            [
                *recall_warnings,
                *fit_warnings,
                *operation_warnings,
                *disambiguation_warnings,
                *decision_warnings,
            ]
        ),
    )


async def run_candidate_pipeline_async(
    *,
    context: ContextT,
    recall: Callable[[ContextT], list[CandidateT]],
    augment: Callable[
        [ContextT, list[CandidateT]],
        Awaitable[tuple[list[CandidateT], list[str]]],
    ],
    coverage: Callable[[ContextT, list[CandidateT]], Set[CoverageT]],
    capability_fit: Callable[
        [ContextT, list[CandidateT]],
        Awaitable[tuple[list[CandidateT], list[str]]],
    ],
    operation_fit: Callable[
        [ContextT, list[CandidateT]],
        Awaitable[tuple[list[CandidateT], list[str]]],
    ],
    disambiguate: Callable[
        [ContextT, list[CandidateT]],
        Awaitable[tuple[list[CandidateT], list[str]]],
    ],
    decide: Callable[
        [ContextT, list[CandidateT]],
        Awaitable[tuple[list[CandidateT], list[str]]],
    ],
    order: Callable[[ContextT, list[CandidateT]], list[CandidateT]],
) -> CandidatePipelineResult[CandidateT, CoverageT]:
    """Async counterpart preserving the exact same stage and warning order."""

    lexical_candidates = recall(context)
    all_candidates, recall_warnings = await augment(context, lexical_candidates)
    required_coverage = coverage(context, all_candidates)
    fit_candidates, fit_warnings = await capability_fit(context, all_candidates)
    operation_candidates, operation_warnings = await operation_fit(
        context,
        fit_candidates,
    )
    disambiguated_candidates, disambiguation_warnings = await disambiguate(
        context,
        operation_candidates,
    )
    selected_candidates, decision_warnings = await decide(
        context,
        disambiguated_candidates,
    )
    ordered_candidates = order(context, selected_candidates)

    return CandidatePipelineResult(
        all_candidates=tuple(all_candidates),
        candidates=tuple(ordered_candidates),
        required_coverage=frozenset(required_coverage),
        warnings=tuple(
            [
                *recall_warnings,
                *fit_warnings,
                *operation_warnings,
                *disambiguation_warnings,
                *decision_warnings,
            ]
        ),
    )
