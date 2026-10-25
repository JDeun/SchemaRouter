"""Fixed-K5 direct native posting retrieval: controlled EN/KO/JA E0 DEV.

Reuses the same *public* 24-service source and previously disclosed 9x3
synthetic tasks from the G5 DEV corpus. Scorer-only expected operation is
never passed to the ranker, native registry, or optional E5 model. No tool
execution or independent external gold. --mode real-e5-cpu loads one genuinely
pinned local embedding model; validate mode uses a no-model first-K backend.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any

from schemarouter import (
    CapabilityFieldContract,
    NativeDeclaredFieldGroup,
)
from schemarouter.decisions import CallableDecisionBackend, DecisionBackend
from scripts.research_g5_e5_overflow_cpu_dev import (
    ACTOR,
    OOD,
    QUERIES,
    SERVICE_NAMES,
    _source,
)
from scripts.research_indexed_decision_backend_ranker_e0 import (
    ResearchIndexedFieldDecisionRanker,
)

K = 5
LANGUAGES = ("en", "ko", "ja")


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ranked = sorted(values)
    # Nearest-rank interpolation is deterministic and predeclared.
    at = (len(ranked) - 1) * quantile
    lower = math.floor(at)
    upper = math.ceil(at)
    return ranked[lower] + (ranked[upper] - ranked[lower]) * (at - lower)


def _group(query: str) -> NativeDeclaredFieldGroup:
    return NativeDeclaredFieldGroup(
        aliases=(query,),
        required_fields=(CapabilityFieldContract(
            semantic_id="service.status",
            json_schema={"type": "string"},
        ),),
        source_type="crm",
        license="synthetic-reviewed",
    )


def _first_k(request):
    return {"selections": [
        {"option_id": option.id}
        for option in request.options[:request.max_selections]
    ]}


def run(backend: DecisionBackend | None = None) -> dict[str, Any]:
    router, graph, _ = _source()
    index = graph.field_index
    if len(SERVICE_NAMES) != 24 or len(QUERIES) != 9 or len(OOD) != 3:
        raise ValueError("E0 source/task roster changed")
    ranking = ResearchIndexedFieldDecisionRanker(
        backend if backend is not None else CallableDecisionBackend(_first_k),
        omit_identical_descriptions=True,
    )
    # Both arms must use identical original registered schema + principal +
    # policy + FieldGroup + K. First five is a no-model comparator, not gold.
    first_five = lambda _query, _candidates, k: tuple(range(k))
    durations: list[float] = []
    baseline_durations: list[float] = []
    by_language = {
        lang: {
            "supported_count": 0, "hits_at_5": 0,
            "baseline_hits_at_5": 0, "supported_abstentions": 0,
            "ood_count": 0, "ood_nonempty": 0,
            "baseline_ood_nonempty": 0, "ood_abstentions": 0,
        }
        for lang in LANGUAGES
    }
    checked = 0

    for service_name, *translations in QUERIES:
        # Private scorer-only gold; the ranker sees ONLY the query and
        # currently-authorized candidate receipts. Not passed in request.
        gold_route = f"service_{service_name}.read"
        for lang, query in zip(LANGUAGES, translations, strict=True):
            group = _group(query)
            default = index.lookup(
                router, query, principal=ACTOR, group=group,
            )
            if default.status != "over_k_unranked" or default.qualified_count != 24:
                raise ValueError("E0 default overflow/roster drift")
            baseline_start = time.perf_counter()
            baseline = index.lookup(
                router, query, principal=ACTOR, group=group,
                _research_ranker=first_five,
            )
            baseline_durations.append(
                (time.perf_counter() - baseline_start) * 1000
            )
            if (
                baseline.status != "ranked_unverified"
                or baseline.qualified_count != 24
                or len(baseline.candidates) != K
            ):
                raise ValueError("E0 baseline candidate cohort drift")
            start = time.perf_counter()
            result = index.lookup(
                router, query, principal=ACTOR, group=group,
                _research_ranker=ranking,
            )
            durations.append((time.perf_counter() - start) * 1000)
            if (
                result.qualified_count != baseline.qualified_count
                or result.status not in (
                    "ranked_unverified", "ranker_abstained_unverified",
                )
                or (result.status == "ranked_unverified"
                    and (len(result.candidates) != K
                         or len({c.route_id for c in result.candidates}) != K))
                or (result.status == "ranker_abstained_unverified"
                    and result.candidates)
            ):
                raise ValueError("E0 invalid ranked Top-K5 result")
            by_language[lang]["supported_count"] += 1
            by_language[lang]["baseline_hits_at_5"] += int(
                gold_route in {c.route_id for c in baseline.candidates}
            )
            by_language[lang]["hits_at_5"] += int(
                gold_route in {c.route_id for c in result.candidates}
            )
            by_language[lang]["supported_abstentions"] += int(
                result.status == "ranker_abstained_unverified"
            )
            checked += 1

    for lang, query in OOD:
        group = _group(query)
        default = index.lookup(
            router, query, principal=ACTOR, group=group,
        )
        if default.status != "over_k_unranked" or default.qualified_count != 24:
            raise ValueError("E0 OOD default overflow/roster drift")
        baseline_start = time.perf_counter()
        baseline = index.lookup(
            router, query, principal=ACTOR, group=group,
            _research_ranker=first_five,
        )
        baseline_durations.append((time.perf_counter() - baseline_start) * 1000)
        if baseline.status != "ranked_unverified" or len(baseline.candidates) != K:
            raise ValueError("E0 OOD baseline cohort drift")
        start = time.perf_counter()
        result = index.lookup(
            router, query, principal=ACTOR, group=group,
            _research_ranker=ranking,
        )
        durations.append((time.perf_counter() - start) * 1000)
        if (
            result.qualified_count != baseline.qualified_count
            or result.status not in (
                "ranked_unverified", "ranker_abstained_unverified",
            )
            or (result.status == "ranked_unverified"
                and len(result.candidates) != K)
            or (result.status == "ranker_abstained_unverified"
                and result.candidates)
        ):
            raise ValueError("E0 OOD lacks valid explicit uncalibrated status")
        by_language[lang]["ood_count"] += 1
        by_language[lang]["ood_nonempty"] += int(bool(result.candidates))
        by_language[lang]["baseline_ood_nonempty"] += int(bool(baseline.candidates))
        by_language[lang]["ood_abstentions"] += int(
            result.status == "ranker_abstained_unverified"
        )

    supported = sum(v["supported_count"] for v in by_language.values())
    hits = sum(v["hits_at_5"] for v in by_language.values())
    baseline_hits = sum(v["baseline_hits_at_5"] for v in by_language.values())
    supported_abstentions = sum(
        v["supported_abstentions"] for v in by_language.values()
    )
    ood_abstentions = sum(v["ood_abstentions"] for v in by_language.values())
    # The hash fixes input roster provenance only, never independent gold.
    roster_sha256 = hashlib.sha256(json.dumps(
        {"service_names": SERVICE_NAMES, "queries": QUERIES, "ood": OOD},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return {
        "evidence_tier": (
            "E0_INJECTED_DECISION_BACKEND_PUBLIC_SYNTHETIC_DEV_ONLY"
            if backend is not None else
            "E0_NO_MODEL_FIRST_FIVE_PUBLIC_SYNTHETIC_DEV_ONLY"
        ),
        "real_model_routing_measured": False,
        "independent_publisher_gold": False,
        "agent_task_success_measured": False,
        "calibrated_no_fit": False,
        "product_default_promoted": False,
        "source_route_count": len(SERVICE_NAMES) + 1,
        "eligible_complete_candidates": len(SERVICE_NAMES),
        "k": K,
        "languages": LANGUAGES,
        "supported_cases": supported,
        "scorer_only_hits_at_5": hits,
        "supported_recall_at_5": hits / supported,
        "baseline_scorer_only_hits_at_5": baseline_hits,
        "baseline_supported_recall_at_5": baseline_hits / supported,
        "paired_recall_delta_at_5": (hits - baseline_hits) / supported,
        "supported_abstentions": supported_abstentions,
        "by_language": by_language,
        "ood_cases": len(OOD),
        "ood_abstentions": ood_abstentions,
        "ood_nonempty": sum(v["ood_nonempty"] for v in by_language.values()),
        "baseline_ood_nonempty": sum(
            v["baseline_ood_nonempty"] for v in by_language.values()
        ),
        "input_roster_sha256": roster_sha256,
        "total_lookup_calls_measured": len(durations),
        "baseline_total_lookup_calls_measured": len(baseline_durations),
        "baseline_latency_ms_p50": statistics.median(baseline_durations),
        "baseline_latency_ms_p95": _percentile(baseline_durations, 0.95),
        "baseline_latency_ms_p99": _percentile(baseline_durations, 0.99),
        "latency_ms_p50": statistics.median(durations),
        "latency_ms_p95": _percentile(durations, 0.95),
        "latency_ms_p99": _percentile(durations, 0.99),
        "limitations": (
            "Same published synthetic route names/tasks as G5 DEV; "
            "baseline is first-K in registered-route order, not a model. "
            "Both arms are run sequentially against the same catalog, "
            "not interleaved or randomized; process timing is DEV only. "
            "Abstentions are misses on supported tasks, not proof of no-fit. "
            "All route candidates have identical fields; no independent "
            "publisher holdout, no native calls, no valid no-fit calibration, "
            "no installed-package production perf/SLO inference."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", required=True, choices=("validate", "real-e5-cpu"),
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    metadata: dict[str, Any] = {}
    if args.mode == "real-e5-cpu":
        # Reuse the exact pinned real CPU model loader already used by
        # earlier G5 experiments; no model downloads in validate-mode CI.
        from scripts.evaluate_authorized_e5_hybrid_cpu_dev import real_cpu_backend

        backend, metadata = real_cpu_backend()
        report = run(backend)
        report["real_model_routing_measured"] = True
        report["evidence_tier"] = "REAL_PINNED_E5_DIRECT_INDEX_PUBLIC_SYNTHETIC_DEV_ONLY"
        report["model_runtime"] = metadata
    else:
        report = run()
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()
