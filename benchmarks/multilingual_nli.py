"""Research-only multilingual NLI operation entailment scorer.

The scorer preserves SchemaRouter's bounded pairwise contract. It receives only
already-authorized (query, option_text) pairs and returns one entailment
probability per option. The NLI model is loaded lazily so core SchemaRouter has
no runtime dependency on it.

Premise: user query
Hypothesis: "The user is requesting exactly this operation: {operation_text}"
"""

from __future__ import annotations

import os
from typing import Any

_MODEL_NAME = os.environ.get(
    "SCHEMAROUTER_BENCHMARK_NLI_MODEL",
    "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli",
)
_MAX_LENGTH = int(os.environ.get("SCHEMAROUTER_BENCHMARK_NLI_MAX_LENGTH", "256"))
_BATCH_SIZE = int(os.environ.get("SCHEMAROUTER_BENCHMARK_NLI_BATCH_SIZE", "32"))
if _MAX_LENGTH < 16:
    raise RuntimeError("SCHEMAROUTER_BENCHMARK_NLI_MAX_LENGTH must be >= 16")
if _BATCH_SIZE < 1:
    raise RuntimeError("SCHEMAROUTER_BENCHMARK_NLI_BATCH_SIZE must be >= 1")

_tokenizer: Any | None = None
_model: Any | None = None
_entailment_index: int | None = None


def _label_index(id2label: dict[int, str] | dict[str, str]) -> int:
    matches: list[int] = []
    for raw_index, raw_label in id2label.items():
        label = str(raw_label).strip().casefold()
        if "entail" in label:
            matches.append(int(raw_index))
    if len(matches) != 1:
        raise RuntimeError(
            f"{_MODEL_NAME} must expose exactly one entailment label; got {id2label!r}"
        )
    return matches[0]


def _load() -> tuple[Any, Any, int]:
    global _tokenizer, _model, _entailment_index
    if _tokenizer is None or _model is None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        _tokenizer = AutoTokenizer.from_pretrained(_MODEL_NAME)
        _model = AutoModelForSequenceClassification.from_pretrained(_MODEL_NAME)
        _model.eval()
        _entailment_index = _label_index(dict(_model.config.id2label))
    assert _entailment_index is not None
    return _tokenizer, _model, _entailment_index


def _hypothesis(option_text: str) -> str:
    compact = " ; ".join(
        part.strip()
        for part in option_text.splitlines()
        if part.strip()
    )
    return f"The user is requesting exactly this operation: {compact}"


def score_pairs(pairs: list[tuple[str, str]]) -> list[float]:
    """Return NLI entailment probabilities for bounded operation choices."""
    import torch

    if not pairs:
        return []

    tokenizer, model, entailment_index = _load()
    scores: list[float] = []
    for start in range(0, len(pairs), _BATCH_SIZE):
        batch = pairs[start : start + _BATCH_SIZE]
        encoded = tokenizer(
            [query for query, _ in batch],
            [_hypothesis(option) for _, option in batch],
            padding=True,
            truncation=True,
            max_length=_MAX_LENGTH,
            return_tensors="pt",
        )
        with torch.inference_mode():
            logits = model(**encoded, return_dict=True).logits
            probabilities = torch.softmax(logits.float(), dim=-1)
        if entailment_index >= probabilities.shape[1]:
            raise RuntimeError(
                f"{_MODEL_NAME} entailment label index {entailment_index} "
                f"is outside logits width {probabilities.shape[1]}"
            )
        scores.extend(
            probabilities[:, entailment_index].detach().cpu().tolist()
        )

    if len(scores) != len(pairs):
        raise RuntimeError(
            f"{_MODEL_NAME} returned {len(scores)} scores for {len(pairs)} pairs"
        )
    return [float(score) for score in scores]
