"""Real multilingual E5 CPU reranking over *authorized genuine* OpenAPI DEV schemas.

This uses original Open-Meteo publisher YAML and source-verified current
SchemaRouter.retrieve_authorized; E5 only reranks the resulting approved
nine-route candidate set. It does not change product defaults, classify
no-fit, execute provider tools, or create trusted action intents.
"""
from __future__ import annotations

import argparse
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
    AuthorizationPolicy,
    AuthorizationRule,
    DecisionOption,
    DecisionRequest,
    E5CachedEmbedder,
    EmbeddingDecisionBackend,
    InMemoryRegistry,
    PlanRequest,
    PrincipalContext,
    SchemaRouter,
    choose_sync,
)
from scripts.research_open_meteo_real_openapi_dev import (
    LANGUAGES,
    QUERIES,
    SOURCE_COMMIT,
    SOURCE_NAMES,
    UNSUPPORTED,
    load_contracts,
)

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "intfloat/multilingual-e5-small"
# Fixed HF training/checkpoint source, not the mutable "main" branch.
MODEL_REVISION = "fd1525a9fd15316a2d503bf26ab031a61d056e98"


def catalog(
    manifest_path: Path, data_dir: Path,
) -> tuple[SchemaRouter, PrincipalContext, dict[str, list[str]], dict[str, Any]]:
    tools, failures, evidence = load_contracts(manifest_path, data_dir)
    if failures or len(tools) != len(SOURCE_NAMES):
        raise ValueError(f"real publisher source/parser failures: {failures!r}")
    registry = InMemoryRegistry()
    registry.update_many(tools)
    router = SchemaRouter(
        registry=registry,
        authorization_policy=AuthorizationPolicy(
            rules=(AuthorizationRule(
                name="only-real-open-meteo-viewer",
                effect="allow", operation="open_meteo_*.*",
                roles_any=("viewer",),
            ),),
            default_effect="deny",
        ),
    )
    principal = PrincipalContext(
        subject="synthetic-model-cpu-viewer", roles=("viewer",),
    )
    target = {
        source: list(evidence[source]["route_ids"])
        for source in SOURCE_NAMES
    }
    if set(route for routes in target.values() for route in routes) != {
        f"{tool.key}.{ep.name}" for tool in router.registry.tools()
        for ep in tool.endpoints
    }:
        raise ValueError("registered provider route manifest drift")
    return router, principal, target, evidence


def candidate_options(
    router: SchemaRouter,
    principal: PrincipalContext,
    *,
    query: str,
    expected_route_ids: set[str],
) -> tuple[list[DecisionOption], list[str], list[float]]:
    response = router.retrieve_authorized(
        PlanRequest(query=query), principal=principal, k=9,
    )
    ids = [c.route_id for c in response.candidates]
    if (
        len(ids) != len(expected_route_ids) or set(ids) != expected_route_ids
        or len(ids) != len(set(ids))
    ):
        raise ValueError("authorized whole-route candidate set changed")
    return [
        DecisionOption(
            id=c.route_id, label=c.route_id,
            description="\n".join([
                c.tool_description, c.endpoint_description,
            ]),
        )
        for c in response.candidates
    ], ids, [float(c.score) for c in response.candidates]


def validate_semantic_ranks(
    selected: list[str], authorized: set[str],
) -> None:
    if len(selected) != len(authorized) or len(set(selected)) != len(selected):
        raise ValueError("not a full permutation of authorized provider routes")
    if set(selected) != authorized:
        raise ValueError("semantic router returned unauthorized provider route")


