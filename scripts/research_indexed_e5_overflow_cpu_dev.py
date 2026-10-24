"""Source-verified direct-FieldGroup K5 vs model ranking: synthetic DEV only.

Uses the same frozen 24 native service names / EN-KO-JA cases as the G5
research scenario, but with input-free source endpoints for direct retrieval.
No gold enters a model prompt. No tools execute. No independent E2 claim.
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeDeclaredFieldGroup,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.decisions import CallableDecisionBackend, DecisionBackend
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import (
    MODEL_ID,
    MODEL_REVISION,
    real_cpu_backend,
)
from scripts.evaluate_multilingual_embedding_cpu_dev import percentile
from scripts.research_g5_e5_overflow_cpu_dev import OOD, QUERIES, SERVICE_NAMES
from scripts.research_indexed_decision_backend_ranker_e0 import (
    ResearchAuthorizedIndexedDecisionRanker,
)

ROOT = Path(__file__).resolve().parents[1]
K = 5
ACTOR = PrincipalContext(subject="indexed-direct-synthetic-dev", roles=("reader",))


def _source() -> tuple[SchemaRouter, NativeSchemaPostingIndex, NativeDeclaredFieldGroup]:
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
    ))
    for name in SERVICE_NAMES:
        router.add_tool(ToolSpec(
            name=f"service_{name}",
            source_type="crm",
            license="synthetic-reviewed",
            endpoints=[EndpointSpec(
                name="read",
                read_only=True,
                output_fields=[FieldSpec(
                    name="status",
                    semantic_id="service.status",
                    json_schema={"type": "string"},
                )],
            )],
        ))
    index = NativeSchemaPostingIndex.build(router.registry)
    group = NativeDeclaredFieldGroup(
        aliases=("synthetic case status",),
        required_fields=(CapabilityFieldContract(
            semantic_id="service.status", json_schema={"type": "string"},
        ),),
        source_type="crm", license="synthetic-reviewed",
    )
    if (
        index.indexed_route_count != len(SERVICE_NAMES)
        or len(index.postings["service.status"]) != len(SERVICE_NAMES)
    ):
        raise ValueError("direct field-index synthetic source drift")
    return router, index, group


def _first_five(request):
    return {
        "selections": [
            {"option_id": option.id}
            for option in request.options[:request.max_selections]
        ],
    }


def run(semantic_backend: DecisionBackend | None = None) -> dict[str, Any]:
    """Score only public DEV recall; injected backends never attest model ID."""
    router, index, template = _source()
    first5 = ResearchAuthorizedIndexedDecisionRanker(
        CallableDecisionBackend(_first_five),
    )
    semantic = (
        ResearchAuthorizedIndexedDecisionRanker(semantic_backend)
        if semantic_backend is not None else None
    )
    supported = [
        (lang, query, f"service_{service}.read")
        for service, en, ko, ja in QUERIES
        for lang, query in zip(("en", "ko", "ja"), (en, ko, ja), strict=True)
    ]
    unsupported = [(lang, query, None) for lang, query in OOD]
    if len(supported) != 27 or len(unsupported) != 3:
        raise ValueError("synthetic multilingual case fixture changed")

    metrics: dict[str, dict[str, int | None]] = {
        lang: {
            "supported_count": 0,
            "first5_recall_count": 0,
            "model_recall_count": 0 if semantic is not None else None,
            "ood_nonempty_first5_count": 0,
            "ood_nonempty_model_count": 0 if semantic is not None else None,
        }
        for lang in ("en", "ko", "ja")
    }
    latency: dict[str, list[float]] = {
        "unranked": [], "first5": [], "model": [],
    }
    paired_rescued = paired_regressed = 0
    allowed_ids = {f"service_{name}.read" for name in SERVICE_NAMES}
    for lang, query, expected in [*supported, *unsupported]:
        # Exact host-owned semantic carrier. Its alias is the *query*, not
        # the scorer gold: the latter is used ONLY after a selection is made.
        demand = NativeDeclaredFieldGroup(
            aliases=(query,), required_fields=template.required_fields,
            source_type=template.source_type, license=template.license,
        )
        begin = time.perf_counter_ns()
        abstained = index.lookup(
            router, query, principal=ACTOR, group=demand,
            input_free_only=True,
        )
        latency["unranked"].append((time.perf_counter_ns() - begin) / 1e6)
        if (
            abstained.status != "over_k_unranked"
            or abstained.candidates or abstained.qualified_count != len(SERVICE_NAMES)
        ):
            raise ValueError("indexed direct default abstention contract changed")

        begin = time.perf_counter_ns()
        baseline = index.lookup(
            router, query, principal=ACTOR, group=demand,
            input_free_only=True, _research_ranker=first5,
        )
        latency["first5"].append((time.perf_counter_ns() - begin) / 1e6)
        if (
            baseline.status != "ranked_unverified"
            or not baseline.experimental_ranked
            or len(baseline.candidates) != K
            or baseline.qualified_count != len(SERVICE_NAMES)
        ):
            raise ValueError("invalid indexed first-five synthetic control")
        old = {item.route_id for item in baseline.candidates}
        new: set[str] | None = None
        if semantic is not None:
            begin = time.perf_counter_ns()
            ranked = index.lookup(
                router, query, principal=ACTOR, group=demand,
                input_free_only=True, _research_ranker=semantic,
            )
            latency["model"].append((time.perf_counter_ns() - begin) / 1e6)
            if (
                ranked.status != "ranked_unverified"
                or not ranked.experimental_ranked
                or len(ranked.candidates) != K
                or ranked.qualified_count != len(SERVICE_NAMES)
            ):
                raise ValueError("injected indexed model broke the proof contract")
            new = {item.route_id for item in ranked.candidates}
            if not new.issubset(allowed_ids):
                raise ValueError("model escaped source-owned native ID set")
        if not old.issubset(allowed_ids):
            raise ValueError("first-five control escaped native source")
        row = metrics[lang]
        if expected is None:
            row["ood_nonempty_first5_count"] = (
                int(row["ood_nonempty_first5_count"] or 0) + int(bool(old))
            )
            if new is not None:
                row["ood_nonempty_model_count"] = (
                    int(row["ood_nonempty_model_count"] or 0) + int(bool(new))
                )
            continue
        row["supported_count"] = int(row["supported_count"] or 0) + 1
        found_before = expected in old
        row["first5_recall_count"] = (
            int(row["first5_recall_count"] or 0) + int(found_before)
        )
        if new is not None:
            found_after = expected in new
            row["model_recall_count"] = (
                int(row["model_recall_count"] or 0) + int(found_after)
            )
            paired_rescued += int(not found_before and found_after)
            paired_regressed += int(found_before and not found_after)
        index._assert_source(router)

    return {
        "schema_version": 1,
        "evidence_tier": (
            "E0_INJECTED_DIRECT_INDEX_DECISION_DEV_NOT_ATTESTED"
            if semantic is not None else "E0_NO_MODEL_DIRECT_INDEX_SYNTHETIC_DEV_ONLY"
        ),
        "real_model_routing_measured": False,
        "independent_publisher_gold": False,
        "independent_e2_qualified": False,
        "agent_task_success_measured": False,
        "calibrated_no_fit": False,
        "product_default_promoted": False,
        "source_snapshot_id": index.snapshot_id,
        "indexed_route_count": index.indexed_route_count,
        "synthetic_service_paths": len(SERVICE_NAMES),
        "k": K,
        "languages": ("en", "ko", "ja"),
        "supported_case_count": len(supported),
        "ood_case_count": len(unsupported),
        "per_language": metrics,
        "paired_first5_to_model": (
            {"rescued": paired_rescued, "regressed": paired_regressed}
            if semantic is not None else None
        ),
        "whole_lookup_latency_ms": {
            mode: {
                "p50": percentile(values, 50),
                "p95": percentile(values, 95),
                "p99": percentile(values, 99),
                "mean": statistics.fmean(values),
            }
            for mode, values in latency.items() if values
        },
        "model_input_output_tokens": None,
        "limitations": (
            "Synthetic disclosed route IDs/EN-KO-JA query text and developer "
            "gold; matched source tool semantics intentionally identical. "
            "No external publisher validation, agent execution, calibrated "
            "abstention, measured model tokens, independent gold, SLA or "
            "product default promotion. All OOD nonempty counts are false "
            "suggestion diagnostics, not no-fit calibration."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("validate", "real-e5-cpu"))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.mode == "real-e5-cpu" and args.out is None:
        raise ValueError("real E5 mode requires explicit DEV report output")
    model, runtime = real_cpu_backend() if args.mode == "real-e5-cpu" else (None, None)
    report = run(model)
    if runtime is not None:
        if (
            runtime.get("model_id") != MODEL_ID
            or runtime.get("model_revision") != MODEL_REVISION
            or runtime.get("device") != "cpu"
        ):
            raise ValueError("unattested local CPU model identity")
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
        if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError("source revision is not a pinned Git commit")
        report["source_revision"] = sha
        report["model_runtime"] = runtime
        report["evidence_tier"] = "REAL_PINNED_E5_CPU_DIRECT_INDEX_SYNTHETIC_DEV_ONLY"
        report["real_model_routing_measured"] = True
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
