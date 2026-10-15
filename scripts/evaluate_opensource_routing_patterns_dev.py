"""Experimental open-source-inspired routing arms on prior EN/KO/JA DEV text.

A: Semantic Router-style multilingual exemplar nearest-route + fixed abstention.
B: LlamaIndex-style retrieve (MiniLM top-3) then separate multilingual CrossEncoder
   rerank; evaluate forced choice and an independent fixed retrieval-score gate.

These are LOCAL REIMPLEMENTATIONS of design patterns, NOT native package benchmarks,
not independent confirmation and never tool execution or authorization.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.evaluate_operation_intent_cpu_dev import (  # noqa: E402
    DESCRIPTIONS,
    load_corpus,
    p95,
)

SOURCE_SHA256 = "18fce09092e24ebb44d2df14d3224daa47fec9a2df9134d4a0c708b9935dc7d7"
BI_ENCODER = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CROSS_ENCODER = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
ROUTE_THRESHOLD = 0.65  # Arbitrary PRE-SCORING diagnostic, never deployed.
RETRIEVE_THRESHOLD = 0.65  # Arbitrary PRE-SCORING diagnostic, never deployed.
ROUTE_MARGIN = 0.03
TOP_K = 3

# NOT copied from evaluation queries, but created by the same analyst after
# seeing prior 72-case results. Thus not training/holdout independent.
EXEMPLARS: dict[str, tuple[str, str, str]] = {
    "search": (
        "Find relevant publications by keyword",
        "관련 문서 검색",
        "関連資料を検索",
    ),
    "lookup": (
        "Retrieve a stored item's identifier",
        "저장된 항목 조회",
        "保存された記録を照会",
    ),
    "list": (
        "Enumerate available entries",
        "사용 가능한 항목 목록",
        "項目を一覧表示",
    ),
    "history": (
        "Inspect historical events and previous records",
        "지난 거래 내역 확인",
        "過去の履歴を確認",
    ),
    "convert": (
        "Convert between currencies or units",
        "통화 또는 단위 환산",
        "通貨や単位を換算",
    ),
    "directions": (
        "Get turn-by-turn navigation",
        "목적지까지 길 안내",
        "目的地までの道順",
    ),
    "create": (
        "Add a new record",
        "새 기록 생성",
        "新しい記録を作成",
    ),
    "update": (
        "Edit an existing value",
        "기존 정보 수정",
        "既存の情報を更新",
    ),
    "delete": (
        "Erase an existing record",
        "기존 기록 삭제",
        "保存された記録を削除",
    ),
}


def choose_exemplar_route(
    route_scores: dict[str, float], *, threshold: float, margin: float,
) -> str | None:
    """Most-similar-example route; abstain on low score or ambiguity."""
    if not route_scores or any(
        not math.isfinite(score) for score in route_scores.values()
    ):
        raise ValueError("finite nonempty similarity scores required")
    ranked = sorted(route_scores, key=lambda k: (-route_scores[k], k))
    winner = ranked[0]
    runner_up = route_scores[ranked[1]] if len(ranked) > 1 else -1.0
    if route_scores[winner] < threshold:
        return None
    if route_scores[winner] - runner_up < margin:
        return None
    return winner


def bounded_rerank(
    retrieved: list[tuple[str, float]],
    cross_scores: list[float],
    *,
    gate: bool,
    threshold: float = RETRIEVE_THRESHOLD,
) -> str | None:
    """No new routes: the selector can ONLY output retrieved candidate IDs."""
    if not retrieved or len(retrieved) != len(cross_scores):
        raise ValueError("candidate score length mismatch")
    if len({id for id, _ in retrieved}) != len(retrieved):
        raise ValueError("duplicate retrieved IDs")
    if any(
        not math.isfinite(score) for _, score in retrieved
    ) or any(not math.isfinite(s) for s in cross_scores):
        raise ValueError("nonfinite candidate scores")
    best_index = max(range(len(retrieved)), key=lambda i: (cross_scores[i], -i))
    if gate and retrieved[best_index][1] < threshold:
        return None
    return retrieved[best_index][0]


def summary(rows: list[dict[str, Any]], arm: str) -> dict[str, Any]:
    if not rows:
        raise ValueError("cannot score zero rows")
    def one(items: list[dict[str, Any]]) -> dict[str, Any]:
        pos = [r for r in items if r["kind"] == "supported"]
        neg = [r for r in items if r["kind"] == "unsupported"]
        return {
            "supported": len(pos),
            "unsupported": len(neg),
            "correct_supported": sum(
                r["prediction"] == r["expected_operation"] for r in pos
            ),
            "wrong_supported": sum(
                r["prediction"] not in (None, r["expected_operation"])
                for r in pos
            ),
            "false_refusal_supported": sum(
                r["prediction"] is None for r in pos
            ),
            "false_accept_unsupported": sum(
                r["prediction"] is not None for r in neg
            ),
            "latency_p50_ms": statistics.median(r["latency_ms"] for r in items),
            "latency_p95_ms": p95([r["latency_ms"] for r in items]),
        }
    return {
        "arm": arm,
        "overall": one(rows),
        "languages": {
            lang: one([row for row in rows if row["language"] == lang])
            for lang in sorted({row["language"] for row in rows})
        },
    }


def evaluate(
    corpus: dict[str, Any],
    embedder: Any,
    cross_encoder: Any,
) -> dict[str, Any]:
    import numpy as np

    route_keys = tuple(DESCRIPTIONS)
    if route_keys != tuple(EXEMPLARS):
        raise ValueError("route prototypes must match frozen operation choices")
    exemplar_texts = [x for route in route_keys for x in EXEMPLARS[route]]
    route_vectors = embedder.encode(
        exemplar_texts, normalize_embeddings=True, convert_to_numpy=True,
        show_progress_bar=False, batch_size=16,
    )
    doc_vectors = embedder.encode(
        [f"{route}: {DESCRIPTIONS[route]}" for route in route_keys],
        normalize_embeddings=True, convert_to_numpy=True,
        show_progress_bar=False, batch_size=16,
    )
    if route_vectors.shape[0] != 27 or doc_vectors.shape[0] != 9:
        raise RuntimeError("invalid precomputed route vectors")
    arms = {
        "exemplar_forced": [],
        "exemplar_threshold_margin": [],
        "retrieve3_crossencoder_forced": [],
        "retrieve3_crossencoder_score_gate": [],
    }
    for case in corpus["cases"]:
        query = case["query"]
        baseline_start = time.perf_counter()
        vector = embedder.encode(
            query, normalize_embeddings=True,
            convert_to_numpy=True, show_progress_bar=False,
        )
        example_scores = np.asarray(route_vectors) @ np.asarray(vector)
        if not np.isfinite(example_scores).all():
            raise RuntimeError("nonfinite exemplar similarity")
        scores = {
            key: float(max(example_scores[i * 3:(i + 1) * 3]))
            for i, key in enumerate(route_keys)
        }
        ranked = sorted(route_keys, key=lambda k: (-scores[k], k))
        lexical_ms = (time.perf_counter() - baseline_start) * 1000

        doc_start = time.perf_counter()
        retrieval_scores = np.asarray(doc_vectors) @ np.asarray(vector)
        indexes = sorted(
            range(len(route_keys)),
            key=lambda i: (-float(retrieval_scores[i]), route_keys[i]),
        )[:TOP_K]
        retrieved = [
            (route_keys[i], float(retrieval_scores[i])) for i in indexes
        ]
        # This is a separately trained model, not a cosine threshold or LLM.
        pairs = [
            (query, f"{name}: {DESCRIPTIONS[name]}")
            for name, _ in retrieved
        ]
        ranked_scores = [
            float(score) for score in cross_encoder.predict(
                pairs, batch_size=8, show_progress_bar=False,
            )
        ]
        second_stage_ms = (time.perf_counter() - doc_start) * 1000
        predictions = {
            "exemplar_forced": ranked[0],
            "exemplar_threshold_margin": choose_exemplar_route(
                scores, threshold=ROUTE_THRESHOLD, margin=ROUTE_MARGIN,
            ),
            "retrieve3_crossencoder_forced": bounded_rerank(
                retrieved, ranked_scores, gate=False,
            ),
            "retrieve3_crossencoder_score_gate": bounded_rerank(
                retrieved, ranked_scores, gate=True,
            ),
        }
        for arm, predicted in predictions.items():
            metadata = {
                "case_id": case["id"],
                "language": case["language"],
                "kind": case["kind"],
                "expected_operation": case["expected_operation"],
                "prediction": predicted,
                "top_exemplar_score": scores[ranked[0]],
                "retrieved": [name for name, _ in retrieved],
                "retrieved_scores": [score for _, score in retrieved],
                "latency_ms": round(
                    lexical_ms if arm.startswith("exemplar")
                    else lexical_ms + second_stage_ms, 4,
                ),
            }
            arms[arm].append(metadata)
    return {
        name: {"summary": summary(rows, name), "rows": rows}
        for name, rows in arms.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument(
        "--corpus", type=Path,
        default=ROOT / "benchmarks/operation-intent-trilingual-dev-20261015.json",
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("artifacts/opensource-routing-patterns-dev/results.json"),
    )
    args = parser.parse_args()
    corpus, digest = load_corpus(args.corpus)
    if digest != SOURCE_SHA256:
        raise ValueError("publicly frozen 72-query DEV corpus changed")
    if args.preflight:
        print(json.dumps({
            "cases": len(corpus["cases"]), "source_sha256": digest,
            "routes": list(EXEMPLARS), "top_k": TOP_K,
            "prototype_threshold": ROUTE_THRESHOLD,
            "retrieval_threshold": RETRIEVE_THRESHOLD,
            "prototype_margin": ROUTE_MARGIN,
        }))
        return 0

    import resource

    import torch
    from sentence_transformers import CrossEncoder, SentenceTransformer

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    started = time.perf_counter()
    embedder = SentenceTransformer(BI_ENCODER, device="cpu", trust_remote_code=False)
    cross = CrossEncoder(CROSS_ENCODER, device="cpu", trust_remote_code=False)
    if embedder.device.type != "cpu":
        raise RuntimeError("embedding model unexpectedly not on CPU")
    result = evaluate(corpus, embedder, cross)
    payload = {
        "surface": "exploratory_development_only",
        "third_party_native_implementations": False,
        "inspired_by": ["Aurelio Semantic Router", "LlamaIndex tool retriever selector"],
        "not_independent_validation": True,
        "author_written_examples_after_prior_dev": True,
        "default_route_modified": False,
        "no_tool_execution": True,
        "no_execution_authority": True,
        "thresholds_calibrated": False,
        "bi_encoder": BI_ENCODER,
        "cross_encoder": CROSS_ENCODER,
        "model_weight_revisions_attested": False,
        "model_source_licenses_checked_in_docs": True,
        "corpus_sha256": digest,
        "hardware": {
            "requested_device": "cpu",
            "threads": torch.get_num_threads(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "peak_rss_mib": round(
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2,
            ),
        },
        "wall_ms_including_load": round((time.perf_counter()-started)*1000, 2),
        "fixed_diagnostics": {
            "prototype_threshold": ROUTE_THRESHOLD,
            "retrieval_threshold": RETRIEVE_THRESHOLD,
            "prototype_margin": ROUTE_MARGIN,
            "top_k": TOP_K,
        },
        "arms": result,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for name, arm in result.items():
        print(json.dumps({
            "arm": name,
            "metrics": arm["summary"]["overall"],
            "corpus_sha256": digest,
            "note": "DEV-only, patterns reproduced, not native framework benchmarks",
        }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
