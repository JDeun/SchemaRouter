"""Synthetic catalog-size stress test for real multilingual CPU embedders.

Exploratory DEV-only 13/100/250/500 expansion with templated English read-only
distractors. This is NOT 500 real tools, independent validation, or execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from schemarouter import (  # noqa: E402
    DecisionOption,
    DecisionRequest,
    E5CachedEmbedder,
    EmbeddingDecisionBackend,
    choose_sync,
)
from scripts.evaluate_multilingual_embedding_cpu_dev import (  # noqa: E402
    MODEL_CHOICES,
    aggregate,
    load_development_corpus,
)

SIZES = (13, 100, 250, 500)
SEED = "schemarouter-multilingual-20261015-stress-v1"
DOMAINS = (
    "materials", "papers", "weather", "inventory", "flights", "finance",
    "calendar", "maps", "shipping", "medicine", "clinical trials",
    "patents", "molecules", "minerals", "microscopy", "software packages",
    "energy", "transport", "agriculture", "satellites", "meteorology",
    "railways", "airports", "hotels", "museums", "forestry", "oceans",
    "astronomy", "fisheries", "audio recordings", "robotics",
    "network devices", "manufacturing", "geospatial datasets",
)
OPERATIONS = (
    ("search", "Search published records matching specified attributes"),
    ("lookup", "Retrieve one existing record by its known identifier"),
    ("list", "List registered entries for a location or category"),
    ("status", "Read the most recently reported status"),
    ("history", "Inspect historical records across a date range"),
    ("summary", "Read a summary of available records"),
    ("compare", "Compare previously published values for multiple records"),
    ("metadata", "Retrieve metadata such as units and identifiers"),
    ("quality", "Inspect past quality assessment reports"),
    ("audit", "Read a stored audit trail of changes"),
    ("availability", "Find recorded availability and time windows"),
    ("forecast", "Read an existing forecast for a region or period"),
    ("measurements", "Read reported measurement values"),
    ("citations", "Retrieve bibliographic references for a record"),
    ("classification", "Read the assigned category or class for a record"),
    ("constraints", "Inspect documented restrictions and requirements"),
    ("routes", "Read existing route plans between specified endpoints"),
    ("analytics", "Read stored aggregates and analysis results"),
)


def expand_catalog(base: list[dict[str, str]], size: int) -> list[dict[str, str]]:
    """Return nested deterministic catalogs; never remove original targets."""
    if type(size) is not int or size not in SIZES:
        raise ValueError("size must be 13, 100, 250 or 500")
    if len(base) != 13:
        raise ValueError("the 13-route baseline catalog must remain fixed")
    base_ids = [item["id"] for item in base]
    if len(set(base_ids)) != len(base_ids):
        raise ValueError("duplicate baseline routes")
    extra = []
    for domain in DOMAINS:
        key = domain.replace(" ", "_")
        for operation, description in OPERATIONS:
            route = f"dev_stress.{key}.{operation}"
            if route in base_ids:
                raise ValueError("generated route collides with baseline")
            extra.append({
                "id": route,
                "description": (
                    f"Read-only {domain} records. {description} about {domain}. "
                    "Existing indexed information only; does not mutate state."
                ),
            })
    extra.sort(key=lambda x: hashlib.sha256(
        f"{SEED}/{x['id']}".encode("utf-8"),
    ).hexdigest())
    if len(extra) < max(SIZES) - len(base):
        raise ValueError("not enough templated stress distractors")
    return [*base, *extra[: size - len(base)]]


def catalog_hash(catalog: list[dict[str, str]]) -> str:
    serialized = json.dumps(
        catalog, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def check_corpus(corpus: dict[str, Any]) -> None:
    if corpus.get("surface") != "prospective_development_only":
        raise ValueError("development-only corpus required")
    base = corpus["catalog"]
    targets = {item["id"] for item in base}
    for case in corpus["cases"]:
        if case["kind"] == "supported" and case["expected_route"] not in targets:
            raise ValueError("unsupported or unavailable target in base catalog")
        if case["kind"] == "unsupported" and case["expected_route"] is not None:
            raise ValueError("unsupported cases must not have a target")
    sizes = [expand_catalog(base, size) for size in SIZES]
    for a, b in zip(sizes, sizes[1:], strict=False):
        if a != b[:len(a)]:
            raise ValueError("generated catalog is not prefix nested")
    for catalog in sizes:
        ids = [item["id"] for item in catalog]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate generated routes")
        if not targets.issubset(ids):
            raise ValueError("missing baseline targets")


def score_real_models(
    corpus: dict[str, Any],
    source_sha256: str,
    model_key: str,
) -> dict[str, Any]:
    import resource  # POSIX only, in actual Linux model-execution path.

    import torch
    from sentence_transformers import SentenceTransformer

    if model_key not in MODEL_CHOICES:
        raise ValueError("unknown checkpoint")
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    model_id = MODEL_CHOICES[model_key]
    load_start = time.perf_counter()
    model = SentenceTransformer(model_id, device="cpu", trust_remote_code=False)
    model.eval()
    if model.device.type != "cpu":
        raise RuntimeError("CPU-only experiment unexpectedly used a GPU")
    load_ms = (time.perf_counter() - load_start) * 1000

    def encode(texts: list[str]) -> list[list[float]]:
        values = model.encode(
            texts, batch_size=16, normalize_embeddings=True,
            convert_to_numpy=True, show_progress_bar=False,
        ).tolist()
        if any(not math.isfinite(v) for vector in values for v in vector):
            raise RuntimeError("non-finite real model embedding")
        return values

    catalogs = {size: expand_catalog(corpus["catalog"], size) for size in SIZES}
    largest = catalogs[max(SIZES)]
    full_passages = [
        f"{item['id']}\n{item['description']}" for item in largest
    ]
    # Precompute 500 document vectors once per model. The same cached
    # representations serve every width. Every query is encoded afresh.
    if model_key == "e5-small":
        adapter = E5CachedEmbedder(encode, max_cached_passages=len(largest))
        adapter(["catalog cache warmup"] + full_passages)
    else:
        vectors = encode(full_passages)
        cached = dict(zip(full_passages, vectors, strict=True))

        def adapter(texts: list[str]) -> list[list[float]]:
            return [
                *encode([texts[0]]),
                *(list(cached[passage]) for passage in texts[1:]),
            ]

        encode(["catalog cache warmup"])

    backend = EmbeddingDecisionBackend(adapter)
    results: dict[str, Any] = {}
    for size, catalog in catalogs.items():
        options = [
            DecisionOption(
                id=item["id"], label=item["id"], description=item["description"],
            )
            for item in catalog
        ]
        rows = []
        for case in corpus["cases"]:
            request = DecisionRequest(
                query=case["query"], options=options, max_selections=10,
            )
            start = time.perf_counter()
            outcome = choose_sync(backend, request)
            latency_ms = (time.perf_counter() - start) * 1000
            ranked = [x.option_id for x in outcome.selections]
            if outcome.abstained or len(ranked) != 10:
                raise RuntimeError("unthresholded ranking must return 10 routes")
            score = float(outcome.metadata["top_similarity"])
            rows.append({
                "case_id": case["id"],
                "kind": case["kind"],
                "language": case["language"],
                "expected_route": case["expected_route"],
                "top_1": ranked[0],
                "top_5": ranked[:5],
                "top_10": ranked,
                "top_similarity": score,
                "hit_at_1": (
                    case["expected_route"] == ranked[0]
                    if case["kind"] == "supported" else None
                ),
                "hit_at_5": (
                    case["expected_route"] in ranked[:5]
                    if case["kind"] == "supported" else None
                ),
                "hit_at_10": (
                    case["expected_route"] in ranked
                    if case["kind"] == "supported" else None
                ),
                "latency_ms": round(latency_ms, 4),
            })
        summary = aggregate(rows, corpus["thresholds_diagnostic_only"])
        positive = [r for r in rows if r["kind"] == "supported"]
        summary["overall"]["recall_at_10"] = sum(
            r["hit_at_10"] for r in positive
        ) / len(positive)
        for lang, data in summary["by_language"].items():
            supported = [
                r for r in positive if r["language"] == lang
            ]
            data["recall_at_10"] = sum(
                r["hit_at_10"] for r in supported
            ) / len(supported)
        results[str(size)] = {
            "catalog_sha256": catalog_hash(catalog),
            "generated_distractors": size - len(corpus["catalog"]),
            "summary": summary,
            "rows": rows,
        }
    return {
        "surface": "synthetic_stress_development_only",
        "independent_validation": False,
        "true_registered_catalog": False,
        "agent_or_execution_success": False,
        "frozen_0_14_evidence_modified": False,
        "model_key": model_key,
        "model_id": model_id,
        "model_load_ms": round(load_ms, 2),
        "embedding_dim": model.get_sentence_embedding_dimension(),
        "peak_rss_mib": round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2,
        ),
        "cpu_count": os.cpu_count(),
        "python_version": platform.python_version(),
        "corpus_sha256": source_sha256,
        "generator_seed": SEED,
        "nested_sizes": list(SIZES),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus", type=Path,
        default=ROOT / "benchmarks/multilingual-embedding-cpu-dev-20261015.json",
    )
    parser.add_argument(
        "--model", choices=[*MODEL_CHOICES, "validate"], required=True,
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("artifacts/multilingual-catalog-scale/report.json"),
    )
    args = parser.parse_args()
    corpus, digest = load_development_corpus(args.corpus)
    check_corpus(corpus)
    if args.model == "validate":
        print(json.dumps({
            "status": "synthetic catalog integrity passed",
            "catalog_sizes": list(SIZES),
            "corpus_sha256": digest,
            "generator_seed": SEED,
            "catalog_hashes": {
                str(s): catalog_hash(expand_catalog(corpus["catalog"], s))
                for s in SIZES
            },
        }))
        return 0
    result = score_real_models(corpus, digest, args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "model": result["model_id"],
        "results": {
            size: {
                "recall_at_1": v["summary"]["overall"]["recall_at_1"],
                "recall_at_5": v["summary"]["overall"]["recall_at_5"],
                "recall_at_10": v["summary"]["overall"]["recall_at_10"],
                "p95_ms": v["summary"]["overall"]["top1_latency_ms_p95"],
                "unsupported_false_match_at_0_6": v["summary"]["overall"]
                ["threshold_diagnostics"]["0.6"]["unsupported_false_match_rate"],
            }
            for size, v in result["results"].items()
        },
        "note": "templated dev stress, not independent agent/no-match qualification",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
