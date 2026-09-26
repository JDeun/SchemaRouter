"""Research-only cheap-first operation-fit cascade.

The scorer first uses the existing multilingual MiniLM embedding surface to identify
clear rejects or clear sibling-operation accepts. Only ambiguous requests are escalated
to the already-frozen beta=1 sibling-contrastive BGE scorer.

This module is benchmark-only. Both stages receive only the query and texts for the
already-authorized operation choices supplied by PairwiseDecisionBackend.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

_DEFAULT_REJECT_BELOW = 0.30
_DEFAULT_ACCEPT_ABOVE = 0.60
_DEFAULT_ACCEPT_MARGIN = 0.03


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw = os.environ.get(name)
    value = default if raw is None else float(raw)
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be finite and between {minimum} and {maximum}")
    return value


def _settings() -> tuple[float, float, float]:
    reject_below = _env_float(
        "SCHEMAROUTER_BENCHMARK_CASCADE_REJECT_BELOW",
        _DEFAULT_REJECT_BELOW,
        minimum=-1.0,
        maximum=1.0,
    )
    accept_above = _env_float(
        "SCHEMAROUTER_BENCHMARK_CASCADE_ACCEPT_ABOVE",
        _DEFAULT_ACCEPT_ABOVE,
        minimum=-1.0,
        maximum=1.0,
    )
    accept_margin = _env_float(
        "SCHEMAROUTER_BENCHMARK_CASCADE_ACCEPT_MARGIN",
        _DEFAULT_ACCEPT_MARGIN,
        minimum=0.0,
        maximum=2.0,
    )
    if reject_below >= accept_above:
        raise RuntimeError(
            "SCHEMAROUTER_BENCHMARK_CASCADE_REJECT_BELOW must be lower than "
            "SCHEMAROUTER_BENCHMARK_CASCADE_ACCEPT_ABOVE"
        )
    return reject_below, accept_above, accept_margin


def _cosine(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        raise RuntimeError("cascade embedder returned a zero-norm vector")
    value = sum(a * b for a, b in zip(left, right, strict=True)) / (
        left_norm * right_norm
    )
    return max(-1.0, min(1.0, value))


def _embedding_similarities(pairs: list[tuple[str, str]]) -> list[float]:
    from benchmarks.multilingual_embedder import embed

    if not pairs:
        return []
    query = pairs[0][0]
    vectors = embed([query, *(option_text for _, option_text in pairs)])
    if len(vectors) != len(pairs) + 1:
        raise RuntimeError("cascade embedder returned the wrong number of vectors")
    query_vector, *option_vectors = vectors
    return [_cosine(query_vector, vector) for vector in option_vectors]


def _rerank_pairs(pairs: list[tuple[str, str]]) -> list[float]:
    from benchmarks.bge_contrastive import score_pairs as score_bge_pairs

    return score_bge_pairs(pairs)


def _record_telemetry(
    *,
    path_kind: str,
    top_similarity: float,
    top_margin: float,
    option_count: int,
    reject_below: float,
    accept_above: float,
    accept_margin: float,
) -> None:
    destination = os.environ.get("SCHEMAROUTER_BENCHMARK_CASCADE_TELEMETRY")
    if not destination:
        return
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "path": path_kind,
        "top_similarity": top_similarity,
        "top_margin": top_margin,
        "option_count": option_count,
        "reject_below": reject_below,
        "accept_above": accept_above,
        "accept_margin": accept_margin,
    }
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")


def score_pairs(pairs: list[tuple[str, str]]) -> list[float]:
    """Return bounded cascade scores for the already-authorized sibling choices."""
    if not pairs:
        return []
    if len({query for query, _ in pairs}) != 1:
        raise ValueError("cascade scorer requires one shared query per option batch")

    reject_below, accept_above, accept_margin = _settings()
    similarities = _embedding_similarities(pairs)
    if len(similarities) != len(pairs):
        raise RuntimeError("cascade similarity count does not match option count")

    ranked = sorted(
        enumerate(similarities),
        key=lambda item: (-item[1], item[0]),
    )
    top_index, top_similarity = ranked[0]
    runner_up_similarity = ranked[1][1] if len(ranked) > 1 else -1.0
    top_margin = top_similarity - runner_up_similarity

    if top_similarity < reject_below:
        scores = [0.0 for _ in pairs]
        path_kind = "fast_reject"
    elif top_similarity >= accept_above and top_margin >= accept_margin:
        scores = [0.0 for _ in pairs]
        scores[top_index] = 1.0
        path_kind = "fast_accept"
    else:
        scores = _rerank_pairs(pairs)
        path_kind = "reranker"

    _record_telemetry(
        path_kind=path_kind,
        top_similarity=top_similarity,
        top_margin=top_margin,
        option_count=len(pairs),
        reject_below=reject_below,
        accept_above=accept_above,
        accept_margin=accept_margin,
    )
    return scores
