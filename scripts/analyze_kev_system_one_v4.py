"""DEV-only Kev System One choice+noul diagnostic for routing quality v4."""

from __future__ import annotations

import argparse
import json
import math
import os
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

THRESHOLDS = (0.50, 0.70, 0.80, 0.90, 0.95, 0.98, 0.99, 0.995)
ROUTE_INSTRUCTION = (
    "Choose the single registered endpoint that best matches the requested operation. "
    "Use only the explicit endpoint contracts. Do not infer capabilities that are not stated."
)
SUPPORTED_INSTRUCTION = (
    "Can at least one registered endpoint in the supplied endpoint contracts fully execute "
    "the user's requested operation without inferring any unlisted capability?"
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
        "p05": _quantile(values, 0.05),
        "p25": _quantile(values, 0.25),
        "p50": _quantile(values, 0.50),
        "p75": _quantile(values, 0.75),
        "p95": _quantile(values, 0.95),
        "max": max(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
    }


def _safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def endpoint_contracts() -> dict[str, str]:
    registry = reference_registry()
    contracts: dict[str, str] = {}
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            route = f"{tool.key}.{endpoint.name}"
            aliases = ", ".join(sorted(str(item) for item in endpoint.operation_aliases))
            parts = [
                f"Registered endpoint: {route}",
                f"Tool scope: {tool.description}",
                f"Explicit endpoint capability: {endpoint.description}",
            ]
            if aliases:
                parts.append(f"Trusted operation aliases: {aliases}")
            parts.append(f"Scope rule: {SCOPE_RULE}")
            contracts[route] = "\n".join(parts)
    return contracts


def _accepted(row: dict[str, Any], family: str, threshold: float) -> bool:
    value = (
        row["choice_confidence"]
        if family == "choice_confidence"
        else row["supported_probability"]
    )
    return value is not None and float(value) >= threshold


def _evaluate_rule(
    rows: list[dict[str, Any]],
    *,
    family: str,
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

    supported_correct = sum(
        _accepted(row, family, threshold) and row["predicted"] == row["expected"]
        for row in supported
    )
    wrong_supported_accepted = sum(
        _accepted(row, family, threshold) and row["predicted"] != row["expected"]
        for row in supported
    )
    near_rejected = sum(not _accepted(row, family, threshold) for row in near)
    ood_rejected = sum(not _accepted(row, family, threshold) for row in ood)
    false_routes = sum(_accepted(row, family, threshold) for row in unsupported)

    supported_exact = _safe_rate(supported_correct, len(supported))
    near_rejection = _safe_rate(near_rejected, len(near))
    ood_rejection = _safe_rate(ood_rejected, len(ood))
    false_rate = _safe_rate(false_routes, len(unsupported))

    per_language: dict[str, Any] = {}
    for language in sorted({str(row["language"]) for row in rows}):
        subset = [row for row in rows if str(row["language"]) == language]
        lang_supported = [row for row in subset if row["expected"] is not None]
        lang_unsupported = [row for row in subset if row["expected"] is None]
        per_language[language] = {
            "cases": len(subset),
            "supported_exact_route_accuracy": _safe_rate(
                sum(
                    _accepted(row, family, threshold)
                    and row["predicted"] == row["expected"]
                    for row in lang_supported
                ),
                len(lang_supported),
            ),
            "unsupported_rejection": _safe_rate(
                sum(
                    not _accepted(row, family, threshold)
                    for row in lang_unsupported
                ),
                len(lang_unsupported),
            ),
            "false_routes": sum(
                _accepted(row, family, threshold) for row in lang_unsupported
            ),
        }

    per_route: dict[str, Any] = {}
    for route in sorted(
        {str(row["expected"]) for row in supported if row["expected"] is not None}
    ):
        subset = [row for row in supported if row["expected"] == route]
        per_route[route] = {
            "cases": len(subset),
            "exact": sum(
                _accepted(row, family, threshold) and row["predicted"] == route
                for row in subset
            ),
            "exact_rate": _safe_rate(
                sum(
                    _accepted(row, family, threshold)
                    and row["predicted"] == route
                    for row in subset
                ),
                len(subset),
            ),
        }

    per_family: dict[str, Any] = {}
    families = sorted(
        {
            str(row["unsupported_family"])
            for row in rows
            if row["unsupported_family"] is not None
        }
    )
    for unsupported_family in families:
        subset = [
            row
            for row in rows
            if str(row["unsupported_family"]) == unsupported_family
        ]
        rejected = sum(
            not _accepted(row, family, threshold) for row in subset
        )
        per_family[unsupported_family] = {
            "cases": len(subset),
            "rejected": rejected,
            "rejection_rate": _safe_rate(rejected, len(subset)),
        }

    quality_pass = (
        supported_exact >= 0.85
        and near_rejection >= 0.97
        and ood_rejection == 1.0
        and false_rate <= 0.01
    )
    return {
        "rule_id": f"{family}-p{threshold:.3f}",
        "family": family,
        "threshold": threshold,
        "supported_correct": supported_correct,
        "supported_exact_route_accuracy": supported_exact,
        "wrong_supported_accepted": wrong_supported_accepted,
        "near_domain_rejected": near_rejected,
        "near_domain_unsupported_rejection": near_rejection,
        "ood_rejected": ood_rejected,
        "out_of_domain_rejection": ood_rejection,
        "false_routes": false_routes,
        "false_route_rate": false_rate,
        "per_language": per_language,
        "per_expected_route": per_route,
        "unsupported_family_rejection": per_family,
        "quality_gate_pass": quality_pass,
    }


def _geometry(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    groups = {
        "supported_correct_choice": [
            row for row in rows
            if row["expected"] is not None and row["predicted"] == row["expected"]
        ],
        "supported_wrong_choice": [
            row for row in rows
            if row["expected"] is not None and row["predicted"] != row["expected"]
        ],
        "near_domain_unsupported": [
            row for row in rows
            if row["category"] == "near_domain_unsupported_operation"
        ],
        "out_of_domain": [
            row for row in rows if row["category"] == "out_of_domain"
        ],
    }
    return {
        name: _distribution(
            [
                float(row[field])
                for row in group
                if row[field] is not None
            ]
        )
        for name, group in groups.items()
    }


def evaluate(
    corpus_path: Path,
    *,
    base_url: str,
    api_key: str,
    model: str,
) -> dict[str, Any]:
    from typesafe_sdk import Choice, Noul, TypeSafeClient

    contracts = endpoint_contracts()
    allowed_routes = set(contracts)
    cases = load_corpus(corpus_path, allowed_routes=allowed_routes)

    questions = {
        "route": Choice(
            instructions=ROUTE_INSTRUCTION,
            criteria=contracts,
        ),
        "supported": Noul(
            instructions=SUPPORTED_INSTRUCTION,
            criteria={
                "true": (
                    "At least one explicit registered endpoint contract fully supports "
                    "the requested operation."
                ),
                "false": (
                    "No explicit registered endpoint contract fully supports "
                    "the requested operation."
                ),
            },
        ),
    }

    setup_started = time.perf_counter_ns()
    client = TypeSafeClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
    )
    client_setup_ms = (time.perf_counter_ns() - setup_started) / 1_000_000

    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    errors = 0
    authority_violations = 0

    try:
        for case in cases:
            state = {
                "query": case.query,
                "registered_endpoints": contracts,
            }
            started = time.perf_counter_ns()
            try:
                response = client.system_one(
                    state=state,
                    questions=questions,
                )
                latency_ms = (time.perf_counter_ns() - started) / 1_000_000
                route_answer = response.choices["route"]
                supported_answer = response.nouls["supported"]
                predicted = str(route_answer.choice)
                choice_confidence = float(route_answer.confidence)
                supported_probability = float(supported_answer.noul)
                if predicted not in allowed_routes:
                    authority_violations += 1
                    raise ValueError(
                        f"provider returned unknown route {predicted!r}"
                    )
                if (
                    not math.isfinite(choice_confidence)
                    or not 0.0 <= choice_confidence <= 1.0
                    or not math.isfinite(supported_probability)
                    or not 0.0 <= supported_probability <= 1.0
                ):
                    raise ValueError("provider returned invalid probability")
                error = None
            except Exception as exc:
                latency_ms = (time.perf_counter_ns() - started) / 1_000_000
                predicted = None
                choice_confidence = None
                supported_probability = None
                error = f"{type(exc).__name__}: {exc}"
                errors += 1
            latencies.append(latency_ms)
            rows.append(
                {
                    "case_id": case.id,
                    "category": case.category,
                    "language": case.language,
                    "unsupported_family": case.unsupported_family,
                    "expected": case.expected,
                    "predicted": predicted,
                    "choice_confidence": choice_confidence,
                    "supported_probability": supported_probability,
                    "latency_ms": latency_ms,
                    "error": error,
                }
            )
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()

    rules = [
        _evaluate_rule(rows, family=family, threshold=threshold)
        for family in ("choice_confidence", "noul_capability")
        for threshold in THRESHOLDS
    ]
    quality_worthy = [
        rule
        for rule in rules
        if rule["quality_gate_pass"]
        and errors == 0
        and authority_violations == 0
    ]
    quality_worthy.sort(
        key=lambda rule: (
            -float(rule["supported_exact_route_accuracy"]),
            int(rule["false_routes"]),
            -float(rule["near_domain_unsupported_rejection"]),
            float(rule["threshold"]),
        )
    )

    supported = [row for row in rows if row["expected"] is not None]
    raw_correct = sum(
        row["predicted"] == row["expected"] for row in supported
    )
    runtime = _distribution(latencies)
    runtime_pass = (
        runtime["p95"] is not None and float(runtime["p95"]) <= 250.0
    )

    return {
        "experiment": "kev-0.8b-choice-noul-v1",
        "summary": {
            "cases": len(rows),
            "supported_cases": len(supported),
            "raw_choice_supported_top1_accuracy": _safe_rate(
                raw_correct,
                len(supported),
            ),
            "fixed_rule_count": len(rules),
            "quality_worthy_rule_count": len(quality_worthy),
            "best_quality_rule": (
                quality_worthy[0] if quality_worthy else None
            ),
            "runtime_target_pass": runtime_pass,
            "promotable_rule_count": (
                len(quality_worthy) if runtime_pass else 0
            ),
            "execution_errors": errors,
            "authority_violations": authority_violations,
        },
        "runtime": {
            "client_setup_ms": client_setup_ms,
            "server_load_ms": (
                float(os.environ["KEV_SERVER_LOAD_MS"])
                if os.environ.get("KEV_SERVER_LOAD_MS")
                else None
            ),
            "single_request_latency_ms": runtime,
        },
        "probability_geometry": {
            "choice_confidence": _geometry(rows, "choice_confidence"),
            "supported_probability": _geometry(rows, "supported_probability"),
        },
        "rule_results": rules,
        "rows": rows,
        "policy": {
            "data_role": "tuning_eligible_development",
            "provider_training_on_schemarouter": False,
            "failed_270_fresh_used": False,
            "failed_287_fresh_used": False,
            "calibration_or_blind_used": False,
            "provider_can_create_route": False,
            "rank2_fallback": False,
            "prompt_variants_tested": 1,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8009")
    parser.add_argument("--api-key", default="local")
    parser.add_argument("--model", default="kev-latest")
    args = parser.parse_args()

    result = evaluate(
        args.corpus,
        base_url=args.base_url,
        api_key=args.api_key,
        model=args.model,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "raw_choice_supported_top1_accuracy": result["summary"][
                    "raw_choice_supported_top1_accuracy"
                ],
                "quality_worthy_rule_count": result["summary"][
                    "quality_worthy_rule_count"
                ],
                "runtime_target_pass": result["summary"][
                    "runtime_target_pass"
                ],
                "best_quality_rule": result["summary"]["best_quality_rule"],
                "latency_ms": result["runtime"]["single_request_latency_ms"],
                "errors": result["summary"]["execution_errors"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
