"""Verify #423 B2 candidate sets exactly reproduce canonical #420 B1."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_b2_catalog import (  # noqa: E402
    CATALOG_SIZES,
    TASKS,
    build_registry,
    route_ids,
)
from schemarouter import PlanRequest, SchemaPlanner  # noqa: E402
from schemarouter.planner import (  # noqa: E402
    _Candidate,
    _matched_field_qualifiers,
    _normalize,
    _semantic_substring_match,
    _tokens,
)

EXPECTED_SHA256 = "9bea0645f64ec726abe5983d9a19eefe12afb1ab6cfae65ecd87464f545f0176"
EXPECTED_ROWS = 92


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _frozen_b1_rank(registry: Any, query: str) -> list[str]:
    """Rank routes with the exact deterministic scoring surface frozen for B1."""

    planner = SchemaPlanner(registry, candidate_index=False)
    request = planner._prepare_request(PlanRequest(query=query))  # noqa: SLF001
    intent = planner.analyzer.analyze(request, registry)
    query_tokens = _tokens(query)
    concept_norms = {_normalize(concept) for concept in intent.concepts if concept}
    preferred_tools = set(intent.preferred_tools)
    preferred_endpoints = set(intent.preferred_endpoints)
    candidates: list[_Candidate] = []

    for tool in registry.tools():
        for endpoint in tool.endpoints:
            score = 0.0
            if tool.key in preferred_tools or tool.name in preferred_tools:
                score += 100.0
            endpoint_key = f"{tool.key}.{endpoint.name}"
            if endpoint_key in preferred_endpoints:
                score += 250.0

            tool_text = " ".join(
                [tool.name, tool.description, endpoint.name, endpoint.description]
            )
            score += 1.5 * len(query_tokens & _tokens(tool_text))

            matched_fields: list[str] = []
            for field in endpoint.output_fields:
                names = [
                    field.name,
                    field.semantic_id or "",
                    *field.aliases,
                    ".".join(field.projection_path),
                ]
                norms = {_normalize(name) for name in names if name}
                exact = bool(norms & concept_norms)
                lexical = any(query_tokens & _tokens(name) for name in names)
                substring = any(
                    _semantic_substring_match(concept, norm)
                    for concept in concept_norms
                    for norm in norms
                )
                if exact:
                    score += 6.0
                    matched_fields.append(field.name)
                elif lexical:
                    score += 3.0
                    matched_fields.append(field.name)
                elif substring:
                    score += 1.0
                    matched_fields.append(field.name)

                if exact or lexical or substring:
                    if _matched_field_qualifiers(query, field):
                        score += 4.0

            _, argument_sources, _, _ = planner._bind_arguments(  # noqa: SLF001
                endpoint,
                intent.arguments,
            )
            score += 2.0 * len(argument_sources)
            candidates.append(
                _Candidate(
                    tool=tool,
                    endpoint=endpoint,
                    score=score,
                    matched_fields=tuple(dict.fromkeys(matched_fields)),
                )
            )

    candidates.sort(
        key=lambda candidate: (
            -candidate.score,
            candidate.endpoint.server_projection is None,
            candidate.tool.key,
            candidate.endpoint.name,
        )
    )
    return [f"{candidate.tool.key}.{candidate.endpoint.name}" for candidate in candidates]

def candidate_manifest() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for size in CATALOG_SIZES:
        registry = build_registry(size)
        full = sorted(route_ids(registry))
        for task in TASKS:
            ranking = _frozen_b1_rank(registry, task.query)
            rows.append(
                {
                    "catalog_size": size,
                    "task_id": task.task_id,
                    "full": full,
                    "top3": sorted(ranking[:3]),
                    "top5": sorted(ranking[:5]),
                    "top10": sorted(ranking[:10]),
                    "oracle": sorted(task.required_routes),
                }
            )
    rows.sort(key=lambda row: (row["catalog_size"], row["task_id"]))
    return rows


def verify() -> dict[str, Any]:
    rows = candidate_manifest()
    actual = hashlib.sha256(_canonical(rows)).hexdigest()
    if len(rows) != EXPECTED_ROWS:
        raise RuntimeError(
            f"B2 candidate manifest row count drifted: {len(rows)} != {EXPECTED_ROWS}"
        )
    if actual != EXPECTED_SHA256:
        raise RuntimeError(
            f"B2 candidate-set identity drifted: {actual} != {EXPECTED_SHA256}"
        )
    return {
        "rows": len(rows),
        "sha256": actual,
        "status": "pass",
    }


def main() -> None:
    print(json.dumps(verify(), sort_keys=True))


if __name__ == "__main__":
    main()
