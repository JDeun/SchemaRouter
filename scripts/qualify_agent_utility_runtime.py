"""Instrument qualification for the #510 successor screen.

#506's screen produced no signal because its runtime emitted answer envelopes
without ever calling a tool, grounding its "facts" in the tool's name. Choosing
a replacement by running candidates and keeping the best would repeat that
error one level up, so the thresholds and the roster below are frozen by the
preregistration and the FIRST candidate that qualifies is the one used.

Qualification runs on its own surface. Its numbers are evidence about the
instrument and are never reported as experiment evidence.
"""
from __future__ import annotations

from typing import Any

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

# A floor against a rate computed from too few episodes, not a preregistered
# scientific parameter. A single episode qualifying at 1.0/1.0/1.0 is not
# evidence about a runtime; this is a gate against that, independent of the
# ELIGIBILITY thresholds above.
MINIMUM_EPISODES = 24


def qualification_rates(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Per-episode rates for the three preregistered criteria.

    Each row must carry a `semantic_task_id` and no id may repeat: a gate
    that can be fed the same episode twice is not a gate, and duplicate rows
    would silently inflate a rate.

    Raises below MINIMUM_EPISODES, including on an empty list. Returning a
    zero-rate dict for zero episodes would be indistinguishable from a real
    run in which every episode failed — the two must not be able to
    masquerade as each other.
    """
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
        # `score_envelope` reports required_fact_recall: the share of the task's
        # required facts the answer reproduced. Those facts are matched against
        # the frozen observation evidence, so a non-zero recall is exactly "at
        # least one observation-grounded fact". There is no separate count field.
        "grounded_fact_rate": sum(
            1 for row in rows if float(row.get("required_fact_recall", 0.0)) > 0.0
        )
        / total,
    }


def qualifies(rates: dict[str, float]) -> bool:
    """All three criteria must pass. A candidate is not graded on a curve.

    Refuses (raises ValueError) a `rates` that does not carry a real
    measurement for every criterion — a missing key, or a value that isn't a
    number (None included). A rate dict that was never measured must not be
    able to masquerade as a measured failure via a silent `.get(..., 0.0)`
    default.
    """
    missing = sorted(name for name in ELIGIBILITY if name not in rates)
    if missing:
        raise ValueError(f"rates is missing required criteria: {missing}")

    non_numeric = sorted(
        name
        for name in ELIGIBILITY
        if isinstance(rates[name], bool) or not isinstance(rates[name], (int, float))
    )
    if non_numeric:
        raise ValueError(f"rates has a non-numeric value for: {non_numeric}")

    return all(rates[name] >= threshold for name, threshold in ELIGIBILITY.items())


def select_runtime(results: dict[str, dict[str, float]]) -> str | None:
    """Return the first roster runtime that qualifies, or None if none did.

    `results` maps a roster entry to its qualification rates. The roster is
    walked in its frozen order and the first qualifier wins: a later candidate
    is never compared against an earlier one, because choosing among qualifiers
    would select the instrument by its outcome — the error this gate exists to
    prevent.

    Evaluating out of order is the shape that cherry-picking takes, so it is
    refused: a candidate may only have results if every candidate before it in
    the roster already has results and failed.

    The preregistration governs the act, not just the answer: "later
    candidates are not run". So it is refused, too, for a later candidate to
    have results once an earlier one has already qualified — holding those
    later numbers is the forbidden state even if this function would still
    return the correct (first) answer despite them.

    A None return means "no qualifier **so far**". It is a verdict only when
    `roster_exhausted(results)` is also True.
    """
    unknown = sorted(set(results) - set(ROSTER))
    if unknown:
        raise ValueError(f"not on the frozen roster: {unknown}")

    for index, candidate in enumerate(ROSTER):
        if candidate not in results:
            later = [name for name in ROSTER[index + 1:] if name in results]
            if later:
                raise ValueError(
                    f"{candidate!r} has no result but later candidates do ({later}); "
                    "the roster must be evaluated in order"
                )
            return None
        if qualifies(results[candidate]):
            later = [name for name in ROSTER[index + 1:] if name in results]
            if later:
                raise ValueError(
                    f"{candidate!r} qualified but later candidates have results too "
                    f"({later}); later candidates must not be run once an earlier "
                    "one qualifies"
                )
            return candidate
    return None


def roster_exhausted(results: dict[str, dict[str, float]]) -> bool:
    """Whether every frozen roster candidate has been evaluated.

    `select_runtime` returns None both when no candidate has qualified yet and
    when the roster is finished with no qualifier. Only the second is a verdict.
    Declaring "no candidate qualified" — which the preregistration treats as a
    terminal result about the screening approach — requires this to be True.
    """
    return set(results) == set(ROSTER)
