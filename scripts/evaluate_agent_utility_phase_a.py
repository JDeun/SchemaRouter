"""Evaluate #418 Phase-A retrieval coverage and context compression."""

from __future__ import annotations

import argparse
import inspect
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_v1_catalog import (  # noqa: E402
    CATALOG_SIZES,
    K_VALUES,
    TASKS,
    build_registry,
)
from schemarouter import PlanRequest, SchemaPlanner  # noqa: E402


def _endpoint_document(tool: Any, endpoint: Any) -> dict[str, Any]:
    return {
        "tool": tool.key,
        "tool_description": tool.description,
        "endpoint": endpoint.name,
        "endpoint_description": endpoint.description,
        "read_only": endpoint.read_only,
        "destructive": endpoint.destructive,
        "parameters": [
            {
                "name": parameter.name,
                "description": parameter.description,
                "required": parameter.required,
                "schema": parameter.json_schema,
            }
            for parameter in endpoint.parameters
        ],
        "outputs": [
            {
                "name": field.name,
                "semantic_id": field.semantic_id,
                "description": field.description,
                "schema": field.json_schema,
                "unit": field.unit,
                "dimension": (
                    field.unit_normalization.dimension
                    if field.unit_normalization is not None
                    else None
                ),
                "canonical_unit": (
                    field.unit_normalization.canonical_unit
                    if field.unit_normalization is not None
                    else None
                ),
                "qualifiers": field.qualifiers,
            }
            for field in endpoint.output_fields
        ],
    }


def _encoded_size(documents: list[dict[str, Any]]) -> dict[str, int]:
    text = json.dumps(
        documents,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "characters": len(text),
        "utf8_bytes": len(text.encode("utf-8")),
    }


def _rank(registry: Any, query: str) -> list[dict[str, Any]]:
    planner = SchemaPlanner(registry, candidate_index=False)
    request = planner._prepare_request(PlanRequest(query=query))  # noqa: SLF001
    intent = planner.analyzer.analyze(request, registry)
    if inspect.isawaitable(intent):
        raise RuntimeError("Phase-A requires synchronous deterministic analyzer")
    candidates = planner._semantic_recall_catalog(request, intent)  # noqa: SLF001
    candidates.sort(
        key=lambda candidate: (
            -candidate.score,
            candidate.endpoint.server_projection is None,
            candidate.tool.key,
            candidate.endpoint.name,
        )
    )
    return [
        {
            "route_id": f"{candidate.tool.key}.{candidate.endpoint.name}",
            "score": candidate.score,
            "document": _endpoint_document(candidate.tool, candidate.endpoint),
        }
        for candidate in candidates
    ]


def _reciprocal_rank(ranking: list[str], route_id: str) -> float:
    try:
        return 1.0 / (ranking.index(route_id) + 1)
    except ValueError:
        return 0.0


def _ndcg_at_k(ranking: list[str], relevant: set[str], k: int) -> float:
    dcg = 0.0
    for index, route_id in enumerate(ranking[:k], start=1):
        if route_id in relevant:
            dcg += 1.0 / math.log2(index + 1)
    ideal_hits = min(len(relevant), k)
    idcg = sum(
        1.0 / math.log2(index + 1)
        for index in range(1, ideal_hits + 1)
    )
    return dcg / idcg if idcg else 0.0


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "p95": None,
            "min": None,
            "max": None,
        }
    ordered = sorted(values)
    position = 0.95 * (len(ordered) - 1)
    lo = math.floor(position)
    hi = math.ceil(position)
    if lo == hi:
        p95 = ordered[lo]
    else:
        weight = position - lo
        p95 = ordered[lo] * (1.0 - weight) + ordered[hi] * weight
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "p95": p95,
        "min": min(values),
        "max": max(values),
    }


