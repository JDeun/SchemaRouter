"""Evaluate one shard of the #506 output-field projection experiment.

Two runtimes share this evaluator so the scoring path cannot drift between them:

- `--runtime dev` uses the frozen B1 small agent. Development evidence only.
- `--runtime confirmation` uses the canonical strong agent, and is gated by the
  workflow on #423 B2 being terminal.

Every condition receives the same query, the same candidate exposure and the same
frozen raw record. Only the observation handed to the agent differs.
"""
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
    FINAL_SYSTEM_PROMPT,
    build_extended_registry,
    run_generated_episode,
)
from scripts.agent_utility_v7_projection import (  # noqa: E402
    PROJECTION_CONDITIONS,
    project_observation,
)
from scripts.evaluate_agent_utility_v4_final_answer import score_envelope  # noqa: E402

RUNTIMES = ("dev", "confirmation")


def _projection_transform(condition: str):
    def transform(observation: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        return project_observation(
            observation,
            condition=condition,
            planned_fields=step.get("planned_fields", ()),
            gold_fields=step.get("gold_fields", ()),
            field_contracts=step.get("field_contracts", {}),
        )

    return transform


def _observation_chars(row: dict[str, Any]) -> int:
    """Characters of tool payload the agent actually received.

    Token counts depend on the tokenizer and the two runtimes use different
    ones, so the reduction is reported in serialized characters as well. The
    harness records this from the message it really sent rather than recomputing
    the projection here, so the two can never disagree.
    """
    return sum(int(turn.get("observation_chars", 0)) for turn in row["turn_rows"])


def _build_agent(runtime: str) -> tuple[Any, dict[str, Any]]:
    if runtime == "dev":
        from scripts.agent_utility_v7_dev_agent import (
            MAX_NEW_TOKENS,
            MAX_TURNS,
            MODEL_NAME,
            MODEL_REVISION,
            SEED,
            THREADS,
            LocalQwenAgent,
            runtime_identity,
        )

        agent = LocalQwenAgent()
        identity = {
            "runtime": runtime,
            "evidence_class": "development",
            "model": {
                "name": MODEL_NAME,
                "revision": MODEL_REVISION,
                "max_new_tokens": MAX_NEW_TOKENS,
                "max_turns": MAX_TURNS,
                "seed": SEED,
                "threads": THREADS,
            },
            "platform": runtime_identity(),
        }
        return agent, identity

    from scripts.evaluate_agent_utility_phase_b_smollm3 import (
        ATTN_IMPLEMENTATION,
        MAX_NEW_TOKENS,
        MAX_TURNS,
        MODEL_NAME,
        MODEL_REVISION,
        SEED,
        THREADS,
        LocalSmolLM3Agent,
        _runtime_identity,
    )

    agent = LocalSmolLM3Agent()
    identity = {
        "runtime": runtime,
        "evidence_class": "confirmation",
        "model": {
            "name": MODEL_NAME,
            "revision": MODEL_REVISION,
            "attention_implementation": ATTN_IMPLEMENTATION,
            "max_new_tokens": MAX_NEW_TOKENS,
            "max_turns": MAX_TURNS,
            "seed": SEED,
            "threads": THREADS,
        },
        "platform": _runtime_identity(),
    }
    return agent, identity


def evaluate(
    corpus: dict[str, Any],
    *,
    catalog_size: int,
    task_ids: set[str],
    runtime: str,
    conditions: tuple[str, ...] = PROJECTION_CONDITIONS,
) -> dict[str, Any]:
    frozen = set(corpus["condition_manifest"]["conditions"])
    if not set(conditions).issubset(frozen):
        raise ValueError("requested condition is not in the frozen manifest")

    candidate_condition = str(corpus["condition_manifest"]["candidate_condition"])

    tasks = [task for task in corpus["tasks"] if str(task["semantic_task_id"]) in task_ids]
    if {str(task["semantic_task_id"]) for task in tasks} != task_ids:
        raise ValueError("requested task IDs are not all present in the corpus")

    started = time.perf_counter_ns()
    agent, identity = _build_agent(runtime)
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
                candidate_condition=candidate_condition,
                observation_transform=_projection_transform(condition),
            )
            row["catalog_size"] = catalog_size
            row["projection_stratum"] = str(task["projection_stratum"])
            row["observation_chars"] = _observation_chars(row)
            row.update(score_envelope(task, str(row["final_text"])))
            rows.append(row)
            print(
                json.dumps(
                    {
                        "task_id": row["task_id"],
                        "catalog_size": catalog_size,
                        "condition": condition,
                        "required_fact_recall": row["required_fact_recall"],
                        "observation_chars": row["observation_chars"],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    return {
        "schema_version": 1,
        "issue": 506,
        "experiment": corpus["experiment"],
        "tasks_sha256": corpus["tasks_sha256"],
        "source_identity_sha256": corpus["source_identity_sha256"],
        "catalog_size": catalog_size,
        "candidate_condition": candidate_condition,
        "task_ids": sorted(task_ids),
        "conditions": list(conditions),
        "runtime": identity,
        "model_load_ms": model_load_ms,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--catalog-size", required=True, type=int)
    parser.add_argument("--task-ids", required=True)
    parser.add_argument("--runtime", required=True, choices=RUNTIMES)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    task_ids = {value.strip() for value in args.task_ids.split(",") if value.strip()}
    result = evaluate(
        corpus,
        catalog_size=args.catalog_size,
        task_ids=task_ids,
        runtime=args.runtime,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
