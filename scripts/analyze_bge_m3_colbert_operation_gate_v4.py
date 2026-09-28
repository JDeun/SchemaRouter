"""DEV-only BGE-M3 ColBERT operation-contract gate diagnostic (#328)."""

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
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from benchmark_decision_routing import load_corpus, reference_registry  # noqa: E402

from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    ACTION_WEIGHT,
    SCHEMA_WEIGHT,
    _action_text,
    _schema_text,
)

MANIFEST_PATH = (
    _PROJECT_ROOT
    / "benchmarks"
    / "operation-routing-v4-bge-m3-colbert-operation-gate.json"
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


def _scalar(value: Any) -> float:
    if hasattr(value, "item"):
        value = value.item()
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("model produced a non-finite score")
    return result


def _dot(left: Any, right: Any) -> float:
    if len(left) != len(right):
        raise ValueError("dense vectors are not dimensionally aligned")
    return _scalar(sum(float(a) * float(b) for a, b in zip(left, right, strict=True)))


def _catalog() -> list[dict[str, Any]]:
    registry = reference_registry()
    items: list[dict[str, Any]] = []
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            route_id = f"{tool.key}.{endpoint.name}"
            items.append(
                {
                    "route_id": route_id,
                    "tool": tool.key,
                    "schema_text": _schema_text(tool, endpoint),
                    "action_text": _action_text(endpoint),
                }
            )
    return sorted(items, key=lambda item: item["route_id"])


def _load_reference(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("rows")
    if not isinstance(rows, list) or len(rows) != 1800:
        raise ValueError("reference report must contain exactly 1800 rows")
    indexed: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("reference row must be an object")
        case_id = row.get("case_id")
        route = row.get("direct_top_route")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("reference row has invalid case_id")
        if not isinstance(route, str) or not route:
            raise ValueError(f"reference row {case_id!r} has invalid direct_top_route")
        if case_id in indexed:
            raise ValueError(f"duplicate reference case_id: {case_id}")
        indexed[case_id] = route
    return indexed


def _rank(
    route_ids: list[str],
    scores: list[float],
) -> tuple[str, float, float, float]:
    ranked = sorted(
        zip(route_ids, scores, strict=True),
        key=lambda item: (-item[1], item[0]),
    )
    top_route, top_score = ranked[0]
    second_score = ranked[1][1]
    return top_route, top_score, second_score, top_score - second_score


def _metrics(
    rows: list[dict[str, Any]],
    *,
    agreement_field: str,
    threshold: float | None,
) -> dict[str, Any]:
    def accepted(row: dict[str, Any]) -> bool:
        if not bool(row[agreement_field]):
            return False
        if threshold is None:
            return True
        return float(row["colbert_winner_score"]) >= threshold

    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row["category"] == "out_of_domain"]
    unsupported = [row for row in rows if row["expected"] is None]

    supported_correct = sum(
        accepted(row) and row["dense_winner"] == row["expected"]
        for row in supported
    )
    wrong_supported = sum(
        accepted(row)
        and row["dense_winner"] != row["expected"]
        for row in supported
    )
    near_rejected = sum(not accepted(row) for row in near)
    ood_rejected = sum(not accepted(row) for row in ood)
    false_routes = sum(accepted(row) for row in unsupported)

    per_language: dict[str, Any] = {}
    for language in sorted({str(row["language"]) for row in rows}):
        subset = [row for row in rows if str(row["language"]) == language]
        lang_supported = [row for row in subset if row["expected"] is not None]
        lang_unsupported = [row for row in subset if row["expected"] is None]
        per_language[language] = {
            "cases": len(subset),
            "supported_exact_route_accuracy": _safe_rate(
                sum(
                    accepted(row) and row["dense_winner"] == row["expected"]
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

    per_route: dict[str, Any] = {}
    for route in sorted(
        {
            str(row["expected"])
            for row in supported
            if row["expected"] is not None
        }
    ):
        subset = [row for row in supported if row["expected"] == route]
        exact = sum(
            accepted(row) and row["dense_winner"] == route for row in subset
        )
        per_route[route] = {
            "cases": len(subset),
            "exact": exact,
            "exact_rate": _safe_rate(exact, len(subset)),
        }

    return {
        "threshold": threshold,
        "supported_correct": supported_correct,
        "supported_exact_route_accuracy": _safe_rate(
            supported_correct,
            len(supported),
        ),
        "wrong_supported_accepted": wrong_supported,
        "near_domain_rejected": near_rejected,
        "near_domain_unsupported_rejection": _safe_rate(
            near_rejected,
            len(near),
        ),
        "ood_rejected": ood_rejected,
        "out_of_domain_rejection": _safe_rate(ood_rejected, len(ood)),
        "false_routes": false_routes,
        "false_route_rate": _safe_rate(false_routes, len(unsupported)),
        "per_language": per_language,
        "per_expected_route": per_route,
    }


def _frontier(
    rows: list[dict[str, Any]],
    *,
    agreement_field: str,
    false_budgets: tuple[int, ...] = (0, 6, 12),
) -> dict[str, Any]:
    eligible_scores = sorted(
        {
            float(row["colbert_winner_score"])
            for row in rows
            if bool(row[agreement_field])
        }
    )
    if not eligible_scores:
        raise ValueError(f"no rows eligible for {agreement_field}")

    thresholds = [
        eligible_scores[0] - 1e-12,
        *eligible_scores,
        eligible_scores[-1] + 1e-12,
    ]
    candidates = [
        _metrics(rows, agreement_field=agreement_field, threshold=threshold)
        for threshold in thresholds
    ]

    selected: dict[str, Any] = {}
    for budget in false_budgets:
        feasible = [
            candidate
            for candidate in candidates
            if int(candidate["false_routes"]) <= budget
        ]
        if not feasible:
            selected[str(budget)] = None
            continue
        best = max(
            feasible,
            key=lambda candidate: (
                int(candidate["supported_correct"]),
                -int(candidate["false_routes"]),
                -int(candidate["wrong_supported_accepted"]),
                float(candidate["threshold"]),
            ),
        )
        selected[str(budget)] = best
    return {
        "threshold_count": len(thresholds),
        "selected_by_false_budget": selected,
    }


def _geometry(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    groups = {
        "correct_supported_dense_winner": [
            row
            for row in rows
            if row["expected"] is not None
            and row["dense_winner"] == row["expected"]
        ],
        "wrong_supported_dense_winner": [
            row
            for row in rows
            if row["expected"] is not None
            and row["dense_winner"] != row["expected"]
        ],
        "near_domain_unsupported": [
            row
            for row in rows
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
    model_path: Path,
    reference_path: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    from FlagEmbedding import BGEM3FlagModel

    catalog = _catalog()
    route_ids = [str(item["route_id"]) for item in catalog]
    route_to_index = {route: index for index, route in enumerate(route_ids)}
    allowed_routes = set(route_ids)

    reference = _load_reference(reference_path)
    if {case.id for case in cases} != set(reference):
        raise ValueError("reference case IDs do not match canonical corpus")

    model_cfg = manifest["model"]
    load_started = time.perf_counter_ns()
    model = BGEM3FlagModel(
        str(model_path),
        use_fp16=False,
        devices="cpu",
    )
    model_load_ms = (time.perf_counter_ns() - load_started) / 1_000_000

    static_started = time.perf_counter_ns()
    schema_output = model.encode(
        [str(item["schema_text"]) for item in catalog],
        batch_size=16,
        max_length=int(model_cfg["schema_max_length"]),
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False,
    )
    action_output = model.encode(
        [str(item["action_text"]) for item in catalog],
        batch_size=16,
        max_length=int(model_cfg["action_max_length"]),
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=True,
    )
    schema_dense = schema_output["dense_vecs"]
    action_dense = action_output["dense_vecs"]
    action_sparse = action_output["lexical_weights"]
    action_colbert = action_output["colbert_vecs"]
    static_init_ms = (time.perf_counter_ns() - static_started) / 1_000_000

    encode_latencies: list[float] = []
    dense_latencies: list[float] = []
    colbert_latencies: list[float] = []
    sparse_latencies: list[float] = []
    total_latencies: list[float] = []
    rows: list[dict[str, Any]] = []
    parity_mismatches: list[dict[str, str]] = []
    authority_violations = 0
    execution_errors = 0

    for case in cases:
        row_started = time.perf_counter_ns()
        try:
            encode_started = time.perf_counter_ns()
            query_output = model.encode(
                [case.query],
                batch_size=1,
                max_length=int(model_cfg["query_max_length"]),
                return_dense=True,
                return_sparse=True,
                return_colbert_vecs=True,
            )
            encode_ms = (time.perf_counter_ns() - encode_started) / 1_000_000

            query_dense = query_output["dense_vecs"][0]
            query_sparse = query_output["lexical_weights"][0]
            query_colbert = query_output["colbert_vecs"][0]

            dense_started = time.perf_counter_ns()
            fused_scores = [
                SCHEMA_WEIGHT * _dot(query_dense, schema_dense[index])
                + ACTION_WEIGHT * _dot(query_dense, action_dense[index])
                for index in range(len(route_ids))
            ]
            dense_winner, dense_score, dense_second, dense_margin = _rank(
                route_ids,
                fused_scores,
            )
            dense_ms = (time.perf_counter_ns() - dense_started) / 1_000_000

            colbert_started = time.perf_counter_ns()
            colbert_scores = [
                _scalar(model.colbert_score(query_colbert, action_colbert[index]))
                for index in range(len(route_ids))
            ]
            (
                colbert_global_route,
                colbert_global_score,
                colbert_global_second,
                colbert_global_margin,
            ) = _rank(route_ids, colbert_scores)
            winner_index = route_to_index[dense_winner]
            winner_tool = dense_winner.split(".", 1)[0]
            sibling_indexes = [
                index
                for index, route in enumerate(route_ids)
                if route.split(".", 1)[0] == winner_tool
            ]
            sibling_routes = [route_ids[index] for index in sibling_indexes]
            sibling_scores = [colbert_scores[index] for index in sibling_indexes]
            (
                colbert_same_tool_route,
                colbert_same_tool_score,
                colbert_same_tool_second,
                colbert_same_tool_margin,
            ) = _rank(sibling_routes, sibling_scores)
            colbert_winner_score = colbert_scores[winner_index]
            colbert_ms = (time.perf_counter_ns() - colbert_started) / 1_000_000

            sparse_started = time.perf_counter_ns()
            sparse_scores = [
                _scalar(
                    model.compute_lexical_matching_score(
                        query_sparse,
                        action_sparse[index],
                    )
                )
                for index in range(len(route_ids))
            ]
            (
                sparse_global_route,
                sparse_global_score,
                sparse_global_second,
                sparse_global_margin,
            ) = _rank(route_ids, sparse_scores)
            sparse_sibling_scores = [
                sparse_scores[index] for index in sibling_indexes
            ]
            (
                sparse_same_tool_route,
                sparse_same_tool_score,
                sparse_same_tool_second,
                sparse_same_tool_margin,
            ) = _rank(sibling_routes, sparse_sibling_scores)
            sparse_winner_score = sparse_scores[winner_index]
            sparse_ms = (time.perf_counter_ns() - sparse_started) / 1_000_000

            expected_reference = reference[case.id]
            if dense_winner != expected_reference:
                parity_mismatches.append(
                    {
                        "case_id": case.id,
                        "reference": expected_reference,
                        "actual": dense_winner,
                    }
                )

            if dense_winner not in allowed_routes:
                authority_violations += 1

            error = None
        except Exception as exc:
            execution_errors += 1
            encode_ms = dense_ms = colbert_ms = sparse_ms = 0.0
            dense_winner = ""
            dense_score = dense_second = dense_margin = 0.0
            colbert_global_route = colbert_same_tool_route = ""
            colbert_global_score = colbert_global_second = colbert_global_margin = 0.0
            colbert_same_tool_score = colbert_same_tool_second = colbert_same_tool_margin = 0.0
            colbert_winner_score = 0.0
            sparse_global_route = sparse_same_tool_route = ""
            sparse_global_score = sparse_global_second = sparse_global_margin = 0.0
            sparse_same_tool_score = sparse_same_tool_second = sparse_same_tool_margin = 0.0
            sparse_winner_score = 0.0
            error = f"{type(exc).__name__}: {exc}"

        total_ms = (time.perf_counter_ns() - row_started) / 1_000_000
        encode_latencies.append(encode_ms)
        dense_latencies.append(dense_ms)
        colbert_latencies.append(colbert_ms)
        sparse_latencies.append(sparse_ms)
        total_latencies.append(total_ms)

        rows.append(
            {
                "case_id": case.id,
                "category": case.category,
                "language": case.language,
                "unsupported_family": case.unsupported_family,
                "expected": case.expected,
                "dense_winner": dense_winner,
                "dense_top_score": dense_score,
                "dense_second_score": dense_second,
                "dense_margin": dense_margin,
                "colbert_winner_score": colbert_winner_score,
                "colbert_global_top_route": colbert_global_route,
                "colbert_global_top_score": colbert_global_score,
                "colbert_global_second_score": colbert_global_second,
                "colbert_global_margin": colbert_global_margin,
                "colbert_global_agree": colbert_global_route == dense_winner,
                "colbert_same_tool_top_route": colbert_same_tool_route,
                "colbert_same_tool_top_score": colbert_same_tool_score,
                "colbert_same_tool_second_score": colbert_same_tool_second,
                "colbert_same_tool_margin": colbert_same_tool_margin,
                "colbert_same_tool_agree": colbert_same_tool_route == dense_winner,
                "sparse_winner_score": sparse_winner_score,
                "sparse_global_top_route": sparse_global_route,
                "sparse_global_top_score": sparse_global_score,
                "sparse_global_second_score": sparse_global_second,
                "sparse_global_margin": sparse_global_margin,
                "sparse_global_agree": sparse_global_route == dense_winner,
                "sparse_same_tool_top_route": sparse_same_tool_route,
                "sparse_same_tool_top_score": sparse_same_tool_score,
                "sparse_same_tool_second_score": sparse_same_tool_second,
                "sparse_same_tool_margin": sparse_same_tool_margin,
                "sparse_same_tool_agree": sparse_same_tool_route == dense_winner,
                "encode_latency_ms": encode_ms,
                "dense_scoring_latency_ms": dense_ms,
                "colbert_scoring_latency_ms": colbert_ms,
                "sparse_scoring_latency_ms": sparse_ms,
                "total_latency_ms": total_ms,
                "error": error,
            }
        )

    supported = [row for row in rows if row["expected"] is not None]
    raw_correct = sum(
        row["dense_winner"] == row["expected"] for row in supported
    )

    family_a = _metrics(
        rows,
        agreement_field="colbert_global_agree",
        threshold=None,
    )
    family_b = _metrics(
        rows,
        agreement_field="colbert_same_tool_agree",
        threshold=None,
    )
    frontier_c = _frontier(
        rows,
        agreement_field="colbert_global_agree",
    )
    frontier_d = _frontier(
        rows,
        agreement_field="colbert_same_tool_agree",
    )

    total_runtime = _distribution(total_latencies)
    p95_ms = total_runtime["p95"]

    passing_rules: list[dict[str, Any]] = []
    for family_id, metrics in (
        ("A", family_a),
        ("B", family_b),
    ):
        if _gate_pass(
            metrics,
            p95_ms=p95_ms,
            parity_mismatches=len(parity_mismatches),
            authority_violations=authority_violations,
            execution_errors=execution_errors,
        ):
            passing_rules.append(
                {
                    "family": family_id,
                    "rule": metrics,
                }
            )

    for family_id, frontier in (
        ("C", frontier_c),
        ("D", frontier_d),
    ):
        budget6 = frontier["selected_by_false_budget"]["6"]
        if budget6 is not None and _gate_pass(
            budget6,
            p95_ms=p95_ms,
            parity_mismatches=len(parity_mismatches),
            authority_violations=authority_violations,
            execution_errors=execution_errors,
        ):
            passing_rules.append(
                {
                    "family": family_id,
                    "false_budget": 6,
                    "rule": budget6,
                }
            )

    return {
        "experiment": manifest["experiment"],
        "summary": {
            "cases": len(rows),
            "dense_raw_supported_top1_accuracy": _safe_rate(
                raw_correct,
                len(supported),
            ),
            "dense_route_parity_mismatches": len(parity_mismatches),
            "authority_violations": authority_violations,
            "execution_errors": execution_errors,
            "candidate_worthy_rule_count": len(passing_rules),
            "candidate_worthy_rules": passing_rules,
            "model_load_ms": model_load_ms,
            "static_init_ms": static_init_ms,
            "query_encode_latency_ms": _distribution(encode_latencies),
            "dense_scoring_latency_ms": _distribution(dense_latencies),
            "colbert_scoring_latency_ms": _distribution(colbert_latencies),
            "sparse_scoring_latency_ms": _distribution(sparse_latencies),
            "total_latency_ms": total_runtime,
        },
        "family_A_global_agreement": family_a,
        "family_B_same_tool_agreement": family_b,
        "family_C_global_agreement_threshold_frontier": frontier_c,
        "family_D_same_tool_agreement_threshold_frontier": frontier_d,
        "geometry": {
            "colbert_winner_score": _geometry(rows, "colbert_winner_score"),
            "colbert_global_margin": _geometry(rows, "colbert_global_margin"),
            "colbert_same_tool_margin": _geometry(
                rows,
                "colbert_same_tool_margin",
            ),
            "sparse_winner_score": _geometry(rows, "sparse_winner_score"),
            "sparse_global_margin": _geometry(rows, "sparse_global_margin"),
            "sparse_same_tool_margin": _geometry(
                rows,
                "sparse_same_tool_margin",
            ),
        },
        "parity_mismatches": parity_mismatches[:100],
        "rows": rows,
        "policy": {
            "data_role": "tuning_eligible_development",
            "fresh_270_used": False,
            "fresh_287_used": False,
            "fresh_326_used": False,
            "calibration_or_blind_used": False,
            "colbert_can_change_route": False,
            "sparse_can_change_route": False,
            "rank2_fallback": False,
            "route_local_thresholds": False,
            "margin_threshold_search": False,
            "sparse_promotable": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--reference-report", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    registry = reference_registry()
    allowed_routes = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }
    cases = load_corpus(args.corpus, allowed_routes=allowed_routes)
    result = evaluate(
        cases,
        model_path=args.model_path,
        reference_path=args.reference_report,
        manifest=manifest,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
