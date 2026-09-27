"""Research-only action-guided single-pair BGE scorer for v4 diagnostics.

The action selector may choose only among DecisionOptions already supplied by
SchemaRouter. It uses normalized endpoint action names plus trusted
operation_aliases. BGE then scores exactly one selected query-option pair; all
other bounded options receive score 0. This module does not create execution
authority and is not part of the package dependency surface.
"""

from __future__ import annotations

import json
import math
from typing import Any

from schemarouter.decisions import DecisionOption

_ACTION_TEXT_BY_ROUTE: dict[str, str] | None = None
_ACTION_VECTOR_CACHE: dict[str, list[float]] = {}


def _normalize_action_name(name: str) -> str:
    return " ".join(name.replace("_", " ").replace("-", " ").split())


def _action_text_map() -> dict[str, str]:
    global _ACTION_TEXT_BY_ROUTE
    if _ACTION_TEXT_BY_ROUTE is not None:
        return _ACTION_TEXT_BY_ROUTE

    # Imported lazily because benchmark_decision_routing.py is the executable
    # harness and is not part of the schemarouter package.
    from benchmark_decision_routing import reference_registry

    mapping: dict[str, str] = {}
    for tool in reference_registry().tools():
        for endpoint in tool.endpoints:
            parts = [_normalize_action_name(endpoint.name)]
            parts.extend(" ".join(alias.split()) for alias in endpoint.operation_aliases)
            action_text = " ; ".join(dict.fromkeys(part for part in parts if part))
            mapping[f"{tool.key}.{endpoint.name}"] = action_text
    _ACTION_TEXT_BY_ROUTE = mapping
    return mapping


def option_payload(option: DecisionOption) -> str:
    """Serialize action-only selector text plus the unchanged BGE option text."""

    action_text = _action_text_map().get(option.id)
    if not action_text:
        raise ValueError(f"missing action-only text for registered option {option.id!r}")

    label = option.label.strip() or option.id
    description = option.description.strip()
    bge_text = f"{label}\n{description}" if description else label
    return json.dumps(
        {
            "route_id": option.id,
            "action_text": action_text,
            "bge_text": bge_text,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _embed(texts: list[str]) -> list[list[float]]:
    from benchmarks.multilingual_embedder import embed

    return embed(texts)


def _bge_score_pairs(pairs: list[tuple[str, str]]) -> list[float]:
    from benchmarks.bge_reranker import score_pairs as bge_score_pairs

    return bge_score_pairs(pairs)


def _dot(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions must match")
    value = float(sum(a * b for a, b in zip(left, right, strict=True)))
    if not math.isfinite(value):
        raise ValueError("action selector produced a non-finite similarity")
    return value


def _action_vector(text: str) -> list[float]:
    cached = _ACTION_VECTOR_CACHE.get(text)
    if cached is not None:
        return cached
    vector = _embed([text])[0]
    _ACTION_VECTOR_CACHE[text] = vector
    return vector


def _decode_payload(value: str) -> dict[str, str]:
    try:
        payload: Any = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("action-guided scorer requires JSON option payloads") from exc
    if not isinstance(payload, dict):
        raise ValueError("action-guided option payload must be an object")

    result: dict[str, str] = {}
    for key in ("route_id", "action_text", "bge_text"):
        item = payload.get(key)
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"action-guided option payload requires non-empty {key}")
        result[key] = item
    return result


def score_pairs(pairs: list[tuple[str, str]]) -> list[float]:
    """Select one bounded option cheaply, then BGE-score only that pair."""

    if not pairs:
        return []
    queries = [query for query, _ in pairs]
    if any(not isinstance(query, str) or not query.strip() for query in queries):
        raise ValueError("action-guided scorer requires non-empty queries")
    query = queries[0]
    if any(other != query for other in queries[1:]):
        raise ValueError("all bounded operation-fit pairs must share one query")

    payloads = [_decode_payload(option_text) for _, option_text in pairs]
    query_vector = _embed([query])[0]
    action_scores = [
        _dot(query_vector, _action_vector(payload["action_text"]))
        for payload in payloads
    ]
    selected_index = max(
        range(len(action_scores)),
        key=lambda index: (action_scores[index], -index),
    )

    selected_payload = payloads[selected_index]
    selected_score = _bge_score_pairs(
        [(query, selected_payload["bge_text"])]
    )
    if len(selected_score) != 1:
        raise ValueError("single-pair BGE scorer returned the wrong number of scores")

    score = float(selected_score[0])
    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        raise ValueError("single-pair BGE score must be finite and in [0, 1]")

    scores = [0.0] * len(pairs)
    scores[selected_index] = score
    return scores
