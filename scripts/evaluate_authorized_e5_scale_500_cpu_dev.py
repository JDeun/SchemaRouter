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
        "language": strata,
    }


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
        for case in corpus["cases"][:case_limit]:
            query = case["query"]
            view = capture_authorized_agent_tool_surface(
                router, query, principal=PRINCIPAL,
            )
            visible = view.visible_route_ids
            if len(visible) != size:
                raise ValueError("incomplete authorized native catalog exposure")

            begin = time.perf_counter_ns()
            original_result = router.retrieve_authorized(
                query, principal=PRINCIPAL, k=5,
            )
            lexical = [item.route_id for item in original_result.candidates]
            lexical_ms = (time.perf_counter_ns() - begin) / 1e6

            e5_selector = AuthorizedFixed5DecisionSelector(
                view, backend, max_model_input_bytes=STRESS_MODEL_INPUT_BUDGET_BYTES,
            )
            begin = time.perf_counter_ns()
            semantic = e5_selector(query, visible)
            semantic_ms = (time.perf_counter_ns() - begin) / 1e6

            hybrid_selector = AuthorizedHybridFixed5Selector(
                view, backend, max_model_input_bytes=STRESS_MODEL_INPUT_BUDGET_BYTES,
            )
            begin = time.perf_counter_ns()
            hybrid = hybrid_selector(query, visible)
            hybrid_ms = (time.perf_counter_ns() - begin) / 1e6

            choices = {
                ARMS[0]: (lexical, lexical_ms),
                ARMS[1]: (semantic, semantic_ms),
                ARMS[2]: (hybrid, hybrid_ms),
            }
            for arm, (selected, latency) in choices.items():
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
                    "kind": case["kind"], "language": case["language"],
                    "hit_at_1": selected[0] == expected if supported else None,
                    "hit_at_5": expected in selected if supported else None,
                    "nonempty_unsupported": not supported and bool(selected),
                    "selection_latency_ms": latency,
                })
            view.assert_source_unchanged()
        results[str(size)] = {
            "catalog_sha256": catalog_sha,
            "registered_native_routes": size,
            "cases_scored": len(arm_rows[ARMS[0]]),
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
            "Source capture occurs outside reported selection latency, and "
            "embedding passage cache is shared across query order."
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
