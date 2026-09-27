from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from benchmarks.cross_model_rescue_candidate import (
    RESCUE_EPSILON,
    RESCUE_RULES,
    RERANKER_ENABLED_ROUTES,
    FrozenCrossModelRescueBackend,
    _passes_max,
    _passes_min,
)
from schemarouter import DecisionOption, DecisionRequest
from schemarouter.decisions import DecisionResult, DecisionSelection


def _request() -> DecisionRequest:
    return DecisionRequest(
        query="test query",
        options=[
            DecisionOption(id="a", label="calendar.create"),
            DecisionOption(id="b", label="calendar.list"),
        ],
        max_selections=1,
    )


def test_frozen_rescue_contract_has_exact_enabled_routes() -> None:
    assert set(RESCUE_RULES) == {
        "calendar.create",
        "finance.quote",
        "materials.search",
        "papers.search",
        "support.create_ticket",
        "users.lookup",
        "weather.current",
        "weather.forecast",
    }
    assert RERANKER_ENABLED_ROUTES == {
        "calendar.create",
        "materials.search",
        "support.create_ticket",
        "weather.current",
    }
    assert RESCUE_EPSILON == 1e-6


def test_comparison_epsilon_is_symmetric_by_contract() -> None:
    assert _passes_min(0.5 - 5e-7, 0.5)
    assert not _passes_min(0.5 - 2e-6, 0.5)
    assert _passes_max(0.5 + 5e-7, 0.5)
    assert not _passes_max(0.5 + 2e-6, 0.5)


@dataclass
class _FakeBase:
    result: DecisionResult

    def decide(self, request: DecisionRequest) -> DecisionResult:
        return self.result


def test_base_accepted_decision_is_returned_unchanged() -> None:
    accepted = DecisionResult(
        selections=[DecisionSelection(option_id="a", score=0.9)],
        abstained=False,
        metadata={"top_route": "calendar.create", "accepted": True},
    )
    backend = object.__new__(FrozenCrossModelRescueBackend)
    backend.base = _FakeBase(accepted)

    result = backend.decide(_request())

    assert result is accepted


def test_rescue_disabled_route_does_not_invoke_gte() -> None:
    backend = object.__new__(FrozenCrossModelRescueBackend)

    def forbidden_gte(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("GTE must not run for rescue-disabled route")

    backend._gte_rank = forbidden_gte  # type: ignore[method-assign]
    result = backend._rescue_from_base(
        "query",
        ["calendar.list"],
        {
            "top_route": "calendar.list",
            "top_score": 0.1,
            "top_margin": 0.1,
            "accepted": False,
        },
    )
    assert not result["final_accepted"]
    assert not result["gte_invoked"]


def test_gte_winner_disagreement_preserves_abstention() -> None:
    backend = object.__new__(FrozenCrossModelRescueBackend)
    backend._gte_rank = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
        "gte_top_route": "calendar.list",
        "gte_top_score": 0.9,
        "gte_second_score": 0.8,
        "gte_top_margin": 0.1,
    }
    backend.reranker_scorer = lambda *_args: (_ for _ in ()).throw(
        AssertionError("reranker must not run when GTE winner disagrees")
    )

    result = backend._rescue_from_base(
        "query",
        ["calendar.create", "calendar.list"],
        {
            "top_route": "calendar.create",
            "top_score": 0.50,
            "top_margin": 0.03,
            "accepted": False,
        },
    )
    assert result["gte_invoked"]
    assert not result["gte_agrees"]
    assert not result["reranker_invoked"]
    assert not result["final_accepted"]


def test_non_reranker_rule_can_rescue_same_winner_without_cross_encoder() -> None:
    backend = object.__new__(FrozenCrossModelRescueBackend)
    backend._gte_rank = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
        "gte_top_route": "finance.quote",
        "gte_top_score": 0.8,
        "gte_second_score": 0.6,
        "gte_top_margin": 0.2,
    }
    backend.reranker_scorer = lambda *_args: (_ for _ in ()).throw(
        AssertionError("finance.quote rescue must not invoke reranker")
    )

    result = backend._rescue_from_base(
        "query",
        ["finance.quote"],
        {
            "top_route": "finance.quote",
            "top_score": 0.48,
            "top_margin": 0.03,
            "accepted": False,
        },
    )
    assert result["gte_agrees"]
    assert not result["reranker_invoked"]
    assert result["rescue_accepted"]
    assert result["final_route"] == "finance.quote"


def test_reranker_route_uses_exact_same_winner_surface() -> None:
    backend = object.__new__(FrozenCrossModelRescueBackend)
    backend._gte_rank = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
        "gte_top_route": "calendar.create",
        "gte_top_score": 0.9,
        "gte_second_score": 0.7,
        "gte_top_margin": 0.2,
    }
    backend._route_specs = {
        "calendar.create": ("schema", "action", "calendar capability")
    }
    calls: list[tuple[str, str]] = []

    def scorer(query: str, text: str) -> float:
        calls.append((query, text))
        return 0.9

    backend.reranker_scorer = scorer
    result = backend._rescue_from_base(
        "the query",
        ["calendar.create"],
        {
            "top_route": "calendar.create",
            "top_score": 0.50,
            "top_margin": 0.03,
            "accepted": False,
        },
    )
    assert result["rescue_accepted"]
    assert result["reranker_invoked"]
    assert calls == [("the query", "calendar capability")]
