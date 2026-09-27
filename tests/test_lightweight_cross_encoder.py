from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "benchmarks" / "lightweight_cross_encoder.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "lightweight_cross_encoder",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load lightweight cross-encoder scorer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_empty_pairs_do_not_load_model(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _module()

    def fail_load():
        raise AssertionError("model should not be loaded for an empty batch")

    monkeypatch.setattr(module, "_load", fail_load)
    assert module.score_pairs([]) == []


def test_invalid_pair_rejected_before_model_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()

    def fail_load():
        raise AssertionError("model should not be loaded for invalid input")

    monkeypatch.setattr(module, "_load", fail_load)
    with pytest.raises(ValueError, match="non-empty strings"):
        module.score_pairs([("", "operation")])


def test_sigmoid_is_stable_and_bounded() -> None:
    module = _module()
    assert module._sigmoid(0.0) == pytest.approx(0.5)
    assert 0.0 <= module._sigmoid(1000.0) <= 1.0
    assert 0.0 <= module._sigmoid(-1000.0) <= 1.0
