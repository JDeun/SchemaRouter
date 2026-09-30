"""Evaluate preregistered structural K3 vs K5 downstream agent utility.

This harness deliberately reuses the canonical B2 SmolLM3 agent, prompt/tool
serialization, deterministic executor, episode loop, scoring, and bootstrap
implementation. Only the confirmed structural shortlist depth differs.
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

from benchmarks.agent_utility_v1_catalog import (  # noqa: E402
    CATALOG_SIZES,
    TASKS,
    build_registry,
)
from schemarouter import SchemaPlanner  # noqa: E402
from schemarouter.planner import (  # noqa: E402
    _STRUCTURAL_OPERATION_FAMILY_BONUS,
    _STRUCTURAL_TOOL_IDENTIFIER_BONUS,
)
from scripts.evaluate_agent_utility_phase_b_smollm3 import (  # noqa: E402
    ATTN_IMPLEMENTATION,
    MAX_NEW_TOKENS,
    MAX_TURNS,
    MODEL_NAME,
    MODEL_REVISION,
    SEED,
    THREADS,
    LocalSmolLM3Agent,
    _run_episode,
    _runtime_identity,
    _summary,
)

CONDITIONS = ("STRUCT-FIXED-3", "STRUCT-FIXED-5")
K_BY_CONDITION = {
    "STRUCT-FIXED-3": 3,
    "STRUCT-FIXED-5": 5,
}


def _assert_frozen_structural_candidate() -> None:
    if _STRUCTURAL_TOOL_IDENTIFIER_BONUS != 4.5:
        raise RuntimeError("structural tool-identifier bonus drift")
    if _STRUCTURAL_OPERATION_FAMILY_BONUS != 1.5:
        raise RuntimeError("structural operation-family bonus drift")


def _structural_routes(
    registry: Any,
    query: str,
    *,
    k: int,
) -> list[str]:
    planner = SchemaPlanner(
        registry,
        structural_retrieval=True,
    )
    retrieval = planner.retrieve(query, k=k)
    return sorted(
        candidate.route_id
        for candidate in retrieval.candidates
    )


def _run_condition(
    agent: LocalSmolLM3Agent,
    registry: Any,
    task: Any,
    condition: str,
) -> dict[str, Any]:
    k = K_BY_CONDITION[condition]
    episode_started = time.perf_counter_ns()
    selection_started = time.perf_counter_ns()
    visible_routes = _structural_routes(
        registry,
        task.query,
        k=k,
    )
    selection_ms = (
        time.perf_counter_ns() - selection_started
    ) / 1_000_000

    row = _run_episode(
        agent,
        registry,
        task,
        condition,
        initial_routes=visible_routes,
        progressive=False,
    )
    row["candidate_selection_latency_ms"] = selection_ms
    row["episode_wall_latency_ms"] = (
        time.perf_counter_ns() - episode_started
    ) / 1_000_000
    row["structural_retrieval"] = True
    row["structural_k"] = k
    return row


def evaluate(
    *,
    catalog_sizes: tuple[int, ...],
    task_ids: set[str] | None = None,
) -> dict[str, Any]:
    _assert_frozen_structural_candidate()

    invalid_catalogs = sorted(
        set(catalog_sizes).difference(CATALOG_SIZES)
    )
    if invalid_catalogs:
        raise ValueError(
            "unsupported catalog size(s): "
            + ", ".join(str(value) for value in invalid_catalogs)
        )

    known_task_ids = {task.task_id for task in TASKS}
    if task_ids is not None:
        unknown = sorted(task_ids.difference(known_task_ids))
        if unknown:
            raise ValueError(
                "unknown frozen task id(s): " + ", ".join(unknown)
            )

    started = time.perf_counter_ns()
    agent = LocalSmolLM3Agent()
    model_load_ms = (
        time.perf_counter_ns() - started
    ) / 1_000_000

    rows: list[dict[str, Any]] = []
    for catalog_size in catalog_sizes:
        registry = build_registry(catalog_size)
        for task in TASKS:
            if task_ids is not None and task.task_id not in task_ids:
                continue

            k3_routes = _structural_routes(
                registry,
                task.query,
                k=3,
            )
            k5_routes = _structural_routes(
                registry,
                task.query,
                k=5,
            )
            if k3_routes != sorted(
                route
                for route in k5_routes
                if route in set(k3_routes)
            ):
                raise RuntimeError(
                    "structural K3/K5 route identity drift"
                )
            ranked3 = set(k3_routes)
            if not ranked3.issubset(set(k5_routes)):
                raise RuntimeError(
                    "structural K3 must be a subset of K5"
                )

            for condition in CONDITIONS:
                row = _run_condition(
                    agent,
                    registry,
                    task,
                    condition,
                )
                row["catalog_size"] = catalog_size
                rows.append(row)
                print(
                    json.dumps(
                        {
                            "catalog_size": catalog_size,
                            "task_id": task.task_id,
                            "condition": condition,
                            "passed": row["passed"],
                            "tool_schema_tokens": row[
                                "tool_schema_tokens"
                            ],
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )

    overall = {
        condition: _summary(
            [
                row
                for row in rows
                if row["condition"] == condition
            ]
        )
        for condition in CONDITIONS
    }
    summary_by_catalog = {
        str(catalog_size): {
            condition: _summary(
                [
                    row
                    for row in rows
                    if row["catalog_size"] == catalog_size
                    and row["condition"] == condition
                ]
            )
            for condition in CONDITIONS
        }
        for catalog_size in catalog_sizes
    }

    return {
        "schema_version": 1,
        "issue": 430,
        "parent_issue": 423,
        "experiment": "structural-fixed3-agent-utility-v5",
        "runtime": _runtime_identity(),
        "model": {
            "name": MODEL_NAME,
            "revision": MODEL_REVISION,
            "dtype": "bfloat16",
            "device": "cpu",
            "attention_implementation": ATTN_IMPLEMENTATION,
            "max_new_tokens": MAX_NEW_TOKENS,
            "max_turns": MAX_TURNS,
            "seed": SEED,
            "threads": THREADS,
            "enable_thinking": False,
        },
        "retriever": {
            "structural_retrieval": True,
            "tool_identifier_bonus": (
                _STRUCTURAL_TOOL_IDENTIFIER_BONUS
            ),
            "operation_family_bonus": (
                _STRUCTURAL_OPERATION_FAMILY_BONUS
            ),
            "conditions": {
                condition: K_BY_CONDITION[condition]
                for condition in CONDITIONS
            },
        },
        "catalog_sizes": list(catalog_sizes),
        "task_ids": (
            sorted(task_ids)
            if task_ids is not None
            else sorted(known_task_ids)
        ),
        "model_load_ms": model_load_ms,
        "rows": rows,
        "overall": overall,
        "summary_by_catalog": summary_by_catalog,
        "policy": {
            "canonical_b2_agent_reused": True,
            "canonical_b2_episode_loop_reused": True,
            "canonical_b2_executor_scoring_reused": True,
            "schemarouter_rank_scores_visible_to_agent": False,
            "candidate_routes_lexically_sorted": True,
            "product_default_changed": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--catalog-sizes",
        default=",".join(str(value) for value in CATALOG_SIZES),
    )
    parser.add_argument(
        "--task-ids",
        default="",
    )
    args = parser.parse_args()

    catalog_sizes = tuple(
        int(value)
        for value in args.catalog_sizes.split(",")
        if value.strip()
    )
    task_ids = {
        value.strip()
        for value in args.task_ids.split(",")
        if value.strip()
    }
    result = evaluate(
        catalog_sizes=catalog_sizes,
        task_ids=task_ids or None,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
