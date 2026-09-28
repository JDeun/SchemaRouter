from __future__ import annotations

import math

from benchmarks.schema_adb_baseline import ACTION_PHRASES, LANGUAGES
from benchmarks.schema_hard_negative_ellipsoid import (
    HardNegativeEllipsoid,
    SchemaHardNegativeEllipsoidRouter,
    fit_hard_negative_ellipsoid,
    hard_negative_texts,
)
from schemarouter import EndpointSpec, InMemoryRegistry, ToolSpec


def test_hard_negative_bank_is_exact_tool_capability_complement() -> None:
    supported = {"retrieve", "update"}
    rows = hard_negative_texts(
        resource_anchor="demo records",
        supported_leaves=supported,
    )

    assert len(rows) == (len(ACTION_PHRASES) - len(supported)) * len(LANGUAGES)
    assert all(
        ACTION_PHRASES[leaf][language] not in row
        for row in rows
        for leaf in supported
        for language in LANGUAGES
    )
    assert f"{ACTION_PHRASES['delete']['en']}: demo records" in rows


def test_low_rank_ellipsoid_fit_is_deterministic() -> None:
    positives = [
        [1.0, 0.00, 0.00, 0.00],
        [0.99, 0.08, 0.01, 0.00],
        [0.99, -0.07, 0.00, 0.01],
        [0.98, 0.04, -0.03, 0.01],
        [0.98, -0.03, 0.04, -0.01],
    ]
    negatives = [
        [0.10, 0.99, 0.00, 0.00],
        [0.10, -0.99, 0.00, 0.00],
        [0.10, 0.00, 0.99, 0.00],
        [0.10, 0.00, 0.00, 0.99],
    ]

    first = fit_hard_negative_ellipsoid(
        route_id="demo.retrieve",
        tool_key="demo",
        leaf="retrieve",
        positives=positives,
        negatives=negatives,
    )
    second = fit_hard_negative_ellipsoid(
        route_id="demo.retrieve",
        tool_key="demo",
        leaf="retrieve",
        positives=positives,
        negatives=negatives,
    )

    assert first.scales == second.scales
    assert first.axes == second.axes
    assert all(math.isfinite(value) and value > 0.0 for value in first.scales)
    assert first.positive_count == len(positives)
    assert first.negative_count == len(negatives)


def _authority_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="demo",
            description="Demo records",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve one existing record",
                    read_only=True,
                ),
                EndpointSpec(
                    name="update",
                    description="Update an existing record",
                    read_only=False,
                ),
            ],
        )
    )
    return registry


def _toy_embedder(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        lowered = text.casefold()
        if text == "cross":
            vectors.append([0.0, 1.0, 0.0, 0.0])
        elif "update" in lowered or "modify" in lowered or "수정" in lowered:
            vectors.append([0.0, 1.0, 0.0, 0.0])
        elif "retrieve" in lowered or "lookup" in lowered or "조회" in lowered:
            vectors.append([1.0, 0.0, 0.0, 0.0])
        elif "delete" in lowered or "remove" in lowered or "삭제" in lowered:
            vectors.append([0.0, 0.0, 1.0, 0.0])
        else:
            vectors.append([0.4, 0.3, 0.2, 0.8])
    return vectors


def _unit_ball(
    *,
    route_id: str,
    leaf: str,
    center: tuple[float, ...],
    scale: float,
) -> HardNegativeEllipsoid:
    return HardNegativeEllipsoid(
        route_id=route_id,
        tool_key="demo",
        leaf=leaf,
        center=center,
        axes=(),
        initial_scales=(scale,),
        scales=(scale,),
        positive_count=18,
        negative_count=96,
        positive_distances=(0.0,),
        negative_distances=(2.0,),
    )


def test_ellipsoid_can_only_preserve_raw_winner_or_abstain() -> None:
    router = SchemaHardNegativeEllipsoidRouter(_authority_registry(), _toy_embedder)

    router.schema_vectors["demo.retrieve"] = [0.0, 1.0, 0.0, 0.0]
    router.action_vectors["demo.retrieve"] = [0.0, 1.0, 0.0, 0.0]
    router.schema_vectors["demo.update"] = [1.0, 0.0, 0.0, 0.0]
    router.action_vectors["demo.update"] = [1.0, 0.0, 0.0, 0.0]

    router.boundaries["demo.retrieve"] = _unit_ball(
        route_id="demo.retrieve",
        leaf="retrieve",
        center=(1.0, 0.0, 0.0, 0.0),
        scale=0.01,
    )
    router.boundaries["demo.update"] = _unit_ball(
        route_id="demo.update",
        leaf="update",
        center=(0.0, 1.0, 0.0, 0.0),
        scale=0.01,
    )

    result = router.route("cross")
    assert result["raw_top_route"] == "demo.retrieve"
    assert any(
        row["route_id"] == "demo.update" and row["inside"]
        for row in result["boundary_rows"]
    )
    assert result["predicted"] == "demo.retrieve"


def test_unknown_endpoint_semantics_fail_open() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="opaque",
            description="Opaque registered service",
            endpoints=[
                EndpointSpec(
                    name="x17",
                    description="Perform the registered opaque capability",
                )
            ],
        )
    )
    router = SchemaHardNegativeEllipsoidRouter(registry, _toy_embedder)
    result = router.route("cross")

    assert result["raw_top_route"] == "opaque.x17"
    assert result["predicted"] == "opaque.x17"
    assert result["tool_has_unknown_leaf"] is True
    assert result["boundary_rows"] == []
