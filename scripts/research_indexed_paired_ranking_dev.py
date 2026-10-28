"""Paired direct-index Top-K5 retrieval DEV on a disclosed synthetic corpus.

Uses exactly the already-frozen 24-service EN/KO/JA + OOD task fixture from
research_g5_e5_overflow_cpu_dev. Gold NEVER enters original tool contracts,
the ranker, the query-to-field bridge or model-visible options. No endpoint
is invoked. An actual pinned CPU E5 model is optional and explicitly tagged.
This is not independent publisher gold, agent E2, or a release qualification.
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import re
import statistics
import subprocess
import time
import unicodedata
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
from schemarouter.decisions import DecisionBackend
from schemarouter.native_semantic_index import (
    STRICT_K,
    IndexedNativeFieldCandidate,
    NativeSchemaPostingIndex,
)
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import (
    MODEL_ID,
    MODEL_REVISION,
    real_cpu_backend,
)
from scripts.evaluate_multilingual_embedding_cpu_dev import percentile
from scripts.research_g5_e5_overflow_cpu_dev import (
    ACCOUNT_QUERY_CARRIER,
    OOD,
    QUERIES,
    QUERY_VARIANTS,
    SERVICE_NAMES,
)
from scripts.research_indexed_decision_backend_ranker_e0 import (
    ResearchIndexedFieldDecisionRanker,
)

ROOT = Path(__file__).resolve().parents[1]
ACTOR = PrincipalContext(subject="indexed-paired-public-dev", roles=("reader",))
LANGUAGES = ("en", "ko", "ja")
ARMS = ("first5", "lexical5", "e5_5")
FIELD = CapabilityFieldContract(
    semantic_id="service.status", json_schema={"type": "string"},
)


def build_direct_source() -> tuple[SchemaRouter, NativeSchemaPostingIndex]:
    """Construct disclosed native source contract, without scorer case labels."""
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="service_*.read", roles_any=("reader",),
        ),),
    ))
    for service in SERVICE_NAMES:
        router.add_tool(ToolSpec(
            name=f"service_{service}",
            source_type="crm",
            license="synthetic-reviewed",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                output_fields=[FieldSpec(
                    name="status", semantic_id="service.status",
                    json_schema={"type": "string"},
                )],
            )],
        ))
    index = NativeSchemaPostingIndex.build(router.registry)
    if (
        index.indexed_route_count != len(SERVICE_NAMES)
        or len(index.postings["service.status"]) != len(SERVICE_NAMES)
        or len(SERVICE_NAMES) != 24
    ):
        raise ValueError("direct-index synthetic source contract changed")
    return router, index


def first_five(
    _query: str, candidates: tuple[IndexedNativeFieldCandidate, ...], k: int,
) -> tuple[int, ...]:
    if k != STRICT_K or len(candidates) <= k:
        raise ValueError("invalid controlled first-five cohort")
    return tuple(range(k))


def _tokens(value: str) -> frozenset[str]:
    """Deliberately simple, language-independent baseline, not a translator."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return frozenset(word for word in re.split(r"[_\W]+", normalized) if word)


def lexical_five(
    query: str, candidates: tuple[IndexedNativeFieldCandidate, ...], k: int,
) -> tuple[int, ...]:
    """No gold/features outside already authorized route labels and field names."""
    if k != STRICT_K or not k < len(candidates) <= 32:
        raise ValueError("invalid controlled lexical cohort")
    terms = _tokens(query)
    scored = sorted(
        range(len(candidates)),
        key=lambda i: (
            -len(terms & _tokens(candidates[i].route_id)),
            i,  # stable original source order; no gold-aware fill
        ),
    )
    return tuple(scored[:k])


