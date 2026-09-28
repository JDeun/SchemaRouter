"""DEV-only registry-self-calibrated BGE-M3 alias-envelope diagnostic (#332)."""

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

from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    ACTION_WEIGHT,
    MODEL_NAME,
    MODEL_REVISION,
    SCHEMA_WEIGHT,
    _action_text,
    _schema_text,
)

MANIFEST_PATH = (
    _PROJECT_ROOT
    / "benchmarks"
    / "operation-routing-v4-bge-alias-envelope.json"
)
EPSILON = 1e-6


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


def _dot(left: Any, right: Any) -> float:
    if len(left) != len(right) or len(left) == 0:
        raise ValueError("vectors must be non-empty and dimensionally aligned")
    value = sum(float(a) * float(b) for a, b in zip(left, right, strict=True))
    if not math.isfinite(value):
        raise ValueError("non-finite vector score")
    return max(-1.0, min(1.0, float(value)))


def _normalized_endpoint_name(name: str) -> str:
    return " ".join(name.replace("_", " ").replace("-", " ").split())


def _alias_strings(endpoint: Any) -> tuple[str, ...]:
    values = [
        _normalized_endpoint_name(str(endpoint.name)),
        *(str(value).strip() for value in endpoint.operation_aliases),
    ]
    return tuple(dict.fromkeys(value for value in values if value))


def _catalog() -> list[dict[str, Any]]:
    registry = reference_registry()
    items: list[dict[str, Any]] = []
    for tool in registry.tools():
        endpoints = list(tool.endpoints)
        if len(endpoints) != 2:
            raise ValueError(
                f"alias-envelope v1 requires exactly two endpoints per tool: "
                f"{tool.key} has {len(endpoints)}"
            )
        for endpoint in endpoints:
            route_id = f"{tool.key}.{endpoint.name}"
            aliases = _alias_strings(endpoint)
            if len(aliases) < 2:
                raise ValueError(
                    f"route {route_id} requires at least two trusted aliases"
                )
            items.append(
                {
                    "route_id": route_id,
                    "tool": tool.key,
                    "schema_text": _schema_text(tool, endpoint),
                    "action_text": _action_text(endpoint),
                    "aliases": aliases,
                }
            )
    return sorted(items, key=lambda item: str(item["route_id"]))


def _sibling_map(catalog: list[dict[str, Any]]) -> dict[str, str]:
    by_tool: dict[str, list[str]] = {}
    for item in catalog:
        by_tool.setdefault(str(item["tool"]), []).append(str(item["route_id"]))
    siblings: dict[str, str] = {}
    for tool, routes in by_tool.items():
        if len(routes) != 2:
            raise ValueError(
                f"alias-envelope v1 requires exactly two routes for tool {tool}"
            )
        left, right = sorted(routes)
        siblings[left] = right
        siblings[right] = left
    return siblings


def _derive_registry_floors(
    aliases_by_route: dict[str, tuple[str, ...]],
    alias_vectors: dict[str, list[list[float]]],
    sibling_by_route: dict[str, str],
) -> dict[str, dict[str, Any]]:
    floors: dict[str, dict[str, Any]] = {}
    for route in sorted(aliases_by_route):
        own_vectors = alias_vectors[route]
        sibling = sibling_by_route[route]
        sibling_vectors = alias_vectors[sibling]
        if len(own_vectors) < 2:
            raise ValueError(f"route {route} needs >=2 alias vectors")

        points: list[dict[str, float | int | str]] = []
        for index, vector in enumerate(own_vectors):
            own_neighbor = max(
                _dot(vector, other)
                for other_index, other in enumerate(own_vectors)
                if other_index != index
            )
            sibling_neighbor = max(
                _dot(vector, other) for other in sibling_vectors
            )
            alias_margin = own_neighbor - sibling_neighbor
            points.append(
                {
                    "alias_index": index,
                    "alias": aliases_by_route[route][index],
                    "own_neighbor": own_neighbor,
                    "sibling_neighbor": sibling_neighbor,
                    "alias_margin": alias_margin,
                }
            )

        floors[route] = {
            "sibling_route": sibling,
            "route_margin_floor_raw": min(
                float(point["alias_margin"]) for point in points
            ),
            "route_margin_floor": max(
                0.0,
                min(float(point["alias_margin"]) for point in points),
            ),
            "route_cohesion_floor": min(
                float(point["own_neighbor"]) for point in points
            ),
            "alias_points": points,
        }
    return floors


