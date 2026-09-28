# ruff: noqa: E501
"""Schema-derived non-parametric kNN capability membership for experiment #401.

Frozen BGE-M3 remains the sole positive route selector. Local-neighborhood
evidence may preserve that registered winner or veto to NO_ROUTE only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from benchmarks.schema_adb_baseline import (
    ACTION_WEIGHT,
    SCHEMA_WEIGHT,
    _action_text,
    _cosine,
    _schema_text,
    _to_vectors,
    compile_registry_contracts,
)
from benchmarks.schema_hard_negative_ellipsoid import hard_negative_texts

K_NEIGHBORS = 3

BACKGROUND_ANCHORS = (
    "sports scores, team standings, and game results",
    "travel itineraries, flights, hotels, and tourist attractions",
    "restaurants, recipes, cooking, and food recommendations",
    "medical symptoms, diagnosis, treatment, and medications",
    "legal advice, laws, contracts, and court procedures",
    "software programming, debugging, and source code",
    "translation, grammar, and language learning",
    "music, movies, games, and entertainment recommendations",
    "shopping, consumer products, prices, and product reviews",
    "news, politics, elections, and current events",
    "maps, locations, driving directions, and navigation",
    "email, messaging, and social media communication",
    "image generation, photography, and visual design",
    "mathematics, calculations, and homework",
    "personal productivity, notes, and document writing",
    "general knowledge, trivia, and casual conversation",
)


@dataclass(frozen=True)
class EvidencePoint:
    evidence_id: str
    vector: tuple[float, ...]


@dataclass(frozen=True)
class ToolKNNModel:
    tool_key: str
    positive_points: tuple[EvidencePoint, ...]
    complement_points: tuple[EvidencePoint, ...]

    @property
    def width(self) -> int:
        return len(self.positive_points[0].vector)


def _dedupe_rows(rows: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for evidence_id, text in rows:
        if text in seen:
            continue
        seen.add(text)
        result.append((evidence_id, text))
    return result


def _points(
    rows: list[tuple[str, str]],
    vectors: list[list[float]],
) -> tuple[EvidencePoint, ...]:
    if len(rows) != len(vectors):
        raise ValueError("evidence rows and vectors must align")
    return tuple(
        EvidencePoint(
            evidence_id=evidence_id,
            vector=tuple(float(value) for value in vector),
        )
        for (evidence_id, _), vector in zip(rows, vectors, strict=True)
    )


def knn_mean_cosine_distance(
    vector: list[float],
    points: tuple[EvidencePoint, ...],
    *,
    k: int = K_NEIGHBORS,
) -> tuple[float, tuple[tuple[str, float], ...]]:
    if k <= 0:
        raise ValueError("k must be positive")
    if len(points) < k:
        raise ValueError("evidence bank must contain at least k points")

    ranked = sorted(
        (
            (point.evidence_id, 1.0 - _cosine(vector, list(point.vector)))
            for point in points
        ),
        key=lambda item: (item[1], item[0]),
    )
    nearest = tuple(ranked[:k])
    mean_distance = sum(distance for _, distance in nearest) / k
    return mean_distance, nearest


class SchemaKNNMembershipRouter:
    """Frozen BGE routing plus local non-parametric membership veto."""

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

        background_vectors = _to_vectors(embedder(list(BACKGROUND_ANCHORS)))
        if len(background_vectors) != len(BACKGROUND_ANCHORS):
            raise ValueError("unexpected background embedding count")
        self.background_points = tuple(
            EvidencePoint(
                evidence_id=f"background::{index:02d}",
                vector=tuple(float(value) for value in vector),
            )
            for index, vector in enumerate(background_vectors, start=1)
        )

        contracts_by_tool: dict[str, list[Any]] = {}
        for contract in self.contracts.values():
            contracts_by_tool.setdefault(contract.tool_key, []).append(contract)

        self.unknown_tools: set[str] = set()
        self.models: dict[str, ToolKNNModel] = {}

        for tool_key, contracts in contracts_by_tool.items():
            if any(
                contract.leaf is None or len(contract.synthetic_positives) != 18
                for contract in contracts
            ):
                self.unknown_tools.add(tool_key)
                continue

            supported_leaves = {str(contract.leaf) for contract in contracts}
            positive_rows: list[tuple[str, str]] = []
            complement_rows: list[tuple[str, str]] = []

            for contract in contracts:
                positive_rows.extend(
                    (
                        f"{contract.route_id}::positive::{index:02d}",
                        text,
                    )
                    for index, text in enumerate(
                        contract.synthetic_positives,
                        start=1,
                    )
                )
                negatives = hard_negative_texts(
                    resource_anchor=contract.resource_anchor,
                    supported_leaves=supported_leaves,
                )
                if not negatives:
                    self.unknown_tools.add(tool_key)
                    break
                complement_rows.extend(
                    (
                        f"{contract.route_id}::complement::{index:03d}",
                        text,
                    )
                    for index, text in enumerate(negatives, start=1)
                )

            if tool_key in self.unknown_tools:
                continue

            positive_rows = _dedupe_rows(positive_rows)
            complement_rows = _dedupe_rows(complement_rows)
            if (
                len(positive_rows) < K_NEIGHBORS
                or len(complement_rows) < K_NEIGHBORS
            ):
                self.unknown_tools.add(tool_key)
                continue

            all_rows = [*positive_rows, *complement_rows]
            vectors = _to_vectors(
                self.embedder([text for _, text in all_rows])
            )
            positive_count = len(positive_rows)
            positive_vectors = vectors[:positive_count]
            complement_vectors = vectors[positive_count:]

            self.models[tool_key] = ToolKNNModel(
                tool_key=tool_key,
                positive_points=_points(positive_rows, positive_vectors),
                complement_points=_points(complement_rows, complement_vectors),
            )

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

        if raw_tool in self.unknown_tools or raw_tool not in self.models:
            predicted = raw_top_route
            reason = "unknown_tool_knn_preserve"
            d_pos = None
            d_comp = None
            d_bg = None
            nearest_pos = ()
            nearest_comp = ()
            nearest_bg = ()
        else:
            model = self.models[raw_tool]
            d_pos, nearest_pos = knn_mean_cosine_distance(
                query_vector,
                model.positive_points,
            )
            d_comp, nearest_comp = knn_mean_cosine_distance(
                query_vector,
                model.complement_points,
            )
            d_bg, nearest_bg = knn_mean_cosine_distance(
                query_vector,
                self.background_points,
            )

            if d_bg < d_pos:
                predicted = None
                reason = "background_neighborhood_closer"
            elif d_comp < d_pos:
                predicted = None
                reason = "complement_neighborhood_closer"
            else:
                predicted = raw_top_route
                reason = "registered_neighborhood_closer"

        return {
            "predicted": predicted,
            "raw_top_route": raw_top_route,
            "raw_top_score": raw_top_score,
            "raw_tool": raw_tool,
            "tool_has_unknown_knn": raw_tool in self.unknown_tools,
            "d_pos": d_pos,
            "d_comp": d_comp,
            "d_bg": d_bg,
            "nearest_positive": [
                {"evidence_id": evidence_id, "distance": distance}
                for evidence_id, distance in nearest_pos
            ],
            "nearest_complement": [
                {"evidence_id": evidence_id, "distance": distance}
                for evidence_id, distance in nearest_comp
            ],
            "nearest_background": [
                {"evidence_id": evidence_id, "distance": distance}
                for evidence_id, distance in nearest_bg
            ],
            "reason": reason,
            "raw_ranked_routes": [
                {"route_id": route_id, "score": score}
                for route_id, score in raw_ranked
            ],
        }
