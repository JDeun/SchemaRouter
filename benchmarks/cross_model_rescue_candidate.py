"""Frozen zero-false cross-model rescue candidate selected from experiment #262.

Research-only adapter. The confirmed robust BGE-M3 base remains authoritative:
- base acceptances are returned unchanged;
- rescue is considered only after base abstention;
- rescue may select only the same raw BGE-M3 top-1 route;
- GTE and the optional reranker never create or switch route authority.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Iterable
from typing import Any

from schemarouter.decisions import (
    DecisionEvidence,
    DecisionOption,
    DecisionRequest,
    DecisionResult,
    DecisionSelection,
    validate_decision,
)

from benchmarks.bge_m3_frozen_candidate import (
    ACTION_WEIGHT as BASE_ACTION_WEIGHT,
)
from benchmarks.bge_m3_frozen_candidate import (
    BOUNDARY_EPSILON as BASE_BOUNDARY_EPSILON,
)
from benchmarks.bge_m3_frozen_candidate import (
    FROZEN_THRESHOLDS as BASE_THRESHOLDS,
)
from benchmarks.bge_m3_frozen_candidate import (
    MODEL_NAME as BASE_MODEL_NAME,
)
from benchmarks.bge_m3_frozen_candidate import (
    MODEL_REVISION as BASE_MODEL_REVISION,
)
from benchmarks.bge_m3_frozen_candidate import (
    SCHEMA_WEIGHT as BASE_SCHEMA_WEIGHT,
)
from benchmarks.bge_m3_frozen_candidate import (
    FrozenBgeM3DualViewBackend,
    _action_text,
    _cosine,
    _schema_text,
    _to_vectors,
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

RERANKER_ENABLED_ROUTES = frozenset(
    route
    for route, rule in RESCUE_RULES.items()
    if float(rule["min_reranker_score"]) > -1.0
)


def _passes_min(value: float, threshold: float) -> bool:
    return value + RESCUE_EPSILON >= threshold


def _passes_max(value: float, threshold: float) -> bool:
    return value <= threshold + RESCUE_EPSILON


class FrozenCrossModelRescueBackend:
    """Confirmed BGE-M3 base plus frozen same-winner zero-false rescue."""

    def __init__(
        self,
        registry: Any,
        *,
        base_embedder: Callable[[list[str]], list[list[float]]],
        gte_static_embedder: Callable[[list[str]], list[list[float]]],
        gte_query_embedder: Callable[[list[str]], list[list[float]]],
        reranker_scorer: Callable[[str, str], float],
    ) -> None:
        self.registry = registry
        self.base = FrozenBgeM3DualViewBackend(registry, base_embedder)
        self.gte_query_embedder = gte_query_embedder
        self.reranker_scorer = reranker_scorer

        route_specs: dict[str, tuple[str, str, str]] = {}
        for tool in registry.tools():
            for endpoint in tool.endpoints:
                route_id = f"{tool.key}.{endpoint.name}"
                action = _action_text(endpoint)
                capability = "\n".join(
                    part
                    for part in (action, endpoint.description.strip())
                    if part
                )
                route_specs[route_id] = (
                    _schema_text(tool, endpoint),
                    action,
                    capability,
                )

        if set(route_specs) != set(self.base.route_ids):
            raise ValueError("cross-model candidate registry/base route mismatch")
        if not set(RESCUE_RULES).issubset(route_specs):
            raise ValueError("rescue rule references an unregistered route")

        self._route_specs = route_specs
        self._route_ids = tuple(sorted(route_specs))
        static_texts = [
            *(route_specs[route][0] for route in self._route_ids),
            *(route_specs[route][1] for route in self._route_ids),
        ]
        vectors = _to_vectors(gte_static_embedder(static_texts))
        if len(vectors) != len(static_texts):
            raise ValueError("GTE embedder returned unexpected static vector count")
        split = len(self._route_ids)
        self._gte_schema_vectors = dict(
            zip(self._route_ids, vectors[:split], strict=True)
        )
        self._gte_action_vectors = dict(
            zip(self._route_ids, vectors[split:], strict=True)
        )

    @property
    def route_ids(self) -> tuple[str, ...]:
        return self._route_ids

    def _gte_rank(
        self,
        query: str,
        offered_routes: Iterable[str],
    ) -> dict[str, float | str]:
        routes = list(dict.fromkeys(offered_routes))
        if not routes:
            raise ValueError("offered_routes must not be empty")
        unknown = sorted(set(routes) - set(self._route_ids))
        if unknown:
            raise ValueError(
                "GTE candidate requested unknown route(s): " + ", ".join(unknown)
            )

        query_vector = _to_vectors(self.gte_query_embedder([query]))[0]
        scored: list[tuple[str, float]] = []
        for route_id in routes:
            schema_score = _cosine(
                query_vector,
                self._gte_schema_vectors[route_id],
            )
            action_score = _cosine(
                query_vector,
                self._gte_action_vectors[route_id],
            )
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
            "gte_top_route": top_route,
            "gte_top_score": top_score,
            "gte_second_score": second_score if second_score is not None else -1.0,
            "gte_top_margin": margin,
        }

    def _rescue_from_base(
        self,
        query: str,
        offered_routes: Iterable[str],
        base_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        top_route = str(base_metadata["top_route"])
        result: dict[str, Any] = {
            "final_route": None,
            "final_accepted": False,
            "base_top_route": top_route,
            "base_top_score": float(base_metadata["top_score"]),
            "base_top_margin": float(base_metadata["top_margin"]),
            "base_accepted": bool(base_metadata["accepted"]),
            "rescue_enabled": top_route in RESCUE_RULES,
            "gte_invoked": False,
            "gte_agrees": False,
            "gte_latency_ms": 0.0,
            "reranker_invoked": False,
            "reranker_score": None,
            "reranker_latency_ms": 0.0,
            "rescue_accepted": False,
        }
        if result["base_accepted"]:
            result["final_route"] = top_route
            result["final_accepted"] = True
            return result

        rule = RESCUE_RULES.get(top_route)
        if rule is None:
            return result

        result["gte_invoked"] = True
        gte_started = time.perf_counter_ns()
        gte = self._gte_rank(query, offered_routes)
        result["gte_latency_ms"] = (
            time.perf_counter_ns() - gte_started
        ) / 1_000_000
        result.update(gte)
        result["gte_agrees"] = str(gte["gte_top_route"]) == top_route
        if not result["gte_agrees"]:
            return result

        boundary = BASE_THRESHOLDS[top_route]
        score_deficit = max(
            0.0,
            float(boundary["min_score"]) - float(result["base_top_score"]),
        )
        margin_deficit = max(
            0.0,
            float(boundary["min_margin"]) - float(result["base_top_margin"]),
        )
        result["base_score_deficit"] = score_deficit
        result["base_margin_deficit"] = margin_deficit

        if not _passes_min(
            float(gte["gte_top_score"]),
            float(rule["min_gte_score"]),
        ):
            return result
        if not _passes_min(
            float(gte["gte_top_margin"]),
            float(rule["min_gte_margin"]),
        ):
            return result
        if not _passes_max(
            score_deficit,
            float(rule["max_base_score_deficit"]),
        ):
            return result
        if not _passes_max(
            margin_deficit,
            float(rule["max_base_margin_deficit"]),
        ):
            return result

        reranker_threshold = float(rule["min_reranker_score"])
        if reranker_threshold > -1.0:
            result["reranker_invoked"] = True
            capability = self._route_specs[top_route][2]
            reranker_started = time.perf_counter_ns()
            reranker_score = float(self.reranker_scorer(query, capability))
            result["reranker_latency_ms"] = (
                time.perf_counter_ns() - reranker_started
            ) / 1_000_000
            if not math.isfinite(reranker_score):
                raise ValueError("reranker returned a non-finite score")
            result["reranker_score"] = reranker_score
            if not _passes_min(reranker_score, reranker_threshold):
                return result

        result["rescue_accepted"] = True
        result["final_accepted"] = True
        result["final_route"] = top_route
        return result

    def score_routes(
        self,
        query: str,
        offered_routes: Iterable[str],
    ) -> dict[str, Any]:
        routes = list(dict.fromkeys(offered_routes))
        base_started = time.perf_counter_ns()
        base = self.base.score_routes(query, routes)
        base_latency_ms = (
            time.perf_counter_ns() - base_started
        ) / 1_000_000
        return {
            **base,
            "base_latency_ms": base_latency_ms,
            **self._rescue_from_base(query, routes, base),
        }

    def decide(self, request: DecisionRequest) -> DecisionResult:
        # Run the frozen base exactly once. Any accepted base decision is returned
        # unchanged, preserving the confirmed #259 behavior byte-for-byte at this layer.
        base_decision = self.base.decide(request)
        if not base_decision.abstained:
            return base_decision

        option_by_route: dict[str, DecisionOption] = {}
        for option in request.options:
            route_id = option.label.strip()
            if not route_id:
                raise ValueError("candidate option must expose its registered route label")
            if route_id in option_by_route:
                raise ValueError(f"duplicate route label in candidate options: {route_id}")
            option_by_route[route_id] = option

        metadata = dict(base_decision.metadata)
        rescue = self._rescue_from_base(
            request.query,
            option_by_route,
            metadata,
        )
        if not rescue["rescue_accepted"]:
            return base_decision

        top_route = str(rescue["final_route"])
        top_option = option_by_route[top_route]
        evidence = [
            DecisionEvidence(
                kind="route_match",
                state="match",
                source="frozen-cross-model-rescue",
                option_id=top_option.id,
                score=float(rescue["base_top_score"]),
                score_kind="fused_cosine",
                metadata={
                    "route_id": top_route,
                    "same_winner_only": True,
                    "gte_top_score": rescue.get("gte_top_score"),
                    "gte_top_margin": rescue.get("gte_top_margin"),
                    "reranker_score": rescue.get("reranker_score"),
                    "rescue_epsilon": RESCUE_EPSILON,
                },
            )
        ]
        decision = DecisionResult(
            selections=[
                DecisionSelection(
                    option_id=top_option.id,
                    score=max(
                        0.0,
                        min(1.0, (float(rescue["base_top_score"]) + 1.0) / 2.0),
                    ),
                )
            ],
            abstained=False,
            evidence=evidence,
            metadata={
                **metadata,
                **rescue,
                "base_model": BASE_MODEL_NAME,
                "base_model_revision": BASE_MODEL_REVISION,
                "base_schema_weight": BASE_SCHEMA_WEIGHT,
                "base_action_weight": BASE_ACTION_WEIGHT,
                "base_boundary_epsilon": BASE_BOUNDARY_EPSILON,
                "gte_model": GTE_MODEL_NAME,
                "gte_model_revision": GTE_MODEL_REVISION,
                "gte_schema_weight": GTE_SCHEMA_WEIGHT,
                "gte_action_weight": GTE_ACTION_WEIGHT,
                "reranker_model": (
                    RERANKER_MODEL_NAME if rescue["reranker_invoked"] else None
                ),
                "reranker_model_revision": (
                    RERANKER_MODEL_REVISION if rescue["reranker_invoked"] else None
                ),
                "rescue_epsilon": RESCUE_EPSILON,
            },
        )
        return validate_decision(request, decision)