def _load_reference(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("rows")
    if not isinstance(rows, list) or len(rows) != 1800:
        raise ValueError("reference report must contain exactly 1800 rows")
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("reference row must be an object")
        case_id = row.get("case_id")
        route = row.get("direct_top_route")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("reference row has invalid case_id")
        if not isinstance(route, str) or not route:
            raise ValueError(f"reference row {case_id!r} has invalid route")
        if case_id in result:
            raise ValueError(f"duplicate reference case_id {case_id!r}")
        result[case_id] = route
    return result


def _rule_accepts(row: dict[str, Any], family: str) -> bool:
    contrast = float(row["own_max"]) > float(row["sibling_max"]) + EPSILON
    margin = (
        float(row["query_margin"]) + EPSILON
        >= float(row["route_margin_floor"])
    )
    cohesion = (
        float(row["own_max"]) + EPSILON
        >= float(row["route_cohesion_floor"])
    )
    if family == "A":
        return contrast
    if family == "B":
        return contrast and margin
    if family == "C":
        return contrast and cohesion
    if family == "D":
        return contrast and margin and cohesion
    raise ValueError(f"unknown family {family!r}")


def _metrics(rows: list[dict[str, Any]], family: str) -> dict[str, Any]:
    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row["category"] == "out_of_domain"]
    unsupported = [row for row in rows if row["expected"] is None]

    supported_correct = sum(
        _rule_accepts(row, family)
        and row["dense_winner"] == row["expected"]
        for row in supported
    )
    wrong_supported = sum(
        _rule_accepts(row, family)
        and row["dense_winner"] != row["expected"]
        for row in supported
    )
    near_rejected = sum(not _rule_accepts(row, family) for row in near)
    ood_rejected = sum(not _rule_accepts(row, family) for row in ood)
    false_routes = sum(
        _rule_accepts(row, family) for row in unsupported
    )

    per_language: dict[str, Any] = {}
    for language in sorted({str(row["language"]) for row in rows}):
        subset = [row for row in rows if str(row["language"]) == language]
        lang_supported = [row for row in subset if row["expected"] is not None]
        lang_unsupported = [row for row in subset if row["expected"] is None]
        per_language[language] = {
            "cases": len(subset),
            "supported_exact_route_accuracy": _safe_rate(
                sum(
                    _rule_accepts(row, family)
                    and row["dense_winner"] == row["expected"]
                    for row in lang_supported
                ),
                len(lang_supported),
            ),
            "unsupported_rejection": _safe_rate(
                sum(
                    not _rule_accepts(row, family)
                    for row in lang_unsupported
                ),
                len(lang_unsupported),
            ),
            "false_routes": sum(
                _rule_accepts(row, family) for row in lang_unsupported
            ),
        }

    per_route: dict[str, Any] = {}
    for route in sorted(
        str(row["expected"])
        for row in supported
        if row["expected"] is not None
    ):
        if route in per_route:
            continue
        subset = [row for row in supported if row["expected"] == route]
        exact = sum(
            _rule_accepts(row, family)
            and row["dense_winner"] == route
            for row in subset
        )
        per_route[route] = {
            "cases": len(subset),
            "exact": exact,
            "exact_rate": _safe_rate(exact, len(subset)),
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
            row for row in rows
            if str(row["unsupported_family"]) == unsupported_family
        ]
        rejected = sum(
            not _rule_accepts(row, family) for row in subset
        )
        per_family[unsupported_family] = {
            "cases": len(subset),
            "rejected": rejected,
            "rejection_rate": _safe_rate(rejected, len(subset)),
        }

    return {
        "family": family,
        "supported_correct": supported_correct,
        "supported_exact_route_accuracy": _safe_rate(
            supported_correct, len(supported)
        ),
        "wrong_supported_accepted": wrong_supported,
        "near_domain_rejected": near_rejected,
        "near_domain_unsupported_rejection": _safe_rate(
            near_rejected, len(near)
        ),
        "ood_rejected": ood_rejected,
        "out_of_domain_rejection": _safe_rate(ood_rejected, len(ood)),
        "false_routes": false_routes,
        "false_route_rate": _safe_rate(false_routes, len(unsupported)),
        "per_language": per_language,
        "per_expected_route": per_route,
        "unsupported_family_rejection": per_family,
    }


