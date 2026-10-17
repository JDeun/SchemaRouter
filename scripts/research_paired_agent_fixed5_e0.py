"""Paired fixed-K5 agent DEV/E0 report; never independent E2 qualification.

Consumes post-execution, allowlisted HMAC task traces from the *existing*
EVAL-FIXED5-OPTIN agent loop. No raw task queries, tool arguments or gold.
The old #432 statistic implementation is reused without mutating its scores.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any

from scripts.aggregate_agent_utility_v3_heldout import (
    _paired_stratified_bootstrap,
)
from scripts.research_agent_stage_evidence_e0 import (
    CONDITION,
    EVIDENCE_TIER,
    SCHEMA_VERSION,
)

ARMS = ("lexical_k5", "e5_k5", "hybrid_k5")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
OBSERVED = frozenset({
    "passed", "context_overflow_observed",
    "unsupported_tool_executed", "unsupported_no_fit_response_mismatch",
    "initial_required_route_not_exposed", "policy_block_observed",
    "input_schema_rejection_observed", "wrong_operation_attempt_observed",
    "task_argument_mismatch_observed", "tool_execution_error_observed",
    "agent_final_before_task_completion",
    "supported_no_fit_refusal_observed", "unclassified",
})
COUNTS = ("input_tokens", "tool_schema_tokens", "tool_call_count")
LATENCIES = ("candidate_selection_latency_ms", "episode_wall_latency_ms")


def _digest(value: Any, name: str, *, size: int = 64) -> str:
    if type(value) is not str or not (HEX40 if size == 40 else HEX64).fullmatch(value):
        raise ValueError(f"invalid {name}: exact lowercase hex digest required")
    return value


def _nonnegative(value: Any, name: str, *, integer: bool = False) -> float | int:
    if integer:
        if type(value) is not int or value < 0:
            raise ValueError(f"invalid {name}: nonnegative integer required")
        return value
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"invalid {name}: finite nonnegative number required")
    return float(value)


def _identity(manifest: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if type(manifest) is not dict or manifest.get("schema_version") != 1:
        raise ValueError("invalid opt-in paired E0 manifest")
    if (
        manifest.get("evidence_tier") != EVIDENCE_TIER
        or manifest.get("independent_e2_qualified") is not False
        or manifest.get("arms") != list(ARMS)
    ):
        raise ValueError("independent E2 or unregistered arms forbidden in E0")
    _digest(manifest.get("source_revision"), "source_revision", size=40)
    _digest(manifest.get("source_sha256"), "source_sha256")
    _digest(manifest.get("split_sha256"), "split_sha256")
    for key in ("model_revision", "model_runtime", "hardware", "split_name"):
        if type(manifest.get(key)) is not str or not manifest[key].strip():
            raise ValueError(f"missing comparable {key}")
    _nonnegative(manifest.get("seed"), "seed", integer=True)
    if manifest.get("max_k") != 5 or type(manifest.get("max_k")) is not int:
        raise ValueError("fixed K must be exactly five for all arms")
    tasks = manifest.get("tasks")
    if type(tasks) is not list or not tasks:
        raise ValueError("paired task manifest must be nonempty")
    identities: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if type(task) is not dict:
            raise ValueError("malformed task manifest row")
        ident = _digest(task.get("task_hmac_sha256"), "task_hmac_sha256")
        if ident in identities:
            raise ValueError("duplicate task identity")
        if task.get("language") not in ("en", "ko", "ja"):
            raise ValueError("task is outside required EN/KO/JA comparison languages")
        if type(task.get("task_stratum")) is not str or not task["task_stratum"]:
            raise ValueError("missing task stratum")
        if type(task.get("supported")) is not bool:
            raise ValueError("missing supported/OOD label")
        identities[ident] = task
    return identities, {key: manifest[key] for key in (
        "source_revision", "source_sha256", "split_sha256", "model_revision",
        "model_runtime", "hardware", "split_name", "seed", "max_k",
    )}


def _validate_run(
    arm: str,
    run: dict[str, Any],
    identity: dict[str, Any],
    tasks: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if type(run) is not dict or run.get("arm") != arm:
        raise ValueError(f"{arm}: mismatched run arm")
    if run.get("evidence_tier") != EVIDENCE_TIER:
        raise ValueError(f"{arm}: invalid E0 run tier")
    if any(
        type(run.get(name)) is not type(value) or run.get(name) != value
        for name, value in identity.items()
    ):
        raise ValueError(f"{arm}: source/model/hardware/split/seed/K drift")
    rows = run.get("rows")
    if type(rows) is not list or len(rows) != len(tasks):
        raise ValueError(f"{arm}: incomplete or oversampled paired task cohort")
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        if (
            type(row) is not dict
            or row.get("schema_version") != SCHEMA_VERSION
            or row.get("evidence_tier") != EVIDENCE_TIER
            or row.get("independent_e2_qualified") is not False
            or row.get("condition") != CONDITION
            or row.get("source_revision") != identity["source_revision"]
            or row.get("source_sha256") != identity["source_sha256"]
            or type(row.get("seed")) is not int
            or row["seed"] != identity["seed"]
        ):
            raise ValueError(f"{arm}: unsafe or mismatched E0 trace")
        ident = _digest(row.get("task_hmac_sha256"), "task_hmac_sha256")
        if ident not in tasks or ident in by_id:
            raise ValueError(f"{arm}: unknown or duplicate paired task")
        task = tasks[ident]
        if (
            row.get("language") != task["language"]
            or row.get("supported") is not task["supported"]
            or type(row.get("passed")) is not bool
            or type(row.get("task_complete")) is not bool
        ):
            raise ValueError(f"{arm}: task gold/identity/label drift")
        candidate_counts = row.get("visible_candidate_counts")
        if (
            type(candidate_counts) is not list or len(candidate_counts) != 1
            or type(candidate_counts[0]) is not int
            or not 0 <= candidate_counts[0] <= 5
        ):
            raise ValueError(f"{arm}: fixed-K5 candidate exposure violated")
        stages = row.get("observed_stages")
        if (
            type(stages) is not list or not stages
            or any(type(stage) is not str or stage not in OBSERVED for stage in stages)
            or len(set(stages)) != len(stages)
            or (row["passed"] and stages != ["passed"])
            or (not row["passed"] and "passed" in stages)
        ):
            raise ValueError(f"{arm}: malformed post-execution stage evidence")
        for name in COUNTS:
            _nonnegative(row.get(name), name, integer=True)
        for name in LATENCIES:
            _nonnegative(row.get(name), name)
        if _nonnegative(
            row.get("unauthorized_destructive_executions"),
            "unauthorized_destructive_executions",
            integer=True,
        ) != 0:
            raise ValueError(f"{arm}: unauthorized destructive execution: STOP")
        by_id[ident] = row
    if set(by_id) != set(tasks):
        raise ValueError(f"{arm}: tasks not paired to manifest")
    return by_id


def aggregate_paired_e0(
    manifest: dict[str, Any],
    runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate confirmed identical self-declared DEV runs, not E2 claims.

    Source/hardware assertions are untrusted external metadata: a separate
    maintainer verification is required before any scored E2 qualification.
    """
    tasks, identity = _identity(manifest)
    if type(runs) is not dict or set(runs) != set(ARMS):
        raise ValueError("require exactly three fixed-K5 paired runs")
    rows_by_arm = {
        arm: _validate_run(arm, runs[arm], identity, tasks)
        for arm in ARMS
    }
    corpus = {"tasks": [
        {
            "semantic_task_id": ident,
            "language": task["language"],
            "task_stratum": task["task_stratum"],
        }
        for ident, task in sorted(tasks.items())
    ]}
    base = [
        {"task_id": ident, "passed": rows_by_arm["lexical_k5"][ident]["passed"]}
        for ident in sorted(tasks)
    ]
    paired: dict[str, Any] = {}
    for arm in ("e5_k5", "hybrid_k5"):
        target = [
            {"task_id": ident, "passed": rows_by_arm[arm][ident]["passed"]}
            for ident in sorted(tasks)
        ]
        paired[arm] = _paired_stratified_bootstrap(corpus, base, target)

    overall: dict[str, dict[str, Any]] = {}
    for arm, rows in rows_by_arm.items():
        values = list(rows.values())
        by_lang = {
            language: {
                "tasks": sum(row["language"] == language for row in values),
                "pass_rate": (
                    statistics.fmean(
                        float(row["passed"]) for row in values
                        if row["language"] == language
                    )
                    if any(row["language"] == language for row in values)
                    else None
                ),
            }
            for language in ("en", "ko", "ja")
        }
        overall[arm] = {
            "task_pass_rate": statistics.fmean(float(row["passed"]) for row in values),
            "task_count": len(values),
            "by_language": by_lang,
            "mean_input_tokens": statistics.fmean(row["input_tokens"] for row in values),
            "mean_tool_schema_tokens": statistics.fmean(
                row["tool_schema_tokens"] for row in values
            ),
            "mean_selection_latency_ms": statistics.fmean(
                row["candidate_selection_latency_ms"] for row in values
            ),
            "mean_episode_latency_ms": statistics.fmean(
                row["episode_wall_latency_ms"] for row in values
            ),
            "unsupported_executed_observed": sum(
                not row["supported"]
                and "unsupported_tool_executed" in row["observed_stages"]
                for row in values
            ),
            "unsupported_tasks": sum(not row["supported"] for row in values),
            "unauthorized_destructive_executions": 0,
        }
    return {
        "schema_version": 1,
        "issue": 1477,
        "evidence_tier": EVIDENCE_TIER,
        "independent_e2_qualified": False,
        "publication_gate_passed": False,
        "decision": "E0_DESCRIPTIVE_ONLY_NOT_INDEPENDENT_E2",
        "task_count": len(tasks),
        "arms": list(ARMS),
        "source_sha256": identity["source_sha256"],
        "split_sha256": identity["split_sha256"],
        "model_revision": identity["model_revision"],
        "hardware": identity["hardware"],
        "summary": overall,
        "paired_task_pass_delta_vs_lexical_k5": paired,
        "coverage_limitations": [
            "self-declared run metadata is not an authenticated source receipt",
            "no independent publisher-authored tasks or real model outcomes verified",
            "HMAC task identities only; field/route recall unavailable from redacted E0 traces",
            "no automatic release or statistical success gate from E0",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = aggregate_paired_e0(
        json.loads(args.manifest.read_text(encoding="utf-8")),
        json.loads(args.runs.read_text(encoding="utf-8")),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print(json.dumps({"decision": result["decision"], "task_count": result["task_count"]}))


if __name__ == "__main__":
    main()
