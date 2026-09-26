from __future__ import annotations

import os
from typing import Any

_MODEL_NAME = os.environ.get(
    "SCHEMAROUTER_BENCHMARK_RERANKER_MODEL",
    "BAAI/bge-reranker-v2-m3",
)
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


def score_pairs(pairs: list[tuple[str, str]]) -> list[float]:
    """Return sigmoid-normalized BGE reranker confidence for bounded query-option pairs."""
    import torch

    if not pairs:
        return []

    tokenizer, model = _load()
    queries = [query for query, _ in pairs]
    options = [option for _, option in pairs]
    encoded = tokenizer(
        queries,
        options,
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
    return torch.sigmoid(flattened[:, 0].float()).cpu().tolist()
