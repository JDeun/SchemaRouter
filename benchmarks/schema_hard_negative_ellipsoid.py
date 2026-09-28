# ruff: noqa: E501
"""Schema-derived hard-negative low-rank ellipsoid for experiment #395.

Frozen BGE-M3 remains the sole positive route selector. The ellipsoid layer is
registry-compiled, veto-only evidence: it can preserve the raw registered winner
or abstain to NO_ROUTE, but it cannot choose another endpoint.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from benchmarks.schema_adb_baseline import (
    ACTION_PHRASES,
    ACTION_WEIGHT,
    LANGUAGES,
    SCHEMA_WEIGHT,
    _action_text,
    _centroid,
    _cosine,
    _schema_text,
    _to_vectors,
    compile_registry_contracts,
)

ELLIPSOID_RANK = 8
ELLIPSOID_STEPS = 400
ELLIPSOID_LR = 0.01
ELLIPSOID_BETA1 = 0.9
ELLIPSOID_BETA2 = 0.999
ELLIPSOID_EPS = 1e-8
ELLIPSOID_NEGATIVE_MARGIN = 1.10
ELLIPSOID_REGULARIZATION = 0.01
ELLIPSOID_SCALE_FLOOR = 1e-3
PCA_ITERATIONS = 200
PCA_EIGEN_EPS = 1e-12


@dataclass(frozen=True)
class HardNegativeEllipsoid:
    route_id: str
    tool_key: str
    leaf: str
    center: tuple[float, ...]
    axes: tuple[tuple[float, ...], ...]
    initial_scales: tuple[float, ...]
    scales: tuple[float, ...]
    positive_count: int
    negative_count: int
    positive_distances: tuple[float, ...]
    negative_distances: tuple[float, ...]

    @property
    def anisotropy(self) -> float:
        if not self.scales:
            return 1.0
        smallest = min(self.scales)
        return max(self.scales) / smallest if smallest > 0.0 else math.inf


def _dot(left: list[float] | tuple[float, ...], right: list[float] | tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must align")
    return sum(float(a) * float(b) for a, b in zip(left, right, strict=True))


def _norm(vector: list[float] | tuple[float, ...]) -> float:
    return math.sqrt(_dot(vector, vector))


def _normalize(vector: list[float]) -> list[float]:
    magnitude = _norm(vector)
    if magnitude <= 0.0 or not math.isfinite(magnitude):
        raise ValueError("vector must have a finite non-zero norm")
    return [value / magnitude for value in vector]


def _subtract(left: list[float], right: list[float]) -> list[float]:
    if len(left) != len(right):
        raise ValueError("vectors must align")
    return [a - b for a, b in zip(left, right, strict=True)]


def _orthogonalize(vector: list[float], basis: list[list[float]]) -> list[float]:
    result = list(vector)
    for previous in basis:
        coefficient = _dot(result, previous)
        result = [
            value - coefficient * axis
            for value, axis in zip(result, previous, strict=True)
        ]
    return result


def _deterministic_start(width: int, component: int, previous: list[list[float]]) -> list[float]:
    candidate = [
        math.sin((index + 1) * (component + 1) * 0.731)
        + math.cos((index + 1) * (component + 2) * 0.379)
        for index in range(width)
    ]
    candidate = _orthogonalize(candidate, previous)
    if _norm(candidate) <= PCA_EIGEN_EPS:
        for offset in range(width):
            candidate = [0.0] * width
            candidate[(component + offset) % width] = 1.0
            candidate = _orthogonalize(candidate, previous)
            if _norm(candidate) > PCA_EIGEN_EPS:
                break
    return _normalize(candidate)


def _gram_pca_axes(residuals: list[list[float]], rank: int) -> list[list[float]]:
    """Return deterministic principal axes using the small sample Gram matrix.

    There are only 18 positive views per endpoint, so decomposing X X^T keeps
    the implementation dependency-free even when the embedding width is large.
    """
    if not residuals:
        raise ValueError("PCA requires positive residuals")
    width = len(residuals[0])
    if any(len(row) != width for row in residuals):
        raise ValueError("residual widths must match")

    count = len(residuals)
    gram = [
        [_dot(residuals[i], residuals[j]) for j in range(count)]
        for i in range(count)
    ]

    sample_vectors: list[list[float]] = []
    axes: list[list[float]] = []
    target_rank = min(rank, max(0, count - 1), width)

    for component in range(target_rank):
        vector = _deterministic_start(count, component, sample_vectors)
        for _ in range(PCA_ITERATIONS):
            updated = [
                sum(gram[row][column] * vector[column] for column in range(count))
                for row in range(count)
            ]
            updated = _orthogonalize(updated, sample_vectors)
            magnitude = _norm(updated)
            if magnitude <= PCA_EIGEN_EPS:
                break
            updated = [value / magnitude for value in updated]
            if _dot(updated, vector) < 0.0:
                updated = [-value for value in updated]
            delta = _norm([a - b for a, b in zip(updated, vector, strict=True)])
            vector = updated
            if delta <= 1e-10:
                break

        gram_vector = [
            sum(gram[row][column] * vector[column] for column in range(count))
            for row in range(count)
        ]
        eigenvalue = _dot(vector, gram_vector)
        if eigenvalue <= PCA_EIGEN_EPS:
            break

        scale = math.sqrt(eigenvalue)
        axis = [
            sum(vector[row] * residuals[row][column] for row in range(count)) / scale
            for column in range(width)
        ]
        axis = _orthogonalize(axis, axes)
        if _norm(axis) <= PCA_EIGEN_EPS:
            break
        axis = _normalize(axis)

        sample_vectors.append(vector)
        axes.append(axis)

    return axes


def _ellipsoid_coordinates(
    vector: list[float],
    center: list[float] | tuple[float, ...],
    axes: list[list[float]] | tuple[tuple[float, ...], ...],
) -> list[float]:
    diff = _subtract(vector, list(center))
    principal = [_dot(diff, list(axis)) for axis in axes]
    total_sq = _dot(diff, diff)
    principal_sq = sum(value * value for value in principal)
    residual = math.sqrt(max(0.0, total_sq - principal_sq))
    return [*principal, residual]


def _initial_scales(positive_coordinates: list[list[float]]) -> list[float]:
    if not positive_coordinates:
        raise ValueError("positive coordinates are required")
    width = len(positive_coordinates[0])
    if width == 0 or any(len(row) != width for row in positive_coordinates):
        raise ValueError("coordinate widths must match")
    return [
        max(
            ELLIPSOID_SCALE_FLOOR,
            math.sqrt(
                sum(row[column] * row[column] for row in positive_coordinates)
                / len(positive_coordinates)
            ),
        )
        for column in range(width)
    ]


def _distance_from_coordinates(coordinates: list[float], scales: list[float]) -> float:
    if len(coordinates) != len(scales) or not scales:
        raise ValueError("coordinates and scales must align")
    return math.sqrt(
        sum(
            (coordinate / scale) ** 2
            for coordinate, scale in zip(coordinates, scales, strict=True)
        )
    )


def _gradient_for_distance(
    coordinates: list[float],
    scales: list[float],
    distance: float,
) -> list[float]:
    denominator = max(distance, 1e-12)
    return [
        -((coordinate / scale) ** 2) / denominator
        for coordinate, scale in zip(coordinates, scales, strict=True)
    ]


def optimize_ellipsoid_scales(
    positive_coordinates: list[list[float]],
    negative_coordinates: list[list[float]],
    initial_scales: list[float],
) -> list[float]:
    """Fit only anisotropic axis scales with the preregistered V6B objective."""
    if not positive_coordinates or not negative_coordinates:
        raise ValueError("both positive and hard-negative coordinates are required")
    width = len(initial_scales)
    if width == 0:
        raise ValueError("at least one ellipsoid coordinate is required")
    if any(len(row) != width for row in [*positive_coordinates, *negative_coordinates]):
        raise ValueError("coordinate widths must align")
    if any(scale <= 0.0 or not math.isfinite(scale) for scale in initial_scales):
        raise ValueError("initial scales must be finite and positive")

    logs = [math.log(scale) for scale in initial_scales]
    initial_logs = list(logs)
    first_moment = [0.0] * width
    second_moment = [0.0] * width

    for step in range(1, ELLIPSOID_STEPS + 1):
        scales = [math.exp(value) for value in logs]
        gradient = [0.0] * width

        positive_active = 0
        for coordinates in positive_coordinates:
            distance = _distance_from_coordinates(coordinates, scales)
            if distance <= 1.0:
                continue
            positive_active += 1
            row_gradient = _gradient_for_distance(coordinates, scales, distance)
            for index, value in enumerate(row_gradient):
                gradient[index] += value
        if positive_active:
            for index in range(width):
                gradient[index] /= len(positive_coordinates)

        negative_gradient = [0.0] * width
        for coordinates in negative_coordinates:
            distance = _distance_from_coordinates(coordinates, scales)
            if distance >= ELLIPSOID_NEGATIVE_MARGIN:
                continue
            row_gradient = _gradient_for_distance(coordinates, scales, distance)
            for index, value in enumerate(row_gradient):
                negative_gradient[index] -= value
        for index in range(width):
            gradient[index] += negative_gradient[index] / len(negative_coordinates)
            gradient[index] += (
                2.0
                * ELLIPSOID_REGULARIZATION
                * (logs[index] - initial_logs[index])
                / width
            )

        for index in range(width):
            value = gradient[index]
            first_moment[index] = (
                ELLIPSOID_BETA1 * first_moment[index]
                + (1.0 - ELLIPSOID_BETA1) * value
            )
            second_moment[index] = (
                ELLIPSOID_BETA2 * second_moment[index]
                + (1.0 - ELLIPSOID_BETA2) * value * value
            )
            m_hat = first_moment[index] / (1.0 - ELLIPSOID_BETA1**step)
            v_hat = second_moment[index] / (1.0 - ELLIPSOID_BETA2**step)
            logs[index] -= ELLIPSOID_LR * m_hat / (math.sqrt(v_hat) + ELLIPSOID_EPS)

    return [math.exp(value) for value in logs]


def hard_negative_texts(
    *,
    resource_anchor: str,
    supported_leaves: set[str],
) -> tuple[str, ...]:
    """Compile the exact schema-derived complement surface frozen in #395."""
    if not resource_anchor or not supported_leaves:
        return ()
    complement = [leaf for leaf in ACTION_PHRASES if leaf not in supported_leaves]
    if not complement:
        return ()
    rows = [
        f"{ACTION_PHRASES[leaf][language]}: {resource_anchor}"
        for leaf in complement
        for language in LANGUAGES
    ]
    return tuple(rows)


