"""DEV-only global signed capability prototype bank diagnostic."""

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
    ACTION_WEIGHT,
    MODEL_NAME,
    MODEL_REVISION,
    SCHEMA_WEIGHT,
    FrozenBgeM3DualViewBackend,
    _cosine,
)

NEGATIVE_CAPABILITY_PROTOTYPES: dict[str, tuple[str, ...]] = {
    "weather": (
        "satellite cloud imagery",
        "aviation METAR and TAF reports",
        "live lightning strike maps",
        "pollen and allergy outlooks",
    ),
    "materials": (
        "XRD pattern simulation",
        "defect formation energy calculation",
        "laboratory synthesis recipe design",
        "molecular dynamics simulation",
    ),
    "papers": (
        "full paper translation",
        "citation network visualization",
        "plagiarism detection",
        "emailing corresponding authors",
    ),
    "finance": (
        "securities trading and selling shares",
        "portfolio rebalancing",
        "live options chains",
        "capital gains tax reporting",
    ),
    "calendar": (
        "declining calendar invitations",
        "setting event reminders",
        "sharing calendars",
        "booking rooms or resources",
    ),
    "support": (
        "reopening support tickets",
        "changing ticket priority",
        "deleting support tickets",
        "escalating tickets to another support tier",
    ),
    "inventory": (
        "printing inventory barcode labels",
        "changing retail prices",
        "creating catalog items",
        "exporting inventory to CSV",
    ),
    "users": (
        "assigning user roles or permissions",
        "suspending user accounts",
        "verifying email addresses",
        "listing active login sessions",
    ),
}

ENVELOPE_MIN_THRESHOLDS = (0.35, 0.40, 0.45, 0.50, 0.55, 0.60)
NEGATIVE_MIN_THRESHOLDS = (0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65)
SIGNED_ADVANTAGE_THRESHOLDS = (-0.10, -0.05, 0.0, 0.025, 0.05, 0.10)
POSITIVE_CONSISTENCY_MODES = (False, True)


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


def _load_model():
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


def _tool(route: str | None) -> str | None:
    if not isinstance(route, str) or "." not in route:
        return None
    return route.split(".", 1)[0]


def _positive_capability_text(endpoint: Any) -> str:
    operation_name = endpoint.name.replace("_", " ").replace("-", " ")
    parts = [
        operation_name,
        *endpoint.operation_aliases,
        endpoint.description.strip(),
    ]
    return "\n".join(dict.fromkeys(part for part in parts if part))


def _positive_bank(registry: Any) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            items.append(
                (
                    f"{tool.key}.{endpoint.name}",
                    _positive_capability_text(endpoint),
                )
            )
    return sorted(items, key=lambda item: item[0])


def _negative_bank() -> list[tuple[str, str]]:
    return [
        (domain, prototype)
        for domain in sorted(NEGATIVE_CAPABILITY_PROTOTYPES)
        for prototype in NEGATIVE_CAPABILITY_PROTOTYPES[domain]
    ]


def _rule_id(
    envelope_min: float,
    negative_min: float,
    signed_advantage_min: float,
    require_positive_consistency: bool,
) -> str:
    consistency = "agree" if require_positive_consistency else "noagree"
    return (
        f"e{envelope_min:.3f}-n{negative_min:.3f}-"
        f"a{signed_advantage_min:+.3f}-{consistency}"
    )


def _apply_rule(
    row: dict[str, Any],
    *,
    envelope_min: float,
    negative_min: float,
    signed_advantage_min: float,
    require_positive_consistency: bool,
) -> dict[str, Any]:
    envelope_veto = float(row["capability_envelope"]) < envelope_min
    negative_veto = (
        float(row["max_negative_score"]) >= negative_min
        and float(row["signed_advantage"]) >= signed_advantage_min
    )
    consistency_veto = (
        require_positive_consistency
        and str(row["top_positive_route"]) != str(row["raw_top_route"])
    )
    veto = envelope_veto or negative_veto or consistency_veto
    return {
        "veto": veto,
        "envelope_veto": envelope_veto,
        "negative_veto": negative_veto,
        "consistency_veto": consistency_veto,
        "predicted": None if veto else str(row["raw_top_route"]),
    }


