"""Scale the *same authorized native* real-E5 fixed-K5 retrieval DEV to 500.

No agent/provider calls; expanded distractors are templated research fixtures,
not 500 external native tools or independent end-to-end E2 evidence.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from schemarouter import EndpointSpec, ToolSpec
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import (
    ARMS,
    CORPUS,
    LANGUAGES,
    PRINCIPAL,
    build_source_router,
    real_cpu_backend,
)
from scripts.evaluate_multilingual_embedding_cpu_dev import (
    load_development_corpus,
    percentile,
)
from scripts.evaluate_multilingual_embedding_scale_dev import (
    SIZES,
    catalog_hash,
    check_corpus,
    expand_catalog,
)
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_authorized_fixed5_decision_bridge import (
    AuthorizedFixed5DecisionSelector,
)
from scripts.research_authorized_hybrid_fixed5 import AuthorizedHybridFixed5Selector

ROOT = Path(__file__).resolve().parents[1]
STRESS_MODEL_INPUT_BUDGET_BYTES = 262144  # Explicit 256 KiB research-only cap.
PROFILED_STAGE_FIELDS = (
    "source_capture_latency_ms",
    "backend_decision_latency_ms",
    "nonbackend_selection_latency_ms",
    "source_capture_plus_selection_latency_ms",
)
E5_PROFILE_STAGE_FIELDS = (
    "selector_constructor_ms",
    "bridge_prevalidation_ms",
    "source_validation_ms",
    "request_materialization_ms",
    "choose_sync_ms",
    "choose_sync_nonbackend_ms",
    "post_decision_validation_ms",
    "bridge_postvalidation_ms",
)


class _ProfiledBackend:
    """Count model decision time without touching queries, source or gold.

    The existing CPU embedding backend is synchronous. This wrapper does not
    alter decisions, cache model vectors or persist any request contents.
    """

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate
        self.calls = 0
        self.elapsed_ns = 0

    def decide(self, request: Any) -> Any:
        began = time.perf_counter_ns()
        try:
            return self._delegate.decide(request)
        finally:
            self.elapsed_ns += time.perf_counter_ns() - began
            self.calls += 1



def native_route_id(distractor_id: str) -> str:
    """Stable one-dot native tool/operation mapping for templated distractors."""
    if (
        type(distractor_id) is not str
        or len(distractor_id.split(".")) != 3
        or distractor_id.split(".")[0] != "dev_stress"
        or any(not component for component in distractor_id.split(".")[1:])
    ):
        raise ValueError("invalid generated research distractor ID")
    _, domain, operation = distractor_id.split(".")
    return f"dev_stress_{domain}.{operation}"


def build_scaled_authorized_router(corpus: dict[str, Any], size: int):
    """Derive actual authorized ToolSpec/EndpointSpec from fixed DEV inventory."""
    check_corpus(corpus)
    catalog = expand_catalog(corpus["catalog"], size)
    if catalog[:13] != corpus["catalog"]:
        raise ValueError("baseline route identity changed")
    router = build_source_router(corpus)
    grouped: dict[str, list[EndpointSpec]] = defaultdict(list)
    expected = {item["id"] for item in corpus["catalog"]}
    for item in catalog[13:]:
        if type(item) is not dict or set(item) != {"id", "description"}:
            raise ValueError("invalid stress catalog item")
        route = native_route_id(item["id"])
        if route in expected:
            raise ValueError("native distractor collides with source")
        expected.add(route)
        tool, op = route.rsplit(".", 1)
        grouped[tool].append(EndpointSpec(
            name=op, description=item["description"], read_only=True,
        ))
    for tool, endpoints in sorted(grouped.items()):
        router.add_tool(ToolSpec(
            name=tool,
            description="Read-only synthetic stress operation catalog",
            endpoints=endpoints,
        ))
    actual = {
        f"{tool.name}.{endpoint.name}"
        for tool in router.registry.tools()
        for endpoint in tool.endpoints
    }
    if actual != expected or len(actual) != size:
        raise ValueError("authorized native source catalog count or identity drift")
    return router, catalog_hash(catalog)


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 84:
        raise ValueError("all 84 paired tasks must be scored")
    positives = [r for r in rows if r["kind"] == "supported"]
    negatives = [r for r in rows if r["kind"] == "unsupported"]
    if len(positives) != 48 or len(negatives) != 36:
        raise ValueError("supported and unsupported denominators drift")
    strata: dict[str, Any] = {}
    for lang in LANGUAGES:
        yes = [r for r in positives if r["language"] == lang]
        no = [r for r in negatives if r["language"] == lang]
        if len(yes) != 8 or len(no) != 6:
            raise ValueError("per-language task counts drifted")
        strata[lang] = {
            "supported": len(yes),
            "unsupported": len(no),
            "supported_recall_at_1": sum(r["hit_at_1"] for r in yes) / len(yes),
            "supported_recall_at_5": sum(r["hit_at_5"] for r in yes) / len(yes),
            "unsupported_nonempty_shortlist_rate": sum(
                r["nonempty_unsupported"] for r in no
            ) / len(no),
        }
    latency = [r["selection_latency_ms"] for r in rows]
    stages = {}
    for name in PROFILED_STAGE_FIELDS:
        observations = [r[name] for r in rows]
        if any(
            type(value) is not float or not math.isfinite(value) or value < 0
            for value in observations
        ):
            raise ValueError("invalid measured CPU latency stage")
        stages[name] = {
            "p50": percentile(observations, 50),
            "p95": percentile(observations, 95),
            "p99": percentile(observations, 99),
        }
    return {
        "supported": len(positives),
        "unsupported": len(negatives),
        "supported_recall_at_1": statistics.fmean(r["hit_at_1"] for r in positives),
        "supported_recall_at_5": statistics.fmean(r["hit_at_5"] for r in positives),
        "unsupported_nonempty_shortlist_rate": statistics.fmean(
            r["nonempty_unsupported"] for r in negatives
        ),
        "selection_latency_ms_p50": percentile(latency, 50),
        "selection_latency_ms_p95": percentile(latency, 95),
        "stage_latency_ms": stages,
        "language": strata,
    }



def aggregate_e5_substages(rows: list[dict[str, float]]) -> dict[str, Any]:
    """Aggregate all original DEV requests without emitting per-case values."""
    if len(rows) != 84:
        raise ValueError("complete E5 substage profiling requires 84 original cases")
    for row in rows:
        if type(row) is not dict or set(row) != set(E5_PROFILE_STAGE_FIELDS):
            raise ValueError("untrusted E5 substage keys")
        if any(
            type(value) is not float or not math.isfinite(value) or value < 0
            for value in row.values()
        ):
            raise ValueError("invalid E5 substage timing")
        if row["choose_sync_nonbackend_ms"] > row["choose_sync_ms"]:
            raise ValueError("E5 nonbackend choice timing exceeds choice call")
    return {
        stage: {
            "p50": percentile([row[stage] for row in rows], 50),
            "p95": percentile([row[stage] for row in rows], 95),
            "p99": percentile([row[stage] for row in rows], 99),
        }
        for stage in E5_PROFILE_STAGE_FIELDS
    }


def paired_retrieval_error_attribution(
    arm_rows: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Explain fixed-K model gains *and losses* on exact same DEV requests.

    Row alignment is source-authenticated by run_scaled_retrieval_dev and
    validated again here. Only aggregate counts leave the evaluation
    process: no query, source gold, tool IDs or per-case model predictions.
    """
    if set(arm_rows) != set(ARMS):
        raise ValueError("paired arms must be the preregistered three conditions")
    sizes = {len(arm_rows[arm]) for arm in ARMS}
    if sizes != {84}:
        raise ValueError("paired attribution requires all 84 original DEV cases")

    primary = arm_rows[ARMS[0]]
    for arm in ARMS:
        for index, row in enumerate(arm_rows[arm]):
            if (
                type(row.get("case_ordinal")) is not int
                or row["case_ordinal"] != index
                or type(row.get("case_id")) is not str
                or not row["case_id"]
                or row.get("kind") not in {"supported", "unsupported"}
                or row.get("language") not in LANGUAGES
                or (row["case_id"], row["kind"], row["language"]) != (
                    primary[index]["case_id"], primary[index]["kind"],
                    primary[index]["language"],
                )
                or type(row.get("nonempty_unsupported")) is not bool
            ):
                raise ValueError("paired task identity or type drift")
            for field in ("hit_at_1", "hit_at_5"):
                expected_type = bool if row["kind"] == "supported" else type(None)
                if type(row.get(field)) is not expected_type:
                    raise ValueError("invalid paired retrieval outcome or support label")

    outcome: dict[str, Any] = {}
    for other in ARMS[1:]:
        sections: dict[str, Any] = {}
        for lang in ("all", *LANGUAGES):
            indexes = [
                i for i, row in enumerate(primary)
                if lang == "all" or row["language"] == lang
            ]
            supported = [
                i for i in indexes if primary[i]["kind"] == "supported"
            ]
            unsupported = [
                i for i in indexes if primary[i]["kind"] == "unsupported"
            ]
            if len(supported) != (48 if lang == "all" else 8):
                raise ValueError("paired supported denominators drift")
            if len(unsupported) != (36 if lang == "all" else 6):
                raise ValueError("paired unsupported denominators drift")
            delta: dict[str, Any] = {
                "supported": len(supported),
                "unsupported": len(unsupported),
            }
            for k in (1, 5):
                key = f"hit_at_{k}"
                before_hits = sum(primary[i][key] for i in supported)
                after_hits = sum(arm_rows[other][i][key] for i in supported)
                rescued = sum(
                    not primary[i][key] and arm_rows[other][i][key]
                    for i in supported
                )
                lost = sum(
                    primary[i][key] and not arm_rows[other][i][key]
                    for i in supported
                )
                both = sum(
                    primary[i][key] and arm_rows[other][i][key]
                    for i in supported
                )
                neither = sum(
                    not primary[i][key] and not arm_rows[other][i][key]
                    for i in supported
                )
                if (
                    before_hits + rescued - lost != after_hits
                    or both + rescued + lost + neither != len(supported)
                ):
                    raise ValueError("paired attribution accounting mismatch")
                delta[f"at_{k}"] = {
                    "lexical_hits": before_hits,
                    "candidate_hits": after_hits,
                    "rescued": rescued,
                    "regressed": lost,
                    "both_hit": both,
                    "neither_hit": neither,
                }
            delta["unsupported_nonempty_both"] = sum(
                primary[i]["nonempty_unsupported"]
                and arm_rows[other][i]["nonempty_unsupported"]
                for i in unsupported
            )
            delta["unsupported_newly_nonempty"] = sum(
                not primary[i]["nonempty_unsupported"]
                and arm_rows[other][i]["nonempty_unsupported"]
                for i in unsupported
            )
            delta["unsupported_newly_empty"] = sum(
                primary[i]["nonempty_unsupported"]
                and not arm_rows[other][i]["nonempty_unsupported"]
                for i in unsupported
            )
            sections[lang] = delta
        outcome[f"{ARMS[0]}_vs_{other}"] = sections
    return outcome


