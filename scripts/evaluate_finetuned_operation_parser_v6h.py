"""Train frozen V6H parser and evaluate DEV exactly once.

The frozen training bank is consumed only for the preregistered generic
scope/operation task. Confirmation is never read by this script.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v6h_catalog import development_registry  # noqa: E402
from benchmarks.schema_adb_baseline import (  # noqa: E402
    BGE_MODEL,
    BGE_REVISION,
    compile_registry_contracts,
)
from benchmarks.schema_finetuned_operation_parser import (  # noqa: E402
    BACKGROUND,
    MINILM_MODEL,
    MINILM_REVISION,
    TOOL_OPERATION,
    FineTunedOperationMembershipRouter,
    assert_finite_history,
    metadata_sha256,
    save_trained_state,
    state_metadata,
    train_multitask_model,
)


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


def _tool(route_id: str) -> str:
    return route_id.split(".", 1)[0]


def evaluate(
    rows: list[dict[str, Any]],
    *,
    state_out: Path,
    metadata_out: Path,
) -> dict[str, Any]:
    from sentence_transformers import SentenceTransformer

    if len(rows) != 552:
        raise ValueError("V6H DEV must contain exactly 552 rows")

    training_started = time.perf_counter_ns()
    parser_model, tokenizer, epoch_history = train_multitask_model(device="cpu")
    training_ms = (time.perf_counter_ns() - training_started) / 1_000_000
    assert_finite_history(epoch_history)

    state_sha = save_trained_state(parser_model, state_out)
    train_metadata = state_metadata(
        state_sha256=state_sha,
        epoch_history=epoch_history,
    )
    train_metadata["metadata_sha256"] = metadata_sha256(train_metadata)
    train_metadata["training_ms"] = training_ms
    metadata_out.parent.mkdir(parents=True, exist_ok=True)
    metadata_out.write_text(
        json.dumps(train_metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    bge_load_started = time.perf_counter_ns()
    bge = SentenceTransformer(
        BGE_MODEL,
        revision=BGE_REVISION,
        trust_remote_code=False,
        device="cpu",
    )
    bge_load_ms = (time.perf_counter_ns() - bge_load_started) / 1_000_000

    registry = development_registry()
    contracts = compile_registry_contracts(registry)

    compile_started = time.perf_counter_ns()
    router = FineTunedOperationMembershipRouter(
        registry,
        _embedder(bge),
        parser_model,
        tokenizer,
        device="cpu",
    )
    compile_ms = (time.perf_counter_ns() - compile_started) / 1_000_000

    result_rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    errors = 0
    switches = 0
    authority = 0

    for case in rows:
        started = time.perf_counter_ns()
        try:
            result = router.route(str(case["query"]))
            elapsed = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed)

            predicted = result["predicted"]
            raw_top = result["raw_top_route"]
            if predicted is not None and predicted != raw_top:
                switches += 1
                authority += 1
            if predicted is not None and predicted not in router.route_ids:
                authority += 1

            expected = case.get("expected")
            gold_operation: str | None
            if expected is not None:
                gold_operation = str(contracts[str(expected)].leaf)
            else:
                unsupported_action = case.get("unsupported_action")
                gold_operation = (
                    str(unsupported_action)
                    if unsupported_action is not None
                    else None
                )

            expected_scope = (
                BACKGROUND
                if case["category"] == "out_of_domain"
                else TOOL_OPERATION
            )

            result_rows.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "category": case["category"],
                    "language": case["language"],
                    "expected": expected,
                    "predicted": predicted,
                    "raw_top_route": raw_top,
                    "scope_class": result["scope_class"],
                    "operation_class": result["operation_class"],
                    "expected_scope": expected_scope,
                    "gold_operation": gold_operation,
                    "reason": result["reason"],
                    "latency_ms": elapsed,
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed)
            errors += 1
            result_rows.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "category": case["category"],
                    "language": case["language"],
                    "expected": case.get("expected"),
                    "predicted": None,
                    "raw_top_route": None,
                    "scope_class": None,
                    "operation_class": None,
                    "expected_scope": (
                        BACKGROUND
                        if case["category"] == "out_of_domain"
                        else TOOL_OPERATION
                    ),
                    "gold_operation": case.get("unsupported_action"),
                    "reason": "exception",
                    "latency_ms": elapsed,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    supported = [row for row in result_rows if row["category"] == "supported"]
    near = [
        row
        for row in result_rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in result_rows if row["category"] == "out_of_domain"]
    unsupported = [*near, *ood]

    supported_exact = sum(
        row["predicted"] == row["expected"] for row in supported
    )
    raw_exact = sum(
        row["raw_top_route"] == row["expected"] for row in supported
    )
    raw_tool = sum(
        row["raw_top_route"] is not None
        and _tool(str(row["raw_top_route"])) == _tool(str(row["expected"]))
        for row in supported
    )
    near_rejected = sum(row["predicted"] is None for row in near)
    ood_rejected = sum(row["predicted"] is None for row in ood)
    false_routes = sum(row["predicted"] is not None for row in unsupported)
    raw_correct_vetoed = sum(
        row["raw_top_route"] == row["expected"] and row["predicted"] is None
        for row in supported
    )
    vetoes = sum(row["predicted"] is None for row in result_rows)
    true_vetoes = sum(row["predicted"] is None for row in unsupported)

    scope_correct = sum(
        row["scope_class"] == row["expected_scope"]
        for row in result_rows
        if row["scope_class"] is not None
    )
    supported_operation_correct = sum(
        row["operation_class"] == row["gold_operation"]
        for row in supported
        if row["operation_class"] is not None
    )
    near_operation_correct = sum(
        row["operation_class"] == row["gold_operation"]
        for row in near
        if row["operation_class"] is not None
    )

    reason_counts: dict[str, int] = {}
    scope_counts: dict[str, dict[str, int]] = {}
    for row in result_rows:
        reason = str(row["reason"])
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        category = str(row["category"])
        scope = str(row["scope_class"])
        scope_counts.setdefault(category, {})
        scope_counts[category][scope] = (
            scope_counts[category].get(scope, 0) + 1
        )

    per_language: dict[str, dict[str, float | int]] = {}
    for language in sorted({str(row["language"]) for row in result_rows}):
        group = [row for row in result_rows if row["language"] == language]
        supp = [row for row in group if row["category"] == "supported"]
        unsup = [row for row in group if row["category"] != "supported"]
        per_language[language] = {
            "cases": len(group),
            "supported_exact": (
                sum(row["predicted"] == row["expected"] for row in supp)
                / len(supp)
            ),
            "unsupported_rejection": (
                sum(row["predicted"] is None for row in unsup)
                / len(unsup)
            ),
        }

    latency = _distribution(latencies)
    p95 = latency["p95"]
    metrics: dict[str, Any] = {
        "supported_exact_route_accuracy": supported_exact / len(supported),
        "raw_supported_exact_route_accuracy": raw_exact / len(supported),
        "raw_supported_tool_accuracy": raw_tool / len(supported),
        "near_domain_unsupported_rejection": near_rejected / len(near),
        "out_of_domain_rejection": ood_rejected / len(ood),
        "false_routes": false_routes,
        "false_route_rate": false_routes / len(unsupported),
        "raw_correct_winner_vetoed": raw_correct_vetoed,
        "raw_correct_winner_veto_rate": (
            raw_correct_vetoed / raw_exact if raw_exact else 0.0
        ),
        "vetoes": vetoes,
        "true_unsupported_vetoes": true_vetoes,
        "veto_precision": true_vetoes / vetoes if vetoes else 0.0,
        "veto_recall": true_vetoes / len(unsupported),
        "scope_accuracy": scope_correct / len(result_rows),
        "supported_operation_accuracy": (
            supported_operation_correct / len(supported)
        ),
        "near_domain_operation_accuracy": near_operation_correct / len(near),
        "reason_counts": reason_counts,
        "scope_counts_by_category": scope_counts,
        "combined_query_latency_ms": latency,
        "training_ms": training_ms,
        "bge_model_load_ms": bge_load_ms,
        "router_compile_ms": compile_ms,
        "positive_route_switches": switches,
        "authority_violations": authority,
        "execution_errors": errors,
        "per_language": per_language,
    }

    quality_gates = {
        "supported_exact_route_accuracy": (
            metrics["supported_exact_route_accuracy"] >= 0.85
        ),
        "near_domain_unsupported_rejection": (
            metrics["near_domain_unsupported_rejection"] >= 0.97
        ),
        "out_of_domain_rejection": metrics["out_of_domain_rejection"] == 1.0,
        "false_route_rate": metrics["false_route_rate"] <= 0.01,
        "authority_violations": authority == 0,
        "positive_route_switches": switches == 0,
        "execution_errors": errors == 0,
    }
    runtime_gate = p95 is not None and float(p95) <= 250.0

    return {
        "experiment": "end-to-end-multilingual-operation-oos-parser-v1",
        "issue": 415,
        "surface": "V6H-development",
        "models": {
            "bge": {"name": BGE_MODEL, "revision": BGE_REVISION},
            "parser_base": {
                "name": MINILM_MODEL,
                "revision": MINILM_REVISION,
            },
        },
        "trained_state": train_metadata,
        "metrics": metrics,
        "quality_gates": quality_gates,
        "runtime_gate": runtime_gate,
        "quality_pass": all(quality_gates.values()),
        "surface_pass": all(quality_gates.values()) and runtime_gate,
        "policy": {
            "confirmation_scored": False,
            "raw_bge_is_sole_positive_selector": True,
            "parser_veto_only": True,
            "positive_rerank": False,
            "endpoint_switch": False,
            "rank2_fallback": False,
            "pseudo_route": False,
            "probability_threshold": None,
            "margin_threshold": None,
            "validation_split": False,
            "early_stopping": False,
            "dev_selected_hyperparameters": False,
        },
        "rows": result_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--state-out", type=Path, required=True)
    parser.add_argument("--metadata-out", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rows = json.loads(args.development.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("development corpus must be a list of objects")

    result = evaluate(
        rows,
        state_out=args.state_out,
        metadata_out=args.metadata_out,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "surface": result["surface"],
                "quality_pass": result["quality_pass"],
                "runtime_gate": result["runtime_gate"],
                "surface_pass": result["surface_pass"],
                "trained_state": result["trained_state"],
                "metrics": result["metrics"],
                "quality_gates": result["quality_gates"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