def fit_hard_negative_ellipsoid(
    *,
    route_id: str,
    tool_key: str,
    leaf: str,
    positives: list[list[float]],
    negatives: list[list[float]],
) -> HardNegativeEllipsoid:
    positive_vectors = _to_vectors(positives)
    negative_vectors = _to_vectors(negatives)
    center = _centroid(positive_vectors)
    residuals = [_subtract(vector, center) for vector in positive_vectors]
    axes = _gram_pca_axes(residuals, ELLIPSOID_RANK)

    positive_coordinates = [
        _ellipsoid_coordinates(vector, center, axes)
        for vector in positive_vectors
    ]
    negative_coordinates = [
        _ellipsoid_coordinates(vector, center, axes)
        for vector in negative_vectors
    ]
    initial_scales = _initial_scales(positive_coordinates)
    scales = optimize_ellipsoid_scales(
        positive_coordinates,
        negative_coordinates,
        initial_scales,
    )
    positive_distances = tuple(
        _distance_from_coordinates(row, scales)
        for row in positive_coordinates
    )
    negative_distances = tuple(
        _distance_from_coordinates(row, scales)
        for row in negative_coordinates
    )

    return HardNegativeEllipsoid(
        route_id=route_id,
        tool_key=tool_key,
        leaf=leaf,
        center=tuple(center),
        axes=tuple(tuple(axis) for axis in axes),
        initial_scales=tuple(initial_scales),
        scales=tuple(scales),
        positive_count=len(positive_vectors),
        negative_count=len(negative_vectors),
        positive_distances=positive_distances,
        negative_distances=negative_distances,
    )


