# ruff: noqa: E501
"""Schema-derived tied-Gaussian density-ratio membership for experiment #397.

Frozen BGE-M3 remains the sole positive route selector. Tool-local density
evidence may preserve the raw registered winner or veto to NO_ROUTE only.
"""

from __future__ import annotations

import math
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

VARIANCE_FLOOR = 1e-6


@dataclass(frozen=True)
class ToolDensityModel:
    tool_key: str
    positive_mean: tuple[float, ...]
    negative_mean: tuple[float, ...]
    variance: tuple[float, ...]
    positive_count: int
    negative_count: int

    @property
    def width(self) -> int:
        return len(self.variance)


def _mean(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        raise ValueError("mean requires vectors")
    width = len(vectors[0])
    if width == 0 or any(len(vector) != width for vector in vectors):
        raise ValueError("vectors must share a non-zero width")
    return [
        sum(vector[index] for vector in vectors) / len(vectors)
        for index in range(width)
    ]


def fit_tied_diagonal_density(
    *,
    tool_key: str,
    positives: list[list[float]],
    negatives: list[list[float]],
) -> ToolDensityModel:
    positive_vectors = _to_vectors(positives)
    negative_vectors = _to_vectors(negatives)
    width = len(positive_vectors[0])
    if any(len(vector) != width for vector in negative_vectors):
        raise ValueError("positive and negative embedding widths must match")

    positive_mean = _mean(positive_vectors)
    negative_mean = _mean(negative_vectors)
    denominator = max(1, len(positive_vectors) + len(negative_vectors) - 2)

    variance: list[float] = []
    for index in range(width):
        total = sum(
            (vector[index] - positive_mean[index]) ** 2
            for vector in positive_vectors
        )
        total += sum(
            (vector[index] - negative_mean[index]) ** 2
            for vector in negative_vectors
        )
        variance.append(max(VARIANCE_FLOOR, total / denominator))

    return ToolDensityModel(
        tool_key=tool_key,
        positive_mean=tuple(positive_mean),
        negative_mean=tuple(negative_mean),
        variance=tuple(variance),
        positive_count=len(positive_vectors),
        negative_count=len(negative_vectors),
    )


def squared_mahalanobis(
    vector: list[float],
    mean: tuple[float, ...],
    variance: tuple[float, ...],
) -> float:
    if len(vector) != len(mean) or len(vector) != len(variance) or not vector:
        raise ValueError("density vectors must align")
    value = 0.0
    for item, center, var in zip(vector, mean, variance, strict=True):
        if var <= 0.0 or not math.isfinite(var):
            raise ValueError("variance must be finite and positive")
        value += (float(item) - float(center)) ** 2 / float(var)
    return value


def density_ratio(
    vector: list[float],
    model: ToolDensityModel,
) -> tuple[float, float, float]:
    d_positive_sq = squared_mahalanobis(
        vector,
        model.positive_mean,
        model.variance,
    )
    d_negative_sq = squared_mahalanobis(
        vector,
        model.negative_mean,
        model.variance,
    )
    ratio = 0.5 * (d_negative_sq - d_positive_sq)
    return ratio, d_positive_sq, d_negative_sq


class SchemaDensityRatioRouter:
    """Frozen BGE routing plus schema-derived tool-level density-ratio veto."""

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
        self.models: dict[str, ToolDensityModel] = {}

        for tool_key, contracts in contracts_by_tool.items():
            if any(
                contract.leaf is None or len(contract.synthetic_positives) != 18
                for contract in contracts
            ):
                self.unknown_tools.add(tool_key)
                continue

            supported_leaves = {str(contract.leaf) for contract in contracts}
            positive_texts: list[str] = []
            negative_texts: list[str] = []
            for contract in contracts:
                positive_texts.extend(contract.synthetic_positives)
                negatives = hard_negative_texts(
                    resource_anchor=contract.resource_anchor,
                    supported_leaves=supported_leaves,
                )
                if not negatives:
                    self.unknown_tools.add(tool_key)
                    break
                negative_texts.extend(negatives)

            if tool_key in self.unknown_tools:
                continue

            positive_texts = list(dict.fromkeys(positive_texts))
            negative_texts = list(dict.fromkeys(negative_texts))
            if not positive_texts or not negative_texts:
                self.unknown_tools.add(tool_key)
                continue

            vectors = _to_vectors(self.embedder([*positive_texts, *negative_texts]))
            positive_vectors = vectors[: len(positive_texts)]
            negative_vectors = vectors[len(positive_texts) :]
            self.models[tool_key] = fit_tied_diagonal_density(
                tool_key=tool_key,
                positives=positive_vectors,
                negatives=negative_vectors,
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
            reason = "unknown_tool_density_preserve"
            ratio = None
            d_positive_sq = None
            d_negative_sq = None
        else:
            model = self.models[raw_tool]
            ratio, d_positive_sq, d_negative_sq = density_ratio(
                query_vector,
                model,
            )
            if ratio >= 0.0:
                predicted = raw_top_route
                reason = "registered_density_dominates"
            else:
                predicted = None
                reason = "complement_density_dominates"

        return {
            "predicted": predicted,
            "raw_top_route": raw_top_route,
            "raw_top_score": raw_top_score,
            "raw_tool": raw_tool,
            "tool_has_unknown_density": raw_tool in self.unknown_tools,
            "density_ratio": ratio,
            "positive_mahalanobis_sq": d_positive_sq,
            "negative_mahalanobis_sq": d_negative_sq,
            "reason": reason,
            "raw_ranked_routes": [
                {"route_id": route_id, "score": score}
                for route_id, score in raw_ranked
            ],
        }
