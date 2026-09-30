"""Run strong-agent downstream evaluation for frozen #432 held-out tasks."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_utility_generated_common import (  # noqa: E402
    LocalSmolLM3Agent,
    build_extended_registry,
    run_generated_episode,
    summarize_rows,
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


def evaluate(
    corpus: dict[str, Any],
    *,
    catalog_size: int,
    task_ids: set[str],
    conditions: tuple[str, ...],
) -> dict[str, Any]:
    frozen_conditions = set(corpus["condition_manifest"]["conditions"])
    if not set(conditions).issubset(frozen_conditions):
        raise ValueError("requested condition is not in the frozen held-out manifest")

    tasks = [
        task
        for task in corpus["tasks"]
        if str(task["semantic_task_id"]) in task_ids
    ]
    if {str(task["semantic_task_id"]) for task in tasks} != task_ids:
        raise ValueError("requested held-out task IDs are not all present")

    started = time.perf_counter_ns()
    agent = LocalSmolLM3Agent()
    model_load_ms = (time.perf_counter_ns() - started) / 1_000_000
    registry = build_extended_registry(catalog_size)

    rows: list[dict[str, Any]] = []
    for task in tasks:
        for condition in conditions:
            row = run_generated_episode(agent, registry, task, condition)
            row["catalog_size"] = catalog_size
            rows.append(row)
            print(
                json.dumps(
                    {
                        "task_id": row["task_id"],
                        "catalog_size": catalog_size,
                        "condition": condition,
                        "passed": row["passed"],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    return {
        "schema_version": 1,
        "issue": 432,
        "benchmark": corpus["benchmark"],
        "generator_source_revision": corpus["generator_source_revision"],
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
        "overall": {
            condition: summarize_rows(
                [row for row in rows if row["condition"] == condition]
            )
            for condition in conditions
        },
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
    task_ids = {item for item in args.task_ids.split(",") if item}
    conditions = tuple(item for item in args.conditions.split(",") if item)
    result = evaluate(
        corpus,
        catalog_size=args.catalog_size,
        task_ids=task_ids,
        conditions=conditions,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
