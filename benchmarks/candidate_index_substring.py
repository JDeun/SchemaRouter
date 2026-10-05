from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections.abc import Callable

from schemarouter import EndpointSpec, FieldSpec, PlanRequest, QueryIntent, ToolSpec
from schemarouter.planner import _CandidateIndex, _normalize, _semantic_substring_match


def _catalog(size: int) -> tuple[ToolSpec, ...]:
    return tuple(
        ToolSpec(
            name=f"catalog_tool_{index}",
            endpoints=[
                EndpointSpec(
                    name="lookup",
                    output_fields=[
                        FieldSpec(
                            name=(
                                f"material_property_{index}_thermal_conductivity"
                                if index % 250 == 0
                                else f"material_property_{index}_specific_heat_capacity"
                            )
                        )
                    ],
                    read_only=True,
                )
            ],
        )
        for index in range(size)
    )


def _legacy_lookup(index: _CandidateIndex, concepts: tuple[str, ...]) -> int:
    concept_norms = {
        _normalize(concept)
        for concept in concepts
        if concept and _normalize(concept)
    }
    refs = set()
    for concept in concept_norms:
        refs.update(index._field_norm_refs.get(concept, ()))
    for norm, norm_refs in index._field_norm_refs.items():
        if any(
            _semantic_substring_match(concept, norm)
            for concept in concept_norms
        ):
            refs.update(norm_refs)
    return len(refs)


def _measure(call: Callable[[], object], iterations: int) -> float:
    samples = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        call()
        samples.append((time.perf_counter_ns() - started) / 1_000)
    return statistics.median(samples)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=10_000)
    parser.add_argument("--iterations", type=int, default=200)
    args = parser.parse_args()

    tools = _catalog(args.size)
    build_started = time.perf_counter_ns()
    index = _CandidateIndex(1, tools)
    build_ms = (time.perf_counter_ns() - build_started) / 1_000_000

    concepts = ("conductivity",)
    request = PlanRequest(query="__no_catalog_match__")
    intent = QueryIntent(concepts=list(concepts))

    expected = _legacy_lookup(index, concepts)
    actual = len(index.endpoint_pairs(request, intent))
    if actual != expected:
        raise SystemExit(
            f"candidate mismatch: indexed={actual} legacy={expected}"
        )

    legacy_us = _measure(
        lambda: _legacy_lookup(index, concepts),
        args.iterations,
    )
    indexed_us = _measure(
        lambda: index.endpoint_pairs(request, intent),
        args.iterations,
    )

    trigram_associations = sum(
        len(norms)
        for norms in index._field_trigram_norms.values()
    )
    trigram_bound = sum(
        max(len(norm) - 2, 0)
        for norm in index._field_norm_refs
    )
    approx_container_bytes = (
        sys.getsizeof(index._field_trigram_norms)
        + sum(
            sys.getsizeof(key)
            + sys.getsizeof(norms)
            + sum(sys.getsizeof(norm) for norm in norms)
            for key, norms in index._field_trigram_norms.items()
        )
    )

    payload = {
        "catalog_size": args.size,
        "field_norm_count": len(index._field_norm_refs),
        "build_ms": round(build_ms, 3),
        "legacy_scan_median_us": round(legacy_us, 3),
        "indexed_median_us": round(indexed_us, 3),
        "speedup": round(legacy_us / indexed_us, 3) if indexed_us else None,
        "candidate_count": actual,
        "trigram_key_count": len(index._field_trigram_norms),
        "trigram_norm_associations": trigram_associations,
        "trigram_association_bound": trigram_bound,
        "approx_trigram_container_bytes": approx_container_bytes,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
