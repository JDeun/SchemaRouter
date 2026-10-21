"""Verify the archived negative E1 result; never score as independent E2.

Only bounded, source-agnostic metrics and categories are permitted in the
committed snapshot. This is an integrity guard, not a source authenticity
proof: origin is the separately downloaded Actions ZIP / immutable digest.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

SOURCE = Path(__file__).resolve().parents[1] / (
    "benchmarks/research-qwen-verified-reminder-e1-negative-v1.json"
)
ARMS = ("original", "one_verified_reminder")
LANGUAGES = ("en", "ko", "ja")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
EXPECTED_RUN = 39533699395
EXPECTED_ARTIFACT = 12316407743
EXPECTED_DIGEST = "c965ad7c8deca49fbd66bb3a8540c508d44eca0cb1f6847e894261ea3bb06cc4"
EXPECTED_JSON_DIGEST = "2e31a3be8c9d8ba3df24ee87bbd6d2e005e26ad2bf54d8e98a2f04df365a4608"
TOP_KEYS = frozenset({
    "schema_version", "experiment_id", "issue", "evidence_tier",
    "decision", "control_arm", "candidate_arm", "run", "runtime",
    "study", "by_arm", "gates", "cautions",
})
STUDY_KEYS = frozenset({
    "paired_language_count", "language_order", "source",
    "retries_per_http_get", "model_turn_cap", "model_menu",
    "total_http_attempt_ceiling", "live_source_drift_possible",
})
CAUTIONS = [
    "N=3 disclosed language cases per arm, not a disjoint benchmark",
    "Korean candidate suffered live geocoding timeout, so throughput and token aggregates are not causal",
    "English opt-in reminder did not recover second tool call",
    "Japanese and Korean baseline terminal shapes were wrong after verified two sources",
    "Never modify historical frozen #432 outcomes or release PR #1356 based on this snapshot",
]
ROW_KEYS = frozenset({
    "termination", "geocodes", "forecasts", "http_attempts", "turns",
    "host_reminders", "final_failure", "transport_failure",
})
ARM_KEYS = frozenset({
    "strict_tasks_passed", "http_attempts", "model_turns", "host_reminders",
    "model_generation_ms", "input_tokens", "tool_tokens", "output_tokens",
    "by_language",
})
REASONS = {
    "premature_final", "incorrect_final_value_or_format",
    "host_or_native_source_denied",
}


def _nonnegative_int(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"invalid nonnegative count: {label}")
    return value


def _bounded_number(value: Any, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"invalid finite timing: {label}")
    return float(value)


def verify(snapshot: dict[str, Any]) -> dict[str, Any]:
    if (
        type(snapshot) is not dict
        or set(snapshot) != TOP_KEYS
        or snapshot.get("schema_version") != 1
        or type(snapshot.get("schema_version")) is not int
        or snapshot.get("experiment_id")
        != "qwen-verified-reminder-paired-live-open-meteo-e1-20261021"
        or snapshot.get("cautions") != CAUTIONS
    ):
        raise ValueError("invalid or unallowlisted negative-evidence schema")
    if (
        snapshot.get("evidence_tier")
        != "EXPOSED_SELF_AUTHORED_LIVE_PROVIDER_E1_DEV_ONLY"
        or snapshot.get("decision") != "VALID_NEGATIVE_NO_STRICT_TASK_PASS_UPLIFT"
        or snapshot.get("control_arm") != "original"
        or snapshot.get("candidate_arm") != "one_verified_reminder"
        or snapshot.get("issue") != 1477
    ):
        raise ValueError("E1 evidence must retain unqualified negative identity")
    run = snapshot.get("run")
    if type(run) is not dict or set(run) != {
        "workflow_run_id", "artifact_id", "artifact_zip_sha256",
        "report_json_sha256", "pr_head_sha", "workflow_report_source_revision",
        "merge_sha",
    }:
        raise ValueError("incomplete immutable source provenance")
    if (
        run["workflow_run_id"] != EXPECTED_RUN
        or type(run["workflow_run_id"]) is not int
        or run["artifact_id"] != EXPECTED_ARTIFACT
        or type(run["artifact_id"]) is not int
        or run["artifact_zip_sha256"] != EXPECTED_DIGEST
        or run["report_json_sha256"] != EXPECTED_JSON_DIGEST
        or any(
            type(run[key]) is not str or HEX40.fullmatch(run[key]) is None
            for key in (
                "pr_head_sha", "workflow_report_source_revision", "merge_sha",
            )
        )
        or HEX64.fullmatch(run["artifact_zip_sha256"]) is None
        or HEX64.fullmatch(run["report_json_sha256"]) is None
    ):
        raise ValueError("unverified origin or artifact digest")
    runtime = snapshot.get("runtime")
    if (
        type(runtime) is not dict
        or set(runtime) != {
            "model_id", "model_revision", "python", "torch", "transformers",
            "hardware",
        }
        or runtime["model_id"] != "Qwen/Qwen3-0.6B"
        or runtime["model_revision"]
        != "c1899de289a04d12100db370d81485cdf75e47ca"
    ):
        raise ValueError("unverified model identity")
    study = snapshot.get("study")
    if (
        type(study) is not dict
        or set(study) != STUDY_KEYS
        or study.get("source")
        != "Open-Meteo original live geocoding/weather endpoints"
        or study.get("paired_language_count") != 3
        or type(study.get("paired_language_count")) is not int
        or study.get("language_order") != list(LANGUAGES)
        or study.get("retries_per_http_get") != 1
        or type(study.get("retries_per_http_get")) is not int
        or study.get("model_turn_cap") != 4
        or type(study.get("model_turn_cap")) is not int
        or study.get("model_menu") != "state_ready"
        or study.get("total_http_attempt_ceiling") != 24
        or type(study.get("total_http_attempt_ceiling")) is not int
        or study.get("live_source_drift_possible") is not True
    ):
        raise ValueError("live comparison protocol drift")
    gates = snapshot.get("gates")
    if type(gates) is not dict or set(gates) != {
        "independent_task_author_confirmed", "independent_e2_qualified",
        "calibrated_no_fit", "product_default_changed", "release_qualified",
    } or any(value is not False for value in gates.values()):
        raise ValueError("independent qualification or product promotion forbidden")
    by_arm = snapshot.get("by_arm")
    if type(by_arm) is not dict or set(by_arm) != set(ARMS):
        raise ValueError("require both original and candidate arms")

    report: dict[str, Any] = {}
    for arm in ARMS:
        data = by_arm[arm]
        if type(data) is not dict or set(data) != ARM_KEYS:
            raise ValueError("unallowlisted arm data (possible source leak)")
        rows = data["by_language"]
        if type(rows) is not dict or set(rows) != set(LANGUAGES):
            raise ValueError("incomplete paired source-native languages")
        attempts = turns = reminders = 0
        for language in LANGUAGES:
            row = rows[language]
            if type(row) is not dict or set(row) != ROW_KEYS:
                raise ValueError("unallowlisted row data (possible source leak)")
            for name in ("geocodes", "forecasts", "http_attempts", "turns",
                         "host_reminders"):
                _nonnegative_int(row[name], f"{arm}/{language}/{name}")
            if not (
                0 <= row["forecasts"] <= row["geocodes"] <= 1
                and 0 <= row["http_attempts"] <= 4
                and 1 <= row["turns"] <= 4
                and 0 <= row["host_reminders"] <= 1
                and row["http_attempts"]
                >= row["geocodes"] + row["forecasts"]
                and row["termination"] in REASONS
            ):
                raise ValueError("unbounded or internally invalid E1 source row")
            if row["final_failure"] not in (None, "invalid_shape"):
                raise ValueError("unexpected final category: do not fabricate source scores")
            if row["transport_failure"] not in (None, "connect_timeout"):
                raise ValueError("unknown native provider transport class")
            if row["termination"] == "premature_final" and (
                row["forecasts"] or row["final_failure"] is not None
            ):
                raise ValueError("premature final cannot have verified weather")
            if row["termination"] == "incorrect_final_value_or_format" and (
                row["forecasts"] != 1 or row["final_failure"] != "invalid_shape"
            ):
                raise ValueError("wrong final must preserve actual source validation")
            if row["termination"] == "host_or_native_source_denied" and (
                row["transport_failure"] is None or row["forecasts"]
            ):
                raise ValueError("source denial cannot become model success")
            if arm == "original" and row["host_reminders"]:
                raise ValueError("control arm contamination")
            if row["host_reminders"] and (
                row["geocodes"] != 1 or row["turns"] < 3
            ):
                raise ValueError("unearned host continuation")
            attempts += row["http_attempts"]
            turns += row["turns"]
            reminders += row["host_reminders"]
        for name in ("strict_tasks_passed", "http_attempts", "model_turns",
                     "host_reminders", "input_tokens", "tool_tokens",
                     "output_tokens"):
            _nonnegative_int(data[name], f"{arm}/{name}")
        _bounded_number(data["model_generation_ms"], f"{arm}/model_generation_ms")
        if (
            data["strict_tasks_passed"] != 0
            or data["http_attempts"] != attempts
            or data["model_turns"] != turns
            or data["host_reminders"] != reminders
            or data["tool_tokens"] > data["input_tokens"]
            or data["input_tokens"] == 0
            or (arm == "one_verified_reminder" and reminders > 1)
        ):
            raise ValueError("negative task result or source-cost totals mutated")
        report[arm] = {
            "strict_tasks_passed": data["strict_tasks_passed"],
            "http_attempts": attempts,
            "model_turns": turns,
            "host_reminders": reminders,
        }
    if sum(data["http_attempts"] for data in report.values()) > 24:
        raise ValueError("exceeded preregistered external request limit")
    if (
        by_arm["original"]["by_language"]["en"]["termination"] != "premature_final"
        or by_arm["one_verified_reminder"]["by_language"]["en"]["termination"] != "premature_final"
        or by_arm["one_verified_reminder"]["by_language"]["en"]["host_reminders"] != 1
        or by_arm["one_verified_reminder"]["by_language"]["ko"]["transport_failure"]
        != "connect_timeout"
    ):
        raise ValueError("measured no-uplift/transport-confounded observations changed")
    return {
        "decision": "VALID_NEGATIVE_NO_STRICT_TASK_PASS_UPLIFT",
        "independent_e2_qualified": False,
        "arms": report,
        "artifact_digest_verified_against_record": True,
        "zip_bytes_independently_checked_here": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=SOURCE)
    args = parser.parse_args()
    data = json.loads(args.snapshot.read_text(encoding="utf-8"))
    print(json.dumps(verify(data), sort_keys=True))


if __name__ == "__main__":
    main()
