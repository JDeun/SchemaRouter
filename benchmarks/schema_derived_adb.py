"""Schema-derived adaptive decision boundary baseline for experiment #383.

Research-only. Frozen BGE-M3 remains the sole positive route selector. Endpoint-specific
open-set boundaries are built at registration time from trusted schema metadata only.
The boundary may preserve the raw route or veto to NO_ROUTE; it never selects another route.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

BGE_MODEL = "BAAI/bge-m3"
BGE_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
SCHEMA_WEIGHT = 0.55
ACTION_WEIGHT = 0.45

ADB_MIN_VIEWS = 4
ADB_STEPS = 200
ADB_LEARNING_RATE = 0.05
ADB_BETA1 = 0.9
ADB_BETA2 = 0.999
ADB_EPS = 1e-8
ADB_INITIAL_DELTA_HAT = 0.0
ADB_SEED = 20260928


@dataclass(frozen=True)
class RouteContract:
    route_id: str
    tool_key: str
    read_only: bool | None
    destructive: bool | None
    method: str | None
    adapter: str | None
    data_contract: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class EndpointBoundary:
    route_id: str
    tool_key: str
    center: tuple[float, ...]
    radius: float
    view_count: int
    positive_views: tuple[str, ...]


def _normalize_text(text: str) -> str:
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = text.replace("_", " ").replace("-", " ")
    return " ".join(text.split())


def _schema_type(schema: dict[str, Any]) -> str:
    raw = schema.get("type")
    if isinstance(raw, str):
        base = raw
    elif isinstance(raw, list):
        base = "|".join(str(value) for value in raw)
    elif isinstance(schema.get("properties"), dict):
        base = "object"
    else:
        base = "unknown"
    if base == "array" and isinstance(schema.get("items"), dict):
        return f"array<{_schema_type(schema['items'])}>"
    return base


def _data_contract(endpoint: Any) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for parameter in endpoint.parameters:
        rows.append(
            {
                "role": "input",
                "name": str(parameter.name),
                "type": _schema_type(parameter.json_schema),
                "required": bool(parameter.required),
            }
        )
    for field in endpoint.output_fields:
        normalization = field.unit_normalization
        rows.append(
            {
                "role": "output",
                "name": str(field.name),
                "semantic_id": field.semantic_id,
                "type": _schema_type(field.json_schema),
                "source_unit": field.unit,
                "canonical_unit": (
                    normalization.canonical_unit
                    if normalization is not None
                    else None
                ),
                "dimension": (
                    normalization.dimension
                    if normalization is not None
                    else None
                ),
                "scale": normalization.scale if normalization is not None else None,
                "offset": normalization.offset if normalization is not None else None,
                "qualifiers": dict(field.qualifiers),
                "identifier": bool(field.identifier),
            }
        )
    return tuple(rows)


def compile_registry_contracts(registry: Any) -> dict[str, RouteContract]:
    contracts: dict[str, RouteContract] = {}
    for tool in registry.tools():
        adapter = tool.execution_metadata.get("adapter")
        for endpoint in tool.endpoints:
            route_id = f"{tool.key}.{endpoint.name}"
            contracts[route_id] = RouteContract(
                route_id=route_id,
                tool_key=str(tool.key),
                read_only=endpoint.read_only,
                destructive=endpoint.destructive,
                method=(str(endpoint.method).upper() if endpoint.method else None),
                adapter=(str(adapter) if isinstance(adapter, str) else None),
                data_contract=_data_contract(endpoint),
            )
    return contracts


def schema_positive_views(tool: Any, endpoint: Any) -> tuple[str, ...]:
    """Build the exact preregistered positive view bank from trusted schema metadata."""
    tool_description = str(tool.description or "").strip()
    endpoint_description = str(endpoint.description or "").strip()
    endpoint_name = _normalize_text(str(endpoint.name)).strip()
    aliases = [
        _normalize_text(str(alias)).strip()
        for alias in endpoint.operation_aliases
        if str(alias).strip()
    ]
    aliases_text = ", ".join(aliases)
    field_labels = [
        str(field.semantic_id or field.name).strip()
        for field in endpoint.output_fields
        if not field.identifier and str(field.semantic_id or field.name).strip()
    ]
    fields_text = ", ".join(dict.fromkeys(field_labels))

    candidates: list[str] = []
    if endpoint_description:
        candidates.extend(
            [
                endpoint_description,
                f"The user wants to {endpoint_description}.",
                f"Request: {endpoint_description}.",
            ]
        )
    if tool_description and endpoint_description:
        candidates.append(
            f"{tool_description}. Operation: {endpoint_description}."
        )
    if endpoint_name and endpoint_description:
        candidates.append(f"{endpoint_name}. {endpoint_description}.")
    if aliases_text and endpoint_description:
        candidates.append(f"{aliases_text}. {endpoint_description}.")
    if endpoint_description and fields_text:
        candidates.append(
            f"{endpoint_description}. Returned data: {fields_text}."
        )
    if tool_description and endpoint_description and fields_text:
        candidates.append(
            f"{tool_description}. The user wants to {endpoint_description}. "
            f"Returned data: {fields_text}."
        )

    deduped: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        normalized = " ".join(value.split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return tuple(deduped)


def _softplus(value: float) -> float:
    if value > 30.0:
        return value
    if value < -30.0:
        return math.exp(value)
    return math.log1p(math.exp(value))


def _sigmoid(value: float) -> float:
    if value >= 0:
        exp_neg = math.exp(-value)
        return 1.0 / (1.0 + exp_neg)
    exp_pos = math.exp(value)
    return exp_pos / (1.0 + exp_pos)


def learn_adb_radius(
    distances: list[float],
    *,
    steps: int = ADB_STEPS,
    learning_rate: float = ADB_LEARNING_RATE,
) -> float:
    """Optimize one scalar ADB radius using the preregistered boundary-loss protocol."""
    if not distances:
        raise ValueError("ADB radius requires at least one positive distance")
    if any((not math.isfinite(value) or value < 0.0) for value in distances):
        raise ValueError("ADB distances must be finite and non-negative")
    if steps <= 0 or learning_rate <= 0.0:
        raise ValueError("ADB optimizer configuration must be positive")

    delta_hat = ADB_INITIAL_DELTA_HAT
    first_moment = 0.0
    second_moment = 0.0

    for step in range(1, steps + 1):
        radius = _softplus(delta_hat)
        # dL / d radius = +1 for points inside/on boundary, -1 for outside.
        mean_radius_gradient = sum(
            1.0 if distance <= radius else -1.0
            for distance in distances
        ) / len(distances)
        gradient = mean_radius_gradient * _sigmoid(delta_hat)

        first_moment = (
            ADB_BETA1 * first_moment
            + (1.0 - ADB_BETA1) * gradient
        )
        second_moment = (
            ADB_BETA2 * second_moment
            + (1.0 - ADB_BETA2) * gradient * gradient
        )
        first_unbiased = first_moment / (1.0 - ADB_BETA1**step)
        second_unbiased = second_moment / (1.0 - ADB_BETA2**step)
        delta_hat -= learning_rate * first_unbiased / (
            math.sqrt(second_unbiased) + ADB_EPS
        )

    radius = _softplus(delta_hat)
    if not math.isfinite(radius) or radius <= 0.0:
        raise ValueError("learned ADB radius must be finite and positive")
    return radius


def _normalize_vector(vector: Iterable[float]) -> list[float]:
    values = [float(value) for value in vector]
    if not values:
        raise ValueError("embedding vector must not be empty")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("embedding vector contains non-finite values")
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0.0:
        raise ValueError("embedding vector must have non-zero norm")
    return [value / norm for value in values]


def _to_vectors(raw: Iterable[Iterable[float]]) -> list[list[float]]:
    vectors = [_normalize_vector(vector) for vector in raw]
    if not vectors:
        raise ValueError("embedder returned no vectors")
    width = len(vectors[0])
    if any(len(vector) != width for vector in vectors):
        raise ValueError("embedder returned inconsistent dimensions")
    return vectors


def _mean_center(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        raise ValueError("center requires at least one vector")
    width = len(vectors[0])
    if any(len(vector) != width for vector in vectors):
        raise ValueError("center vectors must align")
    mean = [
        sum(vector[index] for vector in vectors) / len(vectors)
        for index in range(width)
    ]
    return _normalize_vector(mean)


def _euclidean(left: Iterable[float], right: Iterable[float]) -> float:
    left_values = [float(value) for value in left]
    right_values = [float(value) for value in right]
    if len(left_values) != len(right_values) or not left_values:
        raise ValueError("distance vectors must align")
    return math.sqrt(
        sum(
            (a - b) * (a - b)
            for a, b in zip(left_values, right_values, strict=True)
        )
    )


def _cosine(left: Iterable[float], right: Iterable[float]) -> float:
    left_values = _normalize_vector(left)
    right_values = _normalize_vector(right)
    return max(
        -1.0,
        min(
            1.0,
            sum(
                a * b
                for a, b in zip(left_values, right_values, strict=True)
            ),
        ),
    )


def _schema_text(tool: Any, endpoint: Any) -> str:
    route_id = f"{tool.key}.{endpoint.name}"
    field_labels = [
        field.semantic_id or field.name
        for field in endpoint.output_fields
        if not field.identifier
    ]
    parts = [route_id, tool.description.strip(), endpoint.description.strip()]
    if field_labels:
        parts.append("Fields: " + ", ".join(dict.fromkeys(field_labels)))
    return "\n".join(part for part in parts if part)


def _action_text(endpoint: Any) -> str:
    operation_name = endpoint.name.replace("_", " ").replace("-", " ")
    aliases = list(endpoint.operation_aliases)
    fallback = endpoint.description.strip() if not aliases else ""
    return "\n".join(
        dict.fromkeys(
            part
            for part in [operation_name, *aliases, fallback]
            if part
        )
    )


class SchemaDerivedADBRouter:
    """Frozen BGE positive routing plus schema-derived endpoint ADB veto."""

    def __init__(self, registry: Any, embedder: Any) -> None:
        self.registry = registry
        self.embedder = embedder
        self.contracts = compile_registry_contracts(registry)

        route_specs: dict[str, tuple[str, str]] = {}
        endpoint_lookup: dict[str, tuple[Any, Any]] = {}
        for tool in registry.tools():
            for endpoint in tool.endpoints:
                route_id = f"{tool.key}.{endpoint.name}"
                route_specs[route_id] = (
                    _schema_text(tool, endpoint),
                    _action_text(endpoint),
                )
                endpoint_lookup[route_id] = (tool, endpoint)

        if set(route_specs) != set(self.contracts):
            raise ValueError("route and contract sets differ")
        self.route_ids = tuple(sorted(route_specs))

        route_texts = [
            *(route_specs[route][0] for route in self.route_ids),
            *(route_specs[route][1] for route in self.route_ids),
        ]
        route_vectors = _to_vectors(embedder(route_texts))
        route_count = len(self.route_ids)
        if len(route_vectors) != route_count * 2:
            raise ValueError("unexpected route embedding count")
        self.schema_vectors = dict(
            zip(self.route_ids, route_vectors[:route_count], strict=True)
        )
        self.action_vectors = dict(
            zip(self.route_ids, route_vectors[route_count:], strict=True)
        )

        views_by_route = {
            route_id: schema_positive_views(*endpoint_lookup[route_id])
            for route_id in self.route_ids
        }
        flat_views: list[str] = []
        spans: dict[str, tuple[int, int]] = {}
        for route_id in self.route_ids:
            views = views_by_route[route_id]
            if len(views) < ADB_MIN_VIEWS:
                continue
            start = len(flat_views)
            flat_views.extend(views)
            spans[route_id] = (start, len(flat_views))

        embedded_views = (
            _to_vectors(embedder(flat_views))
            if flat_views
            else []
        )
        if len(embedded_views) != len(flat_views):
            raise ValueError("unexpected positive-view embedding count")

        boundaries: dict[str, EndpointBoundary | None] = {}
        for route_id in self.route_ids:
            views = views_by_route[route_id]
            span = spans.get(route_id)
            if span is None:
                boundaries[route_id] = None
                continue
            start, end = span
            vectors = embedded_views[start:end]
            center = _mean_center(vectors)
            distances = [
                _euclidean(vector, center)
                for vector in vectors
            ]
            radius = learn_adb_radius(distances)
            boundaries[route_id] = EndpointBoundary(
                route_id=route_id,
                tool_key=self.contracts[route_id].tool_key,
                center=tuple(center),
                radius=radius,
                view_count=len(views),
                positive_views=views,
            )
        self.boundaries = boundaries

    def _rank_raw(self, query_vector: list[float]) -> list[tuple[str, float]]:
        scored: list[tuple[str, float]] = []
        for route_id in self.route_ids:
            score = (
                SCHEMA_WEIGHT
                * _cosine(query_vector, self.schema_vectors[route_id])
                + ACTION_WEIGHT
                * _cosine(query_vector, self.action_vectors[route_id])
            )
            scored.append((route_id, score))
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored

    def route(self, query: str) -> dict[str, Any]:
        query_vector = _to_vectors(self.embedder([query]))[0]
        raw_ranked = self._rank_raw(query_vector)
        raw_top_route, raw_top_score = raw_ranked[0]
        raw_tool = self.contracts[raw_top_route].tool_key

        tool_routes = [
            route_id
            for route_id in self.route_ids
            if self.contracts[route_id].tool_key == raw_tool
        ]
        missing_boundary = any(
            self.boundaries[route_id] is None
            for route_id in tool_routes
        )

        diagnostics: list[dict[str, Any]] = []
        if missing_boundary:
            predicted = raw_top_route
            reason = "unknown_boundary_preserve"
            inside_routes: list[str] = []
        else:
            inside_routes = []
            for route_id in tool_routes:
                boundary = self.boundaries[route_id]
                if boundary is None:
                    raise AssertionError("missing boundary after completeness check")
                distance = _euclidean(query_vector, boundary.center)
                ratio = distance / boundary.radius
                inside = distance <= boundary.radius
                if inside:
                    inside_routes.append(route_id)
                diagnostics.append(
                    {
                        "route_id": route_id,
                        "distance": distance,
                        "radius": boundary.radius,
                        "boundary_ratio": ratio,
                        "inside": inside,
                        "view_count": boundary.view_count,
                    }
                )
            if inside_routes:
                predicted = raw_top_route
                reason = "inside_registered_boundary_preserve"
            else:
                predicted = None
                reason = "outside_all_registered_boundaries"

        return {
            "predicted": predicted,
            "raw_top_route": raw_top_route,
            "raw_top_score": raw_top_score,
            "raw_tool": raw_tool,
            "tool_routes": tool_routes,
            "inside_routes": inside_routes,
            "boundary_diagnostics": diagnostics,
            "missing_boundary": missing_boundary,
            "reason": reason,
            "raw_ranked_routes": [
                {"route_id": route_id, "score": score}
                for route_id, score in raw_ranked
            ],
        }
