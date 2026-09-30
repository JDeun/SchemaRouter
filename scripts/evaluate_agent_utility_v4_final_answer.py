"""Evaluate deterministic final-answer quality for the frozen #424 corpus."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_utility_generated_common import (  # noqa: E402
    FINAL_SYSTEM_PROMPT,
    LocalSmolLM3Agent,
    build_extended_registry,
    run_generated_episode,
)
from scripts.evaluate_agent_utility_phase_b_smollm3 import (  # noqa: E402
    ATTN_IMPLEMENTATION,
    MAX_NEW_TOKENS,
    MAX_TURNS,
    MODEL_NAME,
    MODEL_REVISION,
    SEED,
    THREADS,
    _runtime_identity,
)

JSON_OBJECT_RE = re.compile(r"\{.*\}", flags=re.DOTALL)
ENVELOPE_KEYS = {"answer", "facts", "sources"}
FACT_KEYS = {"key", "value", "unit", "source_id"}


def _parse_envelope(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        match = JSON_OBJECT_RE.search(candidate)
        if match is None:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    if not isinstance(parsed, dict) or set(parsed) != ENVELOPE_KEYS:
        return None
    if not isinstance(parsed["answer"], str):
        return None
    if not isinstance(parsed["facts"], list):
        return None
    if not isinstance(parsed["sources"], list) or any(
        not isinstance(source, str) for source in parsed["sources"]
    ):
        return None
    for fact in parsed["facts"]:
        if not isinstance(fact, dict) or set(fact) != FACT_KEYS:
            return None
        if not isinstance(fact["key"], str) or not fact["key"]:
            return None
        if not isinstance(fact["source_id"], str) or not fact["source_id"]:
            return None
        if fact["unit"] is not None and not isinstance(fact["unit"], str):
            return None
    return parsed


def _numeric_match(
    actual: Any,
    expected: Any,
    tolerance: dict[str, Any],
) -> bool:
    if (
        not isinstance(actual, (int, float))
        or isinstance(actual, bool)
        or not isinstance(expected, (int, float))
        or isinstance(expected, bool)
    ):
        return False
    diff = abs(float(actual) - float(expected))
    absolute = tolerance.get("absolute")
    relative = tolerance.get("relative")
    checks: list[bool] = []
    if isinstance(absolute, (int, float)) and not isinstance(absolute, bool):
        checks.append(diff <= float(absolute))
    if isinstance(relative, (int, float)) and not isinstance(relative, bool):
        scale = max(abs(float(expected)), 1e-12)
        checks.append(diff <= float(relative) * scale)
    return any(checks)


def _value_match(
    actual: Any,
    expected: Any,
    tolerance: dict[str, Any] | None,
) -> bool:
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return _numeric_match(actual, expected, tolerance or {})
    return actual == expected


def score_envelope(task: dict[str, Any], text: str) -> dict[str, Any]:
    envelope = _parse_envelope(text)
    required = list(task["required_facts"])
    numeric_tolerances = dict(task["numeric_tolerances"])
    accepted_units = dict(task["accepted_units"])
    allowed_sources = set(str(value) for value in task["allowed_source_ids"])
    forbidden = list(task["forbidden_facts"])

    numeric_required = [
        fact
        for fact in required
        if isinstance(fact["value"], (int, float))
        and not isinstance(fact["value"], bool)
    ]
    unit_required = [fact for fact in required if fact["unit"] is not None]

    if envelope is None:
        return {
            "final_envelope_valid": False,
            "required_fact_recall": 0.0,
            "numeric_value_accuracy": 0.0 if numeric_required else None,
            "unit_accuracy": 0.0 if unit_required else None,
            "provenance_accuracy": 0.0,
            "unsupported_fact_count": 0,
            "unsupported_fact_rate": 0.0,
            "contradiction_count": 0,
            "exact_field_completion": False,
            "structured_fact_count": 0,
            "source_list_valid": False,
        }

    actual_facts = list(envelope["facts"])
    matched_required: set[str] = set()
    numeric_hits = 0
    unit_hits = 0
    provenance_hits = 0
    unsupported = 0
    contradictions = 0

    required_by_key = {str(fact["key"]): fact for fact in required}
    for actual in actual_facts:
        key = str(actual["key"])
        expected = required_by_key.get(key)
        licensed = False
        if expected is not None:
            value_ok = _value_match(
                actual["value"],
                expected["value"],
                numeric_tolerances.get(key),
            )
            unit_ok = (
                actual["unit"] in accepted_units[key]
                if key in accepted_units
                else actual["unit"] == expected["unit"]
            )
            source_ok = (
                actual["source_id"] in allowed_sources
                and actual["source_id"] == expected["source_id"]
            )
            licensed = value_ok and unit_ok and source_ok
            if licensed:
                matched_required.add(key)
                provenance_hits += 1
                if key in numeric_tolerances:
                    numeric_hits += 1
                if key in accepted_units:
                    unit_hits += 1

        if not licensed:
            unsupported += 1

        for forbidden_fact in forbidden:
            if (
                key == forbidden_fact["key"]
                and _value_match(
                    actual["value"],
                    forbidden_fact["value"],
                    None,
                )
            ):
                contradictions += 1

    source_list = set(str(source) for source in envelope["sources"])
    source_list_valid = (
        source_list.issubset(allowed_sources)
        and all(
            str(fact["source_id"]) in source_list
            for fact in actual_facts
            if str(fact["source_id"]) in allowed_sources
        )
    )

    required_count = len(required)
    mandatory = set(str(value) for value in task["mandatory_answer_fields"])
    exact_fields = mandatory.issubset(matched_required)
    return {
        "final_envelope_valid": True,
        "required_fact_recall": (
            len(matched_required) / required_count if required_count else 1.0
        ),
        "numeric_value_accuracy": (
            numeric_hits / len(numeric_required) if numeric_required else None
        ),
        "unit_accuracy": unit_hits / len(unit_required) if unit_required else None,
        "provenance_accuracy": (
            provenance_hits / required_count if required_count else 1.0
        ),
        "unsupported_fact_count": unsupported,
        "unsupported_fact_rate": (
            unsupported / len(actual_facts) if actual_facts else 0.0
        ),
        "contradiction_count": contradictions,
        "exact_field_completion": exact_fields,
        "structured_fact_count": len(actual_facts),
        "source_list_valid": source_list_valid,
    }


def evaluate(
    corpus: dict[str, Any],
    *,
    catalog_size: int,
    task_ids: set[str],
    conditions: tuple[str, ...],
) -> dict[str, Any]:
    frozen_conditions = set(corpus["condition_manifest"]["conditions"])
    if not set(conditions).issubset(frozen_conditions):
        raise ValueError("requested final-answer condition is not frozen")

    tasks = [
        task
        for task in corpus["tasks"]
        if str(task["semantic_task_id"]) in task_ids
    ]
    if {str(task["semantic_task_id"]) for task in tasks} != task_ids:
        raise ValueError("requested final-answer task IDs are not all present")

    started = time.perf_counter_ns()
    agent = LocalSmolLM3Agent()
    model_load_ms = (time.perf_counter_ns() - started) / 1_000_000
    registry = build_extended_registry(catalog_size)
    rows: list[dict[str, Any]] = []

    for task in tasks:
        for condition in conditions:
            row = run_generated_episode(
                agent,
                registry,
                task,
                condition,
                system_prompt=FINAL_SYSTEM_PROMPT,
            )
            row["catalog_size"] = catalog_size
            row.update(score_envelope(task, str(row["final_text"])))
            rows.append(row)
            print(
                json.dumps(
                    {
                        "task_id": row["task_id"],
                        "catalog_size": catalog_size,
                        "condition": condition,
                        "passed": row["passed"],
                        "required_fact_recall": row["required_fact_recall"],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    return {
        "schema_version": 1,
        "issue": 424,
        "experiment": corpus["experiment"],
        "tasks_sha256": corpus["tasks_sha256"],
        "catalog_size": catalog_size,
        "task_ids": sorted(task_ids),
        "conditions": list(conditions),
        "runtime": _runtime_identity(),
        "model": {
            "name": MODEL_NAME,
            "revision": MODEL_REVISION,
            "attention_implementation": ATTN_IMPLEMENTATION,
            "max_new_tokens": MAX_NEW_TOKENS,
            "max_turns": MAX_TURNS,
            "seed": SEED,
            "threads": THREADS,
        },
        "model_load_ms": model_load_ms,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--catalog-size", type=int, required=True)
    parser.add_argument("--task-ids", required=True)
    parser.add_argument("--conditions", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    result = evaluate(
        corpus,
        catalog_size=args.catalog_size,
        task_ids={item for item in args.task_ids.split(",") if item},
        conditions=tuple(item for item in args.conditions.split(",") if item),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
