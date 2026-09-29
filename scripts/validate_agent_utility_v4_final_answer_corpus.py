"""Validate a frozen #424 final-answer corpus before any inference.

This validator does not generate answer-bearing benchmark content. It verifies the
preregistered 144-slot surface plus deterministic evidence/fact/unit/provenance
contracts so scoring cannot silently repair corpus drift.
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
AUTHORING_SCRIPT = (
    ROOT / "scripts" / "generate_agent_utility_v4_final_answer_authoring_plan.py"
)
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_CATALOGS = (100, 250)


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
    spec = importlib.util.spec_from_file_location("v4_authoring_plan", AUTHORING_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load v4 authoring-plan generator")
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


def _unique_strings(value: object, *, field: str, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    if any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{field} must contain non-empty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{field} must not contain duplicates")
    if not allow_empty and not value:
        raise ValueError(f"{field} must not be empty")
    return value


def _validate_required_facts(
    task_id: str,
    facts: object,
    *,
    allowed_sources: set[str],
    numeric_tolerances: object,
    accepted_units: object,
) -> None:
    if not isinstance(facts, list) or not facts:
        raise ValueError(f"{task_id} required_facts must be a non-empty array")
    if not isinstance(numeric_tolerances, dict):
        raise ValueError(f"{task_id} numeric_tolerances must be an object")
    if not isinstance(accepted_units, dict):
        raise ValueError(f"{task_id} accepted_units must be an object")

    keys: set[str] = set()
    numeric_keys: set[str] = set()
    unit_keys: set[str] = set()

    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            raise ValueError(f"{task_id} required_facts[{index}] must be an object")
        for required in ("key", "value", "unit", "source_id"):
            if required not in fact:
                raise ValueError(
                    f"{task_id} required_facts[{index}] missing {required}"
                )

        key = fact["key"]
        if not isinstance(key, str) or not key:
            raise ValueError(f"{task_id} fact key must be a non-empty string")
        if key in keys:
            raise ValueError(f"{task_id} duplicate required fact key: {key}")
        keys.add(key)

        source_id = fact["source_id"]
        if source_id not in allowed_sources:
            raise ValueError(
                f"{task_id} fact {key} source_id is not allowed evidence"
            )

        value = fact["value"]
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            numeric_keys.add(key)

        unit = fact["unit"]
        if unit is not None:
            if not isinstance(unit, str) or not unit:
                raise ValueError(f"{task_id} fact {key} unit must be string or null")
            unit_keys.add(key)

    if set(numeric_tolerances) != numeric_keys:
        raise ValueError(
            f"{task_id} numeric_tolerances keys must exactly match numeric facts"
        )
    for key, tolerance in numeric_tolerances.items():
        if not isinstance(tolerance, dict):
            raise ValueError(f"{task_id} tolerance for {key} must be an object")
        allowed = {"absolute", "relative"}
        if not set(tolerance).issubset(allowed) or not tolerance:
            raise ValueError(
                f"{task_id} tolerance for {key} needs absolute and/or relative"
            )
        for name, value in tolerance.items():
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or value < 0
            ):
                raise ValueError(
                    f"{task_id} tolerance {name} for {key} must be non-negative"
                )

    if set(accepted_units) != unit_keys:
        raise ValueError(
            f"{task_id} accepted_units keys must exactly match unit-bearing facts"
        )
    facts_by_key = {fact["key"]: fact for fact in facts}
    for key, units in accepted_units.items():
        parsed = _unique_strings(
            units,
            field=f"{task_id}.accepted_units.{key}",
        )
        canonical_unit = facts_by_key[key]["unit"]
        if canonical_unit not in parsed:
            raise ValueError(
                f"{task_id} accepted units for {key} must include canonical unit"
            )


def validate_corpus(data: dict[str, Any]) -> dict[str, Any]:
    plan = _authoring_plan()

    if data.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    if data.get("issue") != 424:
        raise ValueError("issue must be 424")
    if data.get("experiment") != plan["experiment"]:
        raise ValueError("experiment identity does not match preregistration")
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
        if task.get("answer_task_stratum") != slot["answer_task_stratum"]:
            raise ValueError(f"{task_id} answer_task_stratum drifted")
        if task.get("language") != slot["language"]:
            raise ValueError(f"{task_id} language drifted")

        query = task.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"{task_id} query must be non-empty")
        normalized = _normalized_query(query)
        if normalized in seen_queries:
            raise ValueError(f"duplicate normalized query: {task_id}")
        seen_queries.add(normalized)

        _unique_strings(task.get("required_routes"), field=f"{task_id}.required_routes")

        evidence = task.get("evidence_payloads")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"{task_id} evidence_payloads must be non-empty")
        evidence_ids: set[str] = set()
        for evidence_index, row in enumerate(evidence):
            if not isinstance(row, dict):
                raise ValueError(
                    f"{task_id} evidence_payloads[{evidence_index}] must be an object"
                )
            source_id = row.get("source_id")
            if not isinstance(source_id, str) or not source_id:
                raise ValueError(f"{task_id} evidence source_id must be non-empty")
            if source_id in evidence_ids:
                raise ValueError(f"{task_id} duplicate evidence source_id")
            if "payload" not in row:
                raise ValueError(f"{task_id} evidence payload is missing")
            evidence_ids.add(source_id)

        allowed_sources = set(
            _unique_strings(
                task.get("allowed_source_ids"),
                field=f"{task_id}.allowed_source_ids",
            )
        )
        if not allowed_sources.issubset(evidence_ids):
            raise ValueError(
                f"{task_id} allowed_source_ids must reference frozen evidence"
            )

        _validate_required_facts(
            task_id,
            task.get("required_facts"),
            allowed_sources=allowed_sources,
            numeric_tolerances=task.get("numeric_tolerances"),
            accepted_units=task.get("accepted_units"),
        )

        forbidden_facts = task.get("forbidden_facts")
        if not isinstance(forbidden_facts, list):
            raise ValueError(f"{task_id} forbidden_facts must be an array")
        for fact_index, fact in enumerate(forbidden_facts):
            if not isinstance(fact, dict) or "key" not in fact or "value" not in fact:
                raise ValueError(
                    f"{task_id} forbidden_facts[{fact_index}] needs key and value"
                )
            if "source_id" in fact and fact["source_id"] not in allowed_sources:
                raise ValueError(
                    f"{task_id} forbidden fact source_id is not allowed evidence"
                )

        _unique_strings(
            task.get("mandatory_answer_fields"),
            field=f"{task_id}.mandatory_answer_fields",
        )

        corrective = task.get("corrective_contract")
        if slot["answer_task_stratum"] == "corrective_expansion_required":
            if not isinstance(corrective, dict):
                raise ValueError(f"{task_id} corrective_contract is required")
            if corrective.get("initial_candidate_miss") is not True:
                raise ValueError(f"{task_id} must freeze initial_candidate_miss=true")
            if corrective.get("ground_truth_trigger_visible") is not False:
                raise ValueError(
                    f"{task_id} must freeze ground_truth_trigger_visible=false"
                )
        elif corrective is not None and not isinstance(corrective, dict):
            raise ValueError(f"{task_id} corrective_contract must be object or null")

    if seen_ids != set(expected_slots):
        missing = sorted(set(expected_slots) - seen_ids)
        raise ValueError(f"missing semantic_task_id values: {missing[:5]}")

    expected_tasks_sha = _sha(tasks)
    if data.get("tasks_sha256") != expected_tasks_sha:
        raise ValueError("tasks_sha256 does not match canonical task content")

    return {
        "issue": 424,
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
        raise SystemExit("final-answer corpus root must be a JSON object")
    print(json.dumps(validate_corpus(data), sort_keys=True))


if __name__ == "__main__":
    main()
