"""Executable lightweight BGE negative-veto + conditional GTE rescue candidate."""

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

import analyze_dual_view_embedding_v4 as dual  # noqa: E402
import analyze_embedding_backbone_screen_v4 as screen  # noqa: E402
from benchmark_decision_routing import reference_registry  # noqa: E402
from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    ACTION_WEIGHT,
    BOUNDARY_EPSILON,
    FROZEN_THRESHOLDS,
    SCHEMA_WEIGHT,
    FrozenBgeM3DualViewBackend,
    _cosine,
)

MANIFEST_PATH = (
    _PROJECT_ROOT
    / "benchmarks"
    / "operation-routing-v4-lightweight-negative-gte-executable.json"
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


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _catalog(registry: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            items.append(
                {
                    "route_id": f"{tool.key}.{endpoint.name}",
                    "schema_text": dual._schema_text(tool, endpoint),  # noqa: SLF001
                    "action_text": dual._action_text(endpoint),  # noqa: SLF001
                }
            )
    return sorted(items, key=lambda item: item["route_id"])


def _tool(route: str) -> str:
    if "." not in route:
        raise ValueError(f"invalid route id: {route!r}")
    return route.split(".", 1)[0]


def _base_accept(top_route: str, top_score: float, top_margin: float) -> bool:
    boundary = FROZEN_THRESHOLDS[top_route]
    return (
        top_score + BOUNDARY_EPSILON >= float(boundary["min_score"])
        and top_margin + BOUNDARY_EPSILON >= float(boundary["min_margin"])
    )


def _negative_veto(
    *,
    max_negative_score: float,
    negative_advantage: float,
    score_min: float,
    advantage_min: float,
) -> bool:
    return (
        max_negative_score >= score_min
        and negative_advantage >= advantage_min
    )


def _gte_rescue(
    *,
    gte_route: str,
    bge_route: str,
    gte_score: float,
    gte_margin: float,
    base_score_deficit: float,
    base_margin_deficit: float,
    rule: dict[str, float],
) -> bool:
    if gte_route != bge_route:
        return False
    return (
        gte_score >= float(rule["min_gte_score"])
        and gte_margin >= float(rule["min_gte_margin"])
        and base_score_deficit <= float(rule["max_base_score_deficit"])
        and base_margin_deficit <= float(rule["max_base_margin_deficit"])
    )


def _reference_rows(path: Path) -> dict[str, str | None]:
    data = _load_json(path)
    rows = data.get("rows")
    if not isinstance(rows, list) or len(rows) != 1800:
        raise ValueError("offline reference must contain exactly 1800 rows")
    indexed: dict[str, str | None] = {}
    for row in rows:
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("offline reference contains invalid case_id")
        if case_id in indexed:
            raise ValueError(f"duplicate offline reference case_id: {case_id}")
        final_route = row.get("final_route")
        if final_route is not None and not isinstance(final_route, str):
            raise ValueError(f"invalid reference final_route for {case_id}")
        indexed[case_id] = final_route
    return indexed


def evaluate(
    cases: list[dict[str, Any]],
    *,
    manifest: dict[str, Any],
    reference_path: Path,
) -> dict[str, Any]:
    registry = reference_registry()
    catalog = _catalog(registry)
    route_ids = [item["route_id"] for item in catalog]
    allowed_routes = set(route_ids)

    bge_load_started = time.perf_counter_ns()
    bge_config, bge_static, bge_query = screen._build_embedders("bge-m3")  # noqa: SLF001
    bge_load_ms = (time.perf_counter_ns() - bge_load_started) / 1_000_000

    bge_init_started = time.perf_counter_ns()
    bge_backend = FrozenBgeM3DualViewBackend(registry, bge_query)
    bge_static_texts = [
        *(bge_backend._route_specs[route][0] for route in bge_backend.route_ids),  # noqa: SLF001
        *(bge_backend._route_specs[route][1] for route in bge_backend.route_ids),  # noqa: SLF001
    ]
    bge_vectors = bge_static(bge_static_texts)
    split = len(bge_backend.route_ids)
    bge_backend._schema_vectors = dict(  # noqa: SLF001
        zip(bge_backend.route_ids, bge_vectors[:split], strict=True)
    )
    bge_backend._action_vectors = dict(  # noqa: SLF001
        zip(bge_backend.route_ids, bge_vectors[split:], strict=True)
    )

    negative_cfg = manifest["negative_veto"]
    prototypes = negative_cfg["prototypes"]
    negative_items = [
        (domain, text)
        for domain in sorted(prototypes)
        for text in prototypes[domain]
    ]
    negative_static = bge_static([text for _, text in negative_items])
    negative_vectors: dict[str, list[tuple[str, list[float]]]] = {
        domain: [] for domain in prototypes
    }
    for (domain, text), vector in zip(
        negative_items,
        negative_static,
        strict=True,
    ):
        negative_vectors[domain].append((text, vector))
    bge_static_init_ms = (time.perf_counter_ns() - bge_init_started) / 1_000_000

    gte_load_started = time.perf_counter_ns()
    gte_config, gte_static, gte_query = screen._build_embedders(  # noqa: SLF001
        "gte-multilingual-base"
    )
    gte_load_ms = (time.perf_counter_ns() - gte_load_started) / 1_000_000

    gte_init_started = time.perf_counter_ns()
    gte_static_texts = [
        *(item["schema_text"] for item in catalog),
        *(item["action_text"] for item in catalog),
    ]
    gte_vectors = gte_static(gte_static_texts)
    gte_schema = gte_vectors[: len(catalog)]
    gte_action = gte_vectors[len(catalog) :]
    gte_static_init_ms = (time.perf_counter_ns() - gte_init_started) / 1_000_000

    reference = _reference_rows(reference_path)
    case_ids = {str(case.get("id")) for case in cases}
    if case_ids != set(reference):
        raise ValueError("corpus case IDs do not exactly match offline reference")

    gte_rules = manifest["gte"]["rules"]
    neg_score_min = float(negative_cfg["max_negative_score_min"])
    neg_advantage_min = float(negative_cfg["negative_advantage_min"])

    rows: list[dict[str, Any]] = []
    total_latencies: list[float] = []
    bge_latencies: list[float] = []
    gte_latencies: list[float] = []
    gte_invocations = 0
    parity_mismatches: list[dict[str, Any]] = []
    authority_violations = 0

    for case in cases:
        case_id = str(case["id"])
        query = str(case["query"])
        total_started = time.perf_counter_ns()

        bge_started = time.perf_counter_ns()
        bge_vector = bge_query([query])[0]
        route_scores: list[tuple[str, float, float, float]] = []
        for route in route_ids:
            schema_score = _cosine(
                bge_vector,
                bge_backend._schema_vectors[route],  # noqa: SLF001
            )
            action_score = _cosine(
                bge_vector,
                bge_backend._action_vectors[route],  # noqa: SLF001
            )
            fused = SCHEMA_WEIGHT * schema_score + ACTION_WEIGHT * action_score
            route_scores.append((route, fused, schema_score, action_score))
        route_scores.sort(key=lambda item: (-item[1], item[0]))
        raw_route, raw_score, _, raw_action_score = route_scores[0]
        second_score = route_scores[1][1]
        raw_margin = raw_score - second_score
        base_accepted = _base_accept(raw_route, raw_score, raw_margin)

        boundary = FROZEN_THRESHOLDS[raw_route]
        score_deficit = max(0.0, float(boundary["min_score"]) - raw_score)
        margin_deficit = max(0.0, float(boundary["min_margin"]) - raw_margin)

        final_route: str | None = None
        decision_path = "base_abstain"
        max_negative_score: float | None = None
        negative_advantage: float | None = None
        gte_route: str | None = None
        gte_score: float | None = None
        gte_margin: float | None = None

        if base_accepted:
            domain = _tool(raw_route)
            scored_negative = [
                (text, _cosine(bge_vector, vector))
                for text, vector in negative_vectors[domain]
            ]
            scored_negative.sort(key=lambda item: (-item[1], item[0]))
            _, max_negative_score = scored_negative[0]
            negative_advantage = max_negative_score - raw_action_score
            if _negative_veto(
                max_negative_score=max_negative_score,
                negative_advantage=negative_advantage,
                score_min=neg_score_min,
                advantage_min=neg_advantage_min,
            ):
                decision_path = "negative_veto"
            else:
                final_route = raw_route
                decision_path = "base_accept"
        else:
            bge_elapsed_ms = (time.perf_counter_ns() - bge_started) / 1_000_000
            gte_started = time.perf_counter_ns()
            gte_vector = gte_query([query])[0]
            schema_scores = [
                dual._cosine(gte_vector, vector)  # noqa: SLF001
                for vector in gte_schema
            ]
            action_scores = [
                dual._cosine(gte_vector, vector)  # noqa: SLF001
                for vector in gte_action
            ]
            fused = [
                float(manifest["gte"]["schema_weight"]) * schema
                + float(manifest["gte"]["action_weight"]) * action
                for schema, action in zip(
                    schema_scores,
                    action_scores,
                    strict=True,
                )
            ]
            gte_route, gte_score, _, gte_margin = dual._rank(route_ids, fused)  # noqa: SLF001
            gte_elapsed_ms = (time.perf_counter_ns() - gte_started) / 1_000_000
            gte_latencies.append(gte_elapsed_ms)
            gte_invocations += 1

            rule = gte_rules[raw_route]
            if _gte_rescue(
                gte_route=gte_route,
                bge_route=raw_route,
                gte_score=float(gte_score),
                gte_margin=float(gte_margin),
                base_score_deficit=score_deficit,
                base_margin_deficit=margin_deficit,
                rule=rule,
            ):
                final_route = raw_route
                decision_path = "gte_rescue"
            bge_latencies.append(bge_elapsed_ms)

        if base_accepted:
            bge_latencies.append(
                (time.perf_counter_ns() - bge_started) / 1_000_000
            )

        total_latency_ms = (time.perf_counter_ns() - total_started) / 1_000_000
        total_latencies.append(total_latency_ms)

        if raw_route not in allowed_routes:
            authority_violations += 1
        if final_route is not None and final_route != raw_route:
            authority_violations += 1

        expected_reference = reference[case_id]
        if final_route != expected_reference:
            parity_mismatches.append(
                {
                    "case_id": case_id,
                    "expected_reference": expected_reference,
                    "actual": final_route,
                    "raw_route": raw_route,
                    "decision_path": decision_path,
                }
            )

        rows.append(
            {
                "case_id": case_id,
                "category": case.get("category"),
                "language": case.get("language"),
                "unsupported_family": case.get("unsupported_family"),
                "expected": case.get("expected"),
                "raw_top_route": raw_route,
                "raw_top_score": raw_score,
                "raw_top_margin": raw_margin,
                "raw_top_action_score": raw_action_score,
                "base_accepted": base_accepted,
                "max_negative_score": max_negative_score,
                "negative_advantage": negative_advantage,
                "gte_route": gte_route,
                "gte_top_score": gte_score,
                "gte_margin": gte_margin,
                "decision_path": decision_path,
                "final_route": final_route,
                "latency_ms": total_latency_ms,
            }
        )

    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row["category"] == "out_of_domain"]
    unsupported = [row for row in rows if row["expected"] is None]

    supported_correct = sum(
        row["final_route"] == row["expected"] for row in supported
    )
    near_rejected = sum(row["final_route"] is None for row in near)
    ood_rejected = sum(row["final_route"] is None for row in ood)
    false_routes = sum(row["final_route"] is not None for row in unsupported)
    wrong_supported = sum(
        row["final_route"] is not None
        and row["final_route"] != row["expected"]
        for row in supported
    )

    negative_veto_rows = [
        row for row in rows if row["decision_path"] == "negative_veto"
    ]
    rescued_rows = [row for row in rows if row["decision_path"] == "gte_rescue"]

    summary = {
        "cases": len(rows),
        "supported_correct": supported_correct,
        "supported_exact_route_accuracy": supported_correct / len(supported),
        "wrong_supported_accepted": wrong_supported,
        "near_domain_rejected": near_rejected,
        "near_domain_unsupported_rejection": near_rejected / len(near),
        "out_of_domain_rejected": ood_rejected,
        "out_of_domain_rejection": ood_rejected / len(ood),
        "false_routes": false_routes,
        "false_route_rate": false_routes / len(unsupported),
        "authority_violations": authority_violations,
        "execution_errors": 0,
        "parity_mismatch_count": len(parity_mismatches),
        "negative_veto_total": len(negative_veto_rows),
        "negative_veto_correct_supported": sum(
            row["expected"] == row["raw_top_route"]
            for row in negative_veto_rows
            if row["expected"] is not None
        ),
        "negative_veto_unsupported": sum(
            row["expected"] is None for row in negative_veto_rows
        ),
        "rescued_correct_supported": sum(
            row["expected"] == row["raw_top_route"]
            for row in rescued_rows
            if row["expected"] is not None
        ),
        "rescued_wrong_supported": sum(
            row["expected"] is not None
            and row["expected"] != row["raw_top_route"]
            for row in rescued_rows
        ),
        "rescued_unsupported": sum(
            row["expected"] is None for row in rescued_rows
        ),
        "gte_invocations": gte_invocations,
        "gte_invocation_rate": gte_invocations / len(rows),
        "bge_model_load_ms": bge_load_ms,
        "bge_static_init_ms": bge_static_init_ms,
        "gte_model_load_ms": gte_load_ms,
        "gte_static_init_ms": gte_static_init_ms,
        "bge_query_latency_ms": _distribution(bge_latencies),
        "gte_conditional_latency_ms": _distribution(gte_latencies),
        "total_latency_ms": _distribution(total_latencies),
    }

    expected_parity = manifest["expected_parity"]
    parity_counts_match = all(
        int(summary[key]) == int(value)
        for key, value in expected_parity.items()
    )
    gate = manifest["gate"]
    latency_p95 = summary["total_latency_ms"]["p95"]
    promotion_pass = (
        summary["supported_exact_route_accuracy"]
        >= float(gate["supported_exact_route_accuracy_min"])
        and summary["near_domain_unsupported_rejection"]
        >= float(gate["near_domain_unsupported_rejection_min"])
        and summary["out_of_domain_rejection"]
        == float(gate["out_of_domain_rejection"])
        and summary["false_route_rate"] <= float(gate["false_route_rate_max"])
        and authority_violations <= int(gate["authority_violations_max"])
        and len(parity_mismatches) == 0
        and parity_counts_match
        and latency_p95 is not None
        and float(latency_p95) <= float(gate["p95_ms_max"])
    )
    summary["parity_counts_match"] = parity_counts_match
    summary["promotion_gate_pass"] = promotion_pass

    return {
        "candidate": manifest["candidate"],
        "models": {
            "bge": bge_config,
            "gte": gte_config,
        },
        "summary": summary,
        "parity_mismatches": parity_mismatches[:100],
        "rows": rows,
        "policy": {
            "failed_270_fresh_used": False,
            "failed_287_fresh_used": False,
            "calibration_or_blind_used": False,
            "rank2_fallback": False,
            "same_bge_winner_only": True,
            "negative_vetoed_base_accepts_rescue_eligible": False,
            "gte_conditional_on_original_base_abstention": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--reference-analysis", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cases = _load_json(args.corpus)
    if not isinstance(cases, list) or any(not isinstance(row, dict) for row in cases):
        raise ValueError("corpus must be a list of objects")

    manifest = _load_json(args.manifest)
    result = evaluate(
        cases,
        manifest=manifest,
        reference_path=args.reference_analysis,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["summary"], sort_keys=True))

    if not result["summary"]["parity_counts_match"]:
        raise SystemExit("executable parity counts differ from frozen offline candidate")
    if result["summary"]["parity_mismatch_count"] != 0:
        raise SystemExit("executable row-level decisions differ from offline candidate")


if __name__ == "__main__":
    main()
