"""Research-only lightweight multilingual cross-encoder scorer.

The scorer implements SchemaRouter's bounded PairwiseDecisionBackend contract:
it receives only already-authorized (query, option_text) pairs and returns one
finite confidence in [0, 1] per pair. The model is selected exclusively by
SCHEMAROUTER_BENCHMARK_RERANKER_MODEL so this module remains outside the core
dependency surface.
"""

from __future__ import annotations

import math
import os
from typing import Any

_MODEL: Any | None = None
_TOKENIZER: Any | None = None
_MODEL_NAME: str | None = None
_MAX_LENGTH = 256


def _model_name() -> str:
    value = os.environ.get("SCHEMAROUTER_BENCHMARK_RERANKER_MODEL", "").strip()
    if not value:
        raise RuntimeError(
            "SCHEMAROUTER_BENCHMARK_RERANKER_MODEL must be non-empty"
        )
    return value


def _load() -> tuple[Any, Any]:
    global _MODEL, _MODEL_NAME, _TOKENIZER

    model_name = _model_name()
    if _MODEL is None or _TOKENIZER is None or _MODEL_NAME != model_name:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        _TOKENIZER = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True,
        )
        _MODEL = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            trust_remote_code=True,
        )
        _MODEL.eval()
        _MODEL_NAME = model_name
    return _TOKENIZER, _MODEL


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def score_pairs(pairs: list[tuple[str, str]]) -> list[float]:
    """Score authorized query/operation pairs with one selected cross-encoder."""

    if not pairs:
        return []
    if any(
        not isinstance(query, str)
        or not query.strip()
        or not isinstance(option_text, str)
        or not option_text.strip()
        for query, option_text in pairs
    ):
        raise ValueError("pairwise scorer input must contain non-empty strings")

    import torch

    tokenizer, model = _load()
    encoded = tokenizer(
        [query for query, _ in pairs],
        [option_text for _, option_text in pairs],
        padding=True,
        truncation=True,
        max_length=_MAX_LENGTH,
        return_tensors="pt",
    )
    with torch.no_grad():
        logits = model(**encoded, return_dict=True).logits

    flattened = logits.reshape(logits.shape[0], -1)
    if flattened.shape[0] != len(pairs) or flattened.shape[1] != 1:
        raise RuntimeError(
            f"{_model_name()} returned logits with shape "
            f"{tuple(flattened.shape)}; expected ({len(pairs)}, 1)"
        )

    raw_scores = flattened[:, 0].float().cpu().tolist()
    scores = [_sigmoid(float(value)) for value in raw_scores]
    if len(scores) != len(pairs):
        raise RuntimeError("cross-encoder returned the wrong number of scores")
    if any(not math.isfinite(score) or not 0.0 <= score <= 1.0 for score in scores):
        raise RuntimeError("cross-encoder produced an invalid probability")
    return scores