def ellipsoid_distance(
    vector: list[float],
    boundary: HardNegativeEllipsoid,
) -> float:
    coordinates = _ellipsoid_coordinates(
        vector,
        boundary.center,
        boundary.axes,
    )
    return _distance_from_coordinates(coordinates, list(boundary.scales))


class SchemaHardNegativeEllipsoidRouter:
    """Frozen BGE routing plus registry-derived hard-negative ellipsoid veto."""

    def __init__(self, registry: Any, embedder: Any) -> None:
        self.registry = registry
        self.embedder = embedder
        self.contracts = compile_registry_contracts(registry)

        route_specs: dict[str, tuple[str, str]] = {}
        for tool in registry.tools():
            for endpoint in tool.endpoints:
                route_id = f"{tool.key}.{endpoint.name}"
                route_specs[route_id] = (
                    _schema_text(tool, endpoint),
                    _action_text(endpoint),
                )

        if set(route_specs) != set(self.contracts):
            raise ValueError("route and contract sets differ")
        self.route_ids = tuple(sorted(route_specs))

        route_count = len(self.route_ids)
        route_vectors = _to_vectors(
            embedder(
                [
                    *(route_specs[route][0] for route in self.route_ids),
                    *(route_specs[route][1] for route in self.route_ids),
                ]
            )
        )
        if len(route_vectors) != route_count * 2:
            raise ValueError("unexpected route embedding count")
        self.schema_vectors = dict(
            zip(self.route_ids, route_vectors[:route_count], strict=True)
        )
        self.action_vectors = dict(
            zip(self.route_ids, route_vectors[route_count:], strict=True)
        )

        contracts_by_tool: dict[str, list[Any]] = {}
        for contract in self.contracts.values():
            contracts_by_tool.setdefault(contract.tool_key, []).append(contract)

        self.unknown_tools: set[str] = set()
        self.boundaries: dict[str, HardNegativeEllipsoid] = {}

        for tool_key, contracts in contracts_by_tool.items():
            if any(
                contract.leaf is None or len(contract.synthetic_positives) != 18
                for contract in contracts
            ):
                self.unknown_tools.add(tool_key)
                continue

            supported_leaves = {str(contract.leaf) for contract in contracts}
            for contract in contracts:
                negatives_text = hard_negative_texts(
                    resource_anchor=contract.resource_anchor,
                    supported_leaves=supported_leaves,
                )
                if not negatives_text:
                    self.unknown_tools.add(tool_key)
                    break

                positives = _to_vectors(self.embedder(list(contract.synthetic_positives)))
                negatives = _to_vectors(self.embedder(list(negatives_text)))
                self.boundaries[contract.route_id] = fit_hard_negative_ellipsoid(
                    route_id=contract.route_id,
                    tool_key=contract.tool_key,
                    leaf=str(contract.leaf),
                    positives=positives,
                    negatives=negatives,
                )

            if tool_key in self.unknown_tools:
                for contract in contracts:
                    self.boundaries.pop(contract.route_id, None)

    def _rank_raw(self, query_vector: list[float]) -> list[tuple[str, float]]:
        rows: list[tuple[str, float]] = []
        for route_id in self.route_ids:
            score = (
                SCHEMA_WEIGHT * _cosine(query_vector, self.schema_vectors[route_id])
                + ACTION_WEIGHT * _cosine(query_vector, self.action_vectors[route_id])
            )
            rows.append((route_id, score))
        rows.sort(key=lambda item: (-item[1], item[0]))
        return rows

    def route(self, query: str) -> dict[str, Any]:
        query_vector = _to_vectors(self.embedder([query]))[0]
        raw_ranked = self._rank_raw(query_vector)
        raw_top_route, raw_top_score = raw_ranked[0]
        raw_tool = self.contracts[raw_top_route].tool_key

        tool_contracts = [
            contract
            for contract in self.contracts.values()
            if contract.tool_key == raw_tool
        ]
        tool_has_unknown = (
            raw_tool in self.unknown_tools
            or any(contract.route_id not in self.boundaries for contract in tool_contracts)
        )

        boundary_rows: list[dict[str, Any]] = []
        if tool_has_unknown:
            predicted = raw_top_route
            reason = "unknown_endpoint_semantics_preserve"
        else:
            for contract in tool_contracts:
                boundary = self.boundaries[contract.route_id]
                distance = ellipsoid_distance(query_vector, boundary)
                boundary_rows.append(
                    {
                        "route_id": boundary.route_id,
                        "leaf": boundary.leaf,
                        "distance": distance,
                        "inside": distance <= 1.0,
                        "anisotropy": boundary.anisotropy,
                    }
                )
            if any(row["inside"] for row in boundary_rows):
                predicted = raw_top_route
                reason = "inside_registered_capability_ellipsoid"
            else:
                predicted = None
                reason = "outside_all_registered_capability_ellipsoids"

        return {
            "predicted": predicted,
            "raw_top_route": raw_top_route,
            "raw_top_score": raw_top_score,
            "raw_tool": raw_tool,
            "tool_has_unknown_leaf": tool_has_unknown,
            "boundary_rows": boundary_rows,
            "inside_boundary_count": sum(bool(row["inside"]) for row in boundary_rows),
            "reason": reason,
            "raw_ranked_routes": [
                {"route_id": route, "score": score}
                for route, score in raw_ranked
            ],
        }
