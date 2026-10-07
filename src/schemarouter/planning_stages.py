from __future__ import annotations

from collections.abc import Awaitable, Callable, Hashable, Sequence, Set
from dataclasses import dataclass
from typing import Generic, TypeVar

from .models import ExecutionPlan, FallbackRoute, PlanCoverage, ToolCall

ContextT = TypeVar("ContextT")
CandidateT = TypeVar("CandidateT")
CallT = TypeVar("CallT")
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



@dataclass(frozen=True, slots=True)
class PrimarySelectionResult(Generic[CandidateT, CallT, CoverageT]):
    """Immutable output of primary-call selection."""

    pairs: tuple[tuple[CandidateT, CallT], ...]
    required_coverage: frozenset[CoverageT]


def select_primary_candidates_sync(
    *,
    candidates: list[CandidateT],
    max_calls: int,
    retrieval_mode: str,
    required_coverage: Set[CoverageT],
    coverage_matrix: Callable[
        [list[CandidateT]],
        tuple[Sequence[Set[CoverageT]], Set[CoverageT]],
    ],
    compile_candidate: Callable[[CandidateT], CallT | None],
    provider_key: Callable[[CandidateT], str],
    corroboration_compatible: Callable[
        [CandidateT, CallT, CandidateT, CallT],
        bool,
    ],
    selected_coverage: Callable[[CandidateT, CallT], Set[CoverageT]],
) -> PrimarySelectionResult[CandidateT, CallT, CoverageT]:
    """Select executable primary calls while preserving routing-mode semantics."""

    pairs: list[tuple[CandidateT, CallT]] = []
    effective_required = set(required_coverage)

    if max_calls <= 1:
        for candidate in candidates:
            call = compile_candidate(candidate)
            if call is not None:
                pairs.append((candidate, call))
                break
        return PrimarySelectionResult(
            pairs=tuple(pairs),
            required_coverage=frozenset(effective_required),
        )

    candidate_coverage, matrix_required = coverage_matrix(candidates)
    effective_required = set(matrix_required)
    uncovered = set(effective_required)
    selected_providers: set[str] = set()

    for candidate, potential_coverage in zip(
        candidates,
        candidate_coverage,
        strict=True,
    ):
        if len(pairs) >= max_calls:
            break

        candidate_provider = provider_key(candidate)
        if retrieval_mode == "corroborate":
            if effective_required and not (
                potential_coverage & effective_required
            ):
                continue
            if candidate_provider in selected_providers:
                continue
        elif effective_required and not (potential_coverage & uncovered):
            continue

        call = compile_candidate(candidate)
        if call is None:
            continue

        if (
            retrieval_mode == "corroborate"
            and pairs
            and not any(
                corroboration_compatible(
                    selected_candidate,
                    selected_call,
                    candidate,
                    call,
                )
                for selected_candidate, selected_call in pairs
            )
        ):
            continue

        pairs.append((candidate, call))
        selected_providers.add(candidate_provider)

        if effective_required:
            covered = selected_coverage(candidate, call)
            uncovered.difference_update(covered & potential_coverage)
            if retrieval_mode == "coverage" and not uncovered:
                break

    return PrimarySelectionResult(
        pairs=tuple(pairs),
        required_coverage=frozenset(effective_required),
    )


async def select_primary_candidates_async(
    *,
    candidates: list[CandidateT],
    max_calls: int,
    retrieval_mode: str,
    required_coverage: Set[CoverageT],
    coverage_matrix: Callable[
        [list[CandidateT]],
        tuple[Sequence[Set[CoverageT]], Set[CoverageT]],
    ],
    compile_candidate: Callable[
        [CandidateT],
        Awaitable[CallT | None],
    ],
    provider_key: Callable[[CandidateT], str],
    corroboration_compatible: Callable[
        [CandidateT, CallT, CandidateT, CallT],
        bool,
    ],
    selected_coverage: Callable[[CandidateT, CallT], Set[CoverageT]],
) -> PrimarySelectionResult[CandidateT, CallT, CoverageT]:
    """Async counterpart preserving the exact primary-selection policy."""

    pairs: list[tuple[CandidateT, CallT]] = []
    effective_required = set(required_coverage)

    if max_calls <= 1:
        for candidate in candidates:
            call = await compile_candidate(candidate)
            if call is not None:
                pairs.append((candidate, call))
                break
        return PrimarySelectionResult(
            pairs=tuple(pairs),
            required_coverage=frozenset(effective_required),
        )

    candidate_coverage, matrix_required = coverage_matrix(candidates)
    effective_required = set(matrix_required)
    uncovered = set(effective_required)
    selected_providers: set[str] = set()

    for candidate, potential_coverage in zip(
        candidates,
        candidate_coverage,
        strict=True,
    ):
        if len(pairs) >= max_calls:
            break

        candidate_provider = provider_key(candidate)
        if retrieval_mode == "corroborate":
            if effective_required and not (
                potential_coverage & effective_required
            ):
                continue
            if candidate_provider in selected_providers:
                continue
        elif effective_required and not (potential_coverage & uncovered):
            continue

        call = await compile_candidate(candidate)
        if call is None:
            continue

        if (
            retrieval_mode == "corroborate"
            and pairs
            and not any(
                corroboration_compatible(
                    selected_candidate,
                    selected_call,
                    candidate,
                    call,
                )
                for selected_candidate, selected_call in pairs
            )
        ):
            continue

        pairs.append((candidate, call))
        selected_providers.add(candidate_provider)

        if effective_required:
            covered = selected_coverage(candidate, call)
            uncovered.difference_update(covered & potential_coverage)
            if retrieval_mode == "coverage" and not uncovered:
                break

    return PrimarySelectionResult(
        pairs=tuple(pairs),
        required_coverage=frozenset(effective_required),
    )



