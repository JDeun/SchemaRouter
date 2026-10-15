"""Exploratory trilingual operation intent DEV benchmark (no execution).

Real CPU embedding ranking versus the conservative offline regex hypothesis.
Supported intents and negated/compound/OOD requests have disjoint denominators.
No score here qualifies authorization, no-match policy, or frozen 0.14 gates.
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
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from schemarouter import (  # noqa: E402
    DecisionOption,
    DecisionRequest,
    E5CachedEmbedder,
    EmbeddingDecisionBackend,
    choose_sync,
    infer_operation_intent,
)
from schemarouter.operation_fit import OperationKind  # noqa: E402

MODEL_IDS = {
    "minilm": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "e5-small": "intfloat/multilingual-e5-small",
}
DIAGNOSTIC_THRESHOLDS = (0.5, 0.6, 0.7, 0.8)

# Plain-English *operation* definitions, not tool specifications or authority.
DESCRIPTIONS: dict[OperationKind, str] = {
    "search": "Search and discover records or papers by keywords. Find matching information.",
    "lookup": "Look up or retrieve one previously stored record using its identifier.",
    "list": "List or enumerate registered entries, items, or events.",
    "history": "Read past history, prior transactions, and historical records.",
    "convert": "Convert numeric units, currencies, or measures between formats.",
    "directions": "Provide walking or driving directions and navigation routes.",
    "create": "Create, add, or register a new stored record or calendar event.",
    "update": "Update, edit, or modify an existing record or stored quantity.",
    "delete": "Delete, erase, or remove an existing stored record permanently.",
}


def load_corpus(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    corpus = json.loads(raw)
    if corpus.get("surface") != "prospective_operation_intent_development_only":
        raise ValueError("only new operation-intent development data is supported")
    if any(
        corpus.get(flag) is not False
        for flag in ("independent_holdout", "calibrated_no_match", "execution_safety")
    ):
        raise ValueError("DEV data must not claim validation, safety, or calibration")
    if corpus.get("languages") != ["en", "ko", "ja"]:
        raise ValueError("expected exactly EN/KO/JA language divisions")
    if corpus.get("operation_kinds") != list(DESCRIPTIONS):
        raise ValueError("fixed operation dictionary does not match corpus")
    cases = corpus.get("cases")
    if not isinstance(cases, list) or len(cases) != 72:
        raise ValueError("expected 72 frozen DEV cases")
    ids: set[str] = set()
    by_language_kind: Counter[tuple[str, str]] = Counter()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("invalid case record")
        if not isinstance(case.get("id"), str) or case["id"] in ids:
            raise ValueError("duplicate or invalid case ID")
        ids.add(case["id"])
        if not isinstance(case.get("query"), str) or not case["query"].strip():
            raise ValueError("empty query")
        language, kind, expected = (
            case.get("language"), case.get("kind"), case.get("expected_operation")
        )
        if language not in corpus["languages"]:
            raise ValueError("unknown language")
        if kind == "supported":
            if expected not in DESCRIPTIONS:
                raise ValueError("supported case requires declared operation")
        elif kind == "unsupported":
            if expected is not None:
                raise ValueError("unsupported case must not declare an operation")
        else:
            raise ValueError("unknown case kind")
        by_language_kind[(language, kind)] += 1
    for lang in corpus["languages"]:
        if by_language_kind[(lang, "supported")] != 18:
            raise ValueError("each language requires 18 supported cases")
        if by_language_kind[(lang, "unsupported")] != 6:
            raise ValueError("each language requires 6 unsupported cases")
    return corpus, hashlib.sha256(raw).hexdigest()


def p95(values: list[float]) -> float:
    values = sorted(values)
    index = 0.95 * (len(values) - 1)
    low = math.floor(index)
    high = math.ceil(index)
    return values[low] + (values[high] - values[low]) * (index - low)


def summarize(
    rows: list[dict[str, Any]],
    *,
    confidence_thresholds: tuple[float, ...] = (),
) -> dict[str, Any]:
    if not rows:
        raise ValueError("non-empty measurement set required")
    supported = [x for x in rows if x["kind"] == "supported"]
    unsupported = [x for x in rows if x["kind"] == "unsupported"]
    if not supported or not unsupported:
        raise ValueError("both kinds are required for honest denominators")

    def aggregate(group: list[dict[str, Any]]) -> dict[str, Any]:
        positive = [x for x in group if x["kind"] == "supported"]
        negative = [x for x in group if x["kind"] == "unsupported"]
        result: dict[str, Any] = {
            "supported_count": len(positive),
            "unsupported_count": len(negative),
            "supported_correct_rate": (
                sum(x["predicted_operation"] == x["expected_operation"]
                    for x in positive) / len(positive) if positive else None
            ),
            "supported_false_refusal_rate": (
                sum(x["predicted_operation"] is None for x in positive)
                / len(positive) if positive else None
            ),
            "supported_wrong_operation_rate": (
                sum(x["predicted_operation"] not in (None, x["expected_operation"])
                    for x in positive) / len(positive) if positive else None
            ),
            "unsupported_false_accept_rate": (
                sum(x["predicted_operation"] is not None for x in negative)
                / len(negative) if negative else None
            ),
            "latency_ms_p50": (
                statistics.median(x["latency_ms"] for x in group)
            ),
            "latency_ms_p95": p95([x["latency_ms"] for x in group]),
        }
        if confidence_thresholds:
            result["posthoc_threshold_diagnostics_only"] = {
                str(threshold): {
                    "supported_correct_and_accepted_rate": (
                        sum(x["predicted_operation"] == x["expected_operation"]
                            and x["top_similarity"] >= threshold
                            for x in positive) / len(positive)
                        if positive else None
                    ),
                    "supported_false_refusal_rate": (
                        sum(x["top_similarity"] < threshold for x in positive)
                        / len(positive) if positive else None
                    ),
                    "supported_wrong_operation_accepted_rate": (
                        sum(x["top_similarity"] >= threshold
                            and x["predicted_operation"] != x["expected_operation"]
                            for x in positive) / len(positive)
                        if positive else None
                    ),
                    "unsupported_false_accept_rate": (
                        sum(x["top_similarity"] >= threshold for x in negative)
                        / len(negative) if negative else None
                    ),
                }
                for threshold in confidence_thresholds
            }
        return result

    return {
        "overall": aggregate(rows),
        "by_language": {
            lang: aggregate([r for r in rows if r["language"] == lang])
            for lang in sorted({row["language"] for row in rows})
        },
    }


def evaluate_baseline(corpus: dict[str, Any], digest: str) -> dict[str, Any]:
    rows = []
    for case in corpus["cases"]:
        began = time.perf_counter()
        hypothesis = infer_operation_intent(case["query"])
        elapsed = (time.perf_counter() - began) * 1000
        rows.append({
            "case_id": case["id"],
            "language": case["language"],
            "kind": case["kind"],
            "expected_operation": case["expected_operation"],
            "predicted_operation": hypothesis.operation,
            "abstained": hypothesis.abstained,
            "abstain_reason": hypothesis.reason,
            "top_similarity": None,
            "latency_ms": round(elapsed, 5),
        })
    return {
        "model_key": "lexical_baseline",
        "surface": "prospective_operation_intent_development_only",
        "independent_validation": False,
        "grants_execution_authority": False,
        "corpus_sha256": digest,
        "summary": summarize(rows),
        "rows": rows,
    }


def evaluate_real(
    model_key: str, corpus: dict[str, Any], digest: str,
) -> dict[str, Any]:
    import resource  # Linux Actions only, never loaded during offline checks.

    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    model_name = MODEL_IDS[model_key]
    before_load = time.perf_counter()
    model = SentenceTransformer(model_name, device="cpu", trust_remote_code=False)
    model.eval()
    if model.device.type != "cpu":
        raise RuntimeError("CPU-only assessment requires CPU inference")
    load_ms = (time.perf_counter() - before_load) * 1000

    options = [
        DecisionOption(id=k, label=k, description=v)
        for k, v in DESCRIPTIONS.items()
    ]
    passages = [f"{o.label}\n{o.description}" for o in options]

    def encode(texts: list[str]) -> list[list[float]]:
        return model.encode(
            texts, batch_size=16, normalize_embeddings=True,
            convert_to_numpy=True, show_progress_bar=False,
        ).tolist()

    if model_key == "e5-small":
        adapter = E5CachedEmbedder(encode, max_cached_passages=len(passages))
        adapter(["warm-up"] + passages)
    else:
        cached_vectors = encode(passages)

        def adapter(texts: list[str]) -> list[list[float]]:
            if texts[1:] != passages:
                raise ValueError("option set unexpectedly changed")
            return [*encode([texts[0]]), *cached_vectors]

        encode(["warm-up"])

    backend = EmbeddingDecisionBackend(adapter)
    rows = []
    for case in corpus["cases"]:
        request = DecisionRequest(
            query=case["query"], options=options, max_selections=2,
        )
        started = time.perf_counter()
        ranked = choose_sync(backend, request)
        duration_ms = (time.perf_counter() - started) * 1000
        if ranked.abstained or len(ranked.selections) != 2:
            raise RuntimeError("unthresholded model must rank both top candidates")
        similarity = float(ranked.metadata["top_similarity"])
        if not math.isfinite(similarity):
            raise RuntimeError("non-finite top cosine")
        rows.append({
            "case_id": case["id"],
            "language": case["language"],
            "kind": case["kind"],
            "expected_operation": case["expected_operation"],
            "predicted_operation": ranked.selections[0].option_id,
            "second_operation": ranked.selections[1].option_id,
            "abstained": False,
            "top_similarity": similarity,
            "latency_ms": round(duration_ms, 5),
        })
    return {
        "model_key": model_key,
        "model_id": model_name,
        "embedding_dimension": model.get_sentence_embedding_dimension(),
        "surface": "prospective_operation_intent_development_only",
        "independent_validation": False,
        "grants_execution_authority": False,
        "confidence_calibrated": False,
        "frozen_0_14_unchanged": True,
        "corpus_sha256": digest,
        "model_load_ms": round(load_ms, 2),
        "peak_process_rss_mib": round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2,
        ),
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "summary": summarize(
            rows, confidence_thresholds=DIAGNOSTIC_THRESHOLDS,
        ),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model", choices=[*MODEL_IDS, "validate", "baseline"], required=True,
    )
    parser.add_argument(
        "--corpus", type=Path,
        default=ROOT / "benchmarks/operation-intent-trilingual-dev-20261015.json",
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("artifacts/operation-intent-dev/report.json"),
    )
    args = parser.parse_args()
    corpus, digest = load_corpus(args.corpus)
    if args.model == "validate":
        print(json.dumps({
            "surface": corpus["surface"],
            "cases": len(corpus["cases"]),
            "corpus_sha256": digest,
        }))
        return 0
    report = (
        evaluate_baseline(corpus, digest)
        if args.model == "baseline"
        else evaluate_real(args.model, corpus, digest)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "model": report["model_key"],
        "corpus_sha256": digest,
        "metrics": report["summary"]["overall"],
        "limitations": "development diagnostics only; never authorize execution",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
