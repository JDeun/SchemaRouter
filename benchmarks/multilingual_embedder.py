"""Research-only multilingual SentenceTransformers embedding callable.

This module is intentionally outside the SchemaRouter package dependency surface.
Install sentence-transformers explicitly in the benchmark environment.
"""

from __future__ import annotations

import os
from typing import Any

_MODEL: Any | None = None
_MODEL_NAME: str | None = None


def _model() -> Any:
    global _MODEL, _MODEL_NAME
    model_name = os.environ.get(
        "SCHEMAROUTER_BENCHMARK_EMBEDDING_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    ).strip()
    if not model_name:
        raise RuntimeError("SCHEMAROUTER_BENCHMARK_EMBEDDING_MODEL must be non-empty")
    if _MODEL is None or _MODEL_NAME != model_name:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "benchmark multilingual embeddings require sentence-transformers"
            ) from exc
        _MODEL = SentenceTransformer(model_name)
        _MODEL_NAME = model_name
    return _MODEL


def embed(texts: list[str]) -> list[list[float]]:
    if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("benchmark embedding input must contain non-empty strings")
    vectors = _model().encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return vectors.tolist()