def evaluate() -> dict[str, Any]:
    task_rows = [
        {
            "task_id": task.task_id,
            "query": task.query,
            "required_routes": list(task.required_routes),
            "kind": task.kind,
        }
        for task in TASKS
    ]

    results: dict[str, Any] = {
        "experiment": "0.14-agent-utility-phase-a-v1",
        "issue": 418,
        "phase": "A",
        "conditions": ["FULL", "SR-1", "SR-3", "SR-5", "SR-10"],
        "catalog_sizes": {},
        "policy": {
            "llm_called": False,
            "retriever": "current-main SchemaPlanner deterministic scorer",
            "candidate_index": False,
            "k_values": list(K_VALUES),
            "top1_is_diagnostic_only": True,
            "test_rows_used_for_tuning": False,
        },
    }

    for size in CATALOG_SIZES:
        registry = build_registry(size)
        full_documents = [
            _endpoint_document(tool, endpoint)
            for tool in sorted(registry.tools(), key=lambda item: item.key)
            for endpoint in sorted(tool.endpoints, key=lambda item: item.name)
        ]
        full_size = _encoded_size(full_documents)

        rows: list[dict[str, Any]] = []
        required_total = 0
        recall_hits = {k: 0 for k in K_VALUES}
        task_covered = {k: 0 for k in K_VALUES}
        single_covered = {k: 0 for k in K_VALUES}
        multi_covered = {k: 0 for k in K_VALUES}
        single_count = 0
        multi_count = 0
        rr_values: list[float] = []
        ndcg_values = {k: [] for k in K_VALUES}
        context_ratios = {k: [] for k in K_VALUES}
        context_bytes = {k: [] for k in K_VALUES}
        candidate_counts = {k: [] for k in K_VALUES}

        for task in task_rows:
            ranked = _rank(registry, str(task["query"]))
            ranking = [str(row["route_id"]) for row in ranked]
            required = set(str(value) for value in task["required_routes"])
            required_total += len(required)
            if task["kind"] == "single":
                single_count += 1
            else:
                multi_count += 1

            task_result: dict[str, Any] = {
                **task,
                "ranking": [
                    {
                        "route_id": row["route_id"],
                        "score": row["score"],
                    }
                    for row in ranked[:10]
                ],
                "required_route_ranks": {
                    route_id: (
                        ranking.index(route_id) + 1
                        if route_id in ranking
                        else None
                    )
                    for route_id in sorted(required)
                },
                "conditions": {},
            }

            rr_values.extend(
                _reciprocal_rank(ranking, route_id)
                for route_id in required
            )

            for k in K_VALUES:
                selected = ranked[:k]
                selected_routes = {
                    str(row["route_id"])
                    for row in selected
                }
                hits = len(required.intersection(selected_routes))
                recall_hits[k] += hits
                covered = hits == len(required)
                task_covered[k] += int(covered)
                if task["kind"] == "single":
                    single_covered[k] += int(covered)
                else:
                    multi_covered[k] += int(covered)

                selected_size = _encoded_size(
                    [row["document"] for row in selected]
                )
                ratio = (
                    selected_size["utf8_bytes"] / full_size["utf8_bytes"]
                    if full_size["utf8_bytes"]
                    else 0.0
                )
                context_ratios[k].append(ratio)
                context_bytes[k].append(float(selected_size["utf8_bytes"]))
                candidate_counts[k].append(float(len(selected)))
                ndcg = _ndcg_at_k(ranking, required, k)
                ndcg_values[k].append(ndcg)
                task_result["conditions"][f"SR-{k}"] = {
                    "required_hits": hits,
                    "required_count": len(required),
                    "all_required_covered": covered,
                    "ndcg": ndcg,
                    "candidate_count": len(selected),
                    "schema_context_characters": selected_size["characters"],
                    "schema_context_utf8_bytes": selected_size["utf8_bytes"],
                    "context_ratio_vs_full": ratio,
                }

            rows.append(task_result)

        catalog_metrics: dict[str, Any] = {
            "endpoint_count": size,
            "task_count": len(task_rows),
            "single_task_count": single_count,
            "multi_task_count": multi_count,
            "required_route_instances": required_total,
            "full_schema_context": full_size,
            "mean_reciprocal_rank_required_routes": statistics.fmean(rr_values),
            "k": {},
            "rows": rows,
        }

        for k in K_VALUES:
            catalog_metrics["k"][str(k)] = {
                "required_route_recall": recall_hits[k] / required_total,
                "all_required_task_coverage": task_covered[k] / len(task_rows),
                "single_task_coverage": (
                    single_covered[k] / single_count
                    if single_count
                    else 0.0
                ),
                "multi_task_coverage": (
                    multi_covered[k] / multi_count
                    if multi_count
                    else 0.0
                ),
                "mean_ndcg": statistics.fmean(ndcg_values[k]),
                "schema_context_bytes": _distribution(context_bytes[k]),
                "context_ratio_vs_full": _distribution(context_ratios[k]),
                "candidate_count": _distribution(candidate_counts[k]),
            }

        results["catalog_sizes"][str(size)] = catalog_metrics

    recall10 = [
        results["catalog_sizes"][str(size)]["k"]["10"][
            "required_route_recall"
        ]
        for size in CATALOG_SIZES
    ]
    results["phase_a_gate"] = {
        "required_route_recall_at_10_min_097_all_catalog_sizes": all(
            value >= 0.97 for value in recall10
        ),
        "minimum_recall_at_10": min(recall10),
        "phase_b_eligible": all(value >= 0.97 for value in recall10),
    }
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "phase_a_gate": result["phase_a_gate"],
                "catalog_sizes": {
                    size: {
                        "mrr": metrics[
                            "mean_reciprocal_rank_required_routes"
                        ],
                        "k": metrics["k"],
                        "full_schema_context": metrics[
                            "full_schema_context"
                        ],
                    }
                    for size, metrics in result["catalog_sizes"].items()
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
