"""Development-only #840 adaptive-context evaluation on the frozen 23-task corpus."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_v1_catalog import TASKS, build_registry  # noqa: E402
from scripts.evaluate_agent_utility_phase_a import (  # noqa: E402
    _encoded_size,
    _endpoint_document,
    _rank,
)

CATALOG_SIZE = 100
K = 10


def _route_fields(registry: Any) -> dict[str, set[str]]:
    return {
        f"{tool.key}.{endpoint.name}": {
            field.semantic_id or field.name for field in endpoint.output_fields
        }
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }


def evaluate() -> dict[str, Any]:
    registry = build_registry(CATALOG_SIZE)
    fields = _route_fields(registry)
    full_documents = [
        _endpoint_document(tool, endpoint)
        for tool in sorted(registry.tools(), key=lambda item: item.key)
        for endpoint in sorted(tool.endpoints, key=lambda item: item.name)
    ]
    full_bytes = _encoded_size(full_documents)["utf8_bytes"]

    stateless_exposed = 0
    session_exposed: set[str] = set()
    session_exposed_bytes = 0
    route_hits = 0
    route_total = 0
    field_hits = 0
    field_total = 0
    task_success = 0
    rows: list[dict[str, Any]] = []

    for task in TASKS:
        ranked = _rank(registry, task.query)[:K]
        selected = [str(row["route_id"]) for row in ranked]
        required = set(task.required_routes)
        hits = required.intersection(selected)
        route_hits += len(hits)
        route_total += len(required)
        covered = hits == required
        task_success += int(covered)

        required_fields = set().union(*(fields[route] for route in required))
        selected_fields = set().union(*(fields[route] for route in selected))
        field_hits += len(required_fields.intersection(selected_fields))
        field_total += len(required_fields)

        stateless_exposed += len(selected)
        newly_exposed = [row for row in ranked if str(row["route_id"]) not in session_exposed]
        session_exposed.update(str(row["route_id"]) for row in newly_exposed)
        session_exposed_bytes += _encoded_size(
            [row["document"] for row in newly_exposed]
        )["utf8_bytes"]

        rows.append(
            {
                "task_id": task.task_id,
                "required_routes": sorted(required),
                "selected_routes": selected,
                "all_required_covered": covered,
                "new_schema_routes": [str(row["route_id"]) for row in newly_exposed],
            }
        )

    stateless_bytes = sum(
        _encoded_size([row["document"] for row in _rank(registry, task.query)[:K]])[
            "utf8_bytes"
        ]
        for task in TASKS
    )
    return {
        "schema_version": 1,
        "experiment": "adaptive-context-agent-utility-development-v1",
        "issue": 840,
        "status": "development_scored",
        "performance_evidence": False,
        "corpus": "agent-utility-v1 frozen 23-task development fixture",
        "catalog_size": CATALOG_SIZE,
        "k": K,
        "metrics": {
            "required_route_recall": route_hits / route_total,
            "required_field_recall": field_hits / field_total if field_total else 1.0,
            "task_success_proxy": task_success / len(TASKS),
            "stateless_schema_candidate_exposures": stateless_exposed,
            "session_unique_schema_candidate_exposures": len(session_exposed),
            "stateless_schema_context_utf8_bytes": stateless_bytes,
            "session_schema_context_utf8_bytes": session_exposed_bytes,
            "session_context_ratio_vs_stateless": (
                session_exposed_bytes / stateless_bytes if stateless_bytes else 0.0
            ),
            "full_catalog_schema_context_utf8_bytes": full_bytes,
            "median_new_schema_candidates_per_task": statistics.median(
                len(row["new_schema_routes"]) for row in rows
            ),
            "unsupported_rejection": None,
        },
        "rows": rows,
        "limitations": [
            "Development-only fixture; not held-out evidence.",
            "Task success is a deterministic all-required-routes-covered proxy, "
            "not execution success.",
            "Required-field recall is measured from output semantic fields on selected routes.",
            "This frozen fixture contains no unsupported tasks, so unsupported "
            "rejection is unscored.",
            "Session exposure models duplicate suppression only; no post-hoc routing "
            "tuning is applied.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/adaptive-context-evaluation-v1/agent-utility-dev.json"),
    )
    args = parser.parse_args()
    result = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