def _geometry(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    groups = {
        "correct_supported_dense_winner": [
            row for row in rows
            if row["expected"] is not None
            and row["dense_winner"] == row["expected"]
        ],
        "wrong_supported_dense_winner": [
            row for row in rows
            if row["expected"] is not None
            and row["dense_winner"] != row["expected"]
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
        name: _distribution([float(row[field]) for row in group])
        for name, group in groups.items()
    }


def _gate_pass(
    metrics: dict[str, Any],
    *,
    p95_ms: float | None,
    parity_mismatches: int,
    authority_violations: int,
    execution_errors: int,
) -> bool:
    return (
        float(metrics["supported_exact_route_accuracy"]) >= 0.85
        and float(metrics["near_domain_unsupported_rejection"]) >= 0.97
        and float(metrics["out_of_domain_rejection"]) == 1.0
        and float(metrics["false_route_rate"]) <= 0.01
        and parity_mismatches == 0
        and authority_violations == 0
        and execution_errors == 0
        and p95_ms is not None
        and p95_ms <= 250.0
    )


def evaluate(
    cases: list[Any],
    *,
    reference_path: Path,
) -> dict[str, Any]:
    from sentence_transformers import SentenceTransformer

    catalog = _catalog()
    route_ids = [str(item["route_id"]) for item in catalog]
    route_to_item = {
        str(item["route_id"]): item for item in catalog
    }
    sibling_by_route = _sibling_map(catalog)
    reference = _load_reference(reference_path)
    if {case.id for case in cases} != set(reference):
        raise ValueError("reference case IDs do not match canonical corpus")

    load_started = time.perf_counter_ns()
    model = SentenceTransformer(
        MODEL_NAME,
        revision=MODEL_REVISION,
        trust_remote_code=False,
        device="cpu",
    )
    model_load_ms = (time.perf_counter_ns() - load_started) / 1_000_000

    static_started = time.perf_counter_ns()
    schema_texts = [str(item["schema_text"]) for item in catalog]
    action_texts = [str(item["action_text"]) for item in catalog]
    aliases_by_route = {
        str(item["route_id"]): tuple(item["aliases"])
        for item in catalog
    }
    flat_aliases: list[tuple[str, str]] = [
        (route, alias)
        for route in route_ids
        for alias in aliases_by_route[route]
    ]
    static_texts = [
        *schema_texts,
        *action_texts,
        *(alias for _, alias in flat_aliases),
    ]
    static_vectors = model.encode(
        static_texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    if len(static_vectors) != len(static_texts):
        raise ValueError("unexpected static embedding count")

    route_count = len(route_ids)
    schema_vectors = {
        route: static_vectors[index]
        for index, route in enumerate(route_ids)
    }
    action_vectors = {
        route: static_vectors[route_count + index]
        for index, route in enumerate(route_ids)
    }
    alias_vectors: dict[str, list[Any]] = {route: [] for route in route_ids}
    alias_offset = route_count * 2
    for index, (route, _) in enumerate(flat_aliases):
        alias_vectors[route].append(static_vectors[alias_offset + index])

    floors = _derive_registry_floors(
        aliases_by_route,
        alias_vectors,
        sibling_by_route,
    )
    static_init_ms = (time.perf_counter_ns() - static_started) / 1_000_000

    rows: list[dict[str, Any]] = []
    encode_latencies: list[float] = []
    dense_latencies: list[float] = []
    alias_latencies: list[float] = []
    total_latencies: list[float] = []
    parity_mismatches: list[dict[str, str]] = []
    authority_violations = 0
    execution_errors = 0

    for case in cases:
        row_started = time.perf_counter_ns()
        try:
            encode_started = time.perf_counter_ns()
            query_vectors = model.encode(
                [case.query],
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            query_vector = query_vectors[0]
            encode_ms = (time.perf_counter_ns() - encode_started) / 1_000_000

            dense_started = time.perf_counter_ns()
            fused_scores: list[tuple[str, float]] = []
            for route in route_ids:
                schema_score = _dot(query_vector, schema_vectors[route])
                action_score = _dot(query_vector, action_vectors[route])
                fused_scores.append(
                    (
                        route,
                        SCHEMA_WEIGHT * schema_score
                        + ACTION_WEIGHT * action_score,
                    )
                )
            fused_scores.sort(key=lambda item: (-item[1], item[0]))
            dense_winner = fused_scores[0][0]
            dense_top_score = fused_scores[0][1]
            dense_second_score = fused_scores[1][1]
            dense_margin = dense_top_score - dense_second_score
            dense_ms = (time.perf_counter_ns() - dense_started) / 1_000_000

            alias_started = time.perf_counter_ns()
            sibling = sibling_by_route[dense_winner]
            own_max = max(
                _dot(query_vector, vector)
                for vector in alias_vectors[dense_winner]
            )
            sibling_max = max(
                _dot(query_vector, vector)
                for vector in alias_vectors[sibling]
            )
            query_margin = own_max - sibling_max
            route_floor = floors[dense_winner]
            alias_ms = (time.perf_counter_ns() - alias_started) / 1_000_000

            if dense_winner != reference[case.id]:
                parity_mismatches.append(
                    {
                        "case_id": case.id,
                        "reference": reference[case.id],
                        "actual": dense_winner,
                    }
                )
            if dense_winner not in route_to_item:
                authority_violations += 1
            error = None
        except Exception as exc:
            execution_errors += 1
            encode_ms = dense_ms = alias_ms = 0.0
            dense_winner = ""
            dense_top_score = dense_second_score = dense_margin = 0.0
            sibling = ""
            own_max = sibling_max = query_margin = 0.0
            route_floor = {
                "route_margin_floor": 0.0,
                "route_cohesion_floor": 1.0,
            }
            error = f"{type(exc).__name__}: {exc}"

        total_ms = (time.perf_counter_ns() - row_started) / 1_000_000
        encode_latencies.append(encode_ms)
        dense_latencies.append(dense_ms)
        alias_latencies.append(alias_ms)
        total_latencies.append(total_ms)
        rows.append(
            {
                "case_id": case.id,
                "category": case.category,
                "language": case.language,
                "unsupported_family": case.unsupported_family,
                "expected": case.expected,
                "dense_winner": dense_winner,
                "dense_top_score": dense_top_score,
                "dense_second_score": dense_second_score,
                "dense_margin": dense_margin,
                "sibling_route": sibling,
                "own_max": own_max,
                "sibling_max": sibling_max,
                "query_margin": query_margin,
                "route_margin_floor": route_floor["route_margin_floor"],
                "route_cohesion_floor": route_floor["route_cohesion_floor"],
                "encode_latency_ms": encode_ms,
                "dense_scoring_latency_ms": dense_ms,
                "alias_scoring_latency_ms": alias_ms,
                "total_latency_ms": total_ms,
                "error": error,
            }
        )

    supported = [row for row in rows if row["expected"] is not None]
    raw_correct = sum(
        row["dense_winner"] == row["expected"] for row in supported
    )
    total_runtime = _distribution(total_latencies)
    p95_ms = total_runtime["p95"]

    families = {
        family: _metrics(rows, family)
        for family in ("A", "B", "C", "D")
    }
    passing = [
        {
            "family": family,
            "metrics": metrics,
        }
        for family, metrics in families.items()
        if _gate_pass(
            metrics,
            p95_ms=p95_ms,
            parity_mismatches=len(parity_mismatches),
            authority_violations=authority_violations,
            execution_errors=execution_errors,
        )
    ]
    family_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    passing.sort(key=lambda item: family_order[str(item["family"])])

    return {
        "experiment": "bge-m3-registry-alias-envelope-v1",
        "summary": {
            "cases": len(rows),
            "dense_raw_supported_top1_accuracy": _safe_rate(
                raw_correct, len(supported)
            ),
            "dense_route_parity_mismatches": len(parity_mismatches),
            "authority_violations": authority_violations,
            "execution_errors": execution_errors,
            "candidate_worthy_rule_count": len(passing),
            "selected_candidate": passing[0] if passing else None,
            "model_load_ms": model_load_ms,
            "static_init_ms": static_init_ms,
            "query_encode_latency_ms": _distribution(encode_latencies),
            "dense_scoring_latency_ms": _distribution(dense_latencies),
            "alias_scoring_latency_ms": _distribution(alias_latencies),
            "total_latency_ms": total_runtime,
        },
        "registry_alias_envelopes": {
            route: {
                "aliases": list(aliases_by_route[route]),
                **floors[route],
            }
            for route in route_ids
        },
        "family_A_sibling_contrast": families["A"],
        "family_B_registry_margin": families["B"],
        "family_C_registry_cohesion": families["C"],
        "family_D_joint_registry_envelope": families["D"],
        "geometry": {
            "own_max": _geometry(rows, "own_max"),
            "sibling_max": _geometry(rows, "sibling_max"),
            "query_margin": _geometry(rows, "query_margin"),
        },
        "parity_mismatches": parity_mismatches[:100],
        "rows": rows,
        "policy": {
            "data_role": "tuning_eligible_development",
            "labeled_rows_used_for_floor_derivation": False,
            "fresh_270_used": False,
            "fresh_287_used": False,
            "fresh_326_used": False,
            "calibration_or_blind_used": False,
            "additional_query_model_calls_for_gate": 0,
            "gate_can_change_route": False,
            "rank2_fallback": False,
            "route_local_dev_fitted_thresholds": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--reference-report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    registry = reference_registry()
    allowed_routes = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }
    cases = load_corpus(args.corpus, allowed_routes=allowed_routes)
    result = evaluate(cases, reference_path=args.reference_report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
