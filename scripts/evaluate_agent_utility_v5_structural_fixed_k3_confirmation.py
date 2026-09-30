"""Evaluate the one-shot fresh structural fixed-K3 confirmation."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from schemarouter import SchemaPlanner  # noqa: E402
from scripts.rank_agent_utility_v5_adaptive_dev import (  # noqa: E402
    MODEL_NAME,
    MODEL_REVISION,
    _load_registry,
    _sha,
    _tool_tokens,
)

PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-structural-fixed-k3-preregistration.json"
)
UNSUPPORTED_STRATA = {
    "near_domain_unsupported",
    "out_of_domain",
}


def _load_confirmation(
    freeze_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads(
        (freeze_dir / "freeze-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    if manifest["status"] != "frozen_before_scoring":
        raise RuntimeError(
            "fixed-K3 confirmation was not frozen before scoring"
        )
    tasks = json.loads(
        (freeze_dir / "confirmation-tasks.json").read_text(
            encoding="utf-8"
        )
    )
    if _sha(tasks) != manifest["task_rows_sha256"]:
        raise RuntimeError(
            "fixed-K3 confirmation task hash drifted"
        )
    return manifest, tasks


def _coverage_summary(
    rows: list[dict[str, Any]],
    *,
    k: int,
) -> dict[str, Any]:
    supported = [
        row
        for row in rows
        if row["task_stratum"] not in UNSUPPORTED_STRATA
    ]
    required_total = sum(
        len(row["required_route_ids"])
        for row in supported
    )
    required_hits = sum(
        sum(
            route_id in set(row[f"top{k}_route_ids"])
            for route_id in row["required_route_ids"]
        )
        for row in supported
    )
    full = sum(
        all(
            route_id in set(row[f"top{k}_route_ids"])
            for route_id in row["required_route_ids"]
        )
        for row in supported
    )
    return {
        "supported_task_count": len(supported),
        "required_route_count": required_total,
        "required_route_recall": (
            required_hits / required_total
            if required_total
            else None
        ),
        "all_required_full_coverage": (
            full / len(supported)
            if supported
            else None
        ),
    }


def evaluate(
    freeze_dir: Path,
    *,
    local_files_only: bool,
) -> dict[str, Any]:
    from transformers import AutoTokenizer

    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    manifest, tasks = _load_confirmation(freeze_dir)

    if manifest["fixed_candidate"] != prereg["fixed_candidate"]:
        raise RuntimeError(
            "fixed-K3 candidate drifted after confirmation freeze"
        )

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        revision=MODEL_REVISION,
        trust_remote_code=False,
        local_files_only=local_files_only,
    )

    rows: list[dict[str, Any]] = []
    catalogs = [
        int(value)
        for value in prereg["confirmation_surface"]["catalogs"]
    ]

    for size in catalogs:
        catalog_path = freeze_dir / f"catalog-{size}.json"
        catalog_payload = json.loads(
            catalog_path.read_text(encoding="utf-8")
        )
        if _sha(catalog_payload) != manifest["catalogs"][
            str(size)
        ]["sha256"]:
            raise RuntimeError(
                f"fixed-K3 catalog-{size} hash drifted"
            )

        registry = _load_registry(catalog_path)
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
                    f"{task['task_id']} catalog {size}: expected 5 candidates"
                )
            route_ids = [
                str(candidate.route_id)
                for candidate in retrieval.candidates
            ]
            if len(route_ids) != len(set(route_ids)):
                raise RuntimeError(
                    f"{task['task_id']} catalog {size}: duplicate route"
                )

            top3 = route_ids[:3]
            top5 = route_ids[:5]
            rows.append(
                {
                    **task,
                    "catalog_size": size,
                    "retrieval_latency_ms": latency_ms,
                    "top3_route_ids": top3,
                    "top5_route_ids": top5,
                    "schema_tokens_k3": _tool_tokens(
                        tokenizer,
                        registry,
                        query,
                        top3,
                    ),
                    "schema_tokens_k5": _tool_tokens(
                        tokenizer,
                        registry,
                        query,
                        top5,
                    ),
                }
            )

    expected_rows = len(tasks) * len(catalogs)
    if len(rows) != expected_rows:
        raise RuntimeError(
            f"fixed-K3 confirmation row drift: "
            f"{len(rows)} != {expected_rows}"
        )

    per_catalog: dict[str, Any] = {}
    for size in catalogs:
        subset = [
            row
            for row in rows
            if int(row["catalog_size"]) == size
        ]
        per_catalog[str(size)] = {
            "k3": _coverage_summary(subset, k=3),
            "k5": _coverage_summary(subset, k=5),
        }

    typed_rows = [
        row
        for row in rows
        if row["task_stratum"] == "typed_numeric_units"
    ]
    typed_k3 = _coverage_summary(typed_rows, k=3)

    k3_tokens = [
        int(row["schema_tokens_k3"])
        for row in rows
    ]
    k5_tokens = [
        int(row["schema_tokens_k5"])
        for row in rows
    ]
    latency = [
        float(row["retrieval_latency_ms"])
        for row in rows
    ]

    gates = prereg["gates"]
    coverage_pass = all(
        float(per_catalog[str(size)]["k3"][
            "required_route_recall"
        ])
        >= float(
            gates["required_route_recall_at_3_min_each_catalog"]
        )
        and float(per_catalog[str(size)]["k3"][
            "all_required_full_coverage"
        ])
        >= float(
            gates[
                "all_required_full_coverage_at_3_min_each_catalog"
            ]
        )
        for size in catalogs
    )
    typed_pass = (
        float(typed_k3["required_route_recall"])
        >= float(gates["typed_numeric_units_recall_at_3_min"])
    )
    token_pass = statistics.fmean(k3_tokens) < statistics.fmean(
        k5_tokens
    )

    passed = bool(
        coverage_pass
        and typed_pass
        and token_pass
    )

    return {
        "schema_version": 1,
        "issue": prereg["issue"],
        "experiment": prereg["experiment"],
        "surface": "fresh_confirmation",
        "fixed_candidate": prereg["fixed_candidate"],
        "manifest_identity": {
            "task_rows_sha256": manifest["task_rows_sha256"],
            "catalog_family_sha256": manifest[
                "catalog_family_sha256"
            ],
            "exact_normalized_prior_query_overlap_count": manifest[
                "exact_normalized_prior_query_overlap_count"
            ],
        },
        "row_count": len(rows),
        "per_catalog": per_catalog,
        "typed_numeric_units_k3": typed_k3,
        "context_cost": {
            "mean_schema_tokens_k3": statistics.fmean(k3_tokens),
            "mean_schema_tokens_k5": statistics.fmean(k5_tokens),
            "reduction_vs_k5_fraction": (
                1
                - statistics.fmean(k3_tokens)
                / statistics.fmean(k5_tokens)
            ),
            "candidate_count_k3": 3,
            "candidate_count_k5": 5,
        },
        "retrieval_latency_ms": {
            "mean": statistics.fmean(latency),
            "max": max(latency),
        },
        "gates": {
            "coverage_passed": coverage_pass,
            "typed_numeric_units_passed": typed_pass,
            "schema_token_reduction_passed": token_pass,
            "passed": passed,
        },
        "research_integrity": {
            "confirmation_surface_tuning_used": False,
            "prior_structural_confirmation_rows_used": False,
            "b2_outcomes_used": False,
            "candidate_changed_after_freeze": False,
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--freeze-dir",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
    )
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
                "passed": result["gates"]["passed"],
                "per_catalog": result["per_catalog"],
                "typed_numeric_units_k3": result[
                    "typed_numeric_units_k3"
                ],
                "context_cost": result["context_cost"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
