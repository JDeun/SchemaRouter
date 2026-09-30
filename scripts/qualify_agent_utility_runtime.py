"""Instrument qualification for the #510 successor screen.

A runtime may be selected only from provenance-bearing evidence tied to the
frozen qualification corpus. Bare rate dictionaries remain an internal test
primitive and are not a valid workflow input.
"""
from __future__ import annotations

from typing import Any

from scripts.generate_agent_utility_v8_qualification_corpus import (
    QUALIFICATION_EVIDENCE_CLASS,
    QUALIFICATION_SURFACE,
)
from scripts.validate_agent_utility_v8_qualification_corpus import (
    validate_qualification_corpus,
)

# Frozen by issue #510. Do not tune.
ELIGIBILITY = {
    "envelope_valid_rate": 0.80,
    "tool_call_rate": 0.90,
    "grounded_fact_rate": 0.70,
}

# Frozen and ordered. The first runtime that qualifies is used; later
# candidates are not run for comparison.
ROSTER = (
    "HuggingFaceTB/SmolLM3-3B",
    "Qwen/Qwen3-4B",
    "Qwen/Qwen3-8B",
)

MINIMUM_EPISODES = 24


def qualification_rates(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Compute the three preregistered rates from unique measured episodes."""
    seen_ids: set[Any] = set()
    for row in rows:
        task_id = row.get("semantic_task_id")
        if task_id is None:
            raise ValueError("row is missing semantic_task_id")
        if task_id in seen_ids:
            raise ValueError(f"duplicate episode: semantic_task_id={task_id!r}")
        seen_ids.add(task_id)

    if len(rows) < MINIMUM_EPISODES:
        raise ValueError(
            f"only {len(rows)} episodes, below the MINIMUM_EPISODES floor "
            f"of {MINIMUM_EPISODES}"
        )

    for row in rows:
        valid = row.get("final_envelope_valid")
        if not isinstance(valid, bool):
            raise ValueError(
                f"final_envelope_valid must be a bool, got {valid!r} "
                f"(semantic_task_id={row.get('semantic_task_id')!r})"
            )

    total = float(len(rows))
    return {
        "envelope_valid_rate": sum(
            1 for row in rows if row["final_envelope_valid"] is True
        )
        / total,
        "tool_call_rate": sum(
            1 for row in rows if int(row.get("tool_call_count", 0)) > 0
        )
        / total,
        "grounded_fact_rate": sum(
            1 for row in rows
            if float(row.get("required_fact_recall", 0.0)) > 0.0
        )
        / total,
    }


def qualifies(rates: dict[str, float]) -> bool:
    """Return whether every frozen eligibility threshold passes."""
    missing = sorted(name for name in ELIGIBILITY if name not in rates)
    if missing:
        raise ValueError(f"rates is missing required criteria: {missing}")

    non_numeric = sorted(
        name
        for name in ELIGIBILITY
        if isinstance(rates[name], bool)
        or not isinstance(rates[name], (int, float))
    )
    if non_numeric:
        raise ValueError(f"rates has a non-numeric value for: {non_numeric}")

    return all(rates[name] >= threshold for name, threshold in ELIGIBILITY.items())


def validate_qualification_evidence(
    candidate: str,
    evidence: dict[str, Any],
    qualification_corpus: dict[str, Any],
) -> dict[str, float]:
    """Validate provenance and return measured qualification rates.

    This is the fail-closed boundary that prevents rows from #506, the
    successor experiment surface, ad-hoc subsets, or another model/harness
    from masquerading as qualification evidence.
    """
    validate_qualification_corpus(qualification_corpus)

    if candidate not in ROSTER:
        raise ValueError(f"not on the frozen roster: {candidate!r}")
    if evidence.get("candidate_model") != candidate:
        raise ValueError("qualification evidence candidate_model mismatch")
    if evidence.get("evidence_class") != QUALIFICATION_EVIDENCE_CLASS:
        raise ValueError("qualification evidence_class mismatch")
    if evidence.get("surface") != QUALIFICATION_SURFACE:
        raise ValueError("qualification surface mismatch")

    model_revision = evidence.get("model_revision")
    if not isinstance(model_revision, str) or not model_revision.strip():
        raise ValueError("qualification evidence requires a pinned model_revision")

    source_revision = evidence.get("source_revision")
    if source_revision != qualification_corpus.get("source_revision"):
        raise ValueError("qualification source_revision mismatch")
    if evidence.get("harness_revision") != source_revision:
        raise ValueError("qualification harness_revision must equal frozen source_revision")

    if evidence.get("corpus_tasks_sha256") != qualification_corpus.get("tasks_sha256"):
        raise ValueError("qualification corpus_tasks_sha256 mismatch")

    expected_ids = {
        str(task["semantic_task_id"])
        for task in qualification_corpus["tasks"]
    }
    rows = evidence.get("rows")
    if not isinstance(rows, list):
        raise ValueError("qualification evidence rows must be a list")
    if len(rows) != qualification_corpus.get("expected_episode_count"):
        raise ValueError(
            "qualification episode_count does not match the frozen corpus"
        )

    row_ids = [str(row.get("semantic_task_id")) for row in rows]
    if len(set(row_ids)) != len(row_ids):
        raise ValueError("qualification evidence contains duplicate task ids")
    if set(row_ids) != expected_ids:
        missing = sorted(expected_ids - set(row_ids))
        extra = sorted(set(row_ids) - expected_ids)
        raise ValueError(
            f"qualification task-id set mismatch: missing={missing[:3]} "
            f"extra={extra[:3]}"
        )

    return qualification_rates(rows)


def _select_runtime_from_rates(
    results: dict[str, dict[str, float]],
) -> str | None:
    """Pure ordered-roster selector used after provenance validation."""
    unknown = sorted(set(results) - set(ROSTER))
    if unknown:
        raise ValueError(f"not on the frozen roster: {unknown}")

    for index, candidate in enumerate(ROSTER):
        if candidate not in results:
            later = [name for name in ROSTER[index + 1:] if name in results]
            if later:
                raise ValueError(
                    f"{candidate!r} has no result but later candidates do "
                    f"({later}); the roster must be evaluated in order"
                )
            return None
        if qualifies(results[candidate]):
            later = [name for name in ROSTER[index + 1:] if name in results]
            if later:
                raise ValueError(
                    f"{candidate!r} qualified but later candidates have results "
                    f"too ({later}); later candidates must not be run once an "
                    "earlier one qualifies"
                )
            return candidate
    return None


def select_runtime(
    evidence_by_candidate: dict[str, dict[str, Any]],
    *,
    qualification_corpus: dict[str, Any],
) -> str | None:
    """Select the first qualifying runtime from verified frozen evidence.

    Every supplied candidate result is provenance-validated before the ordered
    roster rule is applied. Workflows must call this function, not the private
    rate-only helper.
    """
    rates_by_candidate: dict[str, dict[str, float]] = {}
    for candidate, evidence in evidence_by_candidate.items():
        rates_by_candidate[candidate] = validate_qualification_evidence(
            candidate,
            evidence,
            qualification_corpus,
        )
    return _select_runtime_from_rates(rates_by_candidate)


def roster_exhausted(results: dict[str, Any]) -> bool:
    """Whether every frozen roster candidate has evidence/results."""
    return set(results) == set(ROSTER)
