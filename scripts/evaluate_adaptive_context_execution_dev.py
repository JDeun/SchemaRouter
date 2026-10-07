"""Development-only execution-oracle audit for #840 on the frozen B2 corpus.

This scorer does not run a model and does not claim agent task success. It verifies that
retrieval coverage can be translated into executable deterministic task paths when the
oracle supplies the frozen task's required calls and arguments.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_b2_catalog import TASKS, build_registry  # noqa: E402
from benchmarks.agent_utility_b2_executor import DeterministicTaskExecutor  # noqa: E402
from scripts.evaluate_agent_utility_phase_a import _rank  # noqa: E402

CATALOG_SIZE = 100
K = 10


def _arguments(task_id: str, route_id: str, state: dict[str, Any]) -> dict[str, Any]:
    fixed: dict[tuple[str, str], dict[str, Any]] = {
        ("single-paper-retrieve", "papers.retrieve"): {"paper_id": "P-104"},
        ("single-paper-summary", "papers.summarize"): {"paper_id": "P-104"},
        ("single-material-retrieve", "materials.retrieve"): {"material_id": "MAT-7"},
        ("single-material-current", "materials.current"): {"material_id": "MAT-7"},
        ("single-material-history", "materials.history"): {"material_id": "MAT-7"},
        ("single-material-forecast", "materials.forecast"): {"material_id": "MAT-7"},
        ("single-inventory-create", "inventory.create"): {"item_name": "cathode-powder"},
        ("single-inventory-update", "inventory.update"): {"item_id": "INV-3"},
        ("single-inventory-delete", "inventory.delete"): {"item_id": "INV-3"},
        ("single-message-send", "messaging.send"): {
            "recipient": "analyst@example.org",
            "message": "Experiment complete.",
        },
        ("single-share", "messaging.share"): {
            "artifact_id": "ART-2",
            "recipient": "analyst@example.org",
        },
        ("single-credit-refund", "credits.refund"): {"credit_id": "CR-8"},
        ("single-runtime-restart", "runtime.restart"): {"runtime_id": "RT-2"},
        ("single-export", "exports.export"): {"artifact_id": "ART-2"},
        ("multi-paper-retrieve-summary", "papers.retrieve"): {"paper_id": "P-205"},
        ("multi-paper-retrieve-summary", "papers.summarize"): {"paper_id": "P-205"},
        ("multi-create-send", "inventory.create"): {"item_name": "anode-binder"},
        ("multi-retrieve-export", "materials.retrieve"): {"material_id": "MAT-7"},
    }
    if (task_id, route_id) in fixed:
        return dict(fixed[(task_id, route_id)])
    if route_id == "papers.search":
        return {"query": "perovskite stability" if task_id.startswith("multi-") else "solid-state battery electrolytes"}
    if route_id == "materials.search":
        return {"query": "nickel-rich cathode" if task_id.startswith("multi-") else "lithium iron phosphate"}
    if task_id == "multi-paper-search-retrieve" and route_id == "papers.retrieve":
        return {"paper_id": state["selected_paper_id"]}
    if task_id == "multi-material-search-current" and route_id == "materials.current":
        return {"material_id": state["selected_material_id"]}
    if task_id == "multi-create-share":
        if route_id == "credits.create":
            return {"amount": 100}
        if route_id == "messaging.share":
            return {"artifact_id": state["created_artifact_id"], "recipient": "analyst@example.org"}
    if task_id == "multi-create-send" and route_id == "messaging.send":
        return {"recipient": "analyst@example.org", "message": f"Created {state['created_item_id']}"}
    if task_id == "multi-retrieve-export" and route_id == "exports.export":
        return {"artifact_id": state["material_artifact_id"]}
    return {}


def evaluate() -> dict[str, Any]:
    registry = build_registry(CATALOG_SIZE)
    rows: list[dict[str, Any]] = []
    for task in TASKS:
        selected = [str(row["route_id"]) for row in _rank(registry, task.query)[:K]]
        executor = DeterministicTaskExecutor(registry, task.task_id)
        for route_id in task.required_routes:
            if route_id not in selected:
                break
            executor.execute(route_id, _arguments(task.task_id, route_id, executor.state))
        rows.append(
            {
                "task_id": task.task_id,
                "required_routes": list(task.required_routes),
                "selected_routes": selected,
                "retrieval_covered": set(task.required_routes).issubset(selected),
                "oracle_execution_complete": executor.complete,
                "attempts": len(executor.attempts),
                "errors": [attempt.error for attempt in executor.attempts if attempt.error],
            }
        )
    covered = sum(row["retrieval_covered"] for row in rows)
    completed = sum(row["oracle_execution_complete"] for row in rows)
    return {
        "schema_version": 1,
        "experiment": "adaptive-context-execution-oracle-development-v1",
        "issue": 840,
        "status": "development_scored",
        "performance_evidence": False,
        "corpus": "agent-utility B2 frozen 23-task development fixture",
        "catalog_size": CATALOG_SIZE,
        "k": K,
        "metrics": {
            "retrieval_coverage_task_rate": covered / len(rows),
            "oracle_execution_completion_rate": completed / len(rows),
        },
        "rows": rows,
        "limitations": [
            "Development-only; not held-out evidence.",
            "Oracle arguments are deterministic benchmark fixtures, not model-generated calls.",
            "This measures executability after retrieval coverage, not end-to-end agent task success.",
            "Unsupported rejection remains a separate unscored development slice.",
        ],
    }


def main() -> int:
    out = Path("benchmarks/adaptive-context-evaluation-v1/execution-oracle-dev.json")
    result = evaluate()
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
