"""DEV-only Laya choice+noul open-set routing diagnostic."""

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

ACCEPTANCE_THRESHOLDS = (0.50, 0.70, 0.80, 0.90, 0.95, 0.98, 0.99, 0.995)
CHOICE_INSTRUCTIONS = (
    "Choose the single registered endpoint that can fully execute the user's requested "
    "operation. Use only capabilities explicitly stated in the registered capability "
    "catalog. Do not infer unlisted operations or capabilities. Return exactly one "
    "offered route ID."
)
NOUL_INSTRUCTIONS = (
    "At least one registered endpoint listed in the capability catalog can fully execute "
    "the user's requested operation exactly as requested, using only capabilities "
    "explicitly stated in that catalog. Do not infer unlisted operations or capabilities."
)
SCOPE_RULE = (
    "This endpoint supports only the capability explicitly stated above. "
    "Unlisted operations are not supported by this endpoint."
)


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    pos = q * (len(values) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return values[lo]
    w = pos - lo
    return values[lo] * (1 - w) + values[hi] * w


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "min": min(values) if values else None,
        "p50": _quantile(values, 0.50),
        "p95": _quantile(values, 0.95),
        "max": max(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
    }


def build_catalog() -> tuple[list[dict[str, Any]], dict[str, str]]:
    registry = reference_registry()
    catalog: list[dict[str, Any]] = []
    criteria: dict[str, str] = {}
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            route = f"{tool.key}.{endpoint.name}"
            aliases = sorted(str(item) for item in endpoint.operation_aliases)
            item = {
                "id": route,
                "tool_scope": tool.description,
                "endpoint_capability": endpoint.description,
                "operation_aliases": aliases,
            }
            catalog.append(item)
            criteria[route] = (
                f"Tool scope: {tool.description}\n"
                f"Explicit endpoint capability: {endpoint.description}\n"
                f"Trusted operation aliases: {', '.join(aliases)}\n"
                f"Scope rule: {SCOPE_RULE}"
            )
    return catalog, criteria


def build_questions(criteria: dict[str, str]) -> dict[str, dict[str, Any]]:
    return {
        "selection": {
            "type": "choice",
            "instructions": CHOICE_INSTRUCTIONS,
            "criteria": criteria,
        },
        "capable": {
            "type": "noul",
            "instructions": NOUL_INSTRUCTIONS,
        },
    }


def _safe_rate(n: int, d: int) -> float:
    return n / d if d else 0.0


def _evaluate_threshold(rows: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    supported = [r for r in rows if r["expected"] is not None]
    near = [r for r in rows if r["category"] == "near_domain_unsupported_operation"]
    ood = [r for r in rows if r["category"] == "out_of_domain"]
    unsupported = [r for r in rows if r["expected"] is None]

    def accepted(row: dict[str, Any]) -> bool:
        value = row["p_capable"]
        return value is not None and float(value) >= threshold

    supported_correct = sum(
        accepted(r) and r["predicted"] == r["expected"] for r in supported
    )
    wrong_supported_accepted = sum(
        accepted(r) and r["predicted"] != r["expected"] for r in supported
    )
    near_rejected = sum(not accepted(r) for r in near)
    ood_rejected = sum(not accepted(r) for r in ood)
    false_routes = sum(accepted(r) for r in unsupported)

    exact = _safe_rate(supported_correct, len(supported))
    near_rejection = _safe_rate(near_rejected, len(near))
    ood_rejection = _safe_rate(ood_rejected, len(ood))
    false_rate = _safe_rate(false_routes, len(unsupported))

    return {
        "rule_id": f"laya-noul-p{threshold:.3f}",
        "threshold": threshold,
        "supported_correct": supported_correct,
        "supported_exact_route_accuracy": exact,
        "wrong_supported_accepted": wrong_supported_accepted,
        "near_domain_rejected": near_rejected,
        "near_domain_unsupported_rejection": near_rejection,
        "ood_rejected": ood_rejected,
        "out_of_domain_rejection": ood_rejection,
        "false_routes": false_routes,
        "false_route_rate": false_rate,
        "quality_gate_pass": (
            exact >= 0.85
            and near_rejection >= 0.97
            and ood_rejection == 1.0
            and false_rate <= 0.01
        ),
    }


def evaluate(corpus_path: Path) -> dict[str, Any]:
    import laya
    from laya.lang import analyse

    catalog, criteria = build_catalog()
    allowed = set(criteria)
    cases = load_corpus(corpus_path, allowed_routes=allowed)
    questions = build_questions(criteria)

    load_started = time.perf_counter_ns()
    router = laya.Router(device="cpu", max_loaded=2, preload=False)
    router.preload(["english", "multilingual"])
    model_load_ms = (time.perf_counter_ns() - load_started) / 1_000_000

    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    errors = 0
    authority_violations = 0

    for case in cases:
        state = {
            "user_request": case.query,
            "capability_catalog": catalog,
        }
        detected = analyse(case.query)
        lang_guess = detected.get("language") if isinstance(detected, dict) else None

        started = time.perf_counter_ns()
        try:
            response = router.predict(
                state,
                questions,
                lang_guess=lang_guess,
            )
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            answers = response["answers"]
            choice = answers["selection"]
            predicted = str(choice["choice"])
            choice_confidence = float(choice["confidence"])
            p_capable = float(answers["capable"]["noul"])
            if predicted not in allowed:
                authority_violations += 1
                raise RuntimeError(f"unregistered route returned: {predicted}")
            routing = response.get("routing", {})
            model = routing.get("model") if isinstance(routing, dict) else None
            repo = routing.get("repo") if isinstance(routing, dict) else None
            error = None
        except Exception as exc:
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            predicted = None
            choice_confidence = None
            p_capable = None
            model = None
            repo = None
            error = f"{type(exc).__name__}: {exc}"
            errors += 1

        latencies.append(elapsed_ms)
        rows.append(
            {
                "case_id": case.id,
                "category": case.category,
                "language": case.language,
                "unsupported_family": case.unsupported_family,
                "expected": case.expected,
                "predicted": predicted,
                "choice_confidence": choice_confidence,
                "p_capable": p_capable,
                "provider_language_guess": lang_guess,
                "model": model,
                "repo": repo,
                "latency_ms": elapsed_ms,
                "error": error,
            }
        )

    rules = [_evaluate_threshold(rows, t) for t in ACCEPTANCE_THRESHOLDS]
    passing = [
        r
        for r in rules
        if r["quality_gate_pass"] and errors == 0 and authority_violations == 0
    ]
    passing.sort(
        key=lambda r: (
            -float(r["supported_exact_route_accuracy"]),
            int(r["false_routes"]),
            float(r["threshold"]),
        )
    )
    runtime = _distribution(latencies)
    runtime_pass = runtime["p95"] is not None and float(runtime["p95"]) <= 250.0

    supported = [r for r in rows if r["expected"] is not None]
    raw_correct = sum(r["predicted"] == r["expected"] for r in supported)

    groups = {
        "supported_correct_choice": [
            float(r["p_capable"])
            for r in rows
            if r["expected"] is not None
            and r["predicted"] == r["expected"]
            and r["p_capable"] is not None
        ],
        "supported_wrong_choice": [
            float(r["p_capable"])
            for r in rows
            if r["expected"] is not None
            and r["predicted"] != r["expected"]
            and r["p_capable"] is not None
        ],
        "near_domain_unsupported": [
            float(r["p_capable"])
            for r in rows
            if r["category"] == "near_domain_unsupported_operation"
            and r["p_capable"] is not None
        ],
        "out_of_domain": [
            float(r["p_capable"])
            for r in rows
            if r["category"] == "out_of_domain" and r["p_capable"] is not None
        ],
    }

    return {
        "experiment": "laya-choice-noul-open-set-v1",
        "summary": {
            "cases": len(rows),
            "raw_supported_choice_accuracy": _safe_rate(raw_correct, len(supported)),
            "quality_worthy_rule_count": len(passing),
            "best_quality_rule": passing[0] if passing else None,
            "runtime_target_pass": runtime_pass,
            "promotable_rule_count": len(passing) if runtime_pass else 0,
            "execution_errors": errors,
            "authority_violations": authority_violations,
            "p_capable_geometry": {
                key: _distribution(values) for key, values in groups.items()
            },
        },
        "runtime": {
            "model_load_ms": model_load_ms,
            "single_request_latency_ms": runtime,
        },
        "rule_results": rules,
        "rows": rows,
        "policy": {
            "data_role": "tuning_eligible_development",
            "failed_270_fresh_used": False,
            "failed_287_fresh_used": False,
            "calibration_or_blind_used": False,
            "benchmark_language_used_for_provider_routing": False,
            "choice_selects_registered_routes_only": True,
            "noul_veto_only": True,
            "rank2_fallback": False,
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
                "best_quality_rule": result["summary"]["best_quality_rule"],
                "runtime_target_pass": result["summary"]["runtime_target_pass"],
                "latency_ms": result["runtime"]["single_request_latency_ms"],
                "errors": result["summary"]["execution_errors"],
                "authority_violations": result["summary"]["authority_violations"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
