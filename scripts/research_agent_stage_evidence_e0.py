"""Opt-in E0 synthetic-agent failure witnesses with non-sensitive JSONL output.

No new executor, no independent E2 claims, no product/legacy behavior changes.
Raw fixture rows and gold remain entirely inside the trusted grading process.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class E0TraceProvenance:
    """Trusted host-supplied synthetic source metadata, never model input."""

    source_revision: str
    source_sha256: str
    hmac_key: bytes = field(repr=False)
    seed: int


CONDITION = "EVAL-FIXED5-OPTIN"
SCHEMA_VERSION = "e0-stage-observations-v1"
EVIDENCE_TIER = "E0_SYNTHETIC_DEV_ONLY"
LANGUAGES = frozenset({"en", "ko", "ja", "es"})
_INT_METRICS = (
    "turns", "tool_call_count", "retrieval_calls", "policy_blocks",
    "unauthorized_destructive_executions", "input_tokens",
    "output_tokens", "tool_schema_tokens",
)
_FLOAT_METRICS = (
    "candidate_selection_latency_ms", "model_generation_latency_ms",
    "episode_wall_latency_ms",
)
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def _flag(row: dict[str, Any], name: str) -> bool:
    value = row.get(name)
    if type(value) is not bool:
        raise ValueError(f"missing or invalid E0 boolean: {name}")
    return value


def observed_stages(row: dict[str, Any]) -> list[str]:
    """Report observations, not adjudicated root causes or model quality.

    Expected-at-step and semantic validity come from the frozen synthetic
    grader AFTER execution; never pass this row or labels to a selector.
    """
    if type(row) is not dict or row.get("condition") != CONDITION:
        raise ValueError("only isolated opt-in E0 episode rows are accepted")
    passed = _flag(row, "passed")
    supported = _flag(row, "supported")
    _flag(row, "task_complete")
    overflow = _flag(row, "context_overflow")
    attempts = row.get("attempts")
    if type(attempts) is not list or any(type(a) is not dict for a in attempts):
        raise ValueError("E0 attempt evidence missing or malformed")
    for attempt in attempts:
        for field in (
            "schema_valid", "semantic_valid", "policy_blocked",
            "expected_at_step", "advanced_task",
        ):
            if type(attempt.get(field)) is not bool:
                raise ValueError("E0 attempt verdict is missing or malformed")
    if passed:
        return ["passed"]
    labels: list[str] = []
    if overflow:
        labels.append("context_overflow_observed")
    if not supported:
        if any(
            a["schema_valid"] and not a["policy_blocked"]
            and a.get("error") is None for a in attempts
        ):
            labels.append("unsupported_tool_executed")
        if row.get("final_text") != "REQUEST_MORE_TOOLS":
            labels.append("unsupported_no_fit_response_mismatch")
    else:
        if _flag(row, "initial_required_route_miss") and not _flag(
            row, "initial_miss_recovered"
        ):
            labels.append("initial_required_route_not_exposed")
        if any(a["policy_blocked"] for a in attempts):
            labels.append("policy_block_observed")
        if any(not a["schema_valid"] for a in attempts):
            labels.append("input_schema_rejection_observed")
        if any(
            a["schema_valid"] and not a["expected_at_step"]
            and not a["policy_blocked"] for a in attempts
        ):
            labels.append("wrong_operation_attempt_observed")
        if any(
            a["schema_valid"] and a["expected_at_step"]
            and not a["semantic_valid"] and not a["policy_blocked"]
            for a in attempts
        ):
            labels.append("task_argument_mismatch_observed")
        if any(
            a["schema_valid"] and a["semantic_valid"]
            and a["expected_at_step"] and a.get("error") is not None
            for a in attempts
        ):
            labels.append("tool_execution_error_observed")
        rows = row.get("turn_rows")
        if (
            type(rows) is list and rows and type(rows[-1]) is dict
            and rows[-1].get("event") == "final"
            and not row["task_complete"]
        ):
            labels.append("agent_final_before_task_completion")
    return labels if labels else ["unclassified"]


def sanitized_e0_trace(
    row: dict[str, Any],
    *,
    source_revision: str,
    source_sha256: str,
    task_identity: str,
    hmac_key: bytes,
    seed: int,
) -> dict[str, Any]:
    """Redact source-native E0 grading evidence to an allowlisted record.

    Shape validation is NOT proof of source authenticity or independent gold.
    Caller must keep raw rows and the HMAC secret out of public artifacts.
    """
    if (
        type(source_revision) is not str or not _HEX40.fullmatch(source_revision)
        or type(source_sha256) is not str or not _HEX64.fullmatch(source_sha256)
    ):
        raise ValueError("source revision and corpus digest must be exact hashes")
    if type(task_identity) is not str or not task_identity:
        raise ValueError("nonempty private task identity required")
    if type(hmac_key) is not bytes or len(hmac_key) < 16:
        raise ValueError("a private key of at least 16 bytes is required")
    if type(seed) is not int or seed < 0:
        raise ValueError("invalid E0 seed")
    if row.get("language") not in LANGUAGES:
        raise ValueError("unrecognized E0 task language")
    labels = observed_stages(row)
    candidate_history = row.get("candidate_history")
    if (
        type(candidate_history) is not list or not candidate_history
        or any(
            type(stage) is not list or len(stage) > 5
            or any(type(route) is not str or not route for route in stage)
            or len(set(stage)) != len(stage)
            for stage in candidate_history
        )
    ):
        raise ValueError("invalid fixed-K5 candidate exposure history")
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "evidence_tier": EVIDENCE_TIER,
        "independent_e2_qualified": False,
        "condition": CONDITION,
        "source_revision": source_revision,
        "source_sha256": source_sha256,
        "task_hmac_sha256": hmac.new(
            hmac_key, task_identity.encode("utf-8"), hashlib.sha256,
        ).hexdigest(),
        "language": row["language"],
        "seed": seed,
        "passed": row["passed"],
        "supported": row["supported"],
        "task_complete": row["task_complete"],
        "observed_stages": labels,
        "visible_candidate_counts": [len(stage) for stage in candidate_history],
    }
    for name in _INT_METRICS:
        if name in row:
            value = row[name]
            if type(value) is not int or value < 0:
                raise ValueError(f"invalid E0 count metric: {name}")
            record[name] = value
    for name in _FLOAT_METRICS:
        if name in row:
            value = row[name]
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f"invalid E0 latency metric: {name}")
            record[name] = float(value)
    return record


def sanitized_e0_jsonl(row: dict[str, Any], **trusted_provenance: Any) -> str:
    """Produce one deterministic, newline-terminated, public-safe E0 row."""
    safe = sanitized_e0_trace(row, **trusted_provenance)
    return json.dumps(
        safe, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ) + "\n"
