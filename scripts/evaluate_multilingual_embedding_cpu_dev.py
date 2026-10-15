"""Real CPU-only multilingual candidate-recall DEV evaluation (#1339).

Prospective development diagnostics, NOT a held-out, agent-success, or release
qualification result. Never imports frozen 0.14 corpora or retunes no-match.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import sys
import time
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from schemarouter import (  # noqa: E402
    DecisionOption,
    DecisionRequest,
    E5CachedEmbedder,
    EmbeddingDecisionBackend,
    choose_sync,
)

MODEL_CHOICES = {
    "e5-small": "intfloat/multilingual-e5-small",
    "minilm": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "bge-m3": "BAAI/bge-m3",
    "qwen3-0.6b": "Qwen/Qwen3-Embedding-0.6B",
}


def load_development_corpus(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    corpus = json.loads(raw)
    if corpus.get("surface") != "prospective_development_only":
        raise ValueError("only a prospective development corpus may be evaluated")
    if corpus.get("validation_or_holdout_claim_allowed") is not False:
        raise ValueError("development data cannot be promoted to a holdout")
    options = corpus.get("catalog")
    cases = corpus.get("cases")
    if not isinstance(options, list) or not isinstance(cases, list) or not options or not cases:
        raise ValueError("non-empty catalog and query cases are required")
    ids = [item["id"] for item in options]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate catalog route IDs")
    seen = set()
    for case in cases:
        if case["id"] in seen:
            raise ValueError("duplicate case IDs")
        seen.add(case["id"])
        if not isinstance(case.get("query"), str) or not case["query"].strip():
            raise ValueError("all queries must be non-empty strings")
        if case["language"] not in corpus["languages"]:
            raise ValueError("unknown language tag")
        if case["kind"] == "supported":
            if case["expected_route"] not in ids:
                raise ValueError("supported case missing its registered route")
        elif case["kind"] == "unsupported":
            if case["expected_route"] is not None:
                raise ValueError("unsupported case must have no target route")
        else:
            raise ValueError("case kind must be supported or unsupported")
    return corpus, hashlib.sha256(raw).hexdigest()


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return math.nan
    values = sorted(values)
    index = (len(values) - 1) * percentile_value / 100
    lower = math.floor(index)
    upper = math.ceil(index)
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def aggregate(rows: list[dict[str, Any]], thresholds: list[float]) -> dict[str, Any]:
    supported = [x for x in rows if x["kind"] == "supported"]
    unsupported = [x for x in rows if x["kind"] == "unsupported"]
    if not supported or not unsupported:
        raise ValueError("both supported and unsupported cases are mandatory")

    def scored(group: list[dict[str, Any]]) -> dict[str, Any]:
        positive = [x for x in group if x["kind"] == "supported"]
        negative = [x for x in group if x["kind"] == "unsupported"]
        result: dict[str, Any] = {
            "cases": len(group),
            "supported": len(positive),
            "unsupported": len(negative),
            "recall_at_1": (
                sum(x["hit_at_1"] for x in positive) / len(positive) if positive else None
            ),
            "recall_at_5": (
                sum(x["hit_at_5"] for x in positive) / len(positive) if positive else None
            ),
            "unsupported_top_similarity_median": (
                statistics.median(x["top_similarity"] for x in negative) if negative else None
            ),
            "top1_latency_ms_p50": percentile([x["latency_ms"] for x in group], 50),
            "top1_latency_ms_p95": percentile([x["latency_ms"] for x in group], 95),
            "threshold_diagnostics": {},
        }
        for threshold in thresholds:
            result["threshold_diagnostics"][str(threshold)] = {
                "unsupported_false_match_rate": (
                    sum(x["top_similarity"] >= threshold for x in negative) / len(negative)
                    if negative else None
                ),
                "supported_false_refusal_rate": (
                    sum(x["top_similarity"] < threshold for x in positive) / len(positive)
                    if positive else None
                ),
                "supported_wrong_route_accepted_rate": (
                    sum(x["top_similarity"] >= threshold and not x["hit_at_1"]
                        for x in positive) / len(positive)
                    if positive else None
                ),
            }
        return result

    return {
        "overall": scored(rows),
        "by_language": {
            lang: scored([x for x in rows if x["language"] == lang])
            for lang in sorted(set(x["language"] for x in rows))
        },
        "counts_by_kind": dict(Counter(x["kind"] for x in rows)),
    }


def evaluate(
    model_key: str,
    corpus: dict[str, Any],
    corpus_sha256: str,
    *,
    device: str,
) -> dict[str, Any]:
    # Imported only when explicitly conducting a real-model run.
    import resource  # Linux CPU Actions only; avoid importing on other platforms.
    import torch
    from sentence_transformers import SentenceTransformer

    if device != "cpu":
        raise ValueError("this first CPU comparison deliberately disallows accelerators")
    torch.set_num_threads(min(os.cpu_count() or 1, 4))
    model_id = MODEL_CHOICES[model_key]
    load_start = time.perf_counter()
    model = SentenceTransformer(model_id, device="cpu", trust_remote_code=False)
    model.eval()
    load_ms = (time.perf_counter() - load_start) * 1000
    if model.device.type != "cpu":
        raise RuntimeError("non-CPU model device is not allowed")

    option_objects = [
        DecisionOption(id=item["id"], label=item["id"], description=item["description"])
        for item in corpus["catalog"]
    ]
    passage_texts = [f"{item.label}\n{item.description}" for item in option_objects]

    def encode(texts: list[str]) -> list[list[float]]:
        # Local model inference only. No paid API/remote inference.
        output = model.encode(
            texts,
            batch_size=16,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return output.tolist()

    if model_key == "e5-small":
        adapter = E5CachedEmbedder(encode, max_cached_passages=len(option_objects))
        # Pre-compute passage vectors outside query latency timing.
        adapter(["warm-up"] + passage_texts)
    else:
        cached_passages = encode(passage_texts)

        def adapter(texts: list[str]) -> list[list[float]]:
            if texts[1:] != passage_texts:
                raise ValueError("catalog option text changed during evaluation")
            return [*encode([texts[0]]), *cached_passages]

        # Warm up a single query without counting it in steady-state latency.
        encode(["warm-up"])

    backend = EmbeddingDecisionBackend(adapter)
    rows: list[dict[str, Any]] = []
    cases = corpus["cases"]
    for case in cases:
        request = DecisionRequest(
            query=case["query"],
            options=option_objects,
            max_selections=min(5, len(option_objects)),
        )
        began = time.perf_counter()
        result = choose_sync(backend, request)
        elapsed_ms = (time.perf_counter() - began) * 1000
        top_ids = [item.option_id for item in result.selections]
        if len(top_ids) != min(5, len(option_objects)) or result.abstained:
            raise RuntimeError("unthresholded ranking returned too few choices")
        top_similarity = float(result.metadata["top_similarity"])
        if not math.isfinite(top_similarity):
            raise RuntimeError("non-finite similarity")
        rows.append({
            "case_id": case["id"],
            "kind": case["kind"],
            "language": case["language"],
            "expected_route": case["expected_route"],
            "top_1": top_ids[0],
            "top_5": top_ids,
            "top_similarity": top_similarity,
            "hit_at_1": case["expected_route"] == top_ids[0]
                        if case["kind"] == "supported" else None,
            "hit_at_5": case["expected_route"] in top_ids
                        if case["kind"] == "supported" else None,
            "latency_ms": round(elapsed_ms, 4),
        })
    totals = aggregate(rows, corpus["thresholds_diagnostic_only"])
    info: dict[str, Any] = {
        "surface": "prospective_development_only",
        "not_independent_validation": True,
        "not_agent_success_or_execution_safety": True,
        "no_fit_thresholds_are_diagnostic_only": True,
        "frozen_0_14_evidence_untouched": True,
        "model_id": model_id,
        "model_key": model_key,
        "encoder_dim": model.get_sentence_embedding_dimension(),
        "model_load_ms": round(load_ms, 2),
        "peak_process_rss_mb_linux": round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2,
        ),
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "sentence_transformers": version("sentence-transformers"),
        "corpus_sha256": corpus_sha256,
        "catalog_size": len(option_objects),
        "query_count": len(cases),
        "scoring": (
            "cosine; top-k bounded option IDs; similarity is not a no-match probability"
        ),
        "embedding": "E5 query/pass prefixes, other models unprefixed library defaults",
        "summary": totals,
        "rows": rows,
    }
    return info


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=[*MODEL_CHOICES, "validate"], required=True)
    parser.add_argument(
        "--corpus", type=Path,
        default=_ROOT / "benchmarks/multilingual-embedding-cpu-dev-20261015.json",
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("artifacts/multilingual-embedding-dev/report.json"),
    )
    args = parser.parse_args()
    corpus, digest = load_development_corpus(args.corpus)
    if args.model == "validate":
        print(json.dumps({
            "corpus_sha256": digest,
            "cases": len(corpus["cases"]),
            "routes": len(corpus["catalog"]),
            "surface": corpus["surface"],
        }))
        return 0
    result = evaluate(args.model, corpus, digest, device="cpu")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    s = result["summary"]["overall"]
    print(json.dumps({
        "model": result["model_id"],
        "recall_at_1": s["recall_at_1"],
        "recall_at_5": s["recall_at_5"],
        "unsupported_median_similarity": s["unsupported_top_similarity_median"],
        "p50_ms": s["top1_latency_ms_p50"],
        "p95_ms": s["top1_latency_ms_p95"],
        "peak_rss_mb": result["peak_process_rss_mb_linux"],
        "corpus_sha256": digest,
        "note": "development diagnostics only, not final agent/no-match qualification",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