@dataclass(frozen=True, slots=True)
class FallbackSelectionResult(Generic[CallT]):
    """Immutable fallback alternatives grouped by primary call index."""

    routes: tuple[tuple[int, tuple[CallT, ...]], ...]


def select_fallbacks_sync(
    *,
    primary_pairs: tuple[tuple[CandidateT, CallT], ...],
    all_candidates: tuple[CandidateT, ...],
    fallback_scope: str,
    max_fallbacks: int,
    is_read_only: Callable[[CandidateT], bool],
    ordered_candidates: Callable[
        [CandidateT, tuple[CandidateT, ...], str],
        list[CandidateT],
    ],
    compile_candidate: Callable[[CandidateT], CallT | None],
    is_executable: Callable[[CallT], bool],
    compatible: Callable[[CandidateT, CallT, CandidateT, CallT], bool],
) -> FallbackSelectionResult[CallT]:
    """Build bounded executable fallbacks for read-only primary calls."""

    if fallback_scope == "disabled" or max_fallbacks <= 0:
        return FallbackSelectionResult(routes=())

    routes: list[tuple[int, tuple[CallT, ...]]] = []
    for index, (primary_candidate, primary_call) in enumerate(primary_pairs):
        if not is_read_only(primary_candidate):
            continue

        alternatives: list[CallT] = []
        for candidate in ordered_candidates(
            primary_candidate,
            all_candidates,
            fallback_scope,
        ):
            if len(alternatives) >= max_fallbacks:
                break
            if not is_read_only(candidate):
                continue

            alternative = compile_candidate(candidate)
            if alternative is None or not is_executable(alternative):
                continue
            if not compatible(
                primary_candidate,
                primary_call,
                candidate,
                alternative,
            ):
                continue
            alternatives.append(alternative)

        if alternatives:
            routes.append((index, tuple(alternatives)))

    return FallbackSelectionResult(routes=tuple(routes))


async def select_fallbacks_async(
    *,
    primary_pairs: tuple[tuple[CandidateT, CallT], ...],
    all_candidates: tuple[CandidateT, ...],
    fallback_scope: str,
    max_fallbacks: int,
    is_read_only: Callable[[CandidateT], bool],
    ordered_candidates: Callable[
        [CandidateT, tuple[CandidateT, ...], str],
        list[CandidateT],
    ],
    compile_candidate: Callable[[CandidateT], Awaitable[CallT | None]],
    is_executable: Callable[[CallT], bool],
    compatible: Callable[[CandidateT, CallT, CandidateT, CallT], bool],
) -> FallbackSelectionResult[CallT]:
    """Async counterpart preserving the exact fallback policy."""

    if fallback_scope == "disabled" or max_fallbacks <= 0:
        return FallbackSelectionResult(routes=())

    routes: list[tuple[int, tuple[CallT, ...]]] = []
    for index, (primary_candidate, primary_call) in enumerate(primary_pairs):
        if not is_read_only(primary_candidate):
            continue

        alternatives: list[CallT] = []
        for candidate in ordered_candidates(
            primary_candidate,
            all_candidates,
            fallback_scope,
        ):
            if len(alternatives) >= max_fallbacks:
                break
            if not is_read_only(candidate):
                continue

            alternative = await compile_candidate(candidate)
            if alternative is None or not is_executable(alternative):
                continue
            if not compatible(
                primary_candidate,
                primary_call,
                candidate,
                alternative,
            ):
                continue
            alternatives.append(alternative)

        if alternatives:
            routes.append((index, tuple(alternatives)))

    return FallbackSelectionResult(routes=tuple(routes))


def assemble_execution_plan(
    *,
    query: str,
    registry_version: int,
    primary_pairs: Sequence[tuple[CandidateT, ToolCall]],
    fallback_routes: Sequence[FallbackRoute],
    warnings: Sequence[str],
    required_coverage: Set[CoverageT],
    all_candidates: list[CandidateT],
    selected_coverage: Callable[[CandidateT, ToolCall], Set[CoverageT]],
    build_coverage: Callable[
        [frozenset[CoverageT], set[CoverageT], list[CandidateT]],
        PlanCoverage | None,
    ],
    coverage_warning: Callable[[PlanCoverage | None], str | None],
) -> ExecutionPlan:
    """Assemble the final public plan from already-selected calls and fallbacks."""

    required = frozenset(required_coverage)
    covered: set[CoverageT] = set()
    for candidate, call in primary_pairs:
        covered.update(selected_coverage(candidate, call) & required)

    coverage = build_coverage(required, covered, all_candidates)
    plan_warnings = list(warnings)
    warning = coverage_warning(coverage)
    if warning:
        plan_warnings.append(warning)

    return ExecutionPlan(
        query=query,
        registry_version=registry_version,
        calls=[call for _, call in primary_pairs],
        fallback_routes=list(fallback_routes),
        warnings=plan_warnings,
        coverage=coverage,
    )
