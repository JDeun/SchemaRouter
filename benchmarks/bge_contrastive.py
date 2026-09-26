"""Research-only contrastive BGE operation-fit scorer.

The scorer preserves the bounded pairwise contract: it receives only the already-authorized
(query, option_text) pairs and returns one confidence in [0, 1] per option.  It augments each
raw BGE relevance logit with the option's margin over its strongest sibling:

    adjusted_i = raw_i + beta * (raw_i - max(raw_j, j != i))

The beta=0 profile is exactly the existing sigmoid(raw logit) baseline.  Positive beta values
test whether sibling-relative evidence can recover supported operations without weakening
near-domain rejection.  This module is benchmark-only and adds no model dependency to core.
"""

from __future__ import annotations

import math
import os
from typing import Any

_MODEL_NAME = os.environ.get(
    "SCHEMAROUTER_BENCHMARK_RERANKER_MODEL",
    "BAAI/bge-reranker-v2-m3",
)
_BETA = float(os.environ.get("SCHEMAROUTER_BENCHMARK_CONTRASTIVE_BETA", "0"))
if not math.isfinite(_BETA) or _BETA < 0:
    raise RuntimeError("SCHEMAROUTER_BENCHMARK_CONTRASTIVE_BETA must be finite and >= 0")

_tokenizer: Any | None = None
_model: Any | None = None


def _load() -> tuple[Any, Any]:
    global _model, _tokenizer
    if _tokenizer is None or _model is None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        _tokenizer = AutoTokenizer.from_pretrained(_MODEL_NAME)
        _model = AutoModelForSequenceClassification.from_pretrained(_MODEL_NAME)
        _model.eval()
    return _tokenizer, _model


def _raw_logits(pairs: list[tuple[str, str]]) -> list[float]:
    import torch

    if not pairs:
        return []

    tokenizer, model = _load()
    encoded = tokenizer(
        [query for query, _ in pairs],
        [option for _, option in pairs],
        padding=True,
        truncation=True,
        max_length=256,
        return_tensors="pt",
    )
    with torch.no_grad():
        logits = model(**encoded, return_dict=True).logits
    flattened = logits.reshape(logits.shape[0], -1)
    if flattened.shape[1] != 1:
        raise RuntimeError(
            f"{_MODEL_NAME} returned {flattened.shape[1]} logits per pair; expected 1"
        )
    return flattened[:, 0].float().cpu().tolist()


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def score_pairs(pairs: list[tuple[str, str]]) -> list[float]:
    """Return sibling-contrastive BGE confidences for bounded operation choices."""
    raw = _raw_logits(pairs)
    if len(raw) <= 1:
        return [_sigmoid(value) for value in raw]

    scores: list[float] = []
    for index, value in enumerate(raw):
        strongest_sibling = max(other for j, other in enumerate(raw) if j != index)
        margin = value - strongest_sibling
        scores.append(_sigmoid(value + _BETA * margin))
    return scores
