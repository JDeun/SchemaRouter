"""Reviewed, deterministic CPU-only search grammar (no generated Python code).

Configurations change weights of registered retrieval features. They never
change a tool registry, required schema, permissions, or execution gate.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from typing import Any

FEATURES = ("base", "token", "trigram", "field", "identifier")
BASE = {"base": 3.0, "token": 0.0, "trigram": 0.0, "field": 0.0, "identifier": 0.0}
BOUNDS = {
    "base": (0.1, 6.0),
    "token": (0.0, 8.0),
    "trigram": (0.0, 8.0),
    "field": (0.0, 8.0),
    "identifier": (0.0, 8.0),
}
WORDS = re.compile(r"[\w]+", re.UNICODE)


def validate(config: Any) -> dict[str, float]:
    if not isinstance(config, dict) or set(config) != set(FEATURES):
        raise ValueError("configuration must contain only reviewed features")
    checked = {}
    for name in FEATURES:
        value = config[name]
        if type(value) not in (float, int) or not BOUNDS[name][0] <= value <= BOUNDS[name][1]:
            raise ValueError(f"unregistered or nonfinite search weight: {name}")
        checked[name] = round(float(value), 4)
    return checked


def fingerprint(config: dict[str, float]) -> str:
    return hashlib.sha256(
        json.dumps(validate(config), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def tokens(text: str) -> set[str]:
    return {word.casefold() for word in WORDS.findall(text) if word}


def trigrams(text: str) -> set[str]:
    compact = "".join(ch for ch in text.casefold() if ch.isalnum())
    if len(compact) < 3:
        return {compact} if compact else set()
    return {compact[index:index + 3] for index in range(len(compact) - 2)}


def overlap(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right) if left and right else 0.0


def rank(query: str, candidates: list[dict[str, Any]], config: dict[str, float]) -> list[str]:
    """Use query and public candidate metadata ONLY. Never receive task gold."""
    weights = validate(config)
    query_words, query_grams = tokens(query), trigrams(query)
    scored = []
    for index, item in enumerate(candidates):
        route_id = item["route_id"]
        if not isinstance(route_id, str) or not route_id:
            raise ValueError("candidate route IDs must be nonempty")
        lexical = " ".join(str(item.get(key, "")) for key in (
            "tool_description", "endpoint_description", "tool", "endpoint",
        ))
        fields = " ".join(
            " ".join(str(field.get(key) or "") for key in (
                "name", "semantic_id", "description", "unit",
            ))
            for field in item.get("output_fields", [])
        )
        matched = " ".join(str(value) for value in item.get("matched_fields", []))
        ids = f"{route_id} {item.get('tool', '')} {item.get('endpoint', '')}"
        score = (
            weights["base"] / (index + 1)
            + weights["token"] * overlap(query_words, tokens(lexical))
            + weights["trigram"] * overlap(query_grams, trigrams(lexical))
            + weights["field"] * overlap(query_words, tokens(fields + " " + matched))
            + weights["identifier"] * overlap(query_words, tokens(ids))
        )
        scored.append((-score, index, route_id))
    return [route_id for _, _, route_id in sorted(scored)]


def generate(
    rng: random.Random, previous: dict[str, float] | None, other: dict[str, float] | None,
) -> dict[str, float]:
    """Exploration + mutation/crossover; adaptive parent depends on prior results."""
    if previous is None or rng.random() < 0.30:
        return validate({
            name: rng.uniform(*BOUNDS[name]) for name in FEATURES
        })
    new = validate(previous)
    if other is not None and rng.random() < 0.35:
        for name in FEATURES:
            if rng.random() < 0.5:
                new[name] = other[name]
    for _ in range(rng.randint(1, 3)):
        key = rng.choice(FEATURES)
        lower, upper = BOUNDS[key]
        new[key] = min(upper, max(lower, new[key] + rng.gauss(0, (upper - lower) / 5)))
    return validate(new)
