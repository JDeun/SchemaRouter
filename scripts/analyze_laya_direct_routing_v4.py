"""DEV-only direct Laya routing diagnostic for operation-routing quality v4."""

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

from benchmark_decision_routing import load_corpus, reference_registry  # noqa: E402

from schemarouter import DecisionOption, DecisionRequest, choose_sync  # noqa: E402
from schemarouter.integrations import LayaDecisionBackend  # noqa: E402

ACCEPTANCE_THRESHOLDS = (
    0.50,
    0.70,
    0.80,
    0.90,
    0.95,
    0.98,
    0.99,
    0.995,
)
SCOPE_RULE = (
    "This endpoint supports only the capability explicitly stated above. "
    "Unlisted operations are not supported by this endpoint."
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
        "p95": _quantile(values, 0.95),
        "max": max(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
    }


def _option_description(tool: Any, endpoint: Any) -> str:
    aliases = ", ".join(sorted(str(item) for item in endpoint.operation_aliases))
    parts = [
        f"Tool scope: {tool.description}",
        f"Explicit endpoint capability: {endpoint.description}",
    ]
    if aliases:
        parts.append(f"Trusted operation aliases: {aliases}")
    parts.append(f"Scope rule: {SCOPE_RULE}")
    return "\n".join(parts)


def build_options() -> list[DecisionOption]:
    registry = reference_registry()
    options: list[DecisionOption] = []
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            route = f"{tool.key}.{endpoint.name}"
            options.append(
                DecisionOption(
                    id=route,
                    label=route,
                    description=_option_description(tool, endpoint),
                )
            )
    return options


def _safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _evaluate_threshold(
    rows: list[dict[str, Any]],
    threshold: float,
) -> dict[str, Any]:
    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row["category"] == "out_of_domain"]
    unsupported = [row for row in rows if row["expected"] is None]

    def accepted(row: dict[str, Any]) -> bool:
        confidence = row["confidence"]
        return confidence is not None and float(confidence) >= threshold

    supported_correct = sum(
        accepted(row) and row["predicted"] == row["expected"] for row in supported
    )
    wrong_supported_accepted = sum(
        accepted(row) and row["predicted"] != row["expected"] for row in supported
    )
    near_rejected = sum(not accepted(row) for row in near)
    ood_rejected = sum(not accepted(row) for row in ood)
    false_routes = sum(accepted(row) for row in unsupported)

    supported_exact = _safe_rate(supported_correct, len(supported))
    near_rejection = _safe_rate(near_rejected, len(near))
    ood_rejection = _safe_rate(ood_rejected, len(ood))
    false_route_rate = _safe_rate(false_routes, len(unsupported))

    per_language: dict[str, Any] = {}
    for language in sorted({str(row["language"]) for row in rows}):
        lang_rows = [row for row in rows if str(row["language"]) == language]
        lang_supported = [row for row in lang_rows if row["expected"] is not None]
        lang_unsupported = [row for row in lang_rows if row["expected"] is None]
        per_language[language] = {
            "cases": len(lang_rows),
            "supported_exact_route_accuracy": _safe_rate(
                sum(
                    accepted(row) and row["predicted"] == row["expected"]
                    for row in lang_supported
                ),
                len(lang_supported),
            ),
            "unsupported_rejection": _safe_rate(
                sum(not accepted(row) for row in lang_unsupported),
                len(lang_unsupported),
            ),
            "false_routes": sum(accepted(row) for row in lang_unsupported),
        }

    quality_pass = (
        supported_exact >= 0.85
        and near_rejection >= 0.97
        and ood_rejection == 1.0
        and false_route_rate <= 0.01
    )
    return {
        "rule_id": f"laya-p{threshold:.3f}",
        "threshold": threshold,
        "supported_correct": supported_correct,
        "supported_exact_route_accuracy": supported_exact,
        "wrong_supported_accepted": wrong_supported_accepted,
        "near_domain_rejected": near_rejected,
        "near_domain_unsupported_rejection": near_rejection,
        "ood_rejected": ood_rejected,
        "out_of_domain_rejection": ood_rejection,
        "false_routes": false_routes,
        "false_route_rate": false_route_rate,
        "per_language": per_language,
        "quality_gate_pass": quality_pass,
    }


