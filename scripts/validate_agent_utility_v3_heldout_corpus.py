"""Validate a frozen #432 held-out corpus before any scoring.

This validator does not generate benchmark content. It checks that a future corpus
matches the preregistered 780-slot authoring plan and records the hashes required
before inference.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUTHORING_SCRIPT = ROOT / "scripts" / "generate_agent_utility_v3_heldout_authoring_plan.py"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_CATALOGS = (100, 250, 500, 1000)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _normalized_query(value: str) -> str:
    return " ".join(value.casefold().split())


def _authoring_plan() -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("v3_authoring_plan", AUTHORING_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load v3 authoring-plan generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_authoring_plan()


def _require_sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or HEX64.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256 hex string")
    return value


def _validate_catalogs(value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError("catalogs must be an object")

    expected_keys = {str(size) for size in EXPECTED_CATALOGS}
    if set(value) != expected_keys:
        raise ValueError(
            f"catalog keys must be exactly {sorted(expected_keys)}"
        )

    for size in EXPECTED_CATALOGS:
        row = value[str(size)]
        if not isinstance(row, dict):
            raise ValueError(f"catalog {size} metadata must be an object")
        if row.get("endpoint_count") != size:
            raise ValueError(
                f"catalog {size} endpoint_count must equal {size}"
            )
        _require_sha256(row.get("sha256"), field=f"catalogs.{size}.sha256")


def validate_corpus(data: dict[str, Any]) -> dict[str, Any]:
    plan = _authoring_plan()

    if data.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    if data.get("issue") != 432:
        raise ValueError("issue must be 432")
    if data.get("benchmark") != plan["benchmark"]:
        raise ValueError("benchmark identity does not match preregistration")
    if data.get("authoring_slots_sha256") != plan["slots_sha256"]:
        raise ValueError("authoring slot hash does not match the frozen plan")

    revision = data.get("generator_source_revision")
    if not isinstance(revision, str) or HEX40.fullmatch(revision) is None:
        raise ValueError("generator_source_revision must be a 40-char lowercase git SHA")

    _validate_catalogs(data.get("catalogs"))
    _require_sha256(
        data.get("candidate_set_manifest_sha256"),
        field="candidate_set_manifest_sha256",
    )

    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("tasks must be an array")
    if len(tasks) != plan["semantic_task_count"]:
        raise ValueError(
            f"expected {plan['semantic_task_count']} tasks, got {len(tasks)}"
        )

    expected_slots = {
        slot["semantic_task_id"]: slot
        for slot in plan["slots"]
    }
    seen_ids: set[str] = set()
    seen_queries: set[str] = set()

    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise ValueError(f"tasks[{index}] must be an object")

        for forbidden in ("queries", "translations", "scores", "model_output", "result"):
            if forbidden in task:
                raise ValueError(
                    f"tasks[{index}] contains forbidden field {forbidden!r}"
                )

        task_id = task.get("semantic_task_id")
        if not isinstance(task_id, str) or task_id not in expected_slots:
            raise ValueError(f"tasks[{index}] has unknown semantic_task_id")
        if task_id in seen_ids:
            raise ValueError(f"duplicate semantic_task_id: {task_id}")
        seen_ids.add(task_id)

        slot = expected_slots[task_id]
        if task.get("task_stratum") != slot["task_stratum"]:
            raise ValueError(f"{task_id} task_stratum drifted")
        if task.get("language") != slot["language"]:
            raise ValueError(f"{task_id} language drifted")

        query = task.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"{task_id} query must be non-empty")
        normalized = _normalized_query(query)
        if normalized in seen_queries:
            raise ValueError(f"duplicate normalized query: {task_id}")
        seen_queries.add(normalized)

        supported = task.get("supported")
        if not isinstance(supported, bool):
            raise ValueError(f"{task_id} supported must be boolean")

        routes = task.get("required_routes")
        if (
            not isinstance(routes, list)
            or any(not isinstance(route, str) or not route for route in routes)
            or len(routes) != len(set(routes))
        ):
            raise ValueError(f"{task_id} required_routes must be unique strings")
        if supported and not routes:
            raise ValueError(f"{task_id} supported task needs required_routes")
        if not supported and routes:
            raise ValueError(f"{task_id} unsupported task must not declare gold routes")

        if slot["task_stratum"] in {"missing_capability_unsupported", "out_of_domain"}:
            if supported:
                raise ValueError(f"{task_id} must be unsupported by preregistered stratum")

        executor_fixture = task.get("executor_fixture")
        if not isinstance(executor_fixture, dict) or not executor_fixture:
            raise ValueError(f"{task_id} executor_fixture must be a non-empty object")

        expected_outcome = task.get("expected_outcome")
        if not isinstance(expected_outcome, dict) or not expected_outcome:
            raise ValueError(f"{task_id} expected_outcome must be a non-empty object")

    if seen_ids != set(expected_slots):
        missing = sorted(set(expected_slots) - seen_ids)
        raise ValueError(f"missing semantic_task_id values: {missing[:5]}")

    expected_tasks_sha = _sha(tasks)
    if data.get("tasks_sha256") != expected_tasks_sha:
        raise ValueError("tasks_sha256 does not match canonical task content")

    return {
        "issue": 432,
        "task_count": len(tasks),
        "unique_query_count": len(seen_queries),
        "tasks_sha256": expected_tasks_sha,
        "authoring_slots_sha256": plan["slots_sha256"],
        "catalog_sizes": list(EXPECTED_CATALOGS),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    args = parser.parse_args()

    data = json.loads(args.corpus.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("held-out corpus root must be a JSON object")
    print(json.dumps(validate_corpus(data), sort_keys=True))


if __name__ == "__main__":
    main()
