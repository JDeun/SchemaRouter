"""DEV-only relative rank-vote open-world diagnostic for operation routing."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Iterable

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = Path(__file__).resolve().parent
for _path in (_PROJECT_ROOT, _SCRIPTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from analyze_dual_negative_openworld_v4 import (  # noqa: E402
    BACKGROUND_PROTOTYPES,
    DOMAIN_ANCHORS,
    NEGATIVE_CAPABILITY_PROTOTYPES,
    _distribution,
    _embedder,
    _load_model,
    _tool,
)
from benchmark_decision_routing import reference_registry  # noqa: E402
from benchmarks.bge_m3_frozen_candidate import (  # noqa: E402
    ACTION_WEIGHT,
    MODEL_NAME,
    MODEL_REVISION,
    SCHEMA_WEIGHT,
    FrozenBgeM3DualViewBackend,
    _cosine,
)

NEGATIVE_VOTE_MINIMUMS = (1, 2, 3, 4)
TOP_K_VALUES = (3, 5, 7)
BACKGROUND_REQUIREMENT_MODES = ("majority", "two_thirds", "unanimous")
REQUIRE_TOP1_BACKGROUND = (False, True)


def _required_background_votes(k: int, mode: str) -> int:
    if mode == "majority":
        return (k // 2) + 1
    if mode == "two_thirds":
        return math.ceil((2 * k) / 3)
    if mode == "unanimous":
        return k
    raise ValueError(f"unknown background requirement mode: {mode}")


def _rule_id(
    negative_votes_min: int,
    top_k: int,
    background_requirement_mode: str,
    require_top1_background: bool,
) -> str:
    top1 = "top1bg" if require_top1_background else "anytop1"
    return (
        f"nv{negative_votes_min}-k{top_k}-"
        f"{background_requirement_mode}-{top1}"
    )


def _iter_rules() -> Iterable[dict[str, Any]]:
    for negative_votes_min in NEGATIVE_VOTE_MINIMUMS:
        for top_k in TOP_K_VALUES:
            for background_requirement_mode in BACKGROUND_REQUIREMENT_MODES:
                for require_top1_background in REQUIRE_TOP1_BACKGROUND:
                    yield {
                        "negative_votes_min": negative_votes_min,
                        "top_k": top_k,
                        "background_requirement_mode": (
                            background_requirement_mode
                        ),
                        "require_top1_background": require_top1_background,
                    }


def _apply_rank_rule(
    row: dict[str, Any],
    *,
    negative_votes_min: int,
    top_k: int,
    background_requirement_mode: str,
    require_top1_background: bool,
) -> dict[str, Any]:
    negative_veto = int(row["negative_votes"]) >= negative_votes_min
    required_background_votes = _required_background_votes(
        top_k,
        background_requirement_mode,
    )
    background_votes = int(row[f"background_votes_top{top_k}"])
    top1_ok = (
        not require_top1_background
        or row["top_evidence_kind"] == "background"
    )
    background_veto = (
        background_votes >= required_background_votes and top1_ok
    )
    veto = negative_veto or background_veto
    return {
        "veto": veto,
        "negative_veto": negative_veto,
        "background_veto": background_veto,
        "required_background_votes": required_background_votes,
        "predicted": None if veto else str(row["raw_top_route"]),
    }


def _safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _evaluate_rule(
    rows: list[dict[str, Any]],
    *,
    negative_votes_min: int,
    top_k: int,
    background_requirement_mode: str,
    require_top1_background: bool,
) -> dict[str, Any]:
    evaluated = [
        (
            row,
            _apply_rank_rule(
                row,
                negative_votes_min=negative_votes_min,
                top_k=top_k,
                background_requirement_mode=background_requirement_mode,
                require_top1_background=require_top1_background,
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
    near_rejected = sum(
        result["predicted"] is None for _, result in near
    )
    ood_rejected = sum(
        result["predicted"] is None for _, result in ood
    )
    false_routes = sum(
        result["predicted"] is not None for _, result in unsupported
    )

    vetoed_supported_correct_winners = sum(
        bool(row["raw_correct"]) and bool(result["veto"])
        for row, result in supported
    )
    vetoed_supported_correct_by_negative = sum(
        bool(row["raw_correct"]) and bool(result["negative_veto"])
        for row, result in supported
    )
    vetoed_supported_correct_by_background = sum(
        bool(row["raw_correct"]) and bool(result["background_veto"])
        for row, result in supported
    )

    near_veto_by_negative = sum(
        bool(result["negative_veto"]) for _, result in near
    )
    near_veto_by_background = sum(
        bool(result["background_veto"]) for _, result in near
    )
    ood_veto_by_negative = sum(
        bool(result["negative_veto"]) for _, result in ood
    )
    ood_veto_by_background = sum(
        bool(result["background_veto"]) for _, result in ood
    )

    per_language: dict[str, Any] = {}
    for language in sorted({str(row["language"]) for row in rows}):
        subset = [
            (row, result)
            for row, result in evaluated
            if str(row["language"]) == language
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
            "cases": len(subset),
            "supported_cases": len(lang_supported),
            "supported_exact_route_accuracy": _safe_rate(
                sum(
                    result["predicted"] == row["expected"]
                    for row, result in lang_supported
                ),
                len(lang_supported),
            ),
            "unsupported_cases": len(lang_unsupported),
            "unsupported_rejection": _safe_rate(
                sum(
                    result["predicted"] is None
                    for _, result in lang_unsupported
                ),
                len(lang_unsupported),
            ),
        }

    per_route: dict[str, Any] = {}
    for route in sorted({str(row["raw_top_route"]) for row in rows}):
        subset = [
            (row, result)
            for row, result in evaluated
            if str(row["raw_top_route"]) == route
        ]
        route_supported = [
            (row, result)
            for row, result in subset
            if row["expected"] is not None
        ]
        route_unsupported = [
            (row, result)
            for row, result in subset
            if row["expected"] is None
        ]
        per_route[route] = {
            "cases": len(subset),
            "supported_cases": len(route_supported),
            "supported_exact": sum(
                result["predicted"] == row["expected"]
                for row, result in route_supported
            ),
            "unsupported_cases": len(route_unsupported),
            "unsupported_rejected": sum(
                result["predicted"] is None
                for _, result in route_unsupported
            ),
        }

    unsupported_family_rejection: dict[str, Any] = {}
    families = sorted(
        {
            str(row["unsupported_family"])
            for row in rows
            if row["unsupported_family"] is not None
        }
    )
    for family in families:
        subset = [
            (row, result)
            for row, result in evaluated
            if str(row["unsupported_family"]) == family
        ]
        unsupported_family_rejection[family] = {
            "cases": len(subset),
            "rejected": sum(
                result["predicted"] is None for _, result in subset
            ),
            "rejection": _safe_rate(
                sum(result["predicted"] is None for _, result in subset),
                len(subset),
            ),
        }

    supported_exact_route_accuracy = _safe_rate(
        supported_correct,
        len(supported),
    )
    near_domain_unsupported_rejection = _safe_rate(
        near_rejected,
        len(near),
    )
    out_of_domain_rejection = _safe_rate(ood_rejected, len(ood))
    false_route_rate = _safe_rate(false_routes, len(unsupported))

    quality_gate_pass = (
        supported_exact_route_accuracy >= 0.85
        and near_domain_unsupported_rejection >= 0.97
        and out_of_domain_rejection == 1.0
        and false_route_rate <= 0.01
    )

    return {
        "rule_id": _rule_id(
            negative_votes_min,
            top_k,
            background_requirement_mode,
            require_top1_background,
        ),
        "negative_votes_min": negative_votes_min,
        "top_k": top_k,
        "background_requirement_mode": background_requirement_mode,
        "required_background_votes": _required_background_votes(
            top_k,
            background_requirement_mode,
        ),
        "require_top1_background": require_top1_background,
        "supported_correct": supported_correct,
        "supported_exact_route_accuracy": supported_exact_route_accuracy,
        "near_domain_rejected": near_rejected,
        "near_domain_unsupported_rejection": (
            near_domain_unsupported_rejection
        ),
        "ood_rejected": ood_rejected,
        "out_of_domain_rejection": out_of_domain_rejection,
        "false_routes": false_routes,
        "false_route_rate": false_route_rate,
        "vetoed_supported_correct_winners": (
            vetoed_supported_correct_winners
        ),
        "vetoed_supported_correct_by_negative": (
            vetoed_supported_correct_by_negative
        ),
        "vetoed_supported_correct_by_background": (
            vetoed_supported_correct_by_background
        ),
        "near_veto_by_negative": near_veto_by_negative,
        "near_veto_by_background": near_veto_by_background,
        "ood_veto_by_negative": ood_veto_by_negative,
        "ood_veto_by_background": ood_veto_by_background,
        "per_language": per_language,
        "per_route": per_route,
        "unsupported_family_rejection": unsupported_family_rejection,
        "quality_gate_pass": quality_gate_pass,
    }


def _vote_distribution(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = [int(row[key]) for row in rows]
    counts = {str(value): values.count(value) for value in sorted(set(values))}
    return {
        "count": len(values),
        "mean": statistics.fmean(values) if values else None,
        "counts": counts,
    }


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    registry = reference_registry()
    model_load_started = time.perf_counter_ns()
    model = _load_model()
    model_load_ms = (time.perf_counter_ns() - model_load_started) / 1_000_000
    embed = _embedder(model)

    route_init_started = time.perf_counter_ns()
    backend = FrozenBgeM3DualViewBackend(registry, embed)
    route_init_ms = (time.perf_counter_ns() - route_init_started) / 1_000_000

    domains = sorted(DOMAIN_ANCHORS)
    negative_items = [
        (domain, prototype)
        for domain in domains
        for prototype in NEGATIVE_CAPABILITY_PROTOTYPES[domain]
    ]
    static_started = time.perf_counter_ns()
    static_vectors = embed(
        [DOMAIN_ANCHORS[domain] for domain in domains]
        + [prototype for _, prototype in negative_items]
        + list(BACKGROUND_PROTOTYPES)
    )
    evidence_static_init_ms = (
        time.perf_counter_ns() - static_started
    ) / 1_000_000

    domain_end = len(domains)
    negative_end = domain_end + len(negative_items)
    domain_vectors = dict(
        zip(domains, static_vectors[:domain_end], strict=True)
    )
    negative_vectors: dict[str, list[tuple[str, list[float]]]] = {
        domain: [] for domain in domains
    }
    for (domain, prototype), vector in zip(
        negative_items,
        static_vectors[domain_end:negative_end],
        strict=True,
    ):
        negative_vectors[domain].append((prototype, vector))
    background_vectors = list(
        zip(
            BACKGROUND_PROTOTYPES,
            static_vectors[negative_end:],
            strict=True,
        )
    )

    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    route_ids = list(backend.route_ids)
    allowed_routes = set(route_ids)

    for case in cases:
        started = time.perf_counter_ns()
        query = str(case["query"])
        query_vector = embed([query])[0]

        route_scores: list[tuple[str, float, float, float]] = []
        for route_id in route_ids:
            schema_score = _cosine(
                query_vector,
                backend._schema_vectors[route_id],  # noqa: SLF001
            )
            action_score = _cosine(
                query_vector,
                backend._action_vectors[route_id],  # noqa: SLF001
            )
            fused = (
                SCHEMA_WEIGHT * schema_score
                + ACTION_WEIGHT * action_score
            )
            route_scores.append(
                (route_id, fused, schema_score, action_score)
            )
        route_scores.sort(key=lambda item: (-item[1], item[0]))
        (
            top_route,
            top_score,
            top_schema_score,
            top_action_score,
        ) = route_scores[0]
        second_score = (
            route_scores[1][1] if len(route_scores) > 1 else None
        )
        top_margin = (
            top_score - second_score
            if second_score is not None
            else 2.0
        )
        winner_domain = _tool(top_route)
        if winner_domain is None or winner_domain not in domain_vectors:
            raise RuntimeError(
                f"raw winner has unknown domain: {top_route}"
            )

        negative_scored = [
            (prototype, _cosine(query_vector, vector))
            for prototype, vector in negative_vectors[winner_domain]
        ]
        negative_scored.sort(key=lambda item: (-item[1], item[0]))
        negative_votes = sum(
            score > top_action_score
            for _, score in negative_scored
        )

        evidence_scored: list[tuple[str, str, float]] = []
        evidence_scored.extend(
            ("known", domain, _cosine(query_vector, vector))
            for domain, vector in domain_vectors.items()
        )
        evidence_scored.extend(
            ("background", prototype, _cosine(query_vector, vector))
            for prototype, vector in background_vectors
        )
        evidence_scored.sort(
            key=lambda item: (-item[2], item[0], item[1])
        )
        (
            top_evidence_kind,
            top_evidence_label,
            top_evidence_score,
        ) = evidence_scored[0]
        background_votes = {
            k: sum(
                kind == "background"
                for kind, _, _ in evidence_scored[:k]
            )
            for k in TOP_K_VALUES
        }

        latency_ms = (
            time.perf_counter_ns() - started
        ) / 1_000_000
        latencies.append(latency_ms)
        rows.append(
            {
                "case_id": case.get("id"),
                "query": query,
                "category": case.get("category"),
                "language": case.get("language"),
                "unsupported_family": case.get("unsupported_family"),
                "expected": case.get("expected"),
                "raw_top_route": top_route,
                "raw_top_score": top_score,
                "raw_top_margin": top_margin,
                "raw_top_schema_score": top_schema_score,
                "raw_top_action_score": top_action_score,
                "raw_correct": top_route == case.get("expected"),
                "winner_domain": winner_domain,
                "negative_votes": negative_votes,
                "top_negative_prototype": negative_scored[0][0],
                "top_negative_score": negative_scored[0][1],
                "top_evidence_kind": top_evidence_kind,
                "top_evidence_label": top_evidence_label,
                "top_evidence_score": top_evidence_score,
                **{
                    f"background_votes_top{k}": background_votes[k]
                    for k in TOP_K_VALUES
                },
                "latency_ms": latency_ms,
                "authority_violation": (
                    top_route not in allowed_routes
                ),
            }
        )

    supported = [
        row for row in rows if row["expected"] is not None
    ]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [
        row for row in rows if row["category"] == "out_of_domain"
    ]
    raw_supported_correct = sum(
        bool(row["raw_correct"]) for row in supported
    )
    authority_violations = sum(
        bool(row["authority_violation"]) for row in rows
    )

    rules = [
        _evaluate_rule(rows, **rule)
        for rule in _iter_rules()
    ]
    latency = _distribution(latencies)
    latency_p95 = latency["p95"]
    candidate_worthy = [
        rule
        for rule in rules
        if bool(rule["quality_gate_pass"])
        and authority_violations == 0
        and latency_p95 is not None
        and float(latency_p95) <= 250.0
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
            row for row in supported if row["raw_correct"]
        ],
        "supported_wrong_winner": [
            row for row in supported if not row["raw_correct"]
        ],
        "near_domain_unsupported": near,
        "out_of_domain": ood,
    }
    evidence_geometry: dict[str, Any] = {}
    for name, group in groups.items():
        evidence_geometry[name] = {
            "cases": len(group),
            "negative_votes": _vote_distribution(
                group,
                "negative_votes",
            ),
            "background_votes_top3": _vote_distribution(
                group,
                "background_votes_top3",
            ),
            "background_votes_top5": _vote_distribution(
                group,
                "background_votes_top5",
            ),
            "background_votes_top7": _vote_distribution(
                group,
                "background_votes_top7",
            ),
            "top1_background_rate": _safe_rate(
                sum(
                    row["top_evidence_kind"] == "background"
                    for row in group
                ),
                len(group),
            ),
        }

    return {
        "experiment": "relative-rank-vote-openworld-v1",
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
            "raw_supported_top1_accuracy": _safe_rate(
                raw_supported_correct,
                len(supported),
            ),
            "authority_violations": authority_violations,
            "execution_errors": 0,
            "model_load_ms": model_load_ms,
            "route_static_init_ms": route_init_ms,
            "evidence_static_init_ms": evidence_static_init_ms,
            "query_scoring_latency_ms": latency,
            "fixed_rule_count": len(rules),
            "candidate_worthy_rule_count": len(candidate_worthy),
            "best_candidate": (
                candidate_worthy[0]
                if candidate_worthy
                else None
            ),
            "evidence_geometry": evidence_geometry,
        },
        "candidate_worthy_rules": candidate_worthy,
        "rule_results": rules,
        "rows": rows,
        "policy": {
            "data_role": "tuning_eligible_development",
            "failed_fresh_confirmation_used_for_tuning": False,
            "calibration_or_blind_used": False,
            "absolute_similarity_thresholds_used": False,
            "negative_evidence_can_select_route": False,
            "background_evidence_can_select_route": False,
            "veto_only": True,
            "no_pseudo_route": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cases = json.loads(
        args.corpus.read_text(encoding="utf-8")
    )
    if not isinstance(cases, list) or any(
        not isinstance(item, dict) for item in cases
    ):
        raise ValueError("corpus must be a JSON object list")

    result = evaluate(cases)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "raw_supported_top1_accuracy": result["summary"][
                    "raw_supported_top1_accuracy"
                ],
                "latency": result["summary"][
                    "query_scoring_latency_ms"
                ],
                "fixed_rule_count": result["summary"][
                    "fixed_rule_count"
                ],
                "candidate_worthy_rule_count": result["summary"][
                    "candidate_worthy_rule_count"
                ],
                "best_candidate": result["summary"][
                    "best_candidate"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
