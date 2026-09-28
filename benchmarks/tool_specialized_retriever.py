"""Deterministic registry-grounded endpoint profiles for V6F experiment #406."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from benchmarks.schema_adb_baseline import compile_registry_contracts

Embedder = Callable[[list[str], bool], list[list[float]]]


@dataclass(frozen=True)
class EndpointProfile:
    route_id: str
    tool_key: str
    text: str


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _field_fact(field: Any) -> str:
    semantic = _clean(field.semantic_id or field.name)
    schema_type = _clean(field.json_schema.get("type")) if field.json_schema else ""
    parts = [semantic]
    if schema_type:
        parts.append(f"type={schema_type}")
    if field.unit:
        parts.append(f"unit={field.unit}")
    if field.unit_normalization is not None:
        parts.append(f"canonical_unit={field.unit_normalization.canonical_unit}")
        parts.append(f"dimension={field.unit_normalization.dimension}")
    if field.qualifiers:
        qualifiers = ",".join(
            f"{key}={value}"
            for key, value in sorted(field.qualifiers.items())
        )
        parts.append(f"qualifiers={qualifiers}")
    return " | ".join(parts)


def _parameter_fact(parameter: Any) -> str:
    schema_type = (
        _clean(parameter.json_schema.get("type"))
        if parameter.json_schema
        else ""
    )
    parts = [_clean(parameter.name)]
    if schema_type:
        parts.append(f"type={schema_type}")
    parts.append(f"required={str(bool(parameter.required)).lower()}")
    parts.append(f"location={parameter.location}")
    return " | ".join(parts)


def build_endpoint_profiles(registry: Any) -> tuple[EndpointProfile, ...]:
    contracts = compile_registry_contracts(registry)
    profiles: list[EndpointProfile] = []

    for tool in registry.tools():
        for endpoint in tool.endpoints:
            route_id = f"{tool.key}.{endpoint.name}"
            contract = contracts[route_id]
            if contract.leaf is None:
                raise ValueError(
                    f"V6F requires known operation semantics for {route_id}"
                )

            aliases = sorted(
                {
                    _clean(alias)
                    for alias in endpoint.operation_aliases
                    if _clean(alias)
                }
            )
            input_facts = sorted(
                {
                    _parameter_fact(parameter)
                    for parameter in endpoint.parameters
                }
            )
            output_facts = sorted(
                {
                    _field_fact(field)
                    for field in endpoint.output_fields
                    if not field.identifier
                }
            )
            semantic_ids = sorted(
                {
                    _clean(field.semantic_id)
                    for field in endpoint.output_fields
                    if not field.identifier and _clean(field.semantic_id)
                }
            )
            qualifiers = sorted(
                {
                    f"{key}={value}"
                    for field in endpoint.output_fields
                    for key, value in field.qualifiers.items()
                }
            )
            tags = [
                contract.leaf,
                contract.resource_anchor,
                *semantic_ids,
                *qualifiers,
            ]

            lines = [
                f"tool: {_clean(tool.key)}",
                f"tool_description: {_clean(tool.description)}",
                f"endpoint: {_clean(endpoint.name)}",
                f"function_description: {_clean(endpoint.description)}",
                (
                    "when_to_use: request asks to "
                    f"{contract.leaf} {contract.resource_anchor}"
                ),
                (
                    "operation_aliases: "
                    + "; ".join(aliases)
                    if aliases
                    else ""
                ),
                f"method: {contract.method or 'unknown'}",
                (
                    "read_only: "
                    + (
                        str(contract.read_only).lower()
                        if contract.read_only is not None
                        else "unknown"
                    )
                ),
                (
                    "destructive: "
                    + (
                        str(contract.destructive).lower()
                        if contract.destructive is not None
                        else "unknown"
                    )
                ),
                (
                    "input_semantics: "
                    + "; ".join(input_facts)
                    if input_facts
                    else ""
                ),
                (
                    "output_semantics: "
                    + "; ".join(output_facts)
                    if output_facts
                    else ""
                ),
                "tags: " + "; ".join(dict.fromkeys(tag for tag in tags if tag)),
            ]
            text = "\n".join(line for line in lines if line)
            if "limitations:" in text:
                raise AssertionError("V6F positive profile must not contain limitations")
            profiles.append(
                EndpointProfile(
                    route_id=route_id,
                    tool_key=str(tool.key),
                    text=text,
                )
            )

    return tuple(profiles)


def _normalize(vector: Iterable[float]) -> list[float]:
    values = [float(value) for value in vector]
    if not values:
        raise ValueError("embedding vector must not be empty")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("embedding vector must contain finite values")
    magnitude = math.sqrt(sum(value * value for value in values))
    if magnitude <= 0.0:
        raise ValueError("embedding vector must have non-zero norm")
    return [value / magnitude for value in values]


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("vectors must align")
    return sum(a * b for a, b in zip(left, right, strict=True))


class ToolSpecializedRouteRetriever:
    """Positive-only route retriever with no abstention or fallback semantics."""

    def __init__(self, registry: Any, embedder: Embedder) -> None:
        self.profiles = build_endpoint_profiles(registry)
        if not self.profiles:
            raise ValueError("V6F requires at least one registered endpoint")
        self.embedder = embedder

        vectors = embedder([profile.text for profile in self.profiles], False)
        if len(vectors) != len(self.profiles):
            raise ValueError("tool embedder returned the wrong profile count")
        self.profile_vectors = tuple(_normalize(vector) for vector in vectors)
        width = len(self.profile_vectors[0])
        if any(len(vector) != width for vector in self.profile_vectors):
            raise ValueError("tool profile embeddings must have one width")

    @property
    def route_ids(self) -> tuple[str, ...]:
        return tuple(profile.route_id for profile in self.profiles)

    def route(self, query: str) -> dict[str, Any]:
        query_vectors = self.embedder([str(query)], True)
        if len(query_vectors) != 1:
            raise ValueError("tool embedder must return one query vector")
        query_vector = _normalize(query_vectors[0])
        if len(query_vector) != len(self.profile_vectors[0]):
            raise ValueError("query/profile embedding widths must match")

        ranking = sorted(
            (
                (_cosine(query_vector, vector), profile.route_id)
                for profile, vector in zip(
                    self.profiles,
                    self.profile_vectors,
                    strict=True,
                )
            ),
            key=lambda item: (-item[0], item[1]),
        )
        top_score, predicted = ranking[0]
        second_score = ranking[1][0] if len(ranking) > 1 else top_score
        return {
            "predicted": predicted,
            "top_score": top_score,
            "top2_margin": top_score - second_score,
            "ranking": [
                {"route_id": route_id, "score": score}
                for score, route_id in ranking
            ],
        }
