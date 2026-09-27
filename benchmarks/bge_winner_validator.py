"""Pinned winner-only BGE reranker validator for v4 research."""

from __future__ import annotations

import math
from typing import Any

MODEL_NAME = "BAAI/bge-reranker-v2-m3"
MODEL_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
MAX_LENGTH = 256

_tokenizer: Any | None = None
_model: Any | None = None


def _load() -> tuple[Any, Any]:
    global _model, _tokenizer
    if _tokenizer is None or _model is None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        _tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME,
            revision=MODEL_REVISION,
        )
        _model = AutoModelForSequenceClassification.from_pretrained(
            MODEL_NAME,
            revision=MODEL_REVISION,
        )
        _model.eval()
    return _tokenizer, _model


def unload() -> None:
    global _model, _tokenizer
    _model = None
    _tokenizer = None
    try:
        import torch

        if hasattr(torch, "cuda") and torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


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
        max_length=MAX_LENGTH,
        return_tensors="pt",
    )
    with torch.no_grad():
        logits = model(**encoded, return_dict=True).logits
    flattened = logits.reshape(logits.shape[0], -1)
    if flattened.shape[1] != 1:
        raise RuntimeError(
            f"{MODEL_NAME} returned {flattened.shape[1]} logits per pair; expected 1"
        )
    return flattened[:, 0].float().cpu().tolist()


def score_pair(query: str, option_text: str) -> float:
    values = _raw_logits([(query, option_text)])
    if len(values) != 1:
        raise RuntimeError("winner validator expected one score")
    return _sigmoid(values[0])


def score_pairs(pairs: list[tuple[str, str]]) -> list[float]:
    return [_sigmoid(value) for value in _raw_logits(pairs)]