def run_scaled_retrieval_dev(
    corpus: dict[str, Any],
    digest: str,
    backend: Any,
    *,
    sizes: tuple[int, ...] = SIZES,
    case_limit: int | None = None,
) -> dict[str, Any]:
    """Source-authenticated comparison; backend identity is NOT verified here."""
    original, authentic_digest = load_development_corpus(CORPUS)
    if (
        corpus != original or digest != authentic_digest
        or type(sizes) is not tuple or not sizes
        or any(type(size) is not int or size not in SIZES for size in sizes)
        or len(set(sizes)) != len(sizes)
    ):
        raise ValueError("unverified or altered DEV corpus or scale")
    if case_limit is not None and (
        type(case_limit) is not int or not 1 <= case_limit <= 84
    ):
        raise ValueError("invalid non-scored smoke case bound")
    check_corpus(corpus)
    results: dict[str, Any] = {}
    for size in sizes:
        router, catalog_sha = build_scaled_authorized_router(corpus, size)
        arm_rows: dict[str, list[dict[str, Any]]] = {
            arm: [] for arm in ARMS
        }
        e5_stage_rows: list[dict[str, float]] = []
        for case_ordinal, case in enumerate(corpus["cases"][:case_limit]):
            query = case["query"]
            capture_began = time.perf_counter_ns()
            view = capture_authorized_agent_tool_surface(
                router, query, principal=PRINCIPAL,
            )
            capture_ms = (time.perf_counter_ns() - capture_began) / 1e6
            visible = view.visible_route_ids
            if len(visible) != size:
                raise ValueError("incomplete authorized native catalog exposure")

            begin = time.perf_counter_ns()
            original_result = router.retrieve_authorized(
                query, principal=PRINCIPAL, k=5,
            )
            lexical = [item.route_id for item in original_result.candidates]
            lexical_ms = (time.perf_counter_ns() - begin) / 1e6

            traced_backend = _ProfiledBackend(backend)
            e5_parts: dict[str, float] = {}
            begin_init = time.perf_counter_ns()
            e5_selector = AuthorizedFixed5DecisionSelector(
                view, traced_backend,
                max_model_input_bytes=STRESS_MODEL_INPUT_BUDGET_BYTES,
                stage_timings_ms=e5_parts,
            )
            init_ms = (time.perf_counter_ns() - begin_init) / 1e6
            begin = time.perf_counter_ns()
            semantic = e5_selector(query, visible)
            semantic_ms = (time.perf_counter_ns() - begin) / 1e6
            if traced_backend.calls != 1:
                raise ValueError("E5 selector used unexpected inference calls")
            semantic_backend_ms = traced_backend.elapsed_ns / 1e6
            # The synchronous choice includes model inference and host-owned
            # response validation; never mislabel all of it model-only.
            if e5_parts.get("choose_sync_ms", -1.0) < semantic_backend_ms:
                raise ValueError("E5 choice time shorter than measured backend")
            e5_parts["selector_constructor_ms"] = init_ms
            e5_parts["choose_sync_nonbackend_ms"] = (
                e5_parts["choose_sync_ms"] - semantic_backend_ms
            )
            if set(e5_parts) != set(E5_PROFILE_STAGE_FIELDS):
                raise ValueError("missing E5 CPU substage instrument")
            e5_stage_rows.append(dict(e5_parts))

            hybrid_selector = AuthorizedHybridFixed5Selector(
                view, traced_backend,
                max_model_input_bytes=STRESS_MODEL_INPUT_BUDGET_BYTES,
            )
            begin = time.perf_counter_ns()
            hybrid = hybrid_selector(query, visible)
            hybrid_ms = (time.perf_counter_ns() - begin) / 1e6
            if traced_backend.calls != 2:
                raise ValueError("hybrid used unexpected inference calls")
            hybrid_backend_ms = (
                traced_backend.elapsed_ns / 1e6 - semantic_backend_ms
            )

            choices = {
                ARMS[0]: (lexical, lexical_ms, 0.0),
                ARMS[1]: (semantic, semantic_ms, semantic_backend_ms),
                ARMS[2]: (hybrid, hybrid_ms, hybrid_backend_ms),
            }
            for arm, (selected, latency, backend_ms) in choices.items():
                if (
                    len(selected) != 5 or len(set(selected)) != 5
                    or not set(selected).issubset(visible)
                    or type(latency) is not float
                    or not math.isfinite(latency) or latency < 0
                ):
                    raise ValueError("untrusted or bounded K5 selection")
                supported = case["kind"] == "supported"
                expected = case["expected_route"]
                if supported and expected not in visible:
                    raise ValueError("supported gold unavailable from real source")
                if not supported and expected is not None:
                    raise ValueError("unsupported gold corrupted")
                arm_rows[arm].append({
                    "case_ordinal": case_ordinal,
                    "case_id": case["id"],
                    "kind": case["kind"], "language": case["language"],
                    "hit_at_1": selected[0] == expected if supported else None,
                    "hit_at_5": expected in selected if supported else None,
                    "nonempty_unsupported": not supported and bool(selected),
                    "selection_latency_ms": latency,
                    "source_capture_latency_ms": capture_ms,
                    "backend_decision_latency_ms": backend_ms,
                    "nonbackend_selection_latency_ms": max(
                        0.0, latency - backend_ms
                    ),
                    "source_capture_plus_selection_latency_ms": (
                        capture_ms + latency
                    ),
                })
            view.assert_source_unchanged()
        results[str(size)] = {
            "catalog_sha256": catalog_sha,
            "registered_native_routes": size,
            "cases_scored": len(arm_rows[ARMS[0]]),
            "e5_substage_profile_ms": (
                aggregate_e5_substages(e5_stage_rows)
                if case_limit is None else {"smoke_only_not_scored": True}
            ),
            "paired_attribution": (
                paired_retrieval_error_attribution(arm_rows)
                if case_limit is None else {
                    "smoke_only_not_scored": True,
                }
            ),
            "arms": {
                arm: _summary(rows)
                if case_limit is None else {
                    "smoke_only_not_scored": True,
                    "cases_exercised": len(rows),
                }
                for arm, rows in arm_rows.items()
            },
        }
    return {
        "schema_version": 1,
        "research_issue": 1477,
        "surface": "previously_disclosed_templated_synthetic_dev",
        "evidence_tier": "UNATTESTED_BACKEND_RETRIEVAL_DEV_ONLY",
        "real_model_routing_measured": False,
        "independent_e2_qualified": False,
        "agent_task_success_measured": False,
        "calibrated_no_fit": False,
        "publication_gate_passed": False,
        "product_default_promoted": False,
        "fixed_k": 5,
        "source_corpus_sha256": digest,
        "candidate_arm_ids": list(ARMS),
        "catalog_sizes": list(sizes),
        "full_84_case_evaluation": case_limit is None,
        "results": results,
        "limitations": (
            "Templated distractors are not true native external services. "
            "No agent execution, E2 generalization or calibrated no-fit. "
            "Source capture is measured separately from selection; "
            "snapshot+selection is a summed shared-snapshot diagnostic, not "
            "a standalone hosted agent latency. Nonbackend overhead includes "
            "authorized retrieval, native schema formatting and validation. "
            "Embedding passage cache is shared across query order. "
            "E5 selector constructor is timed separately from selection; "
            "choose_sync includes host validation, not just backend inference; "
            "profiling stages have independent percentiles and overhead."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("validate", "real-e5-cpu"))
    parser.add_argument("--out", type=Path,
                        default=Path("artifacts/authorized-e5-scale-dev/report.json"))
    args = parser.parse_args()
    corpus, digest = load_development_corpus(CORPUS)
    check_corpus(corpus)
    for size in SIZES:
        build_scaled_authorized_router(corpus, size)
    if args.mode == "validate":
        print(json.dumps({"sizes": SIZES, "cases": 84,
                          "surface": "DEV_ONLY", "corpus_sha256": digest}))
        return

    backend, runtime = real_cpu_backend()
    report = run_scaled_retrieval_dev(corpus, digest, backend)
    if not report["full_84_case_evaluation"]:
        raise RuntimeError("cannot publish partial smoke as full research score")
    report["evidence_tier"] = "REAL_E5_CPU_RETRIEVAL_DEV_ONLY"
    report["real_model_routing_measured"] = True
    source_revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
        text=True, check=True, timeout=10,
    ).stdout.strip()
    if len(source_revision) != 40 or any(c not in "0123456789abcdef" for c in source_revision):
        raise ValueError("unable to attest source revision")
    report["source_revision"] = source_revision
    report["model_runtime"] = runtime
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "source_revision": source_revision,
        "source_corpus_sha256": digest,
        "evidence_tier": report["evidence_tier"],
        "model_runtime": runtime,
        "results": report["results"],
    }, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
