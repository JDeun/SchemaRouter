from __future__ import annotations

import pytest

from benchmarks.multilingual_nli import _hypothesis, _label_index


def test_nli_label_index_requires_exactly_one_entailment_label() -> None:
    assert _label_index(
        {0: "contradiction", 1: "neutral", 2: "entailment"}
    ) == 2

    with pytest.raises(RuntimeError, match="exactly one entailment"):
        _label_index({0: "negative", 1: "neutral", 2: "positive"})


def test_nli_hypothesis_compacts_operation_surface_without_changing_content() -> None:
    rendered = _hypothesis(
        "create ticket\nopen support case\nCreate a customer support ticket"
    )

    assert rendered.startswith(
        "The user is requesting exactly this operation: "
    )
    assert "create ticket ; open support case ; Create a customer support ticket" in rendered
    assert "\n" not in rendered
