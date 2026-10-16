"""Publisher contract-text ablation over *authorized* real OpenAPI E5 candidates.

No manually assigned operation/domain oracle, no query-derived metadata, and
no downstream tool execution. Extra texts are sourced only from the already
authorized, typed CapabilityCandidate interface, never from registry bypass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import resource
import subprocess
import time
from pathlib import Path
from typing import Any

from schemarouter import (
    DecisionOption,
    DecisionRequest,
    E5CachedEmbedder,
    EmbeddingDecisionBackend,
    PlanRequest,
    choose_sync,
)
from scripts.research_open_meteo_real_openapi_dev import (
    LANGUAGES,
    QUERIES,
    SOURCE_NAMES,
    UNSUPPORTED,
)
from scripts.research_real_open_meteo_e5_cpu_dev import (
    MODEL_ID,
    MODEL_REVISION,
    catalog,
    validate_semantic_ranks,
)

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("original", "parameter_names", "parameter_descriptions")
SOURCE_FILES = (
    "scripts/research_real_open_meteo_field_text_ablation_dev.py",
    "scripts/research_real_open_meteo_e5_cpu_dev.py",
    "benchmarks/open-meteo-openapi-real-source-dev-manifest.json",
)


def render_authorized_option(candidate: Any, variant: str) -> DecisionOption:
    if variant not in VARIANTS:
        raise ValueError("unregistered semantic text ablation")
    # The original verified experiment only sent these two descriptions.
    parts = [
        candidate.tool_description,
        candidate.endpoint_description,
    ]
    if variant != "original":
        fields = []
        for item in candidate.parameters:
            if not item.name.strip():
                continue
            value = item.name
            if variant == "parameter_descriptions" and item.description.strip():
                value += ": " + item.description.strip()
            fields.append(value)
        if fields:
            parts.append("Allowed request parameters: " + "; ".join(fields[:32]))
        if candidate.output_fields:
            parts.append(
                "Declared output fields: " + ", ".join(
                    f.semantic_id or f.name for f in candidate.output_fields[:32]
                )
            )
    return DecisionOption(
        id=candidate.route_id,
        label=candidate.route_id,
        description="\n".join(parts),
    )


def evaluate(
    manifest: Path, source_dir: Path, encoder: Any,
    *, model_revision: str,
) -> dict[str, Any]:
    if model_revision != MODEL_REVISION:
        raise ValueError("unregistered immutable E5 model revision")
    router, principal, source_routes, source_evidence = catalog(
        manifest, source_dir,
    )
    authorized = {
        item for group in source_routes.values() for item in group
    }
    if len(authorized) != len(SOURCE_NAMES):
        raise ValueError("expected nine distinct publisher routes")
    backend = {
        variant: EmbeddingDecisionBackend(
            E5CachedEmbedder(encoder, max_cached_passages=128),
        )
        for variant in VARIANTS
    }
    tasks = [
        (src, lang, question, True)
        for src in SOURCE_NAMES
        for lang, question in zip(LANGUAGES, QUERIES[src], strict=True)
    ] + [
        (kind, lang, question, False)
        for kind, *questions in UNSUPPORTED
        for lang, question in zip(LANGUAGES, questions, strict=True)
    ]
    if len(tasks) != 36:
        raise ValueError("publisher query cohort was altered")
    cases: list[dict[str, Any]] = []
    for source, language, question, positive in tasks:
        candidates = router.retrieve_authorized(
            PlanRequest(query=question), principal=principal, k=9,
        ).candidates
        authorized_ids = [c.route_id for c in candidates]
        validate_semantic_ranks(authorized_ids, authorized)
        target = set(source_routes[source]) if positive else set()
        rankings = {}
        wall_ms = {}
        for variant in VARIANTS:
            options = [
                render_authorized_option(c, variant) for c in candidates
            ]
            if {option.id for option in options} != authorized:
                raise ValueError("field-text conversion expanded authority")
            start = time.perf_counter_ns()
            result = choose_sync(backend[variant], DecisionRequest(
                query=question, options=options,
                max_selections=len(options),
            ))
            elapsed = (time.perf_counter_ns() - start) / 1_000_000
            selected = [v.option_id for v in result.selections]
            validate_semantic_ranks(selected, authorized)
            if result.abstained or not math.isfinite(elapsed) or elapsed <= 0:
                raise ValueError("invalid CPU model selection sample")
            rankings[variant] = selected
            wall_ms[variant] = round(elapsed, 5)
        cases.append({
            "source": source, "language": language,
            "kind": "supported" if positive else "unsupported",
            "lexical_top1": authorized_ids[0],
            "lexical_positive_signal": any(c.score > 0 for c in candidates),
            "ranked": rankings, "duration_ms": wall_ms,
            "correct_top1": {
                v: rankings[v][0] in target if positive else None
                for v in VARIANTS
            },
            "correct_top5": {
                v: bool(target.intersection(rankings[v][:5]))
                   if positive else None
                for v in VARIANTS
            },
            "all_variants_authorized": True,
            "tool_executed": False,
            "no_fit_tested": False,
        })
    counts: dict[str, Any] = {}
    for language in (*LANGUAGES, "all"):
        pos = [
            c for c in cases if c["kind"] == "supported"
            and (language == "all" or c["language"] == language)
        ]
        neg = [
            c for c in cases if c["kind"] == "unsupported"
            and (language == "all" or c["language"] == language)
        ]
        expected_positive = 27 if language == "all" else 9
        expected_negative = 9 if language == "all" else 3
        if len(pos) != expected_positive or len(neg) != expected_negative:
            raise ValueError("unbalanced publisher source/query cohort")
        counts[language] = {
            "supported": len(pos), "unsupported": len(neg),
            "top1": {
                v: sum(c["correct_top1"][v] for c in pos)
                for v in VARIANTS
            },
            "top5": {
                v: sum(c["correct_top5"][v] for c in pos)
                for v in VARIANTS
            },
            "negative_shortlist_is_not_a_no_fit_decision": len(neg),
        }
    source_fingerprints = {
        source: source_evidence[source]["sha256"]
        for source in SOURCE_NAMES
    }
    code_fingerprints = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in SOURCE_FILES
    }
    checkout = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True,
        capture_output=True, text=True, timeout=10, cwd=ROOT,
    ).stdout.strip()
    return {
        "schema_version": 1,
        "study": "real_provider_authorized_e5_contract_text_ablation_dev",
        "repository_commit": checkout,
        "original_provider_sources_sha256": source_fingerprints,
        "code_files_sha256": code_fingerprints,
        "model_id": MODEL_ID,
        "pinned_model_revision": model_revision,
        "variants": list(VARIANTS),
        "expected_cases": 36, "actual_cases": len(cases),
        "strata": counts, "cases": cases,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "actions_run_id": os.getenv("GITHUB_RUN_ID"),
        "scope": {
            "real_publisher_openapi": True,
            "candidate_metadata_only_after_authorization": True,
            "no_gold_or_query_intent_used_for_ranking": True,
            "one_provider_only": True,
            "queries_author_written_seen_dev": True,
            "independently_labeled_queries": False,
            "real_host_principal_authenticated": False,
            "operation_fit_or_no_fit_verified": False,
            "agent_or_external_service_executed": False,
            "product_default_unchanged": True,
            "may_release": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    model = SentenceTransformer(
        MODEL_ID, revision=MODEL_REVISION,
        trust_remote_code=False, device="cpu",
    )
    if model.device.type != "cpu":
        raise ValueError("experimental E5 must run on CPU")
    model.eval()

    def encode(texts: list[str]) -> list[list[float]]:
        vectors = model.encode(
            texts, normalize_embeddings=True, batch_size=16,
            show_progress_bar=False, convert_to_numpy=True,
        ).tolist()
        if any(not math.isfinite(n) for v in vectors for n in v):
            raise ValueError("non-finite local E5 embedding")
        return vectors

    report = evaluate(
        args.manifest, args.source_dir, encode,
        model_revision=MODEL_REVISION,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "study": report["study"], "strata": report["strata"],
        "may_release": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
