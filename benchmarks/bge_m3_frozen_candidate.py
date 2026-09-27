"""Frozen BGE-M3 dual-view candidate selected from research experiment #242.

Research-only adapter. It uses only registered route metadata and returns only option IDs
already present in the DecisionRequest. It cannot create execution authority.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

from schemarouter.decisions import (
    DecisionEvidence,
    DecisionOption,
    DecisionRequest,
    DecisionResult,
    DecisionSelection,
    validate_decision,
)

MODEL_NAME = "BAAI/bge-m3"
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
SCHEMA_WEIGHT = 0.55
ACTION_WEIGHT = 0.45
BOUNDARY_EPSILON = 1e-6

FROZEN_THRESHOLDS: dict[str, dict[str, float]] = {
    "calendar.create": {"min_score": 0.5207915599172316, "min_margin": 0.0},
    "calendar.list": {"min_score": 0.5549226120493271, "min_margin": 0.0},
    "finance.history": {"min_score": 0.44227107387387427, "min_margin": 0.0},
    "finance.quote": {"min_score": 0.4893408565908712, "min_margin": 0.02},
    "inventory.search": {"min_score": 0.5359938169033298, "min_margin": 0.0},
    "inventory.update": {"min_score": 0.5376021992095548, "min_margin": 0.0},
    "materials.search": {"min_score": 0.44967027419294425, "min_margin": 0.0},
    "materials.structure": {"min_score": 0.42728435995293546, "min_margin": 0.0},
    "papers.citations": {"min_score": 0.46196385844297233, "min_margin": 0.0},
    "papers.search": {"min_score": 0.4590736815129689, "min_margin": 0.0},
    "support.create_ticket": {"min_score": 0.5326329467130329, "min_margin": 0.0},
    "support.search": {"min_score": 0.4830030958690135, "min_margin": 0.0},
    "users.lookup": {"min_score": 0.49123020769781134, "min_margin": 0.0},
    "users.update": {"min_score": 0.5230594574881653, "min_margin": 0.0},
    "weather.current": {"min_score": 0.5397048468861396, "min_margin": 0.02},
    "weather.forecast": {"min_score": 0.5050024291985815, "min_margin": 0.0},
}


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("embedding vectors must be non-empty and dimensionally aligned")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        raise ValueError("embedding vectors must have non-zero norm")
    value = sum(a * b for a, b in zip(left, right, strict=True))
    value /= left_norm * right_norm
    return max(-1.0, min(1.0, value))


def _schema_text(tool: Any, endpoint: Any) -> str:
    route_id = f"{tool.key}.{endpoint.name}"
    field_labels = [
        field.semantic_id or field.name
        for field in endpoint.output_fields
        if not field.identifier
    ]
    parts = [
        route_id,
        tool.description.strip(),
        endpoint.description.strip(),
    ]
    if field_labels:
        parts.append("Fields: " + ", ".join(dict.fromkeys(field_labels)))
    return "\n".join(part for part in parts if part)


def _action_text(endpoint: Any) -> str:
    operation_name = endpoint.name.replace("_", " ").replace("-", " ")
    return "\n".join(
        dict.fromkeys(
            part
            for part in [operation_name, *endpoint.operation_aliases]
            if part
        )
    )


def _to_vectors(raw: Iterable[Iterable[float]]) -> list[list[float]]:
    vectors = [[float(value) for value in vector] for vector in raw]
    if not vectors:
        raise ValueError("embedder returned no vectors")
    if any(not vector for vector in vectors):
        raise ValueError("embedder returned an empty vector")
    width = len(vectors[0])
    if any(len(vector) != width for vector in vectors):
        raise ValueError("embedder returned inconsistent dimensions")
    if any(not math.isfinite(value) for vector in vectors for value in vector):
        raise ValueError("embedder returned a non-finite value")
    return vectors


class AcceptAllRegisteredRecallBackend:
    """Expose the full registered catalog without inventing any option."""

    def decide(self, request: DecisionRequest) -> DecisionResult:
        selections = [
            DecisionSelection(option_id=option.id, score=1.0)
            for option in request.options[: request.max_selections]
        ]
        return validate_decision(
            request,
            DecisionResult(
                selections=selections,
                metadata={
                    "reason": "registered-catalog recall",
                    "selected_count": len(selections),
                },
            ),
        )


class FrozenBgeM3DualViewBackend:
    """Frozen winner-only BGE-M3 route selector with route-local abstention."""

    def __init__(self, registry: Any, embedder: Any) -> None:
        self.registry = registry
        self.embedder = embedder
        route_specs: dict[str, tuple[str, str]] = {}
        for tool in registry.tools():
            for endpoint in tool.endpoints:
                route_id = f"{tool.key}.{endpoint.name}"
                route_specs[route_id] = (
                    _schema_text(tool, endpoint),
                    _action_text(endpoint),
                )

        if set(route_specs) != set(FROZEN_THRESHOLDS):
            missing = sorted(set(FROZEN_THRESHOLDS) - set(route_specs))
            extra = sorted(set(route_specs) - set(FROZEN_THRESHOLDS))
            raise ValueError(
                "frozen candidate registry mismatch; "
                f"missing={missing}, extra={extra}"
            )

        self._route_specs = route_specs
        self._route_ids = sorted(route_specs)
        static_texts = [
            *(route_specs[route_id][0] for route_id in self._route_ids),
            *(route_specs[route_id][1] for route_id in self._route_ids),
        ]
        vectors = _to_vectors(embedder(static_texts))
        if len(vectors) != len(static_texts):
            raise ValueError(
                "embedder returned an unexpected static vector count"
            )
        split = len(self._route_ids)
        self._schema_vectors = dict(
            zip(self._route_ids, vectors[:split], strict=True)
        )
        self._action_vectors = dict(
            zip(self._route_ids, vectors[split:], strict=True)
        )
        self.last_result: DecisionResult | None = None

    @property
    def route_ids(self) -> tuple[str, ...]:
        return tuple(self._route_ids)

    def score_routes(
        self,
        query: str,
        offered_routes: Iterable[str],
    ) -> dict[str, Any]:
        routes = list(dict.fromkeys(offered_routes))
        if not routes:
            raise ValueError("offered_routes must not be empty")
        unknown = sorted(set(routes) - set(self._route_specs))
        if unknown:
            raise ValueError(
                "candidate requested unknown frozen route(s): " + ", ".join(unknown)
            )

        query_vector = _to_vectors(self.embedder([query]))[0]
        scored: list[tuple[str, float]] = []
        for route_id in routes:
            schema_score = _cosine(
                query_vector,
                self._schema_vectors[route_id],
            )
            action_score = _cosine(
                query_vector,
                self._action_vectors[route_id],
            )
            fused_score = (
                SCHEMA_WEIGHT * schema_score
                + ACTION_WEIGHT * action_score
            )
            scored.append((route_id, fused_score))

        scored.sort(key=lambda item: (-item[1], item[0]))
        top_route, top_score = scored[0]
        second_score = scored[1][1] if len(scored) > 1 else None
        margin = top_score - second_score if second_score is not None else 2.0
        boundary = FROZEN_THRESHOLDS[top_route]
        accepted = (
            top_score + BOUNDARY_EPSILON >= boundary["min_score"]
            and margin + BOUNDARY_EPSILON >= boundary["min_margin"]
        )
        return {
            "top_route": top_route,
            "top_score": top_score,
            "second_score": second_score,
            "top_margin": margin,
            "accepted": accepted,
            "min_score": boundary["min_score"],
            "min_margin": boundary["min_margin"],
            "ranked_routes": [
                {"route_id": route_id, "score": score}
                for route_id, score in scored
            ],
        }

    def decide(self, request: DecisionRequest) -> DecisionResult:
        option_by_route: dict[str, DecisionOption] = {}
        for option in request.options:
            route_id = option.label.strip()
            if not route_id:
                raise ValueError("candidate option must expose its registered route label")
            if route_id in option_by_route:
                raise ValueError(f"duplicate route label in candidate options: {route_id}")
            option_by_route[route_id] = option

        result = self.score_routes(
            request.query,
            option_by_route,
        )
        top_route = str(result["top_route"])
        top_option = option_by_route[top_route]
        accepted = bool(result["accepted"])
        evidence = [
            DecisionEvidence(
                kind="route_match",
                state="match" if accepted else "no_match",
                source="bge-m3-dual-view-budget6",
                option_id=top_option.id,
                score=float(result["top_score"]),
                score_kind="fused_cosine",
                metadata={
                    "route_id": top_route,
                    "top_margin": float(result["top_margin"]),
                    "min_score": float(result["min_score"]),
                    "min_margin": float(result["min_margin"]),
                },
            )
        ]
        decision = DecisionResult(
            selections=(
                [
                    DecisionSelection(
                        option_id=top_option.id,
                        score=max(
                            0.0,
                            min(1.0, (float(result["top_score"]) + 1.0) / 2.0),
                        ),
                    )
                ]
                if accepted
                else []
            ),
            abstained=not accepted,
            evidence=evidence,
            metadata={
                **result,
                "model": MODEL_NAME,
                "model_revision": MODEL_REVISION,
                "schema_weight": SCHEMA_WEIGHT,
                "action_weight": ACTION_WEIGHT,
                "threshold_profile": "false-budget-6-robust-epsilon",
                "boundary_epsilon": BOUNDARY_EPSILON,
            },
        )
        self.last_result = validate_decision(request, decision)
        return self.last_result