def evaluate_with_encoder(
    manifest_path: Path,
    data_dir: Path,
    encoder: Any,
    *,
    model_source_revision: str,
) -> dict[str, Any]:
    if model_source_revision != MODEL_REVISION:
        raise ValueError("model checkpoint must be fixed, not 'main'")
    router, principal, source_routes, evidence = catalog(manifest_path, data_dir)
    expected = set().union(*(set(ids) for ids in source_routes.values()))
    backend = EmbeddingDecisionBackend(
        E5CachedEmbedder(encoder, max_cached_passages=128),
    )
    rows: list[dict[str, Any]] = []
    queries = [
        (source, language, query, True)
        for source in SOURCE_NAMES
        for language, query in zip(LANGUAGES, QUERIES[source], strict=True)
    ] + [
        (kind, language, query, False)
        for kind, *case_queries in UNSUPPORTED
        for language, query in zip(LANGUAGES, case_queries, strict=True)
    ]
    if len(queries) != 36:
        raise ValueError("unexpected author-DEV real-provider query count")
    for source, language, query, positive in queries:
        options, lexical_ids, scores = candidate_options(
            router, principal, query=query, expected_route_ids=expected,
        )
        start = time.perf_counter_ns()
        outcome = choose_sync(backend, DecisionRequest(
            query=query, options=options, max_selections=len(options),
        ))
        semantic_ms = (time.perf_counter_ns() - start) / 1e6
        selected = [x.option_id for x in outcome.selections]
        validate_semantic_ranks(selected, expected)
        if outcome.abstained or not math.isfinite(semantic_ms):
            raise ValueError("invalid full non-threshold semantic DEV ranking")
        target = set(source_routes[source]) if positive else set()
        rows.append({
            "source": source, "language": language,
            "kind": "supported" if positive else "unsupported",
            "lexical_top1": lexical_ids[0],
            "semantic_top1": selected[0],
            "lexical_top5": lexical_ids[:5],
            "semantic_top5": selected[:5],
            "lexical_all_nonpositive": not any(v > 0 for v in scores),
            "lexical_top1_score": round(scores[0], 6),
            "lexical_correct_top1": lexical_ids[0] in target if positive else None,
            "lexical_correct_top5": bool(target.intersection(lexical_ids[:5]))
                if positive else None,
            "semantic_correct_top1": selected[0] in target if positive else None,
            "semantic_correct_top5": bool(target.intersection(selected[:5]))
                if positive else None,
            "semantic_ms": round(semantic_ms, 4),
            "semantic_returned_full_authorized_catalog": True,
            "no_fit_calibration_performed": False,
            "actual_tool_called": False,
        })
    by_language: dict[str, dict[str, Any]] = {}
    for lang in LANGUAGES:
        positives = [
            item for item in rows
            if item["language"] == lang and item["kind"] == "supported"
        ]
        negatives = [
            item for item in rows
            if item["language"] == lang and item["kind"] == "unsupported"
        ]
        if len(positives) != 9 or len(negatives) != 3:
            raise ValueError("incomplete paired real-provider query matrix")
        by_language[lang] = {
            "supported": 9,
            "unsupported": 3,
            "lexical_top1": sum(x["lexical_correct_top1"] for x in positives),
            "lexical_top5": sum(x["lexical_correct_top5"] for x in positives),
            "semantic_top1": sum(x["semantic_correct_top1"] for x in positives),
            "semantic_top5": sum(x["semantic_correct_top5"] for x in positives),
            "lexical_all_nonpositive": sum(
                x["lexical_all_nonpositive"] for x in positives
            ),
            "unsupported_semantic_full_shortlist": len(negatives),
        }
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        timeout=10, check=True, capture_output=True, text=True,
    ).stdout.strip()
    files = {
        source: {
            "git_blob_sha1": data["git_blob_sha1"],
            "sha256": data["sha256"],
        }
        for source, data in evidence.items()
    }
    return {
        "schema_version": 1,
        "study": "genuine_provider_author_scoped_openapi_e5_dev",
        "source_commit": sha,
        "provider_original_git_commit": SOURCE_COMMIT,
        "provider_source_sha256": files,
        "model_id": MODEL_ID,
        "model_revision": model_source_revision,
        "supported": 27, "unsupported": 9,
        "rows": rows, "by_language": by_language,
        "peak_resident_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "system": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "actions_run_id": os.getenv("GITHUB_RUN_ID"),
        },
        "limitations": {
            "genuine_external_provider_authored_openapi": True,
            "real_cpu_e5_encoder": True,
            "product_default_retrieve_uses_e5": False,
            "query_labels_authored_by_researcher": True,
            "independently_reviewed_queries": False,
            "host_principal_authenticated": False,
            "negative_nonempty_shortlist_not_success": True,
            "model_similarity_calibrated_for_no_fit": False,
            "end_to_end_agent_or_real_api_executed": False,
            "may_release": False,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--source-dir", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    model = SentenceTransformer(
        MODEL_ID, revision=MODEL_REVISION,
        trust_remote_code=False, device="cpu",
    )
    if model.device.type != "cpu":
        raise RuntimeError("E5 experiment must run on CPU only")
    model.eval()

    def encode(texts: list[str]) -> list[list[float]]:
        vectors = model.encode(
            texts, batch_size=16, normalize_embeddings=True,
            convert_to_numpy=True, show_progress_bar=False,
        ).tolist()
        if any(not math.isfinite(x) for row in vectors for x in row):
            raise ValueError("real E5 returned invalid embedding")
        return vectors

    result = evaluate_with_encoder(
        args.manifest, args.source_dir, encode,
        model_source_revision=MODEL_REVISION,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "study": result["study"],
        "model_revision": result["model_revision"],
        "languages": result["by_language"],
        "independent": False, "may_release": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
