from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "benchmarks" / "multilingual_nli.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "benchmark_multilingual_nli",
        MODULE,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load multilingual NLI benchmark module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_nli_label_index_requires_exactly_one_entailment_label() -> None:
    module = _module()
    assert module._label_index(
        {0: "contradiction", 1: "neutral", 2: "entailment"}
    ) == 2

    with pytest.raises(RuntimeError, match="exactly one entailment"):
        module._label_index({0: "negative", 1: "neutral", 2: "positive"})


def test_nli_hypothesis_compacts_operation_surface_without_changing_content() -> None:
    module = _module()
    rendered = module._hypothesis(
        "create ticket\nopen support case\nCreate a customer support ticket"
    )

    assert rendered.startswith(
        "The user is requesting exactly this operation: "
    )
    assert "create ticket ; open support case ; Create a customer support ticket" in rendered
    assert "\n" not in rendered
