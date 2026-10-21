"""Actual pinned CPU E5 ranking of 24 fully authorized source-typed G5 paths.

All requests/native schemas/gold in this script are *disclosed synthetic DEV*.
No native provider invocation, no agent, no independent external task gold,
no verified no-fit. Candidate model input is only live scoped path evidence.
"""
from __future__ import annotations

import argparse
import json
import math
import platform
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
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.decisions import (
    CallableDecisionBackend,
    DecisionBackend,
    DecisionRequest,
    DecisionResult,
    EmbeddingDecisionBackend,
    validate_decision,
)
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import (
    MODEL_ID,
    MODEL_REVISION,
    real_cpu_backend,
)
from scripts.evaluate_multilingual_embedding_cpu_dev import percentile
from scripts.research_g5_decision_backend_ranker_e0 import (
    ResearchAuthorizedG5DecisionRanker,
)

ROOT = Path(__file__).resolve().parents[1]
K = 5
# Frozen synthetic account carrier used by the ORIGINAL 6-agent fixture.
# Never extract it from scorer gold or select it based on query outcomes.
ACCOUNT_QUERY_CARRIER = " for account acct_demo_7"
QUERY_VARIANTS = ("task_only", "account_carrier")
SERVICE_NAMES = (
    "account", "appointment", "billing", "booking", "budget", "delivery",
    "enrollment", "expense", "feedback", "identity", "insurance", "invoice",
    "membership", "notification", "order", "payment", "refund", "registration",
    "renewal", "reservation", "return", "shipping", "subscription", "warranty",
)
# Each service has the exact same typed input and output; the ONLY semantic
# differentiation available to the ranker is its registered native route ID.
# This is an intentional G5 path-evidence limitation, not publisher gold.
# Gold is referenced ONLY by the offline scorer after both lookups.
QUERIES = (
    ("refund", "refund request status", "환불 요청 상태", "返金申請の状況"),
    ("invoice", "invoice processing status", "청구서 처리 상태", "請求書の処理状況"),
    ("delivery", "delivery progress status", "배송 진행 상태", "配達の進捗状況"),
    ("appointment", "appointment schedule status", "예약된 진료 약속 상태", "診察予約の状況"),
    ("warranty", "warranty claim status", "제품 보증 청구 상태", "保証請求の状況"),
    ("enrollment", "enrollment application status", "등록 신청 상태", "入学申請の状況"),
    ("subscription", "subscription activation status",
     "구독 활성화 상태", "サブスクリプションの有効化状況"),
    ("shipping", "shipping shipment status", "발송 화물 상태", "出荷状況"),
    ("insurance", "insurance claim status", "보험 청구 처리 상태", "保険金請求の状況"),
)
OOD = (
    ("en", "forecast the lunar eclipse date next century"),
    ("ko", "우주 탐사선의 다음 착륙일 예측"),
    ("ja", "火星探査機の次の着陸日を予測"),
)
ACTOR = PrincipalContext(subject="g5-local-synthetic-dev", roles=("reader",))


def _source() -> tuple[SchemaRouter, NativeSchemaGraphIndex, NativeDeclaredFieldGroup]:
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.*", roles_any=("reader",),
        ),),
    ))
    router.add_tool(ToolSpec(
        name="customer_directory", source_type="crm", license="synthetic-reviewed",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            output_fields=[FieldSpec(
                name="account_id", semantic_id="crm.account_id",
                json_schema={"type": "string"}, identifier=True,
            )],
        )],
    ))
    for name in SERVICE_NAMES:
        router.add_tool(ToolSpec(
            name=f"service_{name}", source_type="crm",
            license="synthetic-reviewed",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                parameters=[ParameterSpec(
                    name="account_id", location="argument",
                    required=True, semantic_id="crm.account_id",
                    json_schema={"type": "string"},
                )],
                input_schema={
                    "type": "object",
                    "properties": {"account_id": {"type": "string"}},
                    "required": ["account_id"],
                },
                output_fields=[FieldSpec(
                    name="status", semantic_id="service.status",
                    json_schema={"type": "string"},
                )],
            )],
        ))
    field_index = NativeSchemaPostingIndex.build(router.registry)
    graph = NativeSchemaGraphIndex.build(field_index)
    group = NativeDeclaredFieldGroup(
        aliases=("synthetic case status",),
        required_fields=(CapabilityFieldContract(
            semantic_id="service.status", json_schema={"type": "string"},
        ),),
        source_type="crm",
        license="synthetic-reviewed",
    )
    if (
        graph.field_index.indexed_route_count != len(SERVICE_NAMES) + 1
        or len(graph.graph.edges) != len(SERVICE_NAMES)
        or graph.native_root_count != 1
        or graph.native_consumer_count != len(SERVICE_NAMES)
    ):
        raise ValueError("invalid 24-path original native G5 source")
    return router, graph, group


