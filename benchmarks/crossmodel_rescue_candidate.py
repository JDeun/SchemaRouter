"""Frozen zero-false cross-model rescue candidate selected from #262.

Research-only adapter. The robust BGE-M3 base remains authoritative. Rescue can only
restore the same raw top-1 registered route after a base abstention.
"""

from __future__ import annotations

import math
import time
from collections.abc import Iterable
from typing import Any, Callable

from benchmarks.bge_m3_frozen_candidate import (
    FROZEN_THRESHOLDS,
    FrozenBgeM3DualViewBackend,
    _action_text,
    _cosine,
    _schema_text,
    _to_vectors,
)
from schemarouter.decisions import (
    DecisionEvidence,
    DecisionOption,
    DecisionRequest,
    DecisionResult,
    DecisionSelection,
    validate_decision,
)

GTE_MODEL_NAME = "Alibaba-NLP/gte-multilingual-base"
GTE_MODEL_REVISION = "087a024525fd6e2fe749cb4679d218d8bcc95bdd"
GTE_SCHEMA_WEIGHT = 0.25
GTE_ACTION_WEIGHT = 0.75

RERANKER_MODEL_NAME = "BAAI/bge-reranker-v2-m3"
RERANKER_MODEL_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
RERANKER_MAX_LENGTH = 256

RESCUE_EPSILON = 1e-6

RESCUE_RULES: dict[str, dict[str, float]] = {
    "calendar.create": {
        "min_gte_score": 0.5049319933930052,
        "min_gte_margin": 0.02,
        "max_base_score_deficit": 0.05,
        "max_base_margin_deficit": 0.0,
        "min_reranker_score": 0.00007667232808125623,
    },
    "finance.quote": {
        "min_gte_score": -1.0,
        "min_gte_margin": 0.10,
        "max_base_score_deficit": 0.05,
        "max_base_margin_deficit": 0.0,
        "min_reranker_score": -1.0,
    },
    "materials.search": {
        "min_gte_score": -1.0,
        "min_gte_margin": 0.0,
        "max_base_score_deficit": 1.0,
        "max_base_margin_deficit": 0.0,
        "min_reranker_score": 0.00007708727670863652,
    },
    "papers.search": {
        "min_gte_score": -1.0,
        "min_gte_margin": 0.0,
        "max_base_score_deficit": 0.02,
        "max_base_margin_deficit": 0.0,
        "min_reranker_score": -1.0,
    },
    "support.create_ticket": {
        "min_gte_score": -1.0,
        "min_gte_margin": 0.0,
        "max_base_score_deficit": 0.02,
        "max_base_margin_deficit": 0.0,
        "min_reranker_score": 0.0011868140695276287,
    },
    "users.lookup": {
        "min_gte_score": -1.0,
        "min_gte_margin": 0.05,
        "max_base_score_deficit": 0.02,
        "max_base_margin_deficit": 0.0,
        "min_reranker_score": -1.0,
    },
    "weather.current": {
        "min_gte_score": -1.0,
        "min_gte_margin": 0.0,
        "max_base_score_deficit": 1.0,
        "max_base_margin_deficit": 0.0,
        "min_reranker_score": 0.004901762022622069,
    },
    "weather.forecast": {
        "min_gte_score": 0.5627313325090175,
        "min_gte_margin": 0.0,
        "max_base_score_deficit": 0.05,
        "max_base_margin_deficit": 0.0,
        "min_reranker_score": -1.0,
    },
}

RerankerCallable = Callable[[str, str], float]


def _gte_rank(
    query_vector: list[float],
    routes: list[str],
    schema_vectors: dict[str, list[float]],
    action_vectors: dict[str, list[float]],
) -> dict[str, Any]:
    scored: list[tuple[str, float]] = []
    for route_id in routes:
        schema_score = _cosine(query_vector, schema_vectors[route_id])
        action_score = _cosine(query_vector, action_vectors[route_id])
        fused = (
            GTE_SCHEMA_WEIGHT * schema_score
            + GTE_ACTION_WEIGHT * action_score
        )
        scored.append((route_id, fused))

    scored.sort(key=lambda item: (-item[1], item[0]))
    top_route, top_score = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else None
    margin = top_score - second_score if second_score is not None else 2.0
    return {
        "top_route": top_route,
        "top_score": top_score,
        "second_score": second_score,
        "top_margin": margin,
    }


