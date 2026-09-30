"""Evaluate fresh structural fixed-K=3 v4 confirmation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from schemarouter import InMemoryRegistry, SchemaPlanner, ToolSpec  # noqa: E402
from schemarouter.planner import (  # noqa: E402
    _STRUCTURAL_OPERATION_FAMILY_BONUS,
    _STRUCTURAL_TOOL_IDENTIFIER_BONUS,
)
from scripts.rank_agent_utility_v5_adaptive_dev import (  # noqa: E402
    MODEL_NAME,
    MODEL_REVISION,
    _tool_tokens,
)

PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-structural-fixed3-v4-preregistration.json"
)
CATALOG_SIZES = (100, 250, 500)
SUPPORTED_STRATA = {
    "clear_single_tool",
    "sibling_operation_ambiguity",
    "semantically_adjacent_distractors",
    "multi_step_first_hop",
    "typed_numeric_units",
    "read_write_siblings",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _distribution(
    values: list[float],
) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "p95": None,
            "min": None,
            "max": None,
        }
    ordered = sorted(values)
    position = 0.95 * (len(ordered) - 1)
    lo = math.floor(position)
    hi = math.ceil(position)
    if lo == hi:
        p95 = ordered[lo]
    else:
        weight = position - lo
        p95 = (
            ordered[lo] * (1.0 - weight)
            + ordered[hi] * weight
        )
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "p95": p95,
        "min": min(values),
        "max": max(values),
    }


def _load_registry(path: Path) -> InMemoryRegistry:
    payload = json.loads(path.read_text(encoding="utf-8"))
    registry = InMemoryRegistry()
    registry.update_many(
        [
            ToolSpec.model_validate(tool)
            for tool in payload
        ]
    )
    return registry


def _verify_freeze(
    freeze_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads(
        (freeze_dir / "freeze-manifest.json")
        .read_text(encoding="utf-8")
    )
    if manifest["status"] != "frozen_before_scoring":
        raise RuntimeError("fixed3 confirmation was not frozen")

    tasks = json.loads(
        (freeze_dir / "confirmation-tasks.json")
        .read_text(encoding="utf-8")
    )
    if _sha(tasks) != manifest["task_rows_sha256"]:
        raise RuntimeError("fixed3 confirmation task hash mismatch")

    for size in CATALOG_SIZES:
        catalog = json.loads(
            (freeze_dir / f"catalog-{size}.json")
            .read_text(encoding="utf-8")
        )
        if (
            _sha(catalog)
            != manifest["catalogs"][str(size)]["sha256"]
        ):
            raise RuntimeError(
                f"fixed3 catalog-{size} hash mismatch"
            )
    return manifest, tasks


def _new_accumulator() -> dict[str, Any]:
    return {
        "required_hits": 0,
        "required_total": 0,
        "full_coverage_hits": 0,
        "supported_rows": 0,
        "candidate_counts": [],
        "schema_tokens": [],
        "retrieval_latencies": [],
    }


def _update(
    accumulator: dict[str, Any],
    *,
    required: set[str],
    selected: set[str],
    candidate_count: int,
    schema_tokens: int,
    retrieval_latency_ms: float,
) -> None:
    hits = len(required & selected)
    accumulator["required_hits"] += hits
    accumulator["required_total"] += len(required)
    accumulator["full_coverage_hits"] += int(
        hits == len(required)
    )
    accumulator["supported_rows"] += 1
    accumulator["candidate_counts"].append(
        float(candidate_count)
    )
    accumulator["schema_tokens"].append(
        float(schema_tokens)
    )
    accumulator["retrieval_latencies"].append(
        retrieval_latency_ms
    )


def _summary(
    accumulator: dict[str, Any],
) -> dict[str, Any]:
    required_total = int(accumulator["required_total"])
    supported_rows = int(accumulator["supported_rows"])
    return {
        "supported_rows": supported_rows,
        "required_route_count": required_total,
        "required_route_recall": (
            accumulator["required_hits"] / required_total
            if required_total
            else None
        ),
        "all_required_full_coverage": (
            accumulator["full_coverage_hits"]
            / supported_rows
            if supported_rows
            else None
        ),
        "candidate_count": _distribution(
            accumulator["candidate_counts"]
        ),
        "schema_tokens": _distribution(
            accumulator["schema_tokens"]
        ),
        "retrieval_latency_ms": _distribution(
            accumulator["retrieval_latencies"]
        ),
    }


def evaluate(
    freeze_dir: Path,
    *,
    local_files_only: bool,
) -> dict[str, Any]:
    from transformers import AutoTokenizer

    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    if (
        prereg["status"]
        != "preregistered_before_fresh_confirmation_surface_generation"
    ):
        raise RuntimeError("fixed3 v4 preregistration drifted")

    fixed_retriever = prereg["fixed_retriever"]
    if (
        float(fixed_retriever["tool_identifier_bonus"])
        != _STRUCTURAL_TOOL_IDENTIFIER_BONUS
    ):
        raise RuntimeError("structural tool bonus drifted")
    if (
        float(fixed_retriever["operation_family_bonus"])
        != _STRUCTURAL_OPERATION_FAMILY_BONUS
    ):
        raise RuntimeError("structural operation bonus drifted")

    manifest, tasks = _verify_freeze(freeze_dir)
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        revision=MODEL_REVISION,
        trust_remote_code=False,
        local_files_only=local_files_only,
    )

    depths = {
        "STRUCT-FIXED-3": 3,
        "STRUCT-FIXED-5": 5,
    }
    pooled = {
        policy: _new_accumulator()
        for policy in depths
    }
    per_catalog: dict[str, dict[str, dict[str, Any]]] = {
        policy: {}
        for policy in depths
    }
    per_stratum: dict[str, dict[str, dict[str, Any]]] = {
        policy: {}
        for policy in depths
    }
    per_language: dict[str, dict[str, dict[str, Any]]] = {
        policy: {}
        for policy in depths
    }
    all_row_tokens: dict[str, list[float]] = {
        policy: []
        for policy in depths
    }
    all_row_candidate_counts: dict[str, list[float]] = {
        policy: []
        for policy in depths
    }
    rows: list[dict[str, Any]] = []

    for size in CATALOG_SIZES:
        registry = _load_registry(
            freeze_dir / f"catalog-{size}.json"
        )
        planner = SchemaPlanner(
            registry,
            structural_retrieval=True,
        )
        for task in tasks:
            query = str(task["query"])
            started = time.perf_counter_ns()
            retrieval = planner.retrieve(query, k=5)
            latency_ms = (
                time.perf_counter_ns() - started
            ) / 1_000_000

            if len(retrieval.candidates) != 5:
                raise RuntimeError(
                    f"{task['task_id']} catalog {size}: fewer than 5 candidates"
                )
            route_ids = [
                candidate.route_id
                for candidate in retrieval.candidates
            ]
            token_counts = {
                policy: _tool_tokens(
                    tokenizer,
                    registry,
                    query,
                    route_ids[:depth],
                )
                for policy, depth in depths.items()
            }
            row = {
                **task,
                "catalog_size": size,
                "top5_route_ids": route_ids,
                "top5_scores": [
                    float(candidate.score)
                    for candidate in retrieval.candidates
                ],
                "retrieval_latency_ms": latency_ms,
                "schema_tokens": token_counts,
            }
            rows.append(row)

            stratum = str(task["task_stratum"])
            language = str(task["language"])
            required = {
                str(route_id)
                for route_id in task["required_route_ids"]
            }
            for policy, depth in depths.items():
                selected = set(route_ids[:depth])
                tokens = int(token_counts[policy])
                all_row_tokens[policy].append(float(tokens))
                all_row_candidate_counts[policy].append(
                    float(depth)
                )
                if stratum not in SUPPORTED_STRATA:
                    continue

                catalog_acc = per_catalog[policy].setdefault(
                    str(size),
                    _new_accumulator(),
                )
                stratum_acc = per_stratum[policy].setdefault(
                    stratum,
                    _new_accumulator(),
                )
                language_acc = per_language[policy].setdefault(
                    language,
                    _new_accumulator(),
                )
                for accumulator in (
                    pooled[policy],
                    catalog_acc,
                    stratum_acc,
                    language_acc,
                ):
                    _update(
                        accumulator,
                        required=required,
                        selected=selected,
                        candidate_count=depth,
                        schema_tokens=tokens,
                        retrieval_latency_ms=latency_ms,
                    )

    metrics: dict[str, Any] = {}
    for policy in depths:
        metrics[policy] = {
            "k": depths[policy],
            "pooled": _summary(pooled[policy]),
            "per_catalog": {
                key: _summary(value)
                for key, value in sorted(
                    per_catalog[policy].items(),
                    key=lambda item: int(item[0]),
                )
            },
            "per_stratum": {
                key: _summary(value)
                for key, value in sorted(
                    per_stratum[policy].items()
                )
            },
            "per_language": {
                key: _summary(value)
                for key, value in sorted(
                    per_language[policy].items()
                )
            },
            "all_row_candidate_count": _distribution(
                all_row_candidate_counts[policy]
            ),
            "all_row_schema_tokens": _distribution(
                all_row_tokens[policy]
            ),
        }

    candidate = metrics["STRUCT-FIXED-3"]
    control = metrics["STRUCT-FIXED-5"]
    gates = prereg["confirmation_gates"]
    catalog_gate = all(
        float(value["required_route_recall"])
        >= float(gates["required_route_recall_min_each_catalog"])
        and float(value["all_required_full_coverage"])
        >= float(gates["all_required_full_coverage_min_each_catalog"])
        for value in candidate["per_catalog"].values()
    )
    typed_gate = (
        float(
            candidate["per_stratum"]["typed_numeric_units"][
                "required_route_recall"
            ]
        )
        >= float(gates["typed_numeric_units_recall_min"])
    )
    candidate_mean = float(
        candidate["all_row_candidate_count"]["mean"]
    )
    candidate_p95 = float(
        candidate["all_row_candidate_count"]["p95"]
    )
    depth_gate = (
        candidate_mean
        == float(gates["mean_candidate_count_must_equal"])
        and candidate_p95
        <= float(gates["p95_candidate_count_max"])
    )
    token_gate = (
        float(candidate["all_row_schema_tokens"]["mean"])
        < float(control["all_row_schema_tokens"]["mean"])
    )

    return {
        "schema_version": 1,
        "issue": 430,
        "experiment": prereg["experiment"],
        "surface": "fresh_confirmation",
        "freeze_manifest_sha256": _sha(manifest),
        "task_rows_sha256": manifest["task_rows_sha256"],
        "catalog_family_sha256": manifest[
            "catalog_family_sha256"
        ],
        "model": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "fixed_retriever": fixed_retriever,
        "candidate": metrics["STRUCT-FIXED-3"],
        "control": metrics["STRUCT-FIXED-5"],
        "gates": {
            "catalog_gate_passed": catalog_gate,
            "typed_numeric_units_gate_passed": typed_gate,
            "fixed_depth_gate_passed": depth_gate,
            "schema_token_gate_passed": token_gate,
        },
        "confirmation_passed": bool(
            catalog_gate
            and typed_gate
            and depth_gate
            and token_gate
        ),
        "confirmation_surface_tuning_used": False,
        "b2_outcomes_used": False,
        "product_default_changed": False,
        "row_count": len(rows),
        "rows": rows,
        "claim_boundary": prereg["claim_boundary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()

    result = evaluate(
        args.freeze_dir,
        local_files_only=args.local_files_only,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "confirmation_passed": result[
                    "confirmation_passed"
                ],
                "candidate_per_catalog": result[
                    "candidate"
                ]["per_catalog"],
                "candidate_mean_schema_tokens": result[
                    "candidate"
                ]["all_row_schema_tokens"]["mean"],
                "control_mean_schema_tokens": result[
                    "control"
                ]["all_row_schema_tokens"]["mean"],
                "gates": result["gates"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
