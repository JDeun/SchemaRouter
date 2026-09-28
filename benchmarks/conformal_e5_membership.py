"""External multilingual-E5 catalog-membership signal for V6G / #412."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from benchmarks.schema_adb_baseline import (
    ACTION_WEIGHT,
    SCHEMA_WEIGHT,
    _action_text,
    _schema_text,
)

E5_MODEL = "intfloat/multilingual-e5-base"
E5_REVISION = "d13f1b27baf31030b7fd040960d60d909913633f"
CONFORMAL_ALPHA = 0.01

Embedder = Callable[[list[str]], list[list[float]]]


@dataclass(frozen=True)
class E0Document:
    route_id: str
    text: str


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def build_e0_documents(registry: Any) -> tuple[E0Document, ...]:
    """Compile the frozen V6G E0 retrieval documents from trusted metadata only."""
    rows: list[E0Document] = []
    for tool in sorted(registry.tools(), key=lambda item: str(item.key)):
        for endpoint in sorted(tool.endpoints, key=lambda item: str(item.name)):
            route_id = f"{tool.key}.{endpoint.name}"
            parameters = sorted(
                {
                    _clean(parameter.name)
                    for parameter in endpoint.parameters
                    if _clean(parameter.name)
                }
            )
            outputs = sorted(
                {
                    _clean(field.semantic_id or field.name)
                    for field in endpoint.output_fields
                    if not field.identifier and _clean(field.semantic_id or field.name)
                }
            )
            parts = [
                _clean(endpoint.name).replace("_", " ").replace("-", " "),
                _clean(endpoint.description),
            ]
            if parameters:
                parts.append("inputs: " + ", ".join(parameters))
            if outputs:
                parts.append("outputs: " + ", ".join(outputs))
            text = "\n".join(part for part in parts if part)
            if not text:
                raise ValueError(f"empty E0 document for {route_id}")
            rows.append(E0Document(route_id=route_id, text=text))
    if not rows:
        raise ValueError("V6G requires at least one registered endpoint")
    return tuple(rows)


def _normalize(vector: Iterable[float]) -> list[float]:
    values = [float(value) for value in vector]
    if not values or any(not math.isfinite(value) for value in values):
        raise ValueError("embedding vector must be finite and non-empty")
    norm = math.sqrt(sum(value * value for value in values))
    if norm <= 0.0:
        raise ValueError("embedding vector must have non-zero norm")
    return [value / norm for value in values]


def _vectors(raw: Iterable[Iterable[float]]) -> list[list[float]]:
    vectors = [_normalize(vector) for vector in raw]
    if not vectors:
        raise ValueError("embedder returned no vectors")
    width = len(vectors[0])
    if any(len(vector) != width for vector in vectors):
        raise ValueError("embedding widths must match")
    return vectors


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must align")
    return sum(a * b for a, b in zip(left, right, strict=True))


class E5CatalogMembershipScorer:
    """Global catalog score only; E5 never receives positive route authority."""

    def __init__(self, registry: Any, embedder: Embedder) -> None:
        self.documents = build_e0_documents(registry)
        self.embedder = embedder
        vectors = _vectors(
            embedder([f"passage: {document.text}" for document in self.documents])
        )
        if len(vectors) != len(self.documents):
            raise ValueError("unexpected E0 embedding count")
        self.document_vectors = tuple(vectors)

    def score(self, query: str) -> dict[str, Any]:
        vector = _vectors(self.embedder([f"query: {query}"]))[0]
        ranked = sorted(
            (
                (_cosine(vector, document_vector), document.route_id)
                for document, document_vector in zip(
                    self.documents,
                    self.document_vectors,
                    strict=True,
                )
            ),
            key=lambda item: (-item[0], item[1]),
        )
        score, diagnostic_route = ranked[0]
        return {
            "catalog_score": score,
            "diagnostic_e5_top_route": diagnostic_route,
        }


def unsupported_conformal_p_value(
    observed_score: float,
    calibration_unsupported_scores: Iterable[float],
) -> float:
    """One-sided p-value under the unsupported-request null."""
    values = [float(value) for value in calibration_unsupported_scores]
    if not values:
        raise ValueError("unsupported calibration scores are required")
    if not math.isfinite(observed_score) or any(
        not math.isfinite(value) for value in values
    ):
        raise ValueError("scores must be finite")
    count = sum(value >= observed_score for value in values)
    return (1.0 + count) / (len(values) + 1.0)


def conformal_accept(
    observed_score: float,
    calibration_unsupported_scores: Iterable[float],
    *,
    alpha: float = CONFORMAL_ALPHA,
) -> tuple[bool, float]:
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0,1)")
    p_value = unsupported_conformal_p_value(
        observed_score,
        calibration_unsupported_scores,
    )
    return p_value <= alpha, p_value


class FrozenBGERawRetriever:
    """Frozen BGE positive endpoint selector used by V6G."""

    def __init__(self, registry: Any, embedder: Embedder) -> None:
        self.embedder = embedder
        specs: dict[str, tuple[str, str]] = {}
        for tool in registry.tools():
            for endpoint in tool.endpoints:
                route_id = f"{tool.key}.{endpoint.name}"
                specs[route_id] = (
                    _schema_text(tool, endpoint),
                    _action_text(endpoint),
                )
        self.route_ids = tuple(sorted(specs))
        count = len(self.route_ids)
        vectors = _vectors(
            embedder(
                [
                    *(specs[route][0] for route in self.route_ids),
                    *(specs[route][1] for route in self.route_ids),
                ]
            )
        )
        if len(vectors) != count * 2:
            raise ValueError("unexpected BGE route embedding count")
        self.schema_vectors = dict(
            zip(self.route_ids, vectors[:count], strict=True)
        )
        self.action_vectors = dict(
            zip(self.route_ids, vectors[count:], strict=True)
        )

    def route(self, query: str) -> dict[str, Any]:
        query_vector = _vectors(self.embedder([query]))[0]
        ranking = sorted(
            (
                (
                    route_id,
                    SCHEMA_WEIGHT
                    * _cosine(query_vector, self.schema_vectors[route_id])
                    + ACTION_WEIGHT
                    * _cosine(query_vector, self.action_vectors[route_id]),
                )
                for route_id in self.route_ids
            ),
            key=lambda item: (-item[1], item[0]),
        )
        route_id, score = ranking[0]
        return {
            "raw_top_route": route_id,
            "raw_top_score": score,
            "ranking": [
                {"route_id": route, "score": value}
                for route, value in ranking
            ],
        }


class ConformalE5MembershipRouter:
    """Frozen BGE route authority plus global E5 conformal veto."""

    def __init__(
        self,
        registry: Any,
        *,
        bge_embedder: Embedder,
        e5_embedder: Embedder,
        calibration_unsupported_scores: Iterable[float],
    ) -> None:
        self.raw_retriever = FrozenBGERawRetriever(registry, bge_embedder)
        self.membership = E5CatalogMembershipScorer(registry, e5_embedder)
        self.calibration_unsupported_scores = tuple(
            float(value) for value in calibration_unsupported_scores
        )
        if not self.calibration_unsupported_scores:
            raise ValueError("calibration unsupported scores required")

    def route(self, query: str) -> dict[str, Any]:
        raw = self.raw_retriever.route(query)
        membership = self.membership.score(query)
        accepted, p_value = conformal_accept(
            membership["catalog_score"],
            self.calibration_unsupported_scores,
        )
        predicted = raw["raw_top_route"] if accepted else None
        return {
            "predicted": predicted,
            "raw_top_route": raw["raw_top_route"],
            "raw_top_score": raw["raw_top_score"],
            "catalog_score": membership["catalog_score"],
            "diagnostic_e5_top_route": membership["diagnostic_e5_top_route"],
            "p_unsupported": p_value,
            "reason": (
                "reject_unsupported_null_preserve_bge"
                if accepted
                else "unsupported_null_not_rejected"
            ),
        }