def _first_k_backend(request):
    return {"selections": [
        {"option_id": option.id}
        for option in request.options[:request.max_selections]
    ]}


class UnscoredE5ScoreObserver:
    """Observes finite cosine metadata; CANNOT select, calibrate or authorize.

    Source-scoped model decision is validated unchanged; per-case evidence is
    consumed only AFTER the live G5 graph returns its current-authorized K5.
    Never emits or retains query strings, gold, selected IDs or embeddings.
    """

    def __init__(self, backend: EmbeddingDecisionBackend) -> None:
        if type(backend) is not EmbeddingDecisionBackend:
            raise TypeError("requires a genuine embedding decision backend")
        self.backend = backend
        self.observed: list[dict[str, float]] = []

    def decide(self, request: DecisionRequest) -> DecisionResult:
        raw = self.backend.decide(request)
        if not isinstance(raw, DecisionResult):
            raise ValueError("research E5 score observer requires sync decision")
        verified = validate_decision(request, raw)
        metadata = verified.metadata
        top_raw = metadata.get("top_similarity")
        if isinstance(top_raw, bool) or not isinstance(
            top_raw, (int, float)
        ):
            raise ValueError("invalid E5 score-only uncalibrated observation")
        top = float(top_raw)
        scores: list[float] = []
        for selection in verified.selections:
            value = selection.score
            if value is None or not math.isfinite(value):
                raise ValueError("invalid E5 score-only uncalibrated observation")
            scores.append(value)
        if (
            metadata.get("provider") != "embedding-similarity"
            or metadata.get("option_count") != len(request.options)
            or len(scores) != K or verified.abstained
            or not math.isfinite(top) or not -1 <= top <= 1
            or any(scores[i] < scores[i + 1]
                   for i in range(len(scores) - 1))
            or not math.isclose(
                2 * scores[0] - 1, top, rel_tol=0, abs_tol=1e-7
            )
        ):
            raise ValueError("invalid E5 score-only uncalibrated observation")
        kth = 2 * scores[-1] - 1
        self.observed.append({
            "top_cosine": top,
            "kth_cosine": kth,
            "top_to_kth_span": top - kth,
        })
        return verified


def _score_summary(values: list[float]) -> dict[str, float]:
    if not values or not all(math.isfinite(x) for x in values):
        raise ValueError("invalid E5 public DEV score aggregation")
    return {
        "min": min(values),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "max": max(values),
    }


