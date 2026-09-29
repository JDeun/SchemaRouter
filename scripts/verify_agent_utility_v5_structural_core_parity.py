"""Verify exact DEV ranking parity between research and core structural retrieval."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_v5_catalog import (  # noqa: E402
    CATALOG_SIZES,
    build_registry,
    build_tasks,
)
from schemarouter import SchemaPlanner  # noqa: E402
from scripts.evaluate_agent_utility_v5_structural_retrieval import (  # noqa: E402
    _base_candidates,
    _rank_variant,
    _specificity_by_route,
)

PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-structural-retrieval-v2-preregistration.json"
)


def _variant() -> dict[str, Any]:
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    if prereg["status"] != "preregistered_before_confirmation_surface_generation":
        raise AssertionError("structural v2 preregistration is not frozen")
    candidate = dict(prereg["fixed_candidate"])
    return {
        "id": str(candidate["id"]),
        "tool_identifier_bonus": float(candidate["tool_identifier_bonus"]),
        "operation_family_bonus": float(candidate["operation_family_bonus"]),
        "specificity_tiebreak": bool(candidate["schema_specificity_tiebreak"]),
    }


def verify() -> dict[str, Any]:
    variant = _variant()
    tasks = build_tasks()
    row_count = 0
    supported_rows = 0
    route_positions_checked = 0

    for catalog_size in CATALOG_SIZES:
        registry = build_registry(catalog_size)
        research_planner = SchemaPlanner(
            registry,
            candidate_index=False,
        )
        core_planner = SchemaPlanner(
            registry,
            structural_retrieval=True,
        )
        specificity = _specificity_by_route(registry)

        for task in tasks:
            query = str(task["query"])
            research_ranking = _rank_variant(
                _base_candidates(research_planner, query),
                query=query,
                specificity=specificity,
                variant=variant,
            )
            core = core_planner.retrieve(query, k=10)

            research_top10 = [
                (
                    str(item["route_id"]),
                    float(item["score"]),
                )
                for item in research_ranking[:10]
            ]
            core_top10 = [
                (
                    candidate.route_id,
                    float(candidate.score),
                )
                for candidate in core.candidates
            ]

            if core_top10 != research_top10:
                raise AssertionError(
                    "structural core/research ranking mismatch: "
                    f"catalog={catalog_size} task={task['task_id']} "
                    f"research={research_top10!r} core={core_top10!r}"
                )

            row_count += 1
            route_positions_checked += len(research_top10)
            if task["required_route_ids"]:
                supported_rows += 1

    expected_rows = len(tasks) * len(CATALOG_SIZES)
    if row_count != expected_rows:
        raise AssertionError(
            f"expected {expected_rows} rows, verified {row_count}"
        )

    return {
        "schema_version": 1,
        "issue": 430,
        "candidate": variant["id"],
        "catalog_sizes": list(CATALOG_SIZES),
        "semantic_task_count": len(tasks),
        "row_count": row_count,
        "supported_row_count": supported_rows,
        "top10_positions_checked": route_positions_checked,
        "exact_route_and_score_parity": True,
        "confirmation_surface_used": False,
        "product_default_enabled": False,
        "preregistration_path": str(PREREG.relative_to(ROOT)),
        "tool_identifier_bonus": variant["tool_identifier_bonus"],
        "operation_family_bonus": variant["operation_family_bonus"],
        "specificity_tiebreak": variant["specificity_tiebreak"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = verify()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
