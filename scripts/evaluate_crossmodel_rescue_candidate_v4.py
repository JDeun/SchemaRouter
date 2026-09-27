"""Execute the frozen cross-model rescue candidate through SchemaPlanner."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = Path(__file__).resolve().parent
for _path in (_PROJECT_ROOT, _SCRIPTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from benchmark_decision_routing import reference_registry  # noqa: E402

from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    MODEL_NAME as BASE_MODEL_NAME,
    MODEL_REVISION as BASE_MODEL_REVISION,
    AcceptAllRegisteredRecallBackend,
    FrozenBgeM3DualViewBackend,
)
from benchmarks.crossmodel_rescue_candidate import (  # noqa: E402
    GTE_MODEL_NAME,
    GTE_MODEL_REVISION,
    RERANKER_MAX_LENGTH,
    RERANKER_MODEL_NAME,
    RERANKER_MODEL_REVISION,
    FrozenCrossModelRescueBackend,
)
from schemarouter import DecisionPolicy, PlanRequest, SchemaPlanner  # noqa: E402


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "min": min(values) if values else None,
        "p50": _quantile(values, 0.50),
        "p90": _quantile(values, 0.90),
        "p95": _quantile(values, 0.95),
        "max": max(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
    }


def _embedder(model: Any):
    def embed(texts: list[str]) -> list[list[float]]:
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    return embed


def _load_base_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        BASE_MODEL_NAME,
        revision=BASE_MODEL_REVISION,
        trust_remote_code=False,
    )


def _load_gte_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        GTE_MODEL_NAME,
        revision=GTE_MODEL_REVISION,
        trust_remote_code=True,
    )


class FrozenReranker:
    def __init__(self) -> None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(
            RERANKER_MODEL_NAME,
            revision=RERANKER_MODEL_REVISION,
        )
        self.model = AutoModelForSequenceClassification.from_pretrained(
            RERANKER_MODEL_NAME,
            revision=RERANKER_MODEL_REVISION,
        )
        self.model.eval()

    @staticmethod
    def _sigmoid(value: float) -> float:
        if value >= 0:
            z = math.exp(-value)
            return 1.0 / (1.0 + z)
        z = math.exp(value)
        return z / (1.0 + z)

    def __call__(self, query: str, text: str) -> float:
        import torch

        encoded = self.tokenizer(
            [query],
            [text],
            padding=True,
            truncation=True,
            max_length=RERANKER_MAX_LENGTH,
            return_tensors="pt",
        )
        with torch.no_grad():
            logits = self.model(**encoded, return_dict=True).logits
        flat = logits.reshape(logits.shape[0], -1)
        if flat.shape != (1, 1):
            raise RuntimeError(
                f"unexpected reranker logits shape: {tuple(flat.shape)}"
            )
        return self._sigmoid(float(flat[0, 0].item()))


def _route_from_plan(plan: Any) -> str | None:
    if not plan.calls:
        return None
    call = plan.calls[0]
    return f"{call.tool}.{call.endpoint}"


def evaluate(
    cases: list[dict[str, Any]],
    *,
    direct_parity: bool,
    expected_supported_correct: int | None,
    expected_false_routes: int | None,
) -> dict[str, Any]:
    registry = reference_registry()

    base_model = _load_base_model()
    base_embed = _embedder(base_model)
    base_static_started = time.perf_counter_ns()
    base_backend = FrozenBgeM3DualViewBackend(registry, base_embed)
    base_static_ms = (time.perf_counter_ns() - base_static_started) / 1_000_000

    gte_model = _load_gte_model()
    gte_embed = _embedder(gte_model)
    reranker = FrozenReranker()

    candidate_static_started = time.perf_counter_ns()
    candidate = FrozenCrossModelRescueBackend(
        registry,
        base_backend=base_backend,
        gte_embedder=gte_embed,
        reranker=reranker,
    )
    gte_static_ms = (
        time.perf_counter_ns() - candidate_static_started
    ) / 1_000_000

    planner = SchemaPlanner(
        registry,
        decision_backend=candidate,
        decision_policy=DecisionPolicy(
            enabled=True,
            tool_selection=True,
            endpoint_selection=True,
            field_selection=False,
            evidence_sufficiency=False,
            recall_on_empty=False,
            candidate_abstention="no_route",
            fallback="error",
        ),
        candidate_recall_backend=AcceptAllRegisteredRecallBackend(),
        candidate_recall_limit=len(candidate.route_ids),
    )

    allowed_routes = set(candidate.route_ids)
    rows: list[dict[str, Any]] = []
    planner_latencies: list[float] = []
    direct_latencies: list[float] = []
    base_latencies: list[float] = []
    gte_latencies: list[float] = []
    reranker_latencies: list[float] = []

    for case in cases:
        query = str(case["query"])
        expected = case.get("expected")

        direct_predicted: str | None = None
        if direct_parity:
            direct_started = time.perf_counter_ns()
            direct = candidate.route_query(query, candidate.route_ids)
            direct_latencies.append(
                (time.perf_counter_ns() - direct_started) / 1_000_000
            )
            direct_predicted = (
                str(direct["final_route"])
                if direct.get("final_route") is not None
                else None
            )

        started = time.perf_counter_ns()
        try:
            plan = planner.plan(PlanRequest(query=query, max_calls=1))
            planner_ms = (time.perf_counter_ns() - started) / 1_000_000
            planner_latencies.append(planner_ms)
            predicted = _route_from_plan(plan)
            trace = dict(candidate.last_trace or {})

            base_latencies.append(float(trace.get("base_latency_ms", 0.0)))
            if trace.get("gte_invoked"):
                gte_latencies.append(float(trace.get("gte_latency_ms", 0.0)))
            if trace.get("reranker_invoked"):
                reranker_latencies.append(
                    float(trace.get("reranker_latency_ms", 0.0))
                )

            base_predicted = (
                str(trace["base_top_route"])
                if trace.get("base_accepted")
                else None
            )
            rows.append(
                {
                    "case_id": case.get("id"),
                    "category": case.get("category"),
                    "language": case.get("language"),
                    "expected": expected,
                    "predicted": predicted,
                    "base_predicted": base_predicted,
                    "base_top_route": trace.get("base_top_route"),
                    "base_accepted": bool(trace.get("base_accepted")),
                    "rescued": bool(trace.get("rescued")),
                    "gte_invoked": bool(trace.get("gte_invoked")),
                    "reranker_invoked": bool(trace.get("reranker_invoked")),
                    "planner_matches_direct": (
                        predicted == direct_predicted if direct_parity else None
                    ),
                    "invalid_plan": (
                        predicted is not None and predicted not in allowed_routes
                    ),
                    "base_accept_changed": (
                        bool(trace.get("base_accepted"))
                        and predicted != trace.get("base_top_route")
                    ),
                    "winner_changed_on_rescue": (
                        bool(trace.get("rescued"))
                        and predicted != trace.get("base_top_route")
                    ),
                    "planner_latency_ms": planner_ms,
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001 - confirmation retains failures.
            planner_ms = (time.perf_counter_ns() - started) / 1_000_000
            planner_latencies.append(planner_ms)
            rows.append(
                {
                    "case_id": case.get("id"),
                    "category": case.get("category"),
                    "language": case.get("language"),
                    "expected": expected,
                    "predicted": None,
                    "base_predicted": None,
                    "base_top_route": None,
                    "base_accepted": False,
                    "rescued": False,
                    "gte_invoked": False,
                    "reranker_invoked": False,
                    "planner_matches_direct": False if direct_parity else None,
                    "invalid_plan": False,
                    "base_accept_changed": False,
                    "winner_changed_on_rescue": False,
                    "planner_latency_ms": planner_ms,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row["category"] == "out_of_domain"]
    no_route = [row for row in rows if row["expected"] is None]

    supported_correct = sum(
        row["predicted"] == row["expected"] for row in supported
    )
    base_supported_correct = sum(
        row["base_predicted"] == row["expected"] for row in supported
    )
    near_rejected = sum(row["predicted"] is None for row in near)
    ood_rejected = sum(row["predicted"] is None for row in ood)
    false_routes = sum(row["predicted"] is not None for row in no_route)
    base_false_routes = sum(
        row["base_predicted"] is not None for row in no_route
    )
    rescued_false_routes = sum(
        row["expected"] is None
        and bool(row["rescued"])
        and row["predicted"] is not None
        for row in rows
    )
    rescued_correct = sum(
        bool(row["rescued"]) and row["predicted"] == row["expected"]
        for row in supported
    )
    rescued_wrong_supported = sum(
        bool(row["rescued"])
        and row["predicted"] is not None
        and row["predicted"] != row["expected"]
        for row in supported
    )

    invalid = sum(bool(row["invalid_plan"]) for row in rows)
    errors = sum(row["error"] is not None for row in rows)
    base_changes = sum(bool(row["base_accept_changed"]) for row in rows)
    winner_changes = sum(
        bool(row["winner_changed_on_rescue"]) for row in rows
    )
    parity_mismatches = (
        sum(not bool(row["planner_matches_direct"]) for row in rows)
        if direct_parity
        else None
    )
    gte_invocations = sum(bool(row["gte_invoked"]) for row in rows)
    reranker_invocations = sum(
        bool(row["reranker_invoked"]) for row in rows
    )

    metrics = {
        "supported_correct": supported_correct,
        "supported_exact_route_accuracy": supported_correct / len(supported),
        "base_supported_correct": base_supported_correct,
        "base_supported_exact_route_accuracy": (
            base_supported_correct / len(supported)
        ),
        "near_domain_unsupported_rejection": near_rejected / len(near),
        "out_of_domain_rejection": ood_rejected / len(ood),
        "false_routes": false_routes,
        "false_route_rate": false_routes / len(no_route),
        "base_false_routes": base_false_routes,
        "additional_false_routes": false_routes - base_false_routes,
        "rescued_false_routes": rescued_false_routes,
        "rescued_correct": rescued_correct,
        "rescued_wrong_supported": rescued_wrong_supported,
        "invalid_plans": invalid,
        "execution_errors": errors,
        "base_accept_changes": base_changes,
        "winner_changes_on_rescue": winner_changes,
        "planner_direct_parity_mismatches": parity_mismatches,
        "gte_invocations": gte_invocations,
        "gte_invocation_rate": gte_invocations / len(rows),
        "reranker_invocations": reranker_invocations,
        "reranker_invocation_rate": reranker_invocations / len(rows),
        "planner_latency_ms": _distribution(planner_latencies),
        "direct_latency_ms": _distribution(direct_latencies),
        "base_component_latency_ms": _distribution(base_latencies),
        "gte_component_latency_ms": _distribution(gte_latencies),
        "reranker_component_latency_ms": _distribution(reranker_latencies),
        "base_static_embedding_ms": base_static_ms,
        "gte_static_embedding_ms": gte_static_ms,
    }

    gates = {
        "supported_exact_route_accuracy": (
            metrics["supported_exact_route_accuracy"] >= 0.85
        ),
        "near_domain_unsupported_rejection": (
            metrics["near_domain_unsupported_rejection"] >= 0.97
        ),
        "false_route_rate": metrics["false_route_rate"] <= 0.01,
        "additional_false_routes": metrics["additional_false_routes"] <= 0,
        "rescued_false_routes": rescued_false_routes == 0,
        "invalid_plans": invalid == 0,
        "execution_errors": errors == 0,
        "base_accept_changes": base_changes == 0,
        "winner_changes_on_rescue": winner_changes == 0,
        "planner_direct_parity": (
            parity_mismatches == 0 if direct_parity else True
        ),
        "expected_supported_correct": (
            supported_correct == expected_supported_correct
            if expected_supported_correct is not None
            else True
        ),
        "expected_false_routes": (
            false_routes == expected_false_routes
            if expected_false_routes is not None
            else True
        ),
    }

    return {
        "candidate": {
            "name": "bge-m3-055-zero-false-crossmodel-rescue-v1",
            "base_model": BASE_MODEL_NAME,
            "base_revision": BASE_MODEL_REVISION,
            "gte_model": GTE_MODEL_NAME,
            "gte_revision": GTE_MODEL_REVISION,
            "reranker_model": RERANKER_MODEL_NAME,
            "reranker_revision": RERANKER_MODEL_REVISION,
            "reranker_max_length": RERANKER_MAX_LENGTH,
        },
        "cases": len(rows),
        "metrics": metrics,
        "gates": gates,
        "all_confirmation_gates_pass": all(gates.values()),
        "rows": rows,
        "policy": {
            "calibration_or_blind_used": False,
            "candidate_frozen_before_execution": True,
            "base_acceptances_immutable": True,
            "same_winner_rescue_only": True,
            "rank2_fallthrough": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--direct-parity", action="store_true")
    parser.add_argument("--expected-supported-correct", type=int)
    parser.add_argument("--expected-false-routes", type=int)
    args = parser.parse_args()

    cases = json.loads(args.corpus.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or any(
        not isinstance(item, dict) for item in cases
    ):
        raise ValueError("corpus must be a JSON object list")

    result = evaluate(
        cases,
        direct_parity=args.direct_parity,
        expected_supported_correct=args.expected_supported_correct,
        expected_false_routes=args.expected_false_routes,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "all_confirmation_gates_pass": result[
                    "all_confirmation_gates_pass"
                ],
                "metrics": result["metrics"],
                "gates": result["gates"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if not result["all_confirmation_gates_pass"]:
        raise SystemExit("frozen cross-model rescue candidate failed gates")


if __name__ == "__main__":
    main()
