from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks import bge_cascade


PAIRS = [
    ("query", "operation one"),
    ("query", "operation two"),
]


def _configure(
    monkeypatch: pytest.MonkeyPatch,
    *,
    reject_below: float = 0.30,
    accept_above: float = 0.60,
    accept_margin: float = 0.03,
) -> None:
    monkeypatch.setenv(
        "SCHEMAROUTER_BENCHMARK_CASCADE_REJECT_BELOW",
        str(reject_below),
    )
    monkeypatch.setenv(
        "SCHEMAROUTER_BENCHMARK_CASCADE_ACCEPT_ABOVE",
        str(accept_above),
    )
    monkeypatch.setenv(
        "SCHEMAROUTER_BENCHMARK_CASCADE_ACCEPT_MARGIN",
        str(accept_margin),
    )
    monkeypatch.delenv("SCHEMAROUTER_BENCHMARK_CASCADE_TELEMETRY", raising=False)


def test_fast_reject_skips_reranker(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)
    monkeypatch.setattr(
        bge_cascade,
        "_embedding_similarities",
        lambda pairs: [0.20, 0.10],
    )

    def fail_rerank(pairs: list[tuple[str, str]]) -> list[float]:
        raise AssertionError("reranker must not run for a confident reject")

    monkeypatch.setattr(bge_cascade, "_rerank_pairs", fail_rerank)

    assert bge_cascade.score_pairs(PAIRS) == [0.0, 0.0]


def test_fast_accept_skips_reranker(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)
    monkeypatch.setattr(
        bge_cascade,
        "_embedding_similarities",
        lambda pairs: [0.72, 0.50],
    )

    def fail_rerank(pairs: list[tuple[str, str]]) -> list[float]:
        raise AssertionError("reranker must not run for a confident accept")

    monkeypatch.setattr(bge_cascade, "_rerank_pairs", fail_rerank)

    assert bge_cascade.score_pairs(PAIRS) == [1.0, 0.0]


def test_ambiguous_case_escalates_to_frozen_reranker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)
    monkeypatch.setattr(
        bge_cascade,
        "_embedding_similarities",
        lambda pairs: [0.58, 0.57],
    )
    calls: list[list[tuple[str, str]]] = []

    def rerank(pairs: list[tuple[str, str]]) -> list[float]:
        calls.append(pairs)
        return [0.25, 0.80]

    monkeypatch.setattr(bge_cascade, "_rerank_pairs", rerank)

    assert bge_cascade.score_pairs(PAIRS) == [0.25, 0.80]
    assert calls == [PAIRS]


def test_accept_requires_margin(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, accept_margin=0.05)
    monkeypatch.setattr(
        bge_cascade,
        "_embedding_similarities",
        lambda pairs: [0.72, 0.70],
    )
    monkeypatch.setattr(
        bge_cascade,
        "_rerank_pairs",
        lambda pairs: [0.90, 0.10],
    )

    assert bge_cascade.score_pairs(PAIRS) == [0.90, 0.10]


def test_invalid_threshold_order_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, reject_below=0.60, accept_above=0.55)

    with pytest.raises(RuntimeError, match="must be lower"):
        bge_cascade.score_pairs(PAIRS)


def test_mixed_queries_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)

    with pytest.raises(ValueError, match="one shared query"):
        bge_cascade.score_pairs(
            [
                ("query one", "operation one"),
                ("query two", "operation two"),
            ]
        )