def _evaluate_rule(
    rows: list[dict[str, Any]],
    *,
    envelope_min: float,
    negative_min: float,
    signed_advantage_min: float,
    require_positive_consistency: bool,
) -> dict[str, Any]:
    evaluated = [
        (
            row,
            _apply_rule(
                row,
                envelope_min=envelope_min,
                negative_min=negative_min,
                signed_advantage_min=signed_advantage_min,
                require_positive_consistency=require_positive_consistency,
            ),
        )
        for row in rows
    ]

    supported = [
        (row, result)
        for row, result in evaluated
        if row["expected"] is not None
    ]
    near = [
        (row, result)
        for row, result in evaluated
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [
        (row, result)
        for row, result in evaluated
        if row["category"] == "out_of_domain"
    ]
    unsupported = [
        (row, result)
        for row, result in evaluated
        if row["expected"] is None
    ]

    supported_correct = sum(
        result["predicted"] == row["expected"]
        for row, result in supported
    )
    near_rejected = sum(result["predicted"] is None for _, result in near)
    ood_rejected = sum(result["predicted"] is None for _, result in ood)
    false_routes = sum(
        result["predicted"] is not None for _, result in unsupported
    )
    wrong_tool = sum(
        result["predicted"] is not None
        and _tool(str(result["predicted"])) != _tool(str(row["expected"]))
        for row, result in supported
    )
    wrong_endpoint = sum(
        result["predicted"] is not None
        and _tool(str(result["predicted"])) == _tool(str(row["expected"]))
        and result["predicted"] != row["expected"]
        for row, result in supported
    )

    def _count_veto(
        subset: list[tuple[dict[str, Any], dict[str, Any]]],
        key: str,
    ) -> int:
        return sum(bool(result[key]) for _, result in subset)

    vetoed_supported_correct = sum(
        bool(row["raw_correct"]) and bool(result["veto"])
        for row, result in supported
    )
    supported_correct_envelope = sum(
        bool(row["raw_correct"]) and bool(result["envelope_veto"])
        for row, result in supported
    )
    supported_correct_negative = sum(
        bool(row["raw_correct"]) and bool(result["negative_veto"])
        for row, result in supported
    )
    supported_correct_consistency = sum(
        bool(row["raw_correct"]) and bool(result["consistency_veto"])
        for row, result in supported
    )

    per_language: dict[str, Any] = {}
    for language in sorted({str(row["language"]) for row in rows}):
        subset = [
            (row, result)
            for row, result in evaluated
            if row["language"] == language
        ]
        lang_supported = [
            (row, result)
            for row, result in subset
            if row["expected"] is not None
        ]
        lang_unsupported = [
            (row, result)
            for row, result in subset
            if row["expected"] is None
        ]
        per_language[language] = {
            "supported_cases": len(lang_supported),
            "supported_exact_route_accuracy": (
                sum(
                    result["predicted"] == row["expected"]
                    for row, result in lang_supported
                )
                / len(lang_supported)
                if lang_supported
                else 0.0
            ),
            "unsupported_cases": len(lang_unsupported),
            "unsupported_rejection": (
                sum(
                    result["predicted"] is None
                    for _, result in lang_unsupported
                )
                / len(lang_unsupported)
                if lang_unsupported
                else 1.0
            ),
        }

    per_route: dict[str, Any] = {}
    for route in sorted({str(row["expected"]) for row, _ in supported}):
        subset = [
            (row, result)
            for row, result in supported
            if row["expected"] == route
        ]
        correct = sum(
            result["predicted"] == route for _, result in subset
        )
        per_route[route] = {
            "cases": len(subset),
            "accepted_correct": correct,
            "supported_recall": correct / len(subset) if subset else 0.0,
        }

    per_family: dict[str, Any] = {}
    families = sorted(
        {
            str(row["unsupported_family"])
            for row, _ in near
            if row.get("unsupported_family") is not None
        }
    )
    for family in families:
        subset = [
            (row, result)
            for row, result in near
            if row.get("unsupported_family") == family
        ]
        rejected = sum(
            result["predicted"] is None for _, result in subset
        )
        per_family[family] = {
            "cases": len(subset),
            "rejected": rejected,
            "rejection_rate": rejected / len(subset) if subset else 1.0,
        }

    metrics = {
        "rule_id": _rule_id(
            envelope_min,
            negative_min,
            signed_advantage_min,
            require_positive_consistency,
        ),
        "envelope_min": envelope_min,
        "negative_min": negative_min,
        "signed_advantage_min": signed_advantage_min,
        "require_positive_consistency": require_positive_consistency,
        "supported_correct": supported_correct,
        "supported_exact_route_accuracy": supported_correct / len(supported),
        "near_domain_unsupported_rejection": near_rejected / len(near),
        "out_of_domain_rejection": ood_rejected / len(ood),
        "false_routes": false_routes,
        "false_route_rate": false_routes / len(unsupported),
        "wrong_tool": wrong_tool,
        "wrong_endpoint": wrong_endpoint,
        "vetoed_supported_correct_winners": vetoed_supported_correct,
        "vetoed_supported_correct_by_envelope": supported_correct_envelope,
        "vetoed_supported_correct_by_negative": supported_correct_negative,
        "vetoed_supported_correct_by_consistency": (
            supported_correct_consistency
        ),
        "near_veto_by_envelope": _count_veto(near, "envelope_veto"),
        "near_veto_by_negative": _count_veto(near, "negative_veto"),
        "near_veto_by_consistency": _count_veto(near, "consistency_veto"),
        "ood_veto_by_envelope": _count_veto(ood, "envelope_veto"),
        "ood_veto_by_negative": _count_veto(ood, "negative_veto"),
        "ood_veto_by_consistency": _count_veto(ood, "consistency_veto"),
        "per_language": per_language,
        "per_route": per_route,
        "unsupported_family_rejection": per_family,
    }
    metrics["quality_gate_pass"] = (
        float(metrics["supported_exact_route_accuracy"]) >= 0.85
        and float(metrics["near_domain_unsupported_rejection"]) >= 0.97
        and float(metrics["out_of_domain_rejection"]) == 1.0
        and float(metrics["false_route_rate"]) <= 0.01
    )
    return metrics


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    registry = reference_registry()

    model_started = time.perf_counter_ns()
    model = _load_model()
    model_load_ms = (time.perf_counter_ns() - model_started) / 1_000_000
    embed = _embedder(model)

    route_started = time.perf_counter_ns()
    route_backend = FrozenBgeM3DualViewBackend(registry, embed)
    route_static_ms = (
        time.perf_counter_ns() - route_started
    ) / 1_000_000

    positive_items = _positive_bank(registry)
    negative_items = _negative_bank()
    prototype_started = time.perf_counter_ns()
    prototype_vectors = embed(
        [text for _, text in positive_items]
        + [text for _, text in negative_items]
    )
    prototype_static_ms = (
        time.perf_counter_ns() - prototype_started
    ) / 1_000_000

    positive_vectors = list(
        zip(
            [route for route, _ in positive_items],
            prototype_vectors[: len(positive_items)],
            strict=True,
        )
    )
    negative_vectors = list(
        zip(
            negative_items,
            prototype_vectors[len(positive_items) :],
            strict=True,
        )
    )

    route_ids = list(route_backend.route_ids)
    allowed_routes = set(route_ids)
    rows: list[dict[str, Any]] = []
    latencies: list[float] = []

    for case in cases:
        started = time.perf_counter_ns()
        query = str(case["query"])
        query_vector = embed([query])[0]

        route_scores: list[tuple[str, float, float, float]] = []
        for route_id in route_ids:
            schema_score = _cosine(
                query_vector,
                route_backend._schema_vectors[route_id],  # noqa: SLF001
            )
            action_score = _cosine(
                query_vector,
                route_backend._action_vectors[route_id],  # noqa: SLF001
            )
            fused_score = (
                SCHEMA_WEIGHT * schema_score
                + ACTION_WEIGHT * action_score
            )
            route_scores.append(
                (route_id, fused_score, schema_score, action_score)
            )
        route_scores.sort(key=lambda item: (-item[1], item[0]))
        raw_top_route, raw_top_score, raw_schema_score, raw_action_score = (
            route_scores[0]
        )
        second_route_score = (
            route_scores[1][1] if len(route_scores) > 1 else None
        )
        raw_margin = (
            raw_top_score - second_route_score
            if second_route_score is not None
            else 2.0
        )

        positive_scored = [
            (route_id, _cosine(query_vector, vector))
            for route_id, vector in positive_vectors
        ]
        positive_scored.sort(key=lambda item: (-item[1], item[0]))
        top_positive_route, max_positive_score = positive_scored[0]

        negative_scored = [
            (
                domain,
                prototype,
                _cosine(query_vector, vector),
            )
            for (domain, prototype), vector in negative_vectors
        ]
        negative_scored.sort(
            key=lambda item: (-item[2], item[0], item[1])
        )
        (
            top_negative_domain,
            top_negative_prototype,
            max_negative_score,
        ) = negative_scored[0]

        signed_advantage = max_negative_score - max_positive_score
        capability_envelope = max(max_positive_score, max_negative_score)

        latency_ms = (time.perf_counter_ns() - started) / 1_000_000
        latencies.append(latency_ms)
        rows.append(
            {
                "case_id": case.get("id"),
                "query": query,
                "category": case.get("category"),
                "language": case.get("language"),
                "unsupported_family": case.get("unsupported_family"),
                "expected": case.get("expected"),
                "raw_top_route": raw_top_route,
                "raw_top_score": raw_top_score,
                "raw_top_margin": raw_margin,
                "raw_top_schema_score": raw_schema_score,
                "raw_top_action_score": raw_action_score,
                "raw_correct": raw_top_route == case.get("expected"),
                "top_positive_route": top_positive_route,
                "max_positive_score": max_positive_score,
                "positive_agrees_with_raw": (
                    top_positive_route == raw_top_route
                ),
                "top_negative_domain": top_negative_domain,
                "top_negative_prototype": top_negative_prototype,
                "max_negative_score": max_negative_score,
                "signed_advantage": signed_advantage,
                "capability_envelope": capability_envelope,
                "latency_ms": latency_ms,
                "authority_violation": raw_top_route not in allowed_routes,
            }
        )

    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row["category"] == "out_of_domain"]
    raw_supported_correct = sum(bool(row["raw_correct"]) for row in supported)
    authority_violations = sum(
        bool(row["authority_violation"]) for row in rows
    )

    rules: list[dict[str, Any]] = []
    for envelope_min in ENVELOPE_MIN_THRESHOLDS:
        for negative_min in NEGATIVE_MIN_THRESHOLDS:
            for advantage_min in SIGNED_ADVANTAGE_THRESHOLDS:
                for consistency in POSITIVE_CONSISTENCY_MODES:
                    rules.append(
                        _evaluate_rule(
                            rows,
                            envelope_min=envelope_min,
                            negative_min=negative_min,
                            signed_advantage_min=advantage_min,
                            require_positive_consistency=consistency,
                        )
                    )

    latency = _distribution(latencies)
    p95 = latency["p95"]
    candidate_worthy = [
        rule
        for rule in rules
        if bool(rule["quality_gate_pass"])
        and authority_violations == 0
        and p95 is not None
        and float(p95) <= 250.0
    ]
    candidate_worthy.sort(
        key=lambda rule: (
            -float(rule["supported_exact_route_accuracy"]),
            int(rule["false_routes"]),
            -float(rule["near_domain_unsupported_rejection"]),
            -float(rule["out_of_domain_rejection"]),
            str(rule["rule_id"]),
        )
    )

    groups = {
        "supported_correct_winner": [
            row for row in supported if bool(row["raw_correct"])
        ],
        "supported_wrong_winner": [
            row for row in supported if not bool(row["raw_correct"])
        ],
        "near_domain_unsupported": near,
        "out_of_domain": ood,
    }
    geometry: dict[str, Any] = {}
    for name, group in groups.items():
        geometry[name] = {
            "cases": len(group),
            "max_positive_score": _distribution(
                [float(row["max_positive_score"]) for row in group]
            ),
            "max_negative_score": _distribution(
                [float(row["max_negative_score"]) for row in group]
            ),
            "signed_advantage": _distribution(
                [float(row["signed_advantage"]) for row in group]
            ),
            "capability_envelope": _distribution(
                [float(row["capability_envelope"]) for row in group]
            ),
            "positive_raw_agreement_rate": (
                statistics.fmean(
                    float(row["positive_agrees_with_raw"])
                    for row in group
                )
                if group
                else None
            ),
        }

    return {
        "experiment": "global-signed-capability-prototype-bank-v1",
        "models": {
            "embedding": {
                "name": MODEL_NAME,
                "revision": MODEL_REVISION,
                "schema_weight": SCHEMA_WEIGHT,
                "action_weight": ACTION_WEIGHT,
                "positive_route_local_gate_used": False,
            }
        },
        "summary": {
            "cases": len(rows),
            "supported_cases": len(supported),
            "near_domain_cases": len(near),
            "ood_cases": len(ood),
            "raw_supported_correct": raw_supported_correct,
            "raw_supported_top1_accuracy": (
                raw_supported_correct / len(supported)
            ),
            "authority_violations": authority_violations,
            "execution_errors": 0,
            "model_load_ms": model_load_ms,
            "route_static_init_ms": route_static_ms,
            "prototype_static_init_ms": prototype_static_ms,
            "query_scoring_latency_ms": latency,
            "fixed_rule_count": len(rules),
            "candidate_worthy_rule_count": len(candidate_worthy),
            "best_candidate": (
                candidate_worthy[0] if candidate_worthy else None
            ),
            "evidence_geometry": geometry,
        },
        "candidate_worthy_rules": candidate_worthy,
        "rule_results": rules,
        "rows": rows,
        "policy": {
            "data_role": "tuning_eligible_development",
            "failed_fresh_confirmation_used_for_tuning": False,
            "calibration_or_blind_used": False,
            "prototype_evidence_can_select_route": False,
            "prototype_evidence_can_create_authority": False,
            "veto_only": True,
            "no_pseudo_route": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cases = json.loads(args.corpus.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or any(
        not isinstance(item, dict) for item in cases
    ):
        raise ValueError("corpus must be a JSON object list")

    result = evaluate(cases)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "raw_supported_top1_accuracy": result["summary"][
                    "raw_supported_top1_accuracy"
                ],
                "latency": result["summary"]["query_scoring_latency_ms"],
                "fixed_rule_count": result["summary"]["fixed_rule_count"],
                "candidate_worthy_rule_count": result["summary"][
                    "candidate_worthy_rule_count"
                ],
                "best_candidate": result["summary"]["best_candidate"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
