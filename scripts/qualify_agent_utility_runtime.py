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


def qualification_rates(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Per-episode rates for the three preregistered criteria."""
    if not rows:
        return {name: 0.0 for name in ELIGIBILITY}

    total = float(len(rows))
    return {
        "envelope_valid_rate": sum(
            1 for row in rows if row.get("final_envelope_valid")
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
    """All three criteria must pass. A candidate is not graded on a curve."""
    return all(rates.get(name, 0.0) >= threshold for name, threshold in ELIGIBILITY.items())


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
            return candidate
    return None