def _cases(query_variant: str) -> tuple[tuple[str, str, str | None], ...]:
    if query_variant not in QUERY_VARIANTS:
        raise ValueError("only original frozen synthetic query variants allowed")
    suffix = ACCOUNT_QUERY_CARRIER if query_variant == "account_carrier" else ""
    return (
        *(
            (lang, query + suffix, f"service_{service}.read")
            for service, en, ko, ja in QUERIES
            for lang, query in zip(LANGUAGES, (en, ko, ja), strict=True)
        ),
        *((lang, query + suffix, None) for lang, query in OOD),
    )


def _latency(values: list[float]) -> dict[str, float]:
    if not values or any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("invalid paired DEV latency measurements")
    return {
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
        "mean": statistics.fmean(values),
    }


def _rank_score(route_ids: tuple[str, ...], gold: str) -> dict[str, float]:
    try:
        rank = route_ids.index(gold) + 1
    except ValueError:
        rank = None
    return {
        "recall_at_5": float(rank is not None),
        "mrr_at_5": 1 / rank if rank is not None else 0.0,
        "ndcg_at_5": 1 / math.log2(rank + 1) if rank is not None else 0.0,
    }


def run_paired_dev(
    backend: DecisionBackend | None = None, *,
    query_variant: str = "task_only",
    omit_identical_descriptions: bool = True,
) -> dict[str, Any]:
    """Score the same retrieval cohort, with gold visible to scorer only."""
    if type(omit_identical_descriptions) is not bool:
        raise ValueError("research description ablation requires boolean")
    router, index = build_direct_source()
    model = (
        ResearchIndexedFieldDecisionRanker(
            backend, omit_identical_descriptions=omit_identical_descriptions,
        ) if backend is not None else None
    )
    arms = ARMS if model is not None else ARMS[:2]
    rows: dict[str, dict[str, list[dict[str, float]]]] = {
        arm: {lang: [] for lang in LANGUAGES} for arm in arms
    }
    ood: dict[str, dict[str, int]] = {
        arm: {lang: 0 for lang in LANGUAGES} for arm in arms
    }
    timings: dict[str, list[float]] = {
        arm: [] for arm in ("unranked", *arms)
    }
    rescues = regressions = 0
    cases = _cases(query_variant)
    for lang, query, gold in cases:
        # One query-specific *host field declaration*, never an inferred
        # task gold route. All 24 routes meet the very same field contract.
        group = NativeDeclaredFieldGroup(
            aliases=(query,), required_fields=(FIELD,),
            source_type="crm", license="synthetic-reviewed",
        )
        start = time.perf_counter_ns()
        baseline = index.lookup(
            router, query, group=group, principal=ACTOR, input_free_only=True,
        )
        timings["unranked"].append((time.perf_counter_ns() - start) / 1e6)
        if (
            baseline.status != "over_k_unranked"
            or baseline.qualified_count != len(SERVICE_NAMES)
            or baseline.candidates
        ):
            raise ValueError("default indexed Top-K boundary changed")
        selected: dict[str, tuple[str, ...]] = {}
        for arm, ranker in (
            ("first5", first_five),
            ("lexical5", lexical_five),
            ("e5_5", model),
        ):
            if arm not in arms:
                continue
            start = time.perf_counter_ns()
            decision = index.lookup(
                router, query, group=group, principal=ACTOR,
                input_free_only=True, _research_ranker=ranker,
            )
            timings[arm].append((time.perf_counter_ns() - start) / 1e6)
            if (
                decision.status != "ranked_unverified"
                or not decision.experimental_ranked
                or decision.qualified_count != len(SERVICE_NAMES)
                or len(decision.candidates) != STRICT_K
            ):
                raise ValueError("invalid source-authorized research ranking")
            ids = tuple(item.route_id for item in decision.candidates)
            if len(set(ids)) != STRICT_K or not set(ids) <= {
                f"service_{name}.read" for name in SERVICE_NAMES
            }:
                raise ValueError("indexed ranking escaped source scope")
            selected[arm] = ids
            if gold is None:
                # Nonempty selection on OOD is NOT a calibrated false positive.
                ood[arm][lang] += int(bool(ids))
            else:
                rows[arm][lang].append(_rank_score(ids, gold))
        if gold is not None and model is not None:
            before = gold in selected["lexical5"]
            after = gold in selected["e5_5"]
            rescues += int(not before and after)
            regressions += int(before and not after)
        index._assert_source(router)
    if len(cases) != 30 or len(QUERIES) != 9 or len(OOD) != 3:
        raise ValueError("synthetic scorer cohort changed")
    summary: dict[str, Any] = {}
    for arm in arms:
        summary[arm] = {
            lang: {
                "supported": len(rows[arm][lang]),
                **{
                    key: statistics.fmean(row[key] for row in rows[arm][lang])
                    for key in ("recall_at_5", "mrr_at_5", "ndcg_at_5")
                },
                "ood_nonempty_shortlist_count": ood[arm][lang],
            }
            for lang in LANGUAGES
        }
    return {
        "schema_version": 1,
        "evidence_tier": (
            "E0_INJECTED_INDEXED_MODEL_SYNTHETIC_DEV_NOT_ATTESTED"
            if model is not None else "E0_NO_MODEL_INDEXED_SYNTHETIC_DEV_ONLY"
        ),
        "original_fixture_origin": "scripts/research_g5_e5_overflow_cpu_dev.py",
        "model_used": model is not None,
        "real_model_runtime_attested": False,
        "source_snapshot_id": index.snapshot_id,
        "source_type": "crm",
        "source_license": "synthetic-reviewed",
        "route_count": len(SERVICE_NAMES),
        "case_count": len(cases),
        "supported_case_count": 27,
        "ood_case_count": 3,
        "query_variant": query_variant,
        "descriptions_omitted_when_identical": omit_identical_descriptions,
        "k": STRICT_K,
        "arms": arms,
        "per_language": summary,
        "paired_lexical5_to_backend": (
            {"rescued": rescues, "regressed": regressions}
            if model is not None else None
        ),
        "latency_ms": {arm: _latency(values) for arm, values in timings.items()},
        "independent_publisher_gold": False,
        "agent_task_success_measured": False,
        "calibrated_no_fit": False,
        "product_default_changed": False,
        "limitations": (
            "Public developer-authored 24-route synthetic corpus; 27 supported "
            "and 3 OOD EN/KO/JA queries. Gold is used only after selection. "
            "English-only tool names and trivial shared status schema; no "
            "publisher-independent cases, native provider execution, agent E2, "
            "calibrated no-fit, or statistically established model advantage."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("validate", "real-e5-cpu"), required=True)
    parser.add_argument("--query-variant", choices=QUERY_VARIANTS, default="task_only")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.mode == "real-e5-cpu" and args.out is None:
        raise ValueError("actual pinned CPU model runs require --out")
    backend, runtime = (
        real_cpu_backend() if args.mode == "real-e5-cpu" else (None, None)
    )
    report = run_paired_dev(backend, query_variant=args.query_variant)
    if runtime is not None:
        if (
            runtime.get("model_id") != MODEL_ID
            or runtime.get("model_revision") != MODEL_REVISION
            or runtime.get("device") != "cpu"
            or report["model_used"] is not True
        ):
            raise ValueError("pinned real-model runtime attestation failed")
        report["model_runtime"] = runtime
        report["evidence_tier"] = "REAL_PINNED_E5_CPU_INDEXED_PUBLIC_SYNTHETIC_DEV_ONLY"
        report["real_model_runtime_attested"] = True
        report["python_version"] = platform.python_version()
        report["source_revision"] = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True,
            text=True, timeout=10, cwd=ROOT,
        ).stdout.strip()
        if len(report["source_revision"]) != 40:
            raise ValueError("missing pinned source revision")
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, allow_nan=False, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, allow_nan=False, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
