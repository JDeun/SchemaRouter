"""Fixed-K5 direct native posting retrieval: controlled EN/KO/JA E0 DEV.

Reuses the same *public* 24-service source and previously disclosed 9x3
synthetic tasks from the G5 DEV corpus. Scorer-only expected operation is
never passed to the ranker, native registry, or optional E5 model. No tool
execution or independent external gold. --mode real-e5-cpu loads one genuinely
pinned local embedding model; validate mode uses a no-model first-K backend.
"""
from __future__ import annotations

import argparse
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
        backend or CallableDecisionBackend(_first_k),
        omit_identical_descriptions=True,
    )
    durations: list[float] = []
    by_language = {
        lang: {"supported_count": 0, "hits_at_5": 0, "ood_count": 0,
               "ood_nonempty": 0}
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
            start = time.perf_counter()
            result = index.lookup(
                router, query, principal=ACTOR, group=group,
                _research_ranker=ranking,
            )
            durations.append((time.perf_counter() - start) * 1000)
            if (
                result.status != "ranked_unverified"
                or result.qualified_count != 24 or len(result.candidates) != K
                or len({c.route_id for c in result.candidates}) != K
            ):
                raise ValueError("E0 invalid ranked Top-K5 result")
            by_language[lang]["supported_count"] += 1
            by_language[lang]["hits_at_5"] += int(
                gold_route in {c.route_id for c in result.candidates}
            )
            checked += 1

    for lang, query in OOD:
        group = _group(query)
        start = time.perf_counter()
        result = index.lookup(
            router, query, principal=ACTOR, group=group,
            _research_ranker=ranking,
        )
        durations.append((time.perf_counter() - start) * 1000)
        if result.status not in ("ranked_unverified", "ranker_abstained_unverified"):
            raise ValueError("E0 OOD lacks explicit uncalibrated status")
        by_language[lang]["ood_count"] += 1
        by_language[lang]["ood_nonempty"] += int(bool(result.candidates))

    supported = sum(v["supported_count"] for v in by_language.values())
    hits = sum(v["hits_at_5"] for v in by_language.values())
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
        "by_language": by_language,
        "ood_cases": len(OOD),
        "total_lookup_calls_measured": len(durations),
        "latency_ms_p50": statistics.median(durations),
        "latency_ms_p95": _percentile(durations, 0.95),
        "latency_ms_p99": _percentile(durations, 0.99),
        "limitations": (
            "Same published synthetic route names/tasks as G5 DEV; "
            "first-K is alphabetic baseline not a learned model. "
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
