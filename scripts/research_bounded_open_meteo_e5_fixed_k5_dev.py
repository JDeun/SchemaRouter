"""Real pinned CPU E5 with opt-in source-scoped strict K5, OLD visible DEV only.

Never a product model promotion, independent multilingual holdout, no-fit
classifier, schema execution, agent completion or protected release gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import resource
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any

from schemarouter import (
    E5CachedEmbedder,
    EmbeddingDecisionBackend,
)
from schemarouter.decisions import DecisionBackend
from scripts.research_bounded_authorized_semantic_diagnostic import (
    propose_bounded_semantic_shortlist,
)
from scripts.research_open_meteo_real_openapi_dev import (
    LANGUAGES,
    QUERIES,
    SOURCE_COMMIT,
    SOURCE_NAMES,
    UNSUPPORTED,
)
from scripts.research_real_open_meteo_e5_cpu_dev import (
    MODEL_ID,
    MODEL_REVISION,
    catalog,
)

ROOT = Path(__file__).resolve().parents[1]
STRICT_K = 5
MAX_REGISTERED_ROUTES = 9
MAX_MODEL_REQUEST_BYTES = 131072
EXPECTED_CASES = 36


def percentile_95(values: list[float]) -> float:
    if not values or any(not math.isfinite(value) for value in values):
        raise ValueError("nonempty finite timing values required")
    return sorted(values)[math.ceil(0.95 * len(values)) - 1]


def run_visible_dev(
    manifest_path: Path,
    source_dir: Path,
    backend: DecisionBackend,
    *,
    checkpoint_revision: str = MODEL_REVISION,
) -> dict[str, Any]:
    """Recheck genuine original OpenAPI byte provenance before any backend call."""
    if checkpoint_revision != MODEL_REVISION:
        raise ValueError("an exact fixed real E5 model revision is required")
    router, principal, target_sources, provenance = catalog(
        manifest_path, source_dir,
    )
    authorized = {
        f"{tool.key}.{ep.name}"
        for tool in router.registry.tools()
        for ep in tool.endpoints
    }
    if len(authorized) != MAX_REGISTERED_ROUTES or set(
        route for ids in target_sources.values() for route in ids
    ) != authorized:
        raise ValueError("source-native route population is no longer nine")

    requests = [
        (name, language, query, True)
        for name in SOURCE_NAMES
        for language, query in zip(LANGUAGES, QUERIES[name], strict=True)
    ] + [
        (name, language, query, False)
        for name, *original in UNSUPPORTED
        for language, query in zip(LANGUAGES, original, strict=True)
    ]
    if (
        len(requests) != EXPECTED_CASES
        or len({(src, lang) for src, lang, _, _ in requests}) != EXPECTED_CASES
        or sum(supported for _, _, _, supported in requests) != 27
    ):
        raise ValueError("original author-visible paired case definitions drifted")

    rows: list[dict[str, Any]] = []
    for group, language, query, supported in requests:
        t0 = time.perf_counter_ns()
        lexical = router.retrieve_authorized(query, principal=principal, k=STRICT_K)
        lexical_ms = (time.perf_counter_ns() - t0) / 1e6
        lexical_ids = [item.route_id for item in lexical.candidates]
        if (
            lexical.requested_k != STRICT_K
            or lexical.total_ranked != MAX_REGISTERED_ROUTES
            or len(lexical_ids) != STRICT_K
            or len(set(lexical_ids)) != STRICT_K
            or not set(lexical_ids) <= authorized
        ):
            raise ValueError("source-scoped lexical K5 population unexpectedly changed")

        t1 = time.perf_counter_ns()
        semantic = propose_bounded_semantic_shortlist(
            router,
            query,
            principal=principal,
            backend=backend,
            k=STRICT_K,
            max_catalog_routes=MAX_REGISTERED_ROUTES,
            max_model_input_bytes=MAX_MODEL_REQUEST_BYTES,
        )
        semantic_ms = (time.perf_counter_ns() - t1) / 1e6
        model_ids = list(semantic.route_ids)
        if (
            semantic.status != "unverified_full_k_model_ranking"
            or semantic.registered_candidate_count != MAX_REGISTERED_ROUTES
            or semantic.selected_k_limit != STRICT_K
            or len(model_ids) != STRICT_K
            or len(set(model_ids)) != STRICT_K
            or not set(model_ids) <= authorized
            or semantic.independent_quality_evidence
            or semantic.calibrated_no_fit
            or semantic.executable_authority
        ):
            raise ValueError("invalid strict-K source-authorized model outcome")

        gold_routes = set(target_sources[group]) if supported else set()
        rows.append({
            "original_group": group,
            "language": language,
            "query": query,
            "kind": "supported" if supported else "unsupported",
            "original_gold_native_route_ids": sorted(gold_routes),
            "lexical_native_k5": lexical_ids,
            "semantic_native_k5": model_ids,
            "lexical_gold_hit": bool(gold_routes & set(lexical_ids)) if supported else None,
            "semantic_gold_hit": bool(gold_routes & set(model_ids)) if supported else None,
            "lexical_unsupported_nonempty_not_no_fit": (
                bool(lexical_ids) if not supported else None
            ),
            "semantic_unsupported_nonempty_not_no_fit": (
                bool(model_ids) if not supported else None
            ),
            "retrieval_lexical_ms": round(lexical_ms, 4),
            "diagnostic_model_path_ms": round(semantic_ms, 4),
            "serialized_model_input_bytes": semantic.model_input_bytes,
            "model_result_status": semantic.status,
            "native_provider_tools_invoked": False,
        })

    metrics: dict[str, Any] = {}
    for lang in LANGUAGES:
        positives = [
            row for row in rows
            if row["language"] == lang and row["kind"] == "supported"
        ]
        negatives = [
            row for row in rows
            if row["language"] == lang and row["kind"] == "unsupported"
        ]
        if len(positives) != 9 or len(negatives) != 3:
            raise ValueError("original multilingual DEV denominators changed")
        metrics[lang] = {
            "supported_cases": len(positives),
            "unsupported_cases": len(negatives),
            "strict_lexical_k5_native_group_hits": sum(
                row["lexical_gold_hit"] for row in positives
            ),
            "strict_model_k5_native_group_hits": sum(
                row["semantic_gold_hit"] for row in positives
            ),
            "lexical_unsupported_nonempty_not_no_fit": sum(
                row["lexical_unsupported_nonempty_not_no_fit"]
                for row in negatives
            ),
            "model_unsupported_nonempty_not_no_fit": sum(
                row["semantic_unsupported_nonempty_not_no_fit"]
                for row in negatives
            ),
        }

    lexical_times = [x["retrieval_lexical_ms"] for x in rows]
    semantic_times = [x["diagnostic_model_path_ms"] for x in rows]
    input_bytes = [x["serialized_model_input_bytes"] for x in rows]
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        timeout=10, check=True, capture_output=True, text=True,
    ).stdout.strip()
    return {
        "schema_version": 1,
        "study": "source_authorized_strict_k5_real_e5_open_meteo_visible_dev",
        "evidence_role": "SAME_AUTHOR_PREVIOUSLY_VISIBLE_EN_KO_JA_DEV_NOT_INDEPENDENT",
        "schemarouter_checkout_sha": sha,
        "original_publisher_commit": SOURCE_COMMIT,
        "source_manifest_sha256": hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest(),
        "original_native_source_files": {
            source: {
                "git_blob_sha1": item["git_blob_sha1"],
                "sha256": item["sha256"],
            }
            for source, item in provenance.items()
        },
        "model_id": MODEL_ID,
        "model_revision": checkpoint_revision,
        "strict_k": STRICT_K,
        "original_native_route_count": MAX_REGISTERED_ROUTES,
        "supported_cases": 27,
        "unsupported_cases": 9,
        "by_language": metrics,
        "aggregate": {
            "lexical_k5_native_group_hits": sum(
                x["strict_lexical_k5_native_group_hits"] for x in metrics.values()
            ),
            "model_k5_native_group_hits": sum(
                x["strict_model_k5_native_group_hits"] for x in metrics.values()
            ),
            "lexical_unsupported_nonempty": sum(
                x["lexical_unsupported_nonempty_not_no_fit"] for x in metrics.values()
            ),
            "model_unsupported_nonempty": sum(
                x["model_unsupported_nonempty_not_no_fit"] for x in metrics.values()
            ),
            "mean_model_input_bytes": statistics.mean(input_bytes),
            "max_model_input_bytes": max(input_bytes),
            "median_lexical_retrieval_ms": statistics.median(lexical_times),
            "p95_lexical_retrieval_ms": percentile_95(lexical_times),
            "median_model_path_ms": statistics.median(semantic_times),
            "p95_model_path_ms": percentile_95(semantic_times),
        },
        "original_visible_dev_rows": rows,
        "peak_resident_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "runtime": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "github_actions_run_id": os.getenv("GITHUB_RUN_ID"),
        },
        "limitations": {
            "real_local_cpu_e5_inference": True,
            "original_provider_native_openapi": True,
            "query_gold_independent": False,
            "case_language_covered_en_ko_ja": True,
            "measured_native_required_input_field_recall": False,
            "calibrated_no_fit": False,
            "measured_agent_task_success": False,
            "measured_live_provider_tool_execution": False,
            "measured_model_input_bytes_not_tokens": True,
            "product_default_changed": False,
            "commercial_release_authorized": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    model = SentenceTransformer(
        MODEL_ID, revision=MODEL_REVISION, device="cpu",
        trust_remote_code=False,
    )
    if model.device.type != "cpu":
        raise RuntimeError("real local E5 must run on CPU")
    model.eval()

    def encode(texts: list[str]) -> list[list[float]]:
        values = model.encode(
            texts, batch_size=16, normalize_embeddings=True,
            convert_to_numpy=True, show_progress_bar=False,
        ).tolist()
        if any(not math.isfinite(x) for row in values for x in row):
            raise ValueError("invalid CPU model embedding")
        return values

    backend = EmbeddingDecisionBackend(
        E5CachedEmbedder(encode, max_cached_passages=128),
    )
    report = run_visible_dev(
        args.manifest, args.source_dir, backend,
        checkpoint_revision=MODEL_REVISION,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "study": report["study"],
        "evidence": report["evidence_role"],
        "metric": report["by_language"],
        "aggregate": report["aggregate"],
        "independent_e2": False,
        "release_authorized": False,
    }))


if __name__ == "__main__":
    main()
