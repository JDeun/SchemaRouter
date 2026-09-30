"""Validate the frozen #431 corrective corpus before any model inference."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from scripts.agent_utility_generated_common import (
    CORRECTIVE_CONDITIONS,
    catalog_manifest,
    sha256_json,
)
from scripts.agent_utility_prior_query_guard import (
    assert_no_prior_query_overlap,
    known_prior_query_manifest,
    normalize_query,
)
from scripts.generate_agent_utility_v6_corrective_authoring_plan import (
    build_authoring_plan,
)

HEX40 = re.compile(r"^[0-9a-f]{40}$")
CATALOGS = (100, 250, 500)


def validate_corpus(data: dict[str, Any]) -> dict[str, Any]:
    plan = build_authoring_plan()
    if data.get("schema_version") != 1 or data.get("issue") != 431:
        raise ValueError("incorrect corrective corpus identity")
    if data.get("experiment") != "execution-state-aware-corrective-retrieval-v1":
        raise ValueError("incorrect corrective experiment identity")
    if data.get("authoring_slots_sha256") != plan["slots_sha256"]:
        raise ValueError("corrective authoring slot hash drifted")
    revision = data.get("generator_source_revision")
    if not isinstance(revision, str) or HEX40.fullmatch(revision) is None:
        raise ValueError("generator_source_revision must be a git SHA")

    expected_catalogs = catalog_manifest(CATALOGS)
    if data.get("catalogs") != expected_catalogs:
        raise ValueError("corrective catalog manifest drifted")

    condition_manifest = data.get("condition_manifest")
    if not isinstance(condition_manifest, dict):
        raise ValueError("condition_manifest must be an object")
    if condition_manifest.get("conditions") != list(CORRECTIVE_CONDITIONS):
        raise ValueError("corrective conditions drifted")
    if data.get("candidate_set_manifest_sha256") != sha256_json(condition_manifest):
        raise ValueError("candidate-set manifest hash drifted")

    prior = known_prior_query_manifest()
    if data.get("prior_query_manifest_sha256") != prior["union_sha256"]:
        raise ValueError("prior query manifest hash drifted")

    tasks = data.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != plan["semantic_task_count"]:
        raise ValueError("corrective task count drifted")
    expected_slots = {
        str(slot["semantic_task_id"]): slot
        for slot in plan["slots"]
    }
    seen_ids: set[str] = set()
    seen_queries: set[str] = set()

    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("corrective task must be an object")
        task_id = task.get("semantic_task_id")
        if not isinstance(task_id, str) or task_id not in expected_slots:
            raise ValueError("unknown corrective semantic_task_id")
        if task_id in seen_ids:
            raise ValueError("duplicate corrective semantic_task_id")
        seen_ids.add(task_id)
        slot = expected_slots[task_id]
        if task.get("task_stratum") != slot["task_stratum"]:
            raise ValueError(f"{task_id}: task_stratum drifted")
        if task.get("language") != slot["language"]:
            raise ValueError(f"{task_id}: language drifted")
        query = task.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"{task_id}: query must be non-empty")
        normalized = normalize_query(query)
        if normalized in seen_queries:
            raise ValueError("duplicate normalized corrective query")
        seen_queries.add(normalized)
        if task.get("supported") is not True:
            raise ValueError(f"{task_id}: corrective task must be supported")
        routes = task.get("required_routes")
        if (
            not isinstance(routes, list)
            or not routes
            or len(routes) != len(set(routes))
            or any(not isinstance(route, str) or not route for route in routes)
        ):
            raise ValueError(f"{task_id}: required_routes invalid")
        fixture = task.get("executor_fixture")
        if not isinstance(fixture, dict) or not fixture.get("steps"):
            raise ValueError(f"{task_id}: executor fixture missing")

    assert_no_prior_query_overlap(seen_queries)
    if set(expected_slots) != seen_ids:
        raise ValueError("corrective corpus is missing frozen slots")
    if data.get("tasks_sha256") != sha256_json(tasks):
        raise ValueError("corrective task hash drifted")

    return {
        "issue": 431,
        "task_count": len(tasks),
        "tasks_sha256": data["tasks_sha256"],
        "catalog_sizes": list(CATALOGS),
        "exact_prior_query_overlap_count": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.corpus.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("corrective corpus root must be an object")
    print(json.dumps(validate_corpus(data), sort_keys=True))


if __name__ == "__main__":
    main()
