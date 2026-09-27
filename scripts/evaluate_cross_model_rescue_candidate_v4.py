"""Execute the frozen zero-false cross-model candidate through SchemaPlanner."""

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
    AcceptAllRegisteredRecallBackend,
)
from benchmarks.cross_model_rescue_candidate import (  # noqa: E402
    BASE_MODEL_NAME,
    BASE_MODEL_REVISION,
    GTE_MODEL_NAME,
    GTE_MODEL_REVISION,
    RERANKER_MAX_LENGTH,
    RERANKER_MODEL_NAME,
    RERANKER_MODEL_REVISION,
    RESCUE_EPSILON,
    FrozenCrossModelRescueBackend,
)
from schemarouter import DecisionPolicy, PlanRequest, SchemaPlanner  # noqa: E402


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
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


def _load_sentence_model(
    name: str,
    revision: str,
    *,
    trust_remote_code: bool,
) -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        name,
        revision=revision,
        trust_remote_code=trust_remote_code,
    )


class _WinnerReranker:
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

    def score(self, query: str, text: str) -> float:
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
                f"{RERANKER_MODEL_NAME} returned unexpected logits "
                f"shape {tuple(flat.shape)}"
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
    dataset_role: str,
) -> dict[str, Any]:
    registry = reference_registry()

    load_started = time.perf_counter_ns()
    base_model = _load_sentence_model(
        BASE_MODEL_NAME,
        BASE_MODEL_REVISION,
        trust_remote_code=False,
    )
    gte_model = _load_sentence_model(
        GTE_MODEL_NAME,
        GTE_MODEL_REVISION,
        trust_remote_code=True,
    )
    reranker = _WinnerReranker()
    model_load_ms = (time.perf_counter_ns() - load_started) / 1_000_000

    init_started = time.perf_counter_ns()
    backend = FrozenCrossModelRescueBackend(
        registry,
        base_embedder=_embedder(base_model),
        gte_static_embedder=_embedder(gte_model),
        gte_query_embedder=_embedder(gte_model),
        reranker_scorer=reranker.score,
    )
    candidate_init_ms = (time.perf_counter_ns() - init_started) / 1_000_000

    planner = SchemaPlanner(
        registry,
        decision_backend=backend,
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
        candidate_recall_limit=len(backend.route_ids),
    )

    allowed_routes = set(backend.route_ids)
    rows: list[dict[str, Any]] = []
    direct_latencies: list[float] = []
    planner_latencies: list[float] = []
    base_latencies: list[float] = []
    gte_latencies: list[float] = []
    reranker_latencies: list[float] = []

    for case in cases:
        query = str(case["query"])
        expected = case.get("expected")

        direct_started = time.perf_counter_ns()
        direct = backend.score_routes(query, backend.route_ids)
        direct_ms = (time.perf_counter_ns() - direct_started) / 1_000_000
        direct_latencies.append(direct_ms)
        base_latencies.append(float(direct["base_latency_ms"]))
        if bool(direct["gte_invoked"]):
            gte_latencies.append(float(direct["gte_latency_ms"]))
        if bool(direct["reranker_invoked"]):
            reranker_latencies.append(float(direct["reranker_latency_ms"]))

        direct_predicted = (
            str(direct["final_route"])
            if bool(direct["final_accepted"])
            else None
        )
        base_predicted = (
            str(direct["base_top_route"])
            if bool(direct["base_accepted"])
            else None
        )

        started = time.perf_counter_ns()
        try:
            plan = planner.plan(PlanRequest(query=query, max_calls=1))
            planner_ms = (time.perf_counter_ns() - started) / 1_000_000
            predicted = _route_from_plan(plan)
            error = None
            warnings = list(plan.warnings)
        except Exception as exc:  # noqa: BLE001 - confirmation records every failure.
            planner_ms = (time.perf_counter_ns() - started) / 1_000_000
            predicted = None
            error = f"{type(exc).__name__}: {exc}"
            warnings = []
        planner_latencies.append(planner_ms)

        rows.append(
            {
                "case_id": case.get("id"),
                "category": case.get("category"),
                "language": case.get("language"),
                "unsupported_family": case.get("unsupported_family"),
                "expected": expected,
                "base_predicted": base_predicted,
                "base_raw_route": direct["base_top_route"],
                "base_accepted": direct["base_accepted"],
                "direct_predicted": direct_predicted,
                "predicted": predicted,
                "planner_matches_direct": predicted == direct_predicted,
                "invalid_plan": (
                    predicted is not None and predicted not in allowed_routes
                ),
                "winner_changed": (
                    direct_predicted is not None
                    and direct_predicted != str(direct["base_top_route"])
                ),
                "base_accept_changed": (
                    bool(direct["base_accepted"])
                    and direct_predicted != str(direct["base_top_route"])
                ),
                "rescue_accepted": direct["rescue_accepted"],
                "gte_invoked": direct["gte_invoked"],
                "gte_agrees": direct["gte_agrees"],
                "reranker_invoked": direct["reranker_invoked"],
                "base_latency_ms": direct["base_latency_ms"],
                "gte_latency_ms": direct["gte_latency_ms"],
                "reranker_latency_ms": direct["reranker_latency_ms"],
                "direct_latency_ms": direct_ms,
                "planner_latency_ms": planner_ms,
                "warnings": warnings,
                "error": error,
            }
        )

    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [
        row
        for row in rows
        if row["category"] == "out_of_domain"
    ]
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
    additional_false_routes = sum(
        row["expected"] is None
        and row["base_predicted"] is None
        and row["predicted"] is not None
        for row in rows
    )
    rescued_correct = sum(
        row["expected"] is not None
        and row["base_predicted"] is None
        and row["predicted"] == row["expected"]
        for row in rows
    )
    rescued_wrong_supported = sum(
        row["expected"] is not None
        and row["base_predicted"] is None
        and row["predicted"] is not None
        and row["predicted"] != row["expected"]
        for row in rows
    )

    parity_mismatches = sum(
        not bool(row["planner_matches_direct"]) for row in rows
    )
    invalid_plans = sum(bool(row["invalid_plan"]) for row in rows)
    errors = sum(row["error"] is not None for row in rows)
    winner_changes = sum(bool(row["winner_changed"]) for row in rows)
    base_accept_changes = sum(bool(row["base_accept_changed"]) for row in rows)

    metrics = {
        "base_supported_correct": base_supported_correct,
        "base_supported_exact_route_accuracy": (
            base_supported_correct / len(supported) if supported else 0.0
        ),
        "supported_correct": supported_correct,
        "supported_exact_route_accuracy": (
            supported_correct / len(supported) if supported else 0.0
        ),
        "near_domain_unsupported_rejection": (
            near_rejected / len(near) if near else 1.0
        ),
        "out_of_domain_rejection": (
            ood_rejected / len(ood) if ood else 1.0
        ),
        "base_false_routes": base_false_routes,
        "false_routes": false_routes,
        "false_route_rate": (
            false_routes / len(no_route) if no_route else 0.0
        ),
        "additional_false_routes": additional_false_routes,
        "rescued_correct_supported": rescued_correct,
        "rescued_wrong_supported": rescued_wrong_supported,
        "planner_direct_parity_mismatches": parity_mismatches,
        "invalid_plans": invalid_plans,
        "execution_errors": errors,
        "winner_changes": winner_changes,
        "base_accept_changes": base_accept_changes,
        "gte_invocations": sum(bool(row["gte_invoked"]) for row in rows),
        "gte_invocation_rate": (
            sum(bool(row["gte_invoked"]) for row in rows) / len(rows)
            if rows
            else 0.0
        ),
        "reranker_invocations": sum(
            bool(row["reranker_invoked"]) for row in rows
        ),
        "reranker_invocation_rate": (
            sum(bool(row["reranker_invoked"]) for row in rows) / len(rows)
            if rows
            else 0.0
        ),
        "model_load_ms": model_load_ms,
        "candidate_init_ms": candidate_init_ms,
        "base_latency_ms": _distribution(base_latencies),
        "gte_latency_ms": _distribution(gte_latencies),
        "reranker_latency_ms": _distribution(reranker_latencies),
        "direct_composed_latency_ms": _distribution(direct_latencies),
        "planner_latency_ms": _distribution(planner_latencies),
    }

    gates = {
        "supported_exact_route_accuracy": (
            metrics["supported_exact_route_accuracy"] >= 0.85
        ),
        "near_domain_unsupported_rejection": (
            metrics["near_domain_unsupported_rejection"] >= 0.97
        ),
        "false_route_rate": metrics["false_route_rate"] <= 0.01,
        "additional_false_routes": additional_false_routes == 0,
        "rescued_wrong_supported": rescued_wrong_supported == 0,
        "planner_matches_direct_case_by_case": parity_mismatches == 0,
        "invalid_plans": invalid_plans == 0,
        "execution_errors": errors == 0,
        "winner_changes": winner_changes == 0,
        "base_accept_changes": base_accept_changes == 0,
    }

    return {
        "candidate": {
            "name": "zero-false-cross-model-rescue-v1",
            "base_model": BASE_MODEL_NAME,
            "base_revision": BASE_MODEL_REVISION,
            "gte_model": GTE_MODEL_NAME,
            "gte_revision": GTE_MODEL_REVISION,
            "reranker_model": RERANKER_MODEL_NAME,
            "reranker_revision": RERANKER_MODEL_REVISION,
            "rescue_epsilon": RESCUE_EPSILON,
        },
        "dataset_role": dataset_role,
        "cases": len(rows),
        "supported_cases": len(supported),
        "near_domain_cases": len(near),
        "out_of_domain_cases": len(ood),
        "metrics": metrics,
        "gates": gates,
        "all_confirmation_gates_pass": all(gates.values()),
        "rows": rows,
        "policy": {
            "base_accepted_decisions_immutable": True,
            "same_winner_rescue_only": True,
            "rank2_fallback": False,
            "calibration_or_blind_used": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--dataset-role", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cases = json.loads(args.corpus.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or any(
        not isinstance(item, dict) for item in cases
    ):
        raise ValueError("corpus must be a JSON object list")

    result = evaluate(cases, dataset_role=args.dataset_role)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "dataset_role": args.dataset_role,
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
        raise SystemExit("cross-model frozen candidate failed confirmation gates")


if __name__ == "__main__":
    main()
