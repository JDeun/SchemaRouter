# ruff: noqa: E501
"""Schema-derived component Gaussian-mixture density ratio for experiment #399.

Frozen BGE-M3 remains the sole positive route selector. Registry-compiled
mixture evidence may preserve the raw registered winner or veto to NO_ROUTE,
but it cannot select or switch an endpoint.
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
    _cosine,
    _schema_text,
    _to_vectors,
    compile_registry_contracts,
)

VARIANCE_FLOOR = 1e-6


@dataclass(frozen=True)
class GaussianComponent:
    component_id: str
    mean: tuple[float, ...]
    sample_count: int


@dataclass(frozen=True)
class ToolMixtureDensityModel:
    tool_key: str
    positive_components: tuple[GaussianComponent, ...]
    negative_components: tuple[GaussianComponent, ...]
    variance: tuple[float, ...]
    positive_sample_count: int
    negative_sample_count: int

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


def _component(
    component_id: str,
    vectors: list[list[float]],
) -> tuple[GaussianComponent, list[list[float]]]:
    rows = _to_vectors(vectors)
    center = _mean(rows)
    return (
        GaussianComponent(
            component_id=component_id,
            mean=tuple(center),
            sample_count=len(rows),
        ),
        rows,
    )


def fit_component_mixture_density(
    *,
    tool_key: str,
    positive_components: list[tuple[str, list[list[float]]]],
    negative_components: list[tuple[str, list[list[float]]]],
) -> ToolMixtureDensityModel:
    if not positive_components or not negative_components:
        raise ValueError("positive and negative components are required")

    fitted_positive: list[GaussianComponent] = []
    fitted_negative: list[GaussianComponent] = []
    residual_groups: list[tuple[GaussianComponent, list[list[float]]]] = []

    for component_id, vectors in positive_components:
        component, rows = _component(component_id, vectors)
        fitted_positive.append(component)
        residual_groups.append((component, rows))

    for component_id, vectors in negative_components:
        component, rows = _component(component_id, vectors)
        fitted_negative.append(component)
        residual_groups.append((component, rows))

    width = fitted_positive[0].sample_count and len(fitted_positive[0].mean)
    if width <= 0:
        raise ValueError("component width must be positive")
    if any(len(component.mean) != width for component in [*fitted_positive, *fitted_negative]):
        raise ValueError("component widths must match")

    total_samples = sum(
        component.sample_count
        for component in [*fitted_positive, *fitted_negative]
    )
    total_components = len(fitted_positive) + len(fitted_negative)
    denominator = max(1, total_samples - total_components)

    variance: list[float] = []
    for index in range(width):
        total = 0.0
        for component, rows in residual_groups:
            center = component.mean[index]
            total += sum((row[index] - center) ** 2 for row in rows)
        variance.append(max(VARIANCE_FLOOR, total / denominator))

    return ToolMixtureDensityModel(
        tool_key=tool_key,
        positive_components=tuple(fitted_positive),
        negative_components=tuple(fitted_negative),
        variance=tuple(variance),
        positive_sample_count=sum(component.sample_count for component in fitted_positive),
        negative_sample_count=sum(component.sample_count for component in fitted_negative),
    )


def squared_mahalanobis(
    vector: list[float],
    mean: tuple[float, ...],
    variance: tuple[float, ...],
) -> float:
    if len(vector) != len(mean) or len(vector) != len(variance) or not vector:
        raise ValueError("mixture vectors must align")
    value = 0.0
    for item, center, var in zip(vector, mean, variance, strict=True):
        if var <= 0.0 or not math.isfinite(var):
            raise ValueError("variance must be finite and positive")
        value += (float(item) - float(center)) ** 2 / float(var)
    return value


def _logsumexp(values: list[float]) -> float:
    if not values:
        raise ValueError("logsumexp requires values")
    maximum = max(values)
    return maximum + math.log(sum(math.exp(value - maximum) for value in values))


def mixture_log_evidence(
    vector: list[float],
    components: tuple[GaussianComponent, ...],
    variance: tuple[float, ...],
) -> tuple[float, float]:
    if not components:
        raise ValueError("mixture components are required")
    component_evidence = [
        -0.5 * squared_mahalanobis(vector, component.mean, variance)
        for component in components
    ]
    mixture = _logsumexp(component_evidence) - math.log(len(component_evidence))
    return mixture, max(component_evidence)


def mixture_density_ratio(
    vector: list[float],
    model: ToolMixtureDensityModel,
) -> tuple[float, float, float, float, float]:
    positive_log, best_positive = mixture_log_evidence(
        vector,
        model.positive_components,
        model.variance,
    )
    negative_log, best_negative = mixture_log_evidence(
        vector,
        model.negative_components,
        model.variance,
    )
    return (
        positive_log - negative_log,
        positive_log,
        negative_log,
        best_positive,
        best_negative,
    )


def _negative_component_texts(
    *,
    resource_anchor: str,
    supported_leaves: set[str],
) -> list[tuple[str, tuple[str, ...]]]:
    if not resource_anchor or not supported_leaves:
        return []
    rows: list[tuple[str, tuple[str, ...]]] = []
    for leaf in ACTION_PHRASES:
        if leaf in supported_leaves:
            continue
        texts = tuple(
            f"{ACTION_PHRASES[leaf][language]}: {resource_anchor}"
            for language in LANGUAGES
        )
        rows.append((leaf, texts))
    return rows


class SchemaComponentMixtureDensityRouter:
    """Frozen BGE route authority plus component-preserving density veto."""

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
        self.models: dict[str, ToolMixtureDensityModel] = {}

        for tool_key, contracts in contracts_by_tool.items():
            if any(
                contract.leaf is None or len(contract.synthetic_positives) != 18
                for contract in contracts
            ):
                self.unknown_tools.add(tool_key)
                continue

            supported_leaves = {str(contract.leaf) for contract in contracts}
            positive_text_components: list[tuple[str, tuple[str, ...]]] = []
            negative_text_components: list[tuple[str, tuple[str, ...]]] = []

            for contract in contracts:
                positive_text_components.append(
                    (contract.route_id, tuple(contract.synthetic_positives))
                )
                negatives = _negative_component_texts(
                    resource_anchor=contract.resource_anchor,
                    supported_leaves=supported_leaves,
                )
                if not negatives:
                    self.unknown_tools.add(tool_key)
                    break
                negative_text_components.extend(
                    (
                        f"{contract.route_id}::{leaf}",
                        texts,
                    )
                    for leaf, texts in negatives
                )

            if tool_key in self.unknown_tools:
                continue

            all_texts = [
                text
                for _, texts in [*positive_text_components, *negative_text_components]
                for text in texts
            ]
            vectors = _to_vectors(self.embedder(all_texts))
            cursor = 0

            positive_vector_components: list[tuple[str, list[list[float]]]] = []
            for component_id, texts in positive_text_components:
                count = len(texts)
                positive_vector_components.append(
                    (component_id, vectors[cursor : cursor + count])
                )
                cursor += count

            negative_vector_components: list[tuple[str, list[list[float]]]] = []
            for component_id, texts in negative_text_components:
                count = len(texts)
                negative_vector_components.append(
                    (component_id, vectors[cursor : cursor + count])
                )
                cursor += count

            if cursor != len(vectors):
                raise ValueError("component embedding partition drifted")

            self.models[tool_key] = fit_component_mixture_density(
                tool_key=tool_key,
                positive_components=positive_vector_components,
                negative_components=negative_vector_components,
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
            reason = "unknown_tool_mixture_preserve"
            ratio = None
            positive_log = None
            negative_log = None
            best_positive = None
            best_negative = None
        else:
            model = self.models[raw_tool]
            (
                ratio,
                positive_log,
                negative_log,
                best_positive,
                best_negative,
            ) = mixture_density_ratio(query_vector, model)
            if ratio >= 0.0:
                predicted = raw_top_route
                reason = "registered_mixture_dominates"
            else:
                predicted = None
                reason = "complement_mixture_dominates"

        return {
            "predicted": predicted,
            "raw_top_route": raw_top_route,
            "raw_top_score": raw_top_score,
            "raw_tool": raw_tool,
            "tool_has_unknown_mixture": raw_tool in self.unknown_tools,
            "mixture_ratio": ratio,
            "positive_log_mixture": positive_log,
            "negative_log_mixture": negative_log,
            "best_positive_component_evidence": best_positive,
            "best_negative_component_evidence": best_negative,
            "reason": reason,
            "raw_ranked_routes": [
                {"route_id": route_id, "score": score}
                for route_id, score in raw_ranked
            ],
        }
