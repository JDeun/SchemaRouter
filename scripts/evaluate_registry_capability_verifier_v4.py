"""Evaluate preregistered registry capability verifier experiment #338."""

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
    MODEL_NAME,
    MODEL_REVISION,
    FrozenBgeM3DualViewBackend,
)
from benchmarks.registry_capability_holdout import (  # noqa: E402
    build_registry as build_registration_registry,
)
from benchmarks.registry_capability_holdout import cases as registration_cases  # noqa: E402
from benchmarks.registry_capability_holdout import manifest as registration_manifest  # noqa: E402
from benchmarks.registry_capability_verifier import RegistryCapabilityVerifier  # noqa: E402


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


def _load_model() -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        MODEL_NAME,
        revision=MODEL_REVISION,
        trust_remote_code=False,
    )


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


def _evaluate_surface(
    *,
    name: str,
    cases: list[dict[str, Any]],
    verifier: RegistryCapabilityVerifier,
    expected_categories: tuple[str, str, str],
    raw_reference: FrozenBgeM3DualViewBackend | None = None,
) -> dict[str, Any]:
    supported_category, near_category, ood_category = expected_categories
    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    authority_violations = 0
    execution_errors = 0
    raw_parity_mismatches = 0

    allowed_routes = set(verifier.route_ids)
    raw_correct_supported = 0
    retained_raw_correct = 0

    for case in cases:
        query = str(case["query"])
        expected = case.get("expected")
        started = time.perf_counter_ns()
        try:
            result = verifier.score(query)
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed_ms)

            top_route = str(result["top_route"])
            accepted = bool(result["accepted"])
            predicted = top_route if accepted else None
            if top_route not in allowed_routes:
                authority_violations += 1

            raw_reference_route: str | None = None
            raw_reference_match: bool | None = None
            if raw_reference is not None:
                raw = raw_reference.score_routes(query, raw_reference.route_ids)
                raw_reference_route = str(raw["top_route"])
                raw_reference_match = raw_reference_route == top_route
                if not raw_reference_match:
                    raw_parity_mismatches += 1
                if expected is not None and raw_reference_route == expected:
                    raw_correct_supported += 1
                    if predicted == expected:
                        retained_raw_correct += 1
            elif expected is not None and top_route == expected:
                raw_correct_supported += 1
                if predicted == expected:
                    retained_raw_correct += 1

            rows.append(
                {
                    "case_id": case.get("id"),
                    "category": case.get("category"),
                    "language": case.get("language"),
                    "unsupported_family": case.get("unsupported_family"),
                    "expected": expected,
                    "raw_top_route": top_route,
                    "raw_reference_route": raw_reference_route,
                    "raw_reference_match": raw_reference_match,
                    "accepted": accepted,
                    "predicted": predicted,
                    "verifier_probability": result["verifier_probability"],
                    "verifier_threshold": result["verifier_threshold"],
                    "hard_structural_veto": result["hard_structural_veto"],
                    "details": result["details"],
                    "latency_ms": elapsed_ms,
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001 -- research evidence records every failure.
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed_ms)
            execution_errors += 1
            rows.append(
                {
                    "case_id": case.get("id"),
                    "category": case.get("category"),
                    "language": case.get("language"),
                    "unsupported_family": case.get("unsupported_family"),
                    "expected": expected,
                    "raw_top_route": None,
                    "raw_reference_route": None,
                    "raw_reference_match": None,
                    "accepted": False,
                    "predicted": None,
                    "verifier_probability": None,
                    "verifier_threshold": verifier.head.threshold,
                    "hard_structural_veto": False,
                    "details": {},
                    "latency_ms": elapsed_ms,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    supported = [
        row
        for row in rows
        if row["category"] == supported_category and row["expected"] is not None
    ]
    near = [row for row in rows if row["category"] == near_category]
    ood = [row for row in rows if row["category"] == ood_category]
    unsupported = [*near, *ood]

    supported_correct = sum(row["predicted"] == row["expected"] for row in supported)
    near_rejected = sum(row["predicted"] is None for row in near)
    ood_rejected = sum(row["predicted"] is None for row in ood)
    false_routes = sum(row["predicted"] is not None for row in unsupported)

    metrics = {
        "supported_exact_route_accuracy": (
            supported_correct / len(supported) if supported else 0.0
        ),
        "near_domain_unsupported_rejection": (
            near_rejected / len(near) if near else 1.0
        ),
        "out_of_domain_rejection": (
            ood_rejected / len(ood) if ood else 1.0
        ),
        "false_routes": false_routes,
        "false_route_rate": (
            false_routes / len(unsupported) if unsupported else 0.0
        ),
        "raw_correct_supported": raw_correct_supported,
        "retained_raw_correct": retained_raw_correct,
        "correct_raw_winner_retention": (
            retained_raw_correct / raw_correct_supported
            if raw_correct_supported
            else 0.0
        ),
        "authority_violations": authority_violations,
        "execution_errors": execution_errors,
        "raw_route_parity_mismatches": raw_parity_mismatches,
        "latency_ms": _distribution(latencies),
    }
    p95 = metrics["latency_ms"]["p95"]
    gates = {
        "supported_exact_route_accuracy": metrics["supported_exact_route_accuracy"] >= 0.85,
        "near_domain_unsupported_rejection": (
            metrics["near_domain_unsupported_rejection"] >= 0.97
        ),
        "out_of_domain_rejection": metrics["out_of_domain_rejection"] == 1.0,
        "false_route_rate": metrics["false_route_rate"] <= 0.01,
        "authority_violations": authority_violations == 0,
        "execution_errors": execution_errors == 0,
        "correct_raw_winner_retention": (
            metrics["correct_raw_winner_retention"] >= 0.97
        ),
    }
    if raw_reference is not None:
        gates["raw_route_parity"] = raw_parity_mismatches == 0
        gates["p95_latency"] = p95 is not None and float(p95) <= 250.0

    return {
        "surface": name,
        "case_count": len(rows),
        "metrics": metrics,
        "gates": gates,
        "all_gates_pass": all(gates.values()),
        "rows": rows,
    }


def evaluate(canonical_cases: list[dict[str, Any]]) -> dict[str, Any]:
    model = _load_model()
    embed = _embedder(model)

    canonical_registry = reference_registry()
    canonical_static_started = time.perf_counter_ns()
    canonical_verifier = RegistryCapabilityVerifier(canonical_registry, embed)
    canonical_static_ms = (
        time.perf_counter_ns() - canonical_static_started
    ) / 1_000_000

    raw_reference = FrozenBgeM3DualViewBackend(canonical_registry, embed)
    canonical = _evaluate_surface(
        name="canonical_dev",
        cases=canonical_cases,
        verifier=canonical_verifier,
        expected_categories=(
            "v4_supported_natural",
            "near_domain_unsupported_operation",
            "out_of_domain",
        ),
        raw_reference=raw_reference,
    )

    registration_registry = build_registration_registry()
    registration_static_started = time.perf_counter_ns()
    registration_verifier = RegistryCapabilityVerifier(registration_registry, embed)
    registration_static_ms = (
        time.perf_counter_ns() - registration_static_started
    ) / 1_000_000
    registration = _evaluate_surface(
        name="registration_generalization_holdout",
        cases=registration_cases(),
        verifier=registration_verifier,
        expected_categories=(
            "registration_supported",
            "registration_near_unsupported",
            "registration_ood",
        ),
    )

    return {
        "experiment": "registry-compiled-capability-verifier-v1",
        "work_item": 338,
        "model": {
            "name": MODEL_NAME,
            "revision": MODEL_REVISION,
        },
        "generic_head": {
            "threshold": canonical_verifier.head.threshold,
            "synthetic_calibration_positive_recall": (
                canonical_verifier.head.calibration_positive_recall
            ),
            "synthetic_calibration_negative_fpr": (
                canonical_verifier.head.calibration_negative_fpr
            ),
            "action_score_floor": canonical_verifier.head.action_score_floor,
            "action_margin_floor": canonical_verifier.head.action_margin_floor,
        },
        "canonical_static_init_ms": canonical_static_ms,
        "registration_static_init_ms": registration_static_ms,
        "registration_manifest": registration_manifest(),
        "canonical_dev": canonical,
        "registration_generalization_holdout": registration,
        "candidate_worthy": (
            canonical["all_gates_pass"]
            and registration["all_gates_pass"]
        ),
        "policy": {
            "fresh_270_used": False,
            "fresh_287_used": False,
            "fresh_326_used": False,
            "calibration_or_blind_used": False,
            "labeled_dev_used_for_head_fit": False,
            "verifier_can_change_route": False,
            "rank2_fallback": False,
            "pseudo_route": False,
            "registration_specific_training": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    canonical_cases = json.loads(args.canonical_corpus.read_text(encoding="utf-8"))
    if not isinstance(canonical_cases, list) or any(
        not isinstance(item, dict) for item in canonical_cases
    ):
        raise ValueError("canonical corpus must be a JSON object list")

    result = evaluate(canonical_cases)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "candidate_worthy": result["candidate_worthy"],
                "canonical": result["canonical_dev"]["metrics"],
                "registration": result[
                    "registration_generalization_holdout"
                ]["metrics"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
