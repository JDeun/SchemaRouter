"""Aggregate the frozen #424 deterministic final-answer benchmark."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

CATALOGS = (100, 250)


def _load_rows(input_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(input_dir.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("issue") != 424 or "rows" not in data:
            continue
        shard = data["rows"]
        if not isinstance(shard, list):
            raise ValueError(f"{path}: rows must be an array")
        rows.extend(shard)
    if not rows:
        raise ValueError("no final-answer rows found")
    return rows


def _mean_optional(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [
        float(row[key])
        for row in rows
        if row.get(key) is not None
    ]
    return statistics.fmean(values) if values else None


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "episodes": len(rows),
        "task_completion_rate": statistics.fmean(float(row["passed"]) for row in rows),
        "final_envelope_valid_rate": statistics.fmean(
            float(row["final_envelope_valid"]) for row in rows
        ),
        "required_fact_recall": statistics.fmean(
            float(row["required_fact_recall"]) for row in rows
        ),
        "numeric_value_accuracy": _mean_optional(rows, "numeric_value_accuracy"),
        "unit_accuracy": _mean_optional(rows, "unit_accuracy"),
        "provenance_accuracy": statistics.fmean(
            float(row["provenance_accuracy"]) for row in rows
        ),
        "unsupported_fact_count": sum(
            int(row["unsupported_fact_count"]) for row in rows
        ),
        "unsupported_fact_rate": statistics.fmean(
            float(row["unsupported_fact_rate"]) for row in rows
        ),
        "contradiction_count": sum(int(row["contradiction_count"]) for row in rows),
        "exact_field_completion_rate": statistics.fmean(
            float(row["exact_field_completion"]) for row in rows
        ),
        "source_list_valid_rate": statistics.fmean(
            float(row["source_list_valid"]) for row in rows
        ),
        "required_tool_evidence_coverage": statistics.fmean(
            float(row["required_route_call_coverage"]) for row in rows
        ),
        "mean_input_tokens": statistics.fmean(float(row["input_tokens"]) for row in rows),
        "mean_tool_schema_tokens": statistics.fmean(
            float(row["tool_schema_tokens"]) for row in rows
        ),
        "mean_output_tokens": statistics.fmean(
            float(row["output_tokens"]) for row in rows
        ),
        "unauthorized_destructive_executions": sum(
            int(row["unauthorized_destructive_executions"]) for row in rows
        ),
    }


def _delta(value: float | None, reference: float | None) -> float | None:
    if value is None or reference is None:
        return None
    return value - reference


def aggregate(input_dir: Path, corpus: dict[str, Any]) -> dict[str, Any]:
    rows = _load_rows(input_dir)
    conditions = list(corpus["condition_manifest"]["conditions"])
    expected = {
        (str(task["semantic_task_id"]), catalog, condition)
        for task in corpus["tasks"]
        for catalog in CATALOGS
        for condition in conditions
    }
    actual = {
        (str(row["task_id"]), int(row["catalog_size"]), str(row["condition"]))
        for row in rows
    }
    if actual != expected or len(rows) != len(expected):
        raise ValueError(
            f"final-answer episode identity mismatch: expected={len(expected)} actual={len(rows)}"
        )

    by_condition = {
        condition: [row for row in rows if row["condition"] == condition]
        for condition in conditions
    }
    overall = {
        condition: _summary(condition_rows)
        for condition, condition_rows in by_condition.items()
    }
    full = overall["FULL"]
    gates: dict[str, Any] = {}

    for condition in conditions:
        if condition in {"FULL", "ORACLE"}:
            continue
        current = overall[condition]
        schema_ratio = (
            current["mean_tool_schema_tokens"] / full["mean_tool_schema_tokens"]
            if full["mean_tool_schema_tokens"]
            else None
        )
        fact_delta = _delta(current["required_fact_recall"], full["required_fact_recall"])
        numeric_delta = _delta(
            current["numeric_value_accuracy"],
            full["numeric_value_accuracy"],
        )
        unit_delta = _delta(current["unit_accuracy"], full["unit_accuracy"])
        provenance_delta = _delta(
            current["provenance_accuracy"],
            full["provenance_accuracy"],
        )
        unsupported_delta = (
            current["unsupported_fact_rate"] - full["unsupported_fact_rate"]
        )
        gate = {
            "fact_recall_delta_vs_full": fact_delta,
            "fact_recall_gate": fact_delta is not None and fact_delta >= -0.02,
            "numeric_accuracy_delta_vs_full": numeric_delta,
            "numeric_accuracy_gate": (
                numeric_delta is None or numeric_delta >= -0.02
            ),
            "unit_accuracy_delta_vs_full": unit_delta,
            "unit_accuracy_gate": unit_delta is None or unit_delta >= -0.02,
            "provenance_accuracy_delta_vs_full": provenance_delta,
            "provenance_accuracy_gate": (
                provenance_delta is not None and provenance_delta >= -0.02
            ),
            "unsupported_fact_rate_delta_vs_full": unsupported_delta,
            "unsupported_fact_rate_gate": unsupported_delta <= 0.01,
            "contradiction_count_gate": (
                current["contradiction_count"] <= full["contradiction_count"]
            ),
            "required_tool_evidence_coverage": current[
                "required_tool_evidence_coverage"
            ],
            "required_tool_evidence_coverage_gate": current[
                "required_tool_evidence_coverage"
            ]
            >= 0.97,
            "total_input_tokens_gate": (
                current["mean_input_tokens"] < full["mean_input_tokens"]
            ),
            "tool_schema_token_ratio_vs_full": schema_ratio,
            "tool_schema_token_gate": (
                schema_ratio is not None and schema_ratio <= 0.4
            ),
            "unauthorized_destructive_executions": current[
                "unauthorized_destructive_executions"
            ],
            "safety_gate": current["unauthorized_destructive_executions"] == 0,
        }
        gate["primary_gate_passed"] = all(
            (
                gate["fact_recall_gate"],
                gate["numeric_accuracy_gate"],
                gate["unit_accuracy_gate"],
                gate["provenance_accuracy_gate"],
                gate["unsupported_fact_rate_gate"],
                gate["contradiction_count_gate"],
                gate["required_tool_evidence_coverage_gate"],
                gate["total_input_tokens_gate"],
                gate["tool_schema_token_gate"],
                gate["safety_gate"],
            )
        )
        gates[condition] = gate

    return {
        "schema_version": 1,
        "issue": 424,
        "experiment": corpus["experiment"],
        "episode_count": len(rows),
        "expected_episode_count": len(expected),
        "unique_semantic_tasks": len(corpus["tasks"]),
        "catalog_sizes": list(CATALOGS),
        "conditions": conditions,
        "generator_source_revision": corpus["generator_source_revision"],
        "tasks_sha256": corpus["tasks_sha256"],
        "freeze_identity_sha256": corpus["freeze_identity_sha256"],
        "overall": overall,
        "primary_gates": gates,
        "any_deployable_condition_passed": any(
            gate["primary_gate_passed"] for gate in gates.values()
        ),
        "claim_boundary": (
            "Final-answer factual quality on the frozen 144-task surface only. "
            "Broad generalization additionally depends on #432."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    result = aggregate(args.input_dir, corpus)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "any_deployable_condition_passed": result[
                    "any_deployable_condition_passed"
                ],
                "primary_gates": result["primary_gates"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
