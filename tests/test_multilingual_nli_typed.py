from __future__ import annotations

from benchmarks.multilingual_nli_typed import (
    _resolve_label_indexes,
    hypothesis,
)


def test_resolve_typed_nli_labels_by_semantics() -> None:
    indexes = _resolve_label_indexes(
        {
            0: "contradiction",
            1: "neutral",
            2: "entailment",
        }
    )
    assert indexes == {
        "contradiction": 0,
        "neutral": 1,
        "entailment": 2,
    }


def test_hypothesis_compacts_operation_surface() -> None:
    value = hypothesis(
        "create ticket\nopen support case\nCreate a support ticket"
    )
    assert value.startswith(
        "The user's request is supported by exactly this registered operation:"
    )
    assert "create ticket ; open support case ; Create a support ticket" in value