def _min_passes(value: float, threshold: float) -> bool:
    return value + RESCUE_EPSILON >= threshold


def _max_passes(value: float, threshold: float) -> bool:
    return value <= threshold + RESCUE_EPSILON


class FrozenCrossModelRescueBackend:
    """Confirmed robust base plus same-winner conditional rescue."""

    def __init__(
        self,
        registry: Any,
        *,
        base_backend: FrozenBgeM3DualViewBackend,
        gte_embedder: Any,
        reranker: RerankerCallable,
    ) -> None:
        self.registry = registry
        self.base_backend = base_backend
        self.gte_embedder = gte_embedder
        self.reranker = reranker

        route_specs: dict[str, tuple[str, str, str]] = {}
        for tool in registry.tools():
            for endpoint in tool.endpoints:
                route_id = f"{tool.key}.{endpoint.name}"
                action = _action_text(endpoint)
                capability = "\n".join(
                    part
                    for part in [action, endpoint.description.strip()]
                    if part
                )
                route_specs[route_id] = (
                    _schema_text(tool, endpoint),
                    action,
                    capability,
                )

        if set(route_specs) != set(base_backend.route_ids):
            raise ValueError("rescue registry must match the frozen base registry")
        if not set(RESCUE_RULES).issubset(route_specs):
            raise ValueError("rescue rules contain an unknown registered route")

        self._route_specs = route_specs
        self._route_ids = sorted(route_specs)

        static_texts = [
            *(route_specs[route][0] for route in self._route_ids),
            *(route_specs[route][1] for route in self._route_ids),
        ]
        vectors = _to_vectors(gte_embedder(static_texts))
        if len(vectors) != len(static_texts):
            raise ValueError("GTE embedder returned an unexpected static vector count")
        split = len(self._route_ids)
        self._gte_schema_vectors = dict(
            zip(self._route_ids, vectors[:split], strict=True)
        )
        self._gte_action_vectors = dict(
            zip(self._route_ids, vectors[split:], strict=True)
        )
        self.last_trace: dict[str, Any] | None = None

    @property
    def route_ids(self) -> tuple[str, ...]:
        return tuple(self._route_ids)

    def route_query(
        self,
        query: str,
        offered_routes: Iterable[str],
    ) -> dict[str, Any]:
        routes = list(dict.fromkeys(offered_routes))
        unknown = sorted(set(routes) - set(self._route_specs))
        if unknown:
            raise ValueError(
                "candidate requested unknown frozen route(s): " + ", ".join(unknown)
            )
        if not routes:
            raise ValueError("offered_routes must not be empty")

        trace: dict[str, Any] = {
            "base_invoked": True,
            "gte_invoked": False,
            "reranker_invoked": False,
            "rescued": False,
            "accepted": False,
            "base_latency_ms": 0.0,
            "gte_latency_ms": 0.0,
            "reranker_latency_ms": 0.0,
        }

        started = time.perf_counter_ns()
        base = self.base_backend.score_routes(query, routes)
        trace["base_latency_ms"] = (time.perf_counter_ns() - started) / 1_000_000
        trace.update(
            {
                "base_top_route": base["top_route"],
                "base_top_score": base["top_score"],
                "base_top_margin": base["top_margin"],
                "base_accepted": base["accepted"],
            }
        )

        base_route = str(base["top_route"])
        if bool(base["accepted"]):
            trace["accepted"] = True
            trace["final_route"] = base_route
            self.last_trace = trace
            return trace

        rule = RESCUE_RULES.get(base_route)
        if rule is None:
            trace["final_route"] = None
            trace["rescue_reason"] = "route_disabled"
            self.last_trace = trace
            return trace

        trace["gte_invoked"] = True
        started = time.perf_counter_ns()
        gte_vector = _to_vectors(self.gte_embedder([query]))[0]
        gte = _gte_rank(
            gte_vector,
            routes,
            self._gte_schema_vectors,
            self._gte_action_vectors,
        )
        trace["gte_latency_ms"] = (time.perf_counter_ns() - started) / 1_000_000
        trace.update(
            {
                "gte_top_route": gte["top_route"],
                "gte_top_score": gte["top_score"],
                "gte_top_margin": gte["top_margin"],
            }
        )

        if str(gte["top_route"]) != base_route:
            trace["final_route"] = None
            trace["rescue_reason"] = "winner_disagreement"
            self.last_trace = trace
            return trace

        boundary = FROZEN_THRESHOLDS[base_route]
        base_score_deficit = max(
            0.0,
            float(boundary["min_score"]) - float(base["top_score"]),
        )
        base_margin_deficit = max(
            0.0,
            float(boundary["min_margin"]) - float(base["top_margin"]),
        )
        trace["base_score_deficit"] = base_score_deficit
        trace["base_margin_deficit"] = base_margin_deficit

        non_reranker_pass = (
            _min_passes(float(gte["top_score"]), rule["min_gte_score"])
            and _min_passes(float(gte["top_margin"]), rule["min_gte_margin"])
            and _max_passes(
                base_score_deficit,
                rule["max_base_score_deficit"],
            )
            and _max_passes(
                base_margin_deficit,
                rule["max_base_margin_deficit"],
            )
        )
        if not non_reranker_pass:
            trace["final_route"] = None
            trace["rescue_reason"] = "prefilter_rejected"
            self.last_trace = trace
            return trace

        reranker_threshold = float(rule["min_reranker_score"])
        if reranker_threshold > -1.0:
            trace["reranker_invoked"] = True
            started = time.perf_counter_ns()
            reranker_score = float(
                self.reranker(
                    query,
                    self._route_specs[base_route][2],
                )
            )
            trace["reranker_latency_ms"] = (
                time.perf_counter_ns() - started
            ) / 1_000_000
            trace["reranker_score"] = reranker_score
            if not _min_passes(reranker_score, reranker_threshold):
                trace["final_route"] = None
                trace["rescue_reason"] = "reranker_rejected"
                self.last_trace = trace
                return trace

        trace["accepted"] = True
        trace["rescued"] = True
        trace["final_route"] = base_route
        trace["rescue_reason"] = "rescued_same_winner"
        self.last_trace = trace
        return trace

    def decide(self, request: DecisionRequest) -> DecisionResult:
        option_by_route: dict[str, DecisionOption] = {}
        for option in request.options:
            route_id = option.label.strip()
            if not route_id:
                raise ValueError("candidate option must expose its registered route label")
            if route_id in option_by_route:
                raise ValueError(f"duplicate route label: {route_id}")
            option_by_route[route_id] = option

        trace = self.route_query(request.query, option_by_route)
        final_route = trace.get("final_route")

        if final_route is None:
            result = DecisionResult(
                selections=[],
                abstained=True,
                metadata={
                    **trace,
                    "candidate": "bge-m3-055-zero-false-crossmodel-rescue-v1",
                    "rescue_epsilon": RESCUE_EPSILON,
                },
            )
            return validate_decision(request, result)

        route_id = str(final_route)
        option = option_by_route[route_id]
        evidence = [
            DecisionEvidence(
                kind="route_match",
                state="match",
                source=(
                    "crossmodel-rescue"
                    if trace["rescued"]
                    else "robust-bge-m3-base"
                ),
                option_id=option.id,
                score=max(
                    0.0,
                    min(
                        1.0,
                        (float(trace["base_top_score"]) + 1.0) / 2.0,
                    ),
                ),
                score_kind="fused_cosine",
                metadata={
                    "route_id": route_id,
                    "rescued": bool(trace["rescued"]),
                    "rescue_epsilon": RESCUE_EPSILON,
                },
            )
        ]
        result = DecisionResult(
            selections=[
                DecisionSelection(
                    option_id=option.id,
                    score=evidence[0].score,
                )
            ],
            abstained=False,
            evidence=evidence,
            metadata={
                **trace,
                "candidate": "bge-m3-055-zero-false-crossmodel-rescue-v1",
                "rescue_epsilon": RESCUE_EPSILON,
            },
        )
        return validate_decision(request, result)
