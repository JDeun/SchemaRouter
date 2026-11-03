"""Private structured-fact oracle for NEW opt-in episodes, not frozen scores.

Reuses #424's existing gold/envelope format. The prose `answer` is not checked
for semantic truth; this cannot establish general final-answer correctness.
No gold, answer text, fact values or source IDs leave this function.
"""
from __future__ import annotations

import math
from typing import Any


def _finite_scalar(value: Any) -> bool:
    if type(value) in (str, bool, type(None)):
        return True
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _usable_gold(task: dict[str, Any]) -> bool:
    required = task.get("required_facts")
    tolerances = task.get("numeric_tolerances")
    units = task.get("accepted_units")
    sources = task.get("allowed_source_ids")
    mandatory = task.get("mandatory_answer_fields")
    forbidden = task.get("forbidden_facts")
    if (
        task.get("supported") is not True
        or type(required) is not list or not required
        or type(tolerances) is not dict or type(units) is not dict
        or type(sources) is not list or not sources
        or any(type(value) is not str or not value for value in sources)
        or type(mandatory) is not list or not mandatory
        or any(type(value) is not str for value in mandatory)
        or type(forbidden) is not list
    ):
        return False
    keys: set[str] = set()
    for fact in required:
        if (
            type(fact) is not dict
            or set(fact) != {"key", "value", "unit", "source_id"}
            or type(fact["key"]) is not str or not fact["key"]
            or fact["key"] in keys or not _finite_scalar(fact["value"])
            or fact["unit"] is not None and type(fact["unit"]) is not str
            or type(fact["source_id"]) is not str or fact["source_id"] not in sources
        ):
            return False
        key = fact["key"]
        keys.add(key)
        if type(fact["value"]) in (int, float):
            tolerance = tolerances.get(key)
            if (
                type(tolerance) is not dict or not tolerance
                or not set(tolerance) <= {"absolute", "relative"}
                or any(type(value) not in (int, float) or value < 0
                       or not _finite_scalar(value) for value in tolerance.values())
            ):
                return False
        if fact["unit"] is not None and key not in units:
            return False
    if not set(mandatory) <= keys or not set(tolerances) <= keys or not set(units) <= keys:
        return False
    if any(type(value) is not list or not value
           or any(item is not None and type(item) is not str for item in value)
           for value in units.values()):
        return False
    return all(
        type(fact) is dict and type(fact.get("key")) is str
        and "value" in fact and _finite_scalar(fact["value"])
        for fact in forbidden
    )


def private_structured_final_result(
    task: dict[str, Any], final_text: str, *, execution_passed: bool,
) -> dict[str, bool | None]:
    """Return only tri-state public outcomes; absent/incomplete gold is unknown."""
    result: dict[str, bool | None] = {
        "structured_final_answer_passed": None,
        "execution_and_structured_final_passed": None,
        "free_text_final_answer_verified": False,
    }
    if not _usable_gold(task):
        return result
    # Lazy import avoids changing startup/import behavior of the frozen loop.
    from scripts.evaluate_agent_utility_v4_final_answer import _parse_envelope, score_envelope

    envelope = _parse_envelope(final_text)
    expected = {fact["key"]: fact for fact in task["required_facts"]}
    scalar_types_match = envelope is not None and all(
        fact["key"] in expected and _finite_scalar(fact["value"])
        and (
            type(fact["value"]) in (int, float)
            if type(expected[fact["key"]]["value"]) in (int, float)
            else type(fact["value"]) is type(expected[fact["key"]]["value"])
        ) for fact in envelope["facts"]
    )
    if not scalar_types_match:
        result["structured_final_answer_passed"] = False
        result["execution_and_structured_final_passed"] = False
        return result
    scores = score_envelope(task, final_text)
    passed = bool(
        scores["final_envelope_valid"]
        and scores["required_fact_recall"] == 1.0
        and scores["numeric_value_accuracy"] in (None, 1.0)
        and scores["unit_accuracy"] in (None, 1.0)
        and scores["provenance_accuracy"] == 1.0
        and scores["unsupported_fact_count"] == 0
        and scores["contradiction_count"] == 0
        and scores["exact_field_completion"]
        and scores["structured_fact_count"] == len(expected)
        and scores["source_list_valid"]
    )
    result["structured_final_answer_passed"] = passed
    result["execution_and_structured_final_passed"] = execution_passed and passed
    return result