def evaluate(corpus_path: Path) -> dict[str, Any]:
    options = build_options()
    allowed_routes = {option.id for option in options}
    cases = load_corpus(corpus_path, allowed_routes=allowed_routes)

    load_started = time.perf_counter_ns()
    backend = LayaDecisionBackend(
        model=None,
        min_confidence=0.0,
        device="cpu",
        preload=True,
        max_loaded=2,
        async_mode=False,
        include_context=False,
    )
    model_load_ms = (time.perf_counter_ns() - load_started) / 1_000_000

    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    errors = 0

    for case in cases:
        request = DecisionRequest(
            query=case.query,
            options=options,
            max_selections=1,
        )
        started = time.perf_counter_ns()
        try:
            result = choose_sync(backend, request)
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed_ms)
            if result.abstained or not result.selections:
                predicted = None
                confidence = None
            else:
                predicted = result.selections[0].option_id
                confidence = result.selections[0].score
            metadata = dict(result.metadata)
            error = None
        except Exception as exc:
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed_ms)
            predicted = None
            confidence = None
            metadata = {}
            error = f"{type(exc).__name__}: {exc}"
            errors += 1

        rows.append(
            {
                "case_id": case.id,
                "category": case.category,
                "language": case.language,
                "unsupported_family": case.unsupported_family,
                "expected": case.expected,
                "predicted": predicted,
                "confidence": confidence,
                "latency_ms": elapsed_ms,
                "model": metadata.get("model"),
                "repo": metadata.get("repo"),
                "requested_device": metadata.get("requested_device"),
                "actual_device": metadata.get("actual_device"),
                "error": error,
            }
        )

    rules = [_evaluate_threshold(rows, threshold) for threshold in ACCEPTANCE_THRESHOLDS]
    passing = [rule for rule in rules if rule["quality_gate_pass"] and errors == 0]
    passing.sort(
        key=lambda rule: (
            -float(rule["supported_exact_route_accuracy"]),
            int(rule["false_routes"]),
            -float(rule["near_domain_unsupported_rejection"]),
            float(rule["threshold"]),
        )
    )
    runtime = _distribution(latencies)
    runtime_pass = (
        runtime["p95"] is not None and float(runtime["p95"]) <= 250.0
    )

    supported = [row for row in rows if row["expected"] is not None]
    raw_correct = sum(row["predicted"] == row["expected"] for row in supported)
    model_counts: dict[str, int] = {}
    for row in rows:
        model = row["model"]
        if isinstance(model, str):
            model_counts[model] = model_counts.get(model, 0) + 1

    return {
        "experiment": "direct-laya-system-one-routing-v1",
        "summary": {
            "cases": len(rows),
            "supported_cases": len(supported),
            "raw_supported_choice_accuracy": _safe_rate(raw_correct, len(supported)),
            "fixed_rule_count": len(rules),
            "quality_worthy_rule_count": len(passing),
            "best_quality_rule": passing[0] if passing else None,
            "runtime_target_pass": runtime_pass,
            "promotable_rule_count": len(passing) if runtime_pass else 0,
            "execution_errors": errors,
            "authority_violations": 0,
            "routed_model_counts": model_counts,
        },
        "runtime": {
            "model_load_ms": model_load_ms,
            "single_request_latency_ms": runtime,
        },
        "option_count": len(options),
        "option_ids": [option.id for option in options],
        "rule_results": rules,
        "rows": rows,
        "policy": {
            "data_role": "tuning_eligible_development",
            "failed_270_fresh_used": False,
            "failed_287_fresh_used": False,
            "calibration_or_blind_used": False,
            "full_registered_route_set": True,
            "provider_can_create_route": False,
            "rank2_fallback": False,
            "prompt_variants_tested": 1,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = evaluate(args.corpus)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "raw_supported_choice_accuracy": result["summary"][
                    "raw_supported_choice_accuracy"
                ],
                "quality_worthy_rule_count": result["summary"][
                    "quality_worthy_rule_count"
                ],
                "runtime_target_pass": result["summary"]["runtime_target_pass"],
                "best_quality_rule": result["summary"]["best_quality_rule"],
                "latency_ms": result["runtime"]["single_request_latency_ms"],
                "errors": result["summary"]["execution_errors"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
