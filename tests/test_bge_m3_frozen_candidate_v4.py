from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from benchmark_decision_routing import reference_registry

from benchmarks.bge_m3_frozen_candidate import (
    ACTION_WEIGHT,
    FROZEN_THRESHOLDS,
    SCHEMA_WEIGHT,
    AcceptAllRegisteredRecallBackend,
    FrozenBgeM3DualViewBackend,
)
from schemarouter import DecisionOption, DecisionRequest


class StaticThenOrthogonalEmbedder:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        if len(texts) > 1:
            return [[1.0, 0.0] for _ in texts]
        return [[0.0, 1.0]]


def _request(route_ids: tuple[str, ...]) -> DecisionRequest:
    return DecisionRequest(
        query="unsupported query",
        options=[
            DecisionOption(
                id=f"candidate:{index}",
                label=route_id,
            )
            for index, route_id in enumerate(route_ids)
        ],
        max_selections=1,
    )


def test_frozen_thresholds_cover_reference_registry_exactly() -> None:
    registry = reference_registry()
    registered = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }
    assert registered == set(FROZEN_THRESHOLDS)
    assert len(registered) == 16
    assert SCHEMA_WEIGHT == 0.5
    assert ACTION_WEIGHT == 0.5


def test_registered_recall_returns_only_offered_ids() -> None:
    request = DecisionRequest(
        query="anything",
        options=[
            DecisionOption(id="recall:0", label="a"),
            DecisionOption(id="recall:1", label="b"),
        ],
        max_selections=2,
    )
    result = AcceptAllRegisteredRecallBackend().decide(request)
    assert not result.abstained
    assert [item.option_id for item in result.selections] == [
        "recall:0",
        "recall:1",
    ]


def test_frozen_backend_abstains_without_falling_through() -> None:
    registry = reference_registry()
    embedder = StaticThenOrthogonalEmbedder()
    backend = FrozenBgeM3DualViewBackend(registry, embedder)

    result = backend.decide(_request(backend.route_ids))

    assert result.abstained
    assert result.selections == []
    assert result.metadata["accepted"] is False
    assert result.metadata["top_route"] == "calendar.create"
    assert result.metadata["top_margin"] == 0.0


def test_frozen_backend_can_select_only_an_offered_registered_route() -> None:
    registry = reference_registry()

    def identical(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    backend = FrozenBgeM3DualViewBackend(registry, identical)
    request = _request(backend.route_ids)
    result = backend.decide(request)

    assert not result.abstained
    assert len(result.selections) == 1
    selected = result.selections[0].option_id
    assert selected in {option.id for option in request.options}
    assert result.metadata["top_route"] == "calendar.create"
