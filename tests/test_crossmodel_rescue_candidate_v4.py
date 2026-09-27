from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from benchmark_decision_routing import reference_registry  # noqa: E402

from benchmarks.crossmodel_rescue_candidate import (  # noqa: E402
    RESCUE_EPSILON,
    RESCUE_RULES,
    FrozenCrossModelRescueBackend,
    _max_passes,
    _min_passes,
)


class FakeBase:
    def __init__(self, route_ids: tuple[str, ...], result: dict[str, Any]) -> None:
        self.route_ids = route_ids
        self.result = result
        self.calls = 0

    def score_routes(self, query: str, offered_routes: list[str]) -> dict[str, Any]:
        self.calls += 1
        return dict(self.result)


class CountingEmbedder:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[1.0, 0.0] for _ in texts]


class CountingReranker:
    def __init__(self, score: float = 1.0) -> None:
        self.calls = 0
        self.score = score

    def __call__(self, query: str, text: str) -> float:
        self.calls += 1
        return self.score


def _routes() -> tuple[str, ...]:
    registry = reference_registry()
    return tuple(
        sorted(
            f"{tool.key}.{endpoint.name}"
            for tool in registry.tools()
            for endpoint in tool.endpoints
        )
    )


def test_frozen_rescue_contract_is_exact() -> None:
    assert RESCUE_EPSILON == 1e-6
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
    reranker_routes = {
        route
        for route, rule in RESCUE_RULES.items()
        if float(rule["min_reranker_score"]) > -1.0
    }
    assert reranker_routes == {
        "calendar.create",
        "materials.search",
        "support.create_ticket",
        "weather.current",
    }


def test_global_epsilon_comparison_contract() -> None:
    threshold = 0.5
    assert _min_passes(threshold - 0.5e-6, threshold)
    assert not _min_passes(threshold - 2.0e-6, threshold)
    assert _max_passes(threshold + 0.5e-6, threshold)
    assert not _max_passes(threshold + 2.0e-6, threshold)


def test_base_accept_skips_gte_and_reranker() -> None:
    registry = reference_registry()
    routes = _routes()
    base = FakeBase(
        routes,
        {
            "top_route": "calendar.create",
            "top_score": 0.9,
            "top_margin": 0.2,
            "accepted": True,
        },
    )
    gte = CountingEmbedder()
    reranker = CountingReranker()
    candidate = FrozenCrossModelRescueBackend(
        registry,
        base_backend=base,
        gte_embedder=gte,
        reranker=reranker,
    )
    init_gte_calls = gte.calls

    trace = candidate.route_query("create a meeting", routes)

    assert trace["final_route"] == "calendar.create"
    assert trace["base_accepted"] is True
    assert trace["gte_invoked"] is False
    assert trace["reranker_invoked"] is False
    assert gte.calls == init_gte_calls
    assert reranker.calls == 0


def test_rescue_disabled_route_skips_gte_and_reranker() -> None:
    registry = reference_registry()
    routes = _routes()
    base = FakeBase(
        routes,
        {
            "top_route": "calendar.list",
            "top_score": 0.1,
            "top_margin": 0.0,
            "accepted": False,
        },
    )
    gte = CountingEmbedder()
    reranker = CountingReranker()
    candidate = FrozenCrossModelRescueBackend(
        registry,
        base_backend=base,
        gte_embedder=gte,
        reranker=reranker,
    )
    init_gte_calls = gte.calls

    trace = candidate.route_query("list meetings", routes)

    assert trace["final_route"] is None
    assert trace["rescue_reason"] == "route_disabled"
    assert trace["gte_invoked"] is False
    assert trace["reranker_invoked"] is False
    assert gte.calls == init_gte_calls
    assert reranker.calls == 0
