"""Fixed-label strict-final diagnosis for research E1, never a second scorer.

No raw final text or source values returned. This function must never
authorize a model call, change a strict final outcome, or extract nested JSON
for acceptance.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from scripts.research_real_qwen_bound_two_step_e0 import _parse_strict_model_json

_CATEGORIES = frozenset({
    "strict_correct",
    "valid_json_wrong_value",
    "valid_json_wrong_type",
    "valid_json_wrong_contract",
    "invalid_json_structure",
    "markdown_fenced_not_strict_json",
    "reasoning_wrapped_not_strict_json",
    "nonjson_or_prefixed_final",
})


def classify_strict_final_e1(
    model_text: str, trusted_observation: Mapping[str, Any],
) -> str:
    """Classify why strict JSON final scorer passed/failed, no repairs."""
    if type(model_text) is not str or not isinstance(trusted_observation, Mapping):
        raise ValueError("model text and trusted observation required")
    try:
        value = _parse_strict_model_json(model_text)
    except (TypeError, ValueError, OverflowError):
        candidate = model_text.strip()
        if candidate.startswith("```"):
            return "markdown_fenced_not_strict_json"
        if "<think>" in candidate or "</think>" in candidate:
            return "reasoning_wrapped_not_strict_json"
        if candidate.startswith(("{", "[")):
            return "invalid_json_structure"
        return "nonjson_or_prefixed_final"
    if type(value) is not dict or set(value) != {"case_state"}:
        return "valid_json_wrong_contract"
    if type(value["case_state"]) is not str:
        return "valid_json_wrong_type"
    if value == {"case_state": trusted_observation.get("case_state")}:
        return "strict_correct"
    return "valid_json_wrong_value"
