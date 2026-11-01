"""Dependency-free deterministic baseline for bounded MCP catalog exposure.

This is a lexical control, not a SchemaRouter or CrewAI integration result.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from collections.abc import Mapping, Sequence

try:
    from .catalog_fixture import public_catalog
except ImportError:
    from catalog_fixture import public_catalog


def lexical_select(
    query: str, tools: Sequence[Mapping[str, object]], *, limit: int
) -> list[Mapping[str, object]]:
    """Conservative keyword baseline; empty/unsupported queries abstain."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    terms = {term.lower() for term in query.split() if len(term) > 2}
    if not terms:
        return []
    ranked: list[tuple[int, str, Mapping[str, object]]] = []
    for tool in tools:
        description = str(tool["description"]).lower().split()
        name = str(tool["name"])
        words = set(description) | set(name.lower().split("_"))
        score = len(terms & words)
        if score:
            ranked.append((-score, name, tool))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ranked[:limit]]


def measure(size: int, *, seed: int = 0, repeats: int = 20, limit: int = 8) -> dict[str, object]:
    """Compare full exposure to lexical bounded control with stable test query."""
    if repeats < 1:
        raise ValueError("repeats must be positive")
    tools = public_catalog(size, seed=seed)
    query = "current weather forecast by city"
    elapsed_ms: list[float] = []
    selected: list[Mapping[str, object]] = []
    for _ in range(repeats):
        started = time.perf_counter()
        selected = lexical_select(query, tools, limit=limit)
        elapsed_ms.append((time.perf_counter() - started) * 1000)
    selected_names = {str(tool["name"]) for tool in selected}
    full_bytes = len(json.dumps(tools, sort_keys=True).encode("utf-8"))
    selected_bytes = len(json.dumps(selected, sort_keys=True).encode("utf-8"))
    return {
        "baseline": "lexical_control_not_crewai_or_schemarouter",
        "size": size,
        "seed": seed,
        "repeats": repeats,
        "limit": limit,
        "full_exposed_schema_bytes": full_bytes,
        "bounded_exposed_schema_bytes": selected_bytes,
        "required_tool_recall": int("weather_lookup" in selected_names),
        "selection_latency_p50_ms": statistics.median(elapsed_ms),
        "selection_latency_p95_ms": sorted(elapsed_ms)[min(repeats - 1, int(0.95 * repeats))],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    print(json.dumps(
        [measure(size, seed=args.seed, repeats=args.repeats, limit=args.limit)
         for size in (32, 128, 512)],
        indent=2,
    ))


if __name__ == "__main__":
    main()
