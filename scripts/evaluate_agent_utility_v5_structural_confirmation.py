"""Evaluate the frozen structural-v2 confirmation surface exactly once."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
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

PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-structural-retrieval-v2-preregistration.json"
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
UNSUPPORTED_STRATA = {
    "near_domain_unsupported",
    "out_of_domain",
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
        raise RuntimeError(
            "confirmation surface was not frozen before scoring"
        )

    tasks = json.loads(
        (freeze_dir / "confirmation-tasks.json")
        .read_text(encoding="utf-8")
    )
    if _sha(tasks) != manifest["task_rows_sha256"]:
        raise RuntimeError(
            "confirmation task hash does not match freeze manifest"
        )

    for size in CATALOG_SIZES:
        catalog = json.loads(
            (freeze_dir / f"catalog-{size}.json")
            .read_text(encoding="utf-8")
        )
        expected = manifest["catalogs"][str(size)]["sha256"]
        if _sha(catalog) != expected:
            raise RuntimeError(
                f"confirmation catalog-{size} hash mismatch"
            )

    return manifest, tasks


def _new_accumulator() -> dict[str, Any]:
    return {
        "required_hits": 0,
        "required_total": 0,
        "full_coverage_hits": 0,
        "supported_rows": 0,
        "candidate_counts": [],
    }


def _update_accumulator(
    accumulator: dict[str, Any],
    *,
    required: set[str],
    selected: set[str],
    candidate_count: int,
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


def _summary(
    accumulator: dict[str, Any],
) -> dict[str, Any]:
    required_total = int(
        accumulator["required_total"]
    )
    supported_rows = int(
        accumulator["supported_rows"]
    )
    return {
        "supported_rows": supported_rows,
        "required_route_count": required_total,
        "required_route_recall_at_10": (
            accumulator["required_hits"]
            / required_total
            if required_total
            else None
        ),
        "all_required_full_coverage_at_10": (
            accumulator["full_coverage_hits"]
            / supported_rows
            if supported_rows
            else None
        ),
        "candidate_count": _distribution(
            accumulator["candidate_counts"]
        ),
    }


def _evaluate_condition(
    *,
    freeze_dir: Path,
    tasks: list[dict[str, Any]],
    structural: bool,
) -> dict[str, Any]:
    pooled = _new_accumulator()
    per_catalog_acc: dict[str, dict[str, Any]] = {}
    per_stratum_acc: dict[str, dict[str, Any]] = {}
    per_language_acc: dict[str, dict[str, Any]] = {}
    unsupported_counts: dict[str, list[float]] = defaultdict(
        list
    )
    rows: list[dict[str, Any]] = []

    for size in CATALOG_SIZES:
        registry = _load_registry(
            freeze_dir / f"catalog-{size}.json"
        )
        planner = SchemaPlanner(
            registry,
            structural_retrieval=structural,
        )

        for task in tasks:
            result = planner.retrieve(
                str(task["query"]),
                k=10,
            )
            selected = {
                candidate.route_id
                for candidate in result.candidates
            }
            required = {
                str(route_id)
                for route_id in task["required_route_ids"]
            }
            stratum = str(task["task_stratum"])
            language = str(task["language"])
            candidate_count = len(result.candidates)

            row = {
                "task_id": str(task["task_id"]),
                "task_stratum": stratum,
                "language": language,
                "catalog_size": size,
                "required_route_ids": sorted(required),
                "top10_route_ids": [
                    candidate.route_id
                    for candidate in result.candidates
                ],
                "top10_scores": [
                    float(candidate.score)
                    for candidate in result.candidates
                ],
                "candidate_count": candidate_count,
            }
            rows.append(row)

            if stratum in SUPPORTED_STRATA:
                catalog_acc = per_catalog_acc.setdefault(
                    str(size),
                    _new_accumulator(),
                )
                stratum_acc = per_stratum_acc.setdefault(
                    stratum,
                    _new_accumulator(),
                )
                language_acc = per_language_acc.setdefault(
                    language,
                    _new_accumulator(),
                )
                for accumulator in (
                    pooled,
                    catalog_acc,
                    stratum_acc,
                    language_acc,
                ):
                    _update_accumulator(
                        accumulator,
                        required=required,
                        selected=selected,
                        candidate_count=candidate_count,
                    )
            elif stratum in UNSUPPORTED_STRATA:
                unsupported_counts[stratum].append(
                    float(candidate_count)
                )
            else:
                raise RuntimeError(
                    f"unknown confirmation stratum: {stratum}"
                )

    return {
        "structural_retrieval": structural,
        "pooled": _summary(pooled),
        "per_catalog": {
            key: _summary(value)
            for key, value in sorted(
                per_catalog_acc.items(),
                key=lambda item: int(item[0]),
            )
        },
        "per_stratum": {
            key: _summary(value)
            for key, value in sorted(
                per_stratum_acc.items()
            )
        },
        "per_language": {
            key: _summary(value)
            for key, value in sorted(
                per_language_acc.items()
            )
        },
        "unsupported_candidate_count": {
            key: _distribution(value)
            for key, value in sorted(
                unsupported_counts.items()
            )
        },
        "rows": rows,
    }


def evaluate(
    freeze_dir: Path,
) -> dict[str, Any]:
    prereg = json.loads(
        PREREG.read_text(encoding="utf-8")
    )
    manifest, tasks = _verify_freeze(freeze_dir)

    fixed = prereg["fixed_candidate"]
    if (
        float(fixed["tool_identifier_bonus"])
        != _STRUCTURAL_TOOL_IDENTIFIER_BONUS
    ):
        raise RuntimeError(
            "core tool-identifier bonus drifted from v2 preregistration"
        )
    if (
        float(fixed["operation_family_bonus"])
        != _STRUCTURAL_OPERATION_FAMILY_BONUS
    ):
        raise RuntimeError(
            "core operation-family bonus drifted from v2 preregistration"
        )
    if not bool(
        fixed["schema_specificity_tiebreak"]
    ):
        raise RuntimeError(
            "v2 preregistration requires specificity tie-break"
        )

    probe_registry = _load_registry(
        freeze_dir / "catalog-100.json"
    )
    if SchemaPlanner(probe_registry).structural_retrieval:
        raise RuntimeError(
            "structural retrieval product default must remain disabled"
        )

    baseline = _evaluate_condition(
        freeze_dir=freeze_dir,
        tasks=tasks,
        structural=False,
    )
    candidate = _evaluate_condition(
        freeze_dir=freeze_dir,
        tasks=tasks,
        structural=True,
    )

    gates = prereg["confirmation_protocol"]
    recall_min = float(
        gates[
            "required_tool_set_recall_min_each_catalog"
        ]
    )
    full_min = float(
        gates[
            "all_required_full_coverage_min_each_catalog"
        ]
    )
    typed_min = float(
        gates["typed_numeric_units_recall_min"]
    )

    catalog_gate = all(
        float(metrics["required_route_recall_at_10"])
        >= recall_min
        and float(
            metrics[
                "all_required_full_coverage_at_10"
            ]
        )
        >= full_min
        for metrics in candidate["per_catalog"].values()
    )
    typed_metrics = candidate["per_stratum"][
        "typed_numeric_units"
    ]
    typed_gate = (
        float(
            typed_metrics[
                "required_route_recall_at_10"
            ]
        )
        >= typed_min
    )

    confirmation_passed = bool(
        catalog_gate and typed_gate
    )

    return {
        "schema_version": 1,
        "issue": 430,
        "experiment": prereg["experiment"],
        "surface": "confirmation",
        "freeze_manifest_sha256": _sha(manifest),
        "task_rows_sha256": manifest[
            "task_rows_sha256"
        ],
        "catalog_family_sha256": manifest[
            "catalog_family_sha256"
        ],
        "fixed_candidate": fixed,
        "baseline": baseline,
        "candidate": candidate,
        "gates": {
            "catalog_recall_min": recall_min,
            "catalog_full_coverage_min": full_min,
            "typed_numeric_units_recall_min": typed_min,
            "catalog_gate_passed": catalog_gate,
            "typed_numeric_units_gate_passed": typed_gate,
        },
        "confirmation_passed": confirmation_passed,
        "confirmation_surface_tuning_used": False,
        "product_default_enabled": False,
        "claim_boundary": (
            "Independent structural retrieval confirmation only; "
            "adaptive-K and downstream-agent promotion remain separate gates."
        ),
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
    args = parser.parse_args()

    result = evaluate(args.freeze_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
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
                "baseline_per_catalog": result[
                    "baseline"
                ]["per_catalog"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