def run(
    semantic_backend: DecisionBackend | None = None,
    *,
    query_variant: str = "task_only",
    omit_identical_descriptions: bool = False,
) -> dict[str, Any]:
    if type(omit_identical_descriptions) is not bool:
        raise ValueError("G5 description ablation requires exact bool")
    if type(query_variant) is not str or query_variant not in QUERY_VARIANTS:
        raise ValueError("only frozen public synthetic G5 query variants allowed")
    router, graph, group = _source()
    # Pair all 27 original task intentions with the SAME source-approved
    # account-carrier added in the old agent fixture. This is the declared
    # generic carrier perturbation, not a gold-aware rewrite/translator.
    cases = [
        (
            lang,
            text + (ACCOUNT_QUERY_CARRIER if query_variant == "account_carrier" else ""),
            f"service_{service}.read",
        )
        for service, en, ko, ja in QUERIES
        for lang, text in zip(("en", "ko", "ja"), (en, ko, ja), strict=True)
    ]
    negative_cases = [(lang, text, None) for lang, text in OOD]
    # The real-model mode uses the SAME source, labels, query text and order
    # as the no-model validator; no expected route is supplied to the backend.
    baseline = ResearchAuthorizedG5DecisionRanker(
        CallableDecisionBackend(_first_k_backend),
    )
    # The observer is optional and model-neutral. Its scores never alter
    # ranking or set a no-fit threshold. Library-injected backends cannot
    # assert actual pinned E5 runtime identity.
    observer = (
        UnscoredE5ScoreObserver(semantic_backend)
        if type(semantic_backend) is EmbeddingDecisionBackend else None
    )
    semantic = (
        ResearchAuthorizedG5DecisionRanker(
            observer or semantic_backend,
            omit_identical_descriptions=omit_identical_descriptions,
        )
        if semantic_backend is not None else None
    )
    score_rows: dict[str, dict[str, list[dict[str, float]]]] = {
        "supported": {lang: [] for lang in ("en", "ko", "ja")},
        "unsupported": {lang: [] for lang in ("en", "ko", "ja")},
    }
    stats: dict[str, dict[str, Any]] = {
        lang: {
            "supported_count": 0, "first5_recall_count": 0,
            "e5_recall_count": 0 if semantic is not None else None,
            "ood_nonempty_first5_count": 0, "ood_nonempty_e5_count": (
                0 if semantic is not None else None
            ),
        }
        for lang in ("en", "ko", "ja")
    }
    durations: dict[str, list[float]] = {"unranked": [], "first5": [], "e5": []}
    paired_rescued = paired_regressed = 0
    for language, query, gold in [*cases, *negative_cases]:
        # Host-provided synthetic query-to-semantic contract for each case.
        # No model/semantic inference or source-owned alias is asserted.
        requested = NativeDeclaredFieldGroup(
            aliases=(query,), required_fields=group.required_fields,
            source_type=group.source_type, license=group.license,
        )
        started = time.perf_counter_ns()
        unranked = graph.lookup(router, query, group=requested, principal=ACTOR)
        durations["unranked"].append((time.perf_counter_ns() - started) / 1e6)
        if (
            unranked.status != "over_k_unranked"
            or unranked.candidates
            or unranked.qualified_path_count != len(SERVICE_NAMES)
        ):
            raise ValueError("changed default G5 strict over-K behavior")
        started = time.perf_counter_ns()
        original = graph.lookup(
            router, query, group=requested, principal=ACTOR,
            _research_ranker=baseline,
        )
        durations["first5"].append((time.perf_counter_ns() - started) / 1e6)
        if (
            original.status != "ranked_unverified"
            or len(original.candidates) != K
            or original.executable_authority or original.calibrated_no_fit
            or original.independent_quality_evidence
        ):
            raise ValueError("invalid fixed first-five control")
        old_ids = {item.consumer_route_id for item in original.candidates}
        new_ids = None
        if semantic is not None:
            observed_count_before = (
                len(observer.observed) if observer is not None else None
            )
            started = time.perf_counter_ns()
            ranked = graph.lookup(
                router, query, group=requested, principal=ACTOR,
                _research_ranker=semantic,
            )
            durations["e5"].append((time.perf_counter_ns() - started) / 1e6)
            if (
                ranked.status != "ranked_unverified"
                or len(ranked.candidates) != K
                or ranked.qualified_path_count != len(SERVICE_NAMES)
                or ranked.executable_authority or ranked.calibrated_no_fit
                or ranked.independent_quality_evidence
            ):
                raise ValueError("unverified E5 G5 ranked contract violated")
            new_ids = {item.consumer_route_id for item in ranked.candidates}
            if not new_ids.issubset({
                f"service_{service}.read" for service in SERVICE_NAMES
            }):
                raise ValueError("native G5 ranker escaped original source scope")
            if observer is not None:
                if (
                    observed_count_before is None
                    or len(observer.observed) != observed_count_before + 1
                ):
                    raise ValueError("not exactly one authorized E5 score trace")
                # Scorer-only label, never added to the decision request.
                group_key = "supported" if gold is not None else "unsupported"
                score_rows[group_key][language].append(
                    observer.observed[-1]
                )
        counters = stats[language]
        if gold is None:
            counters["ood_nonempty_first5_count"] += int(bool(old_ids))
            if new_ids is not None:
                counters["ood_nonempty_e5_count"] += int(bool(new_ids))
            continue
        counters["supported_count"] += 1
        a = gold in old_ids
        counters["first5_recall_count"] += int(a)
        if new_ids is not None:
            b = gold in new_ids
            counters["e5_recall_count"] += int(b)
            paired_rescued += int(not a and b)
            paired_regressed += int(a and not b)
        graph.field_index._assert_source(router)
    full = semantic is not None
    score_diagnostic = None
    if observer is not None:
        if len(observer.observed) != len(cases) + len(negative_cases):
            raise ValueError("missing authorized E5 decision score observations")
        score_diagnostic = {
            "evidence_tier": "UNSCORED_PUBLIC_SYNTHETIC_DEV_SCORE_ONLY",
            "observed_model_calls": len(observer.observed),
            "no_fit_threshold_selected": False,
            "probabilities_calibrated": False,
            "independent_publisher_evidence": False,
            "meaning_of_top_to_kth_span": (
                "top of selected K5 minus fifth-selected cosine, "
                "NOT a top-versus-sixth boundary margin"
            ),
            "by_stratum_language": {
                group: {
                    language: {
                        "count": len(values),
                        **{
                            key: _score_summary([v[key] for v in values])
                            for key in (
                                "top_cosine", "kth_cosine", "top_to_kth_span"
                            )
                        },
                    }
                    for language, values in langs.items() if values
                }
                for group, langs in score_rows.items()
            },
        }
    return {
        "schema_version": 1,
        "query_variant": query_variant,
        "identical_descriptions_omitted": omit_identical_descriptions,
        "evidence_tier": (
            "E0_INJECTED_G5_DECISION_BACKEND_DEV_NOT_ATTESTED"
            if full else "E0_NO_MODEL_G5_OVERFLOW_SYNTHETIC_DEV_ONLY"
        ),
        "real_model_routing_measured": False,
        "independent_e2_qualified": False,
        "independent_publisher_gold": False,
        "agent_task_success_measured": False,
        "calibrated_no_fit": False,
        "product_default_promoted": False,
        "synthetic_service_paths": len(SERVICE_NAMES),
        "native_source_index_snapshot_id": graph.field_index.snapshot_id,
        "required_typed_one_hop_edges": len(graph.graph.edges),
        "k": K,
        "languages": ("en", "ko", "ja"),
        "supported_case_count": len(cases),
        "ood_case_count": len(negative_cases),
        "per_language": stats,
        "e5_score_diagnostic_unscored": score_diagnostic,
        "paired_first5_to_e5": (
            {"rescued": paired_rescued, "regressed": paired_regressed}
            if full else None
        ),
        "whole_lookup_latency_ms": (
            {label: {
                "p50": percentile(values, 50),
                "p95": percentile(values, 95),
                "p99": percentile(values, 99),
                "mean": statistics.fmean(values),
            } for label, values in durations.items() if values}
            if full else None
        ),
        "limitations": (
            "All 24 path names, EN/KO/JA queries and scorer gold are disclosed "
            "developer synthetic. Source-native typed binding and policy are "
            "real local G5 contracts but provider routes are not externally "
            "validated services. Only one semantic status field per path; "
            "the model sees English route IDs, not publisher-authored schema "
            "descriptions or full native schemas. Every OOD shortlisting is "
            "unverified, not a calibrated fit or a real tool invocation. "
            "No agent E2, confidence intervals, model ranking tuning or SLA."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("validate", "real-e5-cpu"), required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.mode == "real-e5-cpu" and args.out is None:
        raise ValueError("real CPU mode requires explicit artifact output")
    backend, metadata = real_cpu_backend() if args.mode == "real-e5-cpu" else (None, None)
    report = run(backend)
    if metadata is not None:
        if (
            metadata.get("model_id") != MODEL_ID
            or metadata.get("model_revision") != MODEL_REVISION
            or metadata.get("device") != "cpu"
            or report["e5_score_diagnostic_unscored"] is None
        ):
            raise ValueError("actual model runtime identity/evidence mismatch")
        carrier = run(backend, query_variant="account_carrier")
        if (
            carrier["query_variant"] != "account_carrier"
            or report["query_variant"] != "task_only"
            or carrier["native_source_index_snapshot_id"]
            != report["native_source_index_snapshot_id"]
            or carrier["synthetic_service_paths"] != report["synthetic_service_paths"]
            or carrier["supported_case_count"] != report["supported_case_count"]
            or carrier["ood_case_count"] != report["ood_case_count"]
            or carrier["independent_e2_qualified"] is not False
            or carrier["real_model_routing_measured"] is not False
            or carrier["calibrated_no_fit"] is not False
        ):
            raise ValueError("changed source/provenance in paired carrier ablation")
        # Optional label-only option-text condition: only strips descriptions
        # that are EXACTLY identical across all 24 currently authorized path
        # options. No task gold or user query text controls the operation.
        task_only_omitted = run(
            backend, omit_identical_descriptions=True,
        )
        carrier_omitted = run(
            backend, query_variant="account_carrier",
            omit_identical_descriptions=True,
        )
        for variant, item in (
            ("task_only", task_only_omitted),
            ("account_carrier", carrier_omitted),
        ):
            if (
                item["query_variant"] != variant
                or item["identical_descriptions_omitted"] is not True
                or item["native_source_index_snapshot_id"]
                != report["native_source_index_snapshot_id"]
                or item["supported_case_count"] != 27
                or item["ood_case_count"] != 3
                or item["synthetic_service_paths"] != 24
                or item["real_model_routing_measured"] is not False
                or item["independent_e2_qualified"] is not False
                or item["calibrated_no_fit"] is not False
                or item["e5_score_diagnostic_unscored"] is None
            ):
                raise ValueError("G5 common-description ablation source drift")
        report["common_source_description_ablation"] = {
            "evidence_tier": "REAL_E5_COMMON_CONTEXT_ABLATION_PUBLIC_DEV_ONLY",
            "source_snapshot_sha256": report["native_source_index_snapshot_id"],
            "description_rule": (
                "omit description iff it is identical for EVERY already "
                "authorized candidate; retain every source route label"
            ),
            "model_id": MODEL_ID,
            "model_revision": MODEL_REVISION,
            "same_original_source_and_gold": True,
            "score_threshold_calibrated": False,
            "heldout_independent": False,
            "agent_execution_measured": False,
            "production_default_changed": False,
            "source_descriptions_remain_unchanged": True,
            "experiment_order": [
                "full_task_only", "full_account_carrier",
                "omitted_task_only", "omitted_account_carrier",
            ],
            "by_language": {
                lang: {
                    "supported_count": 9,
                    "full_task_recall_count": report["per_language"][lang][
                        "e5_recall_count"
                    ],
                    "full_carrier_recall_count": carrier["per_language"][lang][
                        "e5_recall_count"
                    ],
                    "omitted_task_recall_count": task_only_omitted[
                        "per_language"
                    ][lang]["e5_recall_count"],
                    "omitted_carrier_recall_count": carrier_omitted[
                        "per_language"
                    ][lang]["e5_recall_count"],
                }
                for lang in ("en", "ko", "ja")
            },
            "limitations": (
                "Public synthetic task/route labels and account fixture are "
                "already disclosed. Sequential four-arm ranking, no source "
                "owner holdout, no permission calibration, no no-fit "
                "classification, no actual agent/task/final-answer result. "
                "A difference is diagnostic only and cannot authorize "
                "a product schema projection policy."
            ),
        }
        report["account_carrier_ablation"] = {
            "evidence_tier": "REAL_E5_PUBLIC_SYNTHETIC_QUERY_CARRIER_DEV_ONLY",
            "task_only_variant": "task_only",
            "account_carrier_variant": "account_carrier",
            "account_carrier_origin": "original agent fixture fixed account query suffix",
            "source_snapshot_sha256": report["native_source_index_snapshot_id"],
            "real_model_id": MODEL_ID,
            "real_model_revision": MODEL_REVISION,
            "same_synthetic_gold_in_scorer_only": True,
            "different_unsupported_queries": False,
            "sequential_not_interleaved": True,
            "independent_publisher_gold": False,
            "agent_task_success_measured": False,
            "calibrated_no_fit": False,
            "product_default_promoted": False,
            "supported_route_recall_by_language": {
                lang: {
                    "count": report["per_language"][lang]["supported_count"],
                    "task_only_recall_count": report["per_language"][lang]["e5_recall_count"],
                    "account_carrier_recall_count": carrier["per_language"][lang][
                        "e5_recall_count"
                    ],
                    "task_only_top_cosine_p50": report[
                        "e5_score_diagnostic_unscored"
                    ]["by_stratum_language"]["supported"][lang]["top_cosine"]["p50"],
                    "account_carrier_top_cosine_p50": carrier[
                        "e5_score_diagnostic_unscored"
                    ]["by_stratum_language"]["supported"][lang]["top_cosine"]["p50"],
                }
                for lang in ("en", "ko", "ja")
            },
            "limitations": (
                "Same seen synthetic task intent/gold, added fixed account carrier "
                "from original six-agent fixture; not a translation benchmark, "
                "randomized prompt robustness claim, independent test, task pass, "
                "calibrated abstention, or evidence to alter production query text. "
                "Sequential two-block run may include cache or warmup effects."
            ),
        }
        report["evidence_tier"] = (
            "REAL_PINNED_E5_CPU_G5_OVERFLOW_SYNTHETIC_DEV_ONLY"
        )
        report["real_model_routing_measured"] = True
        report["model_runtime"] = metadata
        report["python_version"] = platform.python_version()
        report["source_revision"] = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True,
            text=True, timeout=10, cwd=ROOT,
        ).stdout.strip()
        if len(report["source_revision"]) != 40:
            raise ValueError("missing true source revision")
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
            encoding="utf-8",
        )
    # Emit only aggregated case outcomes and stage durations, never raw case gold.
    print(json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()
