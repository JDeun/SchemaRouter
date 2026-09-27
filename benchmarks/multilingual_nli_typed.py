"""Research-only multilingual typed NLI evidence for registered operations.

The model never selects a route. It scores one already-selected registered operation
and exposes contradiction / neutral / entailment probabilities as distinct evidence.
"""

from __future__ import annotations

import os
from typing import Any

MODEL_NAME = os.environ.get(
    "SCHEMAROUTER_BENCHMARK_TYPED_NLI_MODEL",
    "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli",
)
MODEL_REVISION = os.environ.get(
    "SCHEMAROUTER_BENCHMARK_TYPED_NLI_REVISION",
    "0a71e92a985b6e1ad1828cf67ce9c459639c1dca",
)
MAX_LENGTH = int(
    os.environ.get("SCHEMAROUTER_BENCHMARK_TYPED_NLI_MAX_LENGTH", "256")
)
BATCH_SIZE = int(
    os.environ.get("SCHEMAROUTER_BENCHMARK_TYPED_NLI_BATCH_SIZE", "32")
)
if MAX_LENGTH < 16:
    raise RuntimeError("SCHEMAROUTER_BENCHMARK_TYPED_NLI_MAX_LENGTH must be >= 16")
if BATCH_SIZE < 1:
    raise RuntimeError("SCHEMAROUTER_BENCHMARK_TYPED_NLI_BATCH_SIZE must be >= 1")

_tokenizer: Any | None = None
_model: Any | None = None
_label_indexes: dict[str, int] | None = None


def _resolve_label_indexes(
    id2label: dict[int, str] | dict[str, str],
) -> dict[str, int]:
    expected = {
        "contradiction": "contrad",
        "neutral": "neutral",
        "entailment": "entail",
    }
    resolved: dict[str, int] = {}
    for canonical, needle in expected.items():
        matches = [
            int(raw_index)
            for raw_index, raw_label in id2label.items()
            if needle in str(raw_label).strip().casefold()
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"{MODEL_NAME} must expose exactly one {canonical} label; "
                f"got {id2label!r}"
            )
        resolved[canonical] = matches[0]
    if len(set(resolved.values())) != 3:
        raise RuntimeError(
            f"{MODEL_NAME} NLI labels must map to three distinct indexes: "
            f"{resolved!r}"
        )
    return resolved


def _load() -> tuple[Any, Any, dict[str, int]]:
    global _tokenizer, _model, _label_indexes
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
        _label_indexes = _resolve_label_indexes(dict(_model.config.id2label))
    assert _label_indexes is not None
    return _tokenizer, _model, _label_indexes


def hypothesis(operation_text: str) -> str:
    compact = " ; ".join(
        part.strip()
        for part in operation_text.splitlines()
        if part.strip()
    )
    return (
        "The user's request is supported by exactly this registered operation: "
        f"{compact}"
    )


def score_pairs_typed(
    pairs: list[tuple[str, str]],
) -> list[dict[str, float]]:
    """Return three-class typed NLI probabilities for bounded query/operation pairs."""
    import torch

    if not pairs:
        return []

    tokenizer, model, indexes = _load()
    output: list[dict[str, float]] = []
    for start in range(0, len(pairs), BATCH_SIZE):
        batch = pairs[start : start + BATCH_SIZE]
        encoded = tokenizer(
            [query for query, _ in batch],
            [hypothesis(option) for _, option in batch],
            padding=True,
            truncation=True,
            max_length=MAX_LENGTH,
            return_tensors="pt",
        )
        with torch.inference_mode():
            logits = model(**encoded, return_dict=True).logits
            probabilities = torch.softmax(logits.float(), dim=-1)

        width = int(probabilities.shape[1])
        if any(index >= width for index in indexes.values()):
            raise RuntimeError(
                f"{MODEL_NAME} label index outside logits width {width}: "
                f"{indexes!r}"
            )

        for row in probabilities.detach().cpu().tolist():
            typed = {
                name: float(row[index])
                for name, index in indexes.items()
            }
            total = sum(typed.values())
            if not 0.999 <= total <= 1.001:
                raise RuntimeError(
                    f"{MODEL_NAME} typed NLI probabilities do not sum to one: "
                    f"{typed!r}"
                )
            output.append(typed)

    if len(output) != len(pairs):
        raise RuntimeError(
            f"{MODEL_NAME} returned {len(output)} results for {len(pairs)} pairs"
        )
    return output


def score_pair_typed(query: str, operation_text: str) -> dict[str, float]:
    rows = score_pairs_typed([(query, operation_text)])
    if len(rows) != 1:
        raise RuntimeError("typed NLI scorer expected exactly one result")
    return rows[0]


def unload() -> None:
    global _tokenizer, _model, _label_indexes
    _tokenizer = None
    _model = None
    _label_indexes = None
    try:
        import torch

        if hasattr(torch, "cuda") and torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
