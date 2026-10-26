"""Source-pinned, observed-plan Algorithm 1 A10 no-fit diagnostics (E0 only).

This NEVER certifies the independent authorship, permission, license or gold
quality of untrusted publisher-intake bytes. It does not tune a production
confidence threshold, call a model or infer global absence from no_proven_hit.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.inspect_independent_native_e2_intake import (
    MAX_BYTES,
    SAFE_ID,
    _raw_json,
    inspect_source_pinned_native_cohort,
)
from scripts.research_paper_measured_episode_e0 import (
    PaperMeteredAgentEpisode,
    PaperStageMeasurement,
)
from scripts.research_paper_paired_agent_e0 import PaperPairedAgentE0
from scripts.research_paper_refusal_eval_e0 import decision_from_plan_status
from scripts.research_task_disposition_rubric_e0 import KINDS, LANGUAGES

MAX_OBSERVED_AGENT_TOOL_CALLS = 10000


@dataclass(frozen=True, slots=True)
class PaperPlanObservation:
    """Observed source-scoped plan result; caller must not invent gold."""

    case_id: str
    status: str
    agent_tool_calls: int | None = None


@dataclass(frozen=True, slots=True)
class NoFitDiagnosticLimits:
    """Host-predeclared limits, never optimized against the assessed cohort."""

    min_cases_per_language_and_binary_kind: int
    max_supported_false_refusal_rate: float
    max_unsupported_false_accept_rate: float


def observation_from_paper_paired_agent_e0(
    case_id: str, paired: PaperPairedAgentE0,
) -> PaperPlanObservation:
    """Project real A7 host attempt count and *coarse* paper disposition.

    The A7 paired result does not retain the exact planner status. In
    particular, `abstain` must NOT be relabeled `no_proven_hit`. The offline
    coordinator is solely responsible for associating the source case ID with
    the exact input task of that paired run. This is not an E2 receipt.
    """
    if (
        type(case_id) is not str or SAFE_ID.fullmatch(case_id) is None
        or type(paired) is not PaperPairedAgentE0
        or paired.independent_e2_qualified is not False
        or paired.host_declared_matching_agent_configuration is not True
        or type(paired.paper) is not PaperMeteredAgentEpisode
        or type(paired.paper.measurement) is not PaperStageMeasurement
        or paired.paper.measurement.independent_e2_qualified is not False
        or type(paired.paper.episode) is not dict
        or "supported" in paired.paper.episode
    ):
        raise ValueError("unqualified and sanitized A7 paired result required")
    attempts = paired.paper.episode.get("tool_call_count")
    if type(attempts) is not int or not 0 <= attempts <= MAX_OBSERVED_AGENT_TOOL_CALLS:
        raise ValueError("actual A7 host tool attempt counter required")
    statuses = {
        "offer": "ready", "abstain": "abstain_unclassified",
        "request_arguments": "requires_arguments",
        "request_observation": "requires_observation",
    }
    decision = paired.paper.decision
    if type(decision) is not str or decision not in statuses:
        raise ValueError("unknown A7 paired agent decision")
    return PaperPlanObservation(case_id, statuses[decision], attempts)


def _decision_from_observed_status(status: str) -> str:
    if status == "abstain_unclassified":
        return "abstain"
    return decision_from_plan_status(status)


def _validated_limits(limits: NoFitDiagnosticLimits) -> NoFitDiagnosticLimits:
    if type(limits) is not NoFitDiagnosticLimits:
        raise ValueError("explicit predeclared diagnostic limits required")
    count = limits.min_cases_per_language_and_binary_kind
    if type(count) is not int or not 1 <= count <= 256:
        raise ValueError("invalid diagnostic minimum denominator")
    for value in (
        limits.max_supported_false_refusal_rate,
        limits.max_unsupported_false_accept_rate,
    ):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("invalid predeclared diagnostic error limit")
    return limits


def _summarize(
    rows: list[dict[str, Any]], observations: dict[str, PaperPlanObservation],
) -> dict[str, int | float | None]:
    counts: Counter[str] = Counter()
    for case in rows:
        counts[case["expected_kind"] + "_denominator"] += 1
        observed = observations[case["id"]]
        status = observed.status
        decision = _decision_from_observed_status(status)
        if observed.agent_tool_calls is None:
            counts["agent_tool_attempts_missing_cases"] += 1
        else:
            counts["agent_tool_attempts_reported_cases"] += 1
            counts["agent_tool_attempts_total"] += observed.agent_tool_calls
            if (case["expected_kind"] == "unsupported"
                    and observed.agent_tool_calls > 0):
                counts["unsupported_observed_tool_attempt_cases"] += 1
            if (case["expected_kind"] not in ("supported", "unsupported")
                    and observed.agent_tool_calls > 0):
                counts["nonbinary_observed_tool_attempt_cases"] += 1
            if decision == "abstain" and observed.agent_tool_calls > 0:
                counts["plan_abstained_but_agent_attempted"] += 1
            if case["expected_kind"] == "unsupported":
                counts["unsupported_with_observed_tool_attempts"] += 1
        if status == "no_proven_hit":
            counts["source_no_proven_hit"] += 1
        if status == "abstain_unclassified":
            counts["unclassified_abstention"] += 1
        if status == "ambiguous_paths":
            counts["ambiguous_paths"] += 1
        if decision in ("request_arguments", "request_observation"):
            counts["deferred"] += 1
        if case["expected_kind"] == "supported":
            if decision == "offer" and observed.agent_tool_calls == 0:
                counts["supported_offer_without_agent_attempt"] += 1
            if decision == "abstain":
                counts["supported_false_refusal"] += 1
            elif decision == "offer":
                counts["supported_offer"] += 1
            else:
                counts["supported_deferred"] += 1
        elif case["expected_kind"] == "unsupported":
            if decision == "offer":
                counts["unsupported_false_accept"] += 1
            elif decision == "abstain":
                counts["unsupported_abstain"] += 1
            else:
                counts["unsupported_deferred"] += 1

    supported = counts["supported_denominator"]
    unsupported = counts["unsupported_denominator"]
    result: dict[str, int | float | None] = {
        kind + "_denominator": counts[kind + "_denominator"] for kind in KINDS
    }
    for metric in (
        "source_no_proven_hit", "unclassified_abstention", "ambiguous_paths", "deferred",
        "supported_false_refusal", "supported_offer", "supported_deferred",
        "unsupported_false_accept", "unsupported_abstain", "unsupported_deferred",
        "agent_tool_attempts_missing_cases", "agent_tool_attempts_reported_cases",
        "agent_tool_attempts_total", "unsupported_observed_tool_attempt_cases",
        "nonbinary_observed_tool_attempt_cases", "plan_abstained_but_agent_attempted",
        "supported_offer_without_agent_attempt",
    ):
        result[metric] = counts[metric]
    result["supported_false_refusal_rate"] = (
        counts["supported_false_refusal"] / supported if supported else None
    )
    result["unsupported_false_accept_rate"] = (
        counts["unsupported_false_accept"] / unsupported if unsupported else None
    )
    result["unsupported_observed_tool_attempt_rate"] = (
        counts["unsupported_observed_tool_attempt_cases"]
        / counts["unsupported_with_observed_tool_attempts"]
        if counts["unsupported_with_observed_tool_attempts"] else None
    )
    return result


def calibrate_source_pinned_paper_no_fit_e0(
    manifest_bytes: bytes,
    case_bytes: bytes,
    gold_bytes: bytes,
    development_bytes: bytes,
    native_inventory_bytes: bytes,
    *,
    observations: tuple[PaperPlanObservation, ...],
    limits: NoFitDiagnosticLimits,
) -> dict[str, Any]:
    """Match observed statuses to predeclared gold by exact source-bound ID.

    The calculated error rates are *structural diagnostics*. Even a perfect
    synthetic score must never be marked independent or production-calibrated.
    No case/source/role IDs, model contents or private gold leave this function.
    """
    limits = _validated_limits(limits)
    preflight = inspect_source_pinned_native_cohort(
        manifest_bytes, case_bytes, gold_bytes, development_bytes,
        native_inventory_bytes,
    )
    cases = _raw_json(case_bytes, "cases")["cases"]
    if type(observations) is not tuple or len(observations) != len(cases):
        raise ValueError("complete frozen observed cohort required")

    decisions: dict[str, PaperPlanObservation] = {}
    for observation in observations:
        if (
            type(observation) is not PaperPlanObservation
            or type(observation.case_id) is not str
            or type(observation.status) is not str
            or (observation.agent_tool_calls is not None
                and (type(observation.agent_tool_calls) is not int
                     or not 0 <= observation.agent_tool_calls
                     <= MAX_OBSERVED_AGENT_TOOL_CALLS))
            or observation.case_id in decisions
        ):
            raise ValueError("malformed or duplicate observed plan status")
        try:
            _decision_from_observed_status(observation.status)
        except ValueError:
            raise ValueError("unknown observed paper plan status") from None
        decisions[observation.case_id] = observation
    if set(decisions) != {case["id"] for case in cases}:
        raise ValueError("observed case identities do not match pinned source")

    by_language = {
        language: _summarize(
            [case for case in cases if case["language"] == language], decisions,
        ) for language in LANGUAGES
    }
    totals = _summarize(cases, decisions)
    enough_cases = all(
        by_language[language][kind + "_denominator"]
        >= limits.min_cases_per_language_and_binary_kind
        for language in LANGUAGES for kind in ("supported", "unsupported")
    )
    plan_within_limits: bool | None = None
    if enough_cases:
        plan_within_limits = all(
            (metrics["supported_false_refusal_rate"] is not None
             and metrics["supported_false_refusal_rate"]
             <= limits.max_supported_false_refusal_rate
             and metrics["unsupported_false_accept_rate"] is not None
             and metrics["unsupported_false_accept_rate"]
             <= limits.max_unsupported_false_accept_rate)
            for metrics in (*by_language.values(), totals)
        )
    # A paper plan is not a physical execution. Do not allow the diagnostic
    # to indicate acceptance until ALL host dispatch counters are available;
    # unobserved executions are *unknown*, not presumed zero. Even this is
    # still E0 and never independent end-to-end task quality evidence.
    host_counters_complete = totals["agent_tool_attempts_missing_cases"] == 0
    candidate_within_limits: bool | None = None
    if plan_within_limits is not None and host_counters_complete:
        candidate_within_limits = bool(
            plan_within_limits
            and totals["unsupported_observed_tool_attempt_cases"] == 0
            and totals["nonbinary_observed_tool_attempt_cases"] == 0
            and totals["plan_abstained_but_agent_attempted"] == 0
            and totals["supported_offer_without_agent_attempt"] == 0
        )

    return {
        "status": (
            "STRUCTURAL_DIAGNOSTIC_ONLY" if enough_cases
            else "INSUFFICIENT_DENOMINATORS"
        ),
        "case_count": preflight["case_count"],
        "source_inventory_bytes_sha256_match": preflight[
            "native_inventory_bytes_sha256_match"
        ],
        "by_language": by_language,
        "totals": totals,
        "limits_host_predeclared_not_learned": {
            "min_cases_per_language_and_binary_kind":
                limits.min_cases_per_language_and_binary_kind,
            "max_supported_false_refusal_rate": limits.max_supported_false_refusal_rate,
            "max_unsupported_false_accept_rate": limits.max_unsupported_false_accept_rate,
        },
        "plan_within_declared_limits": plan_within_limits,
        "host_tool_attempt_counters_complete": host_counters_complete,
        "candidate_within_declared_limits": candidate_within_limits,
        "score_scope": "PLAN_STAGE_DIAGNOSTIC_NOT_END_TO_END",
        "source_no_proven_hit_is_global_no_fit": False,
        "global_capability_absence_proven": False,
        "source_author_license_verified": False,
        "gold_independently_reviewed": False,
        "model_inference_executed_by_evaluator": False,
        "scoring_authorized_for_independent_e2": False,
        "independent_e2_qualified": False,
        "release_qualified": False,
        "qualification_gate": "BLOCKED_EXTERNAL",
    }


def _bounded_read(path: Path) -> bytes:
    with path.open("rb") as handle:
        return handle.read(MAX_BYTES + 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("manifest", "cases", "gold", "development", "native-inventory", "observations"):
        parser.add_argument("--" + field, type=Path, required=True)
    parser.add_argument("--minimum-per-language", type=int, required=True)
    parser.add_argument("--maximum-false-refusal", type=float, required=True)
    parser.add_argument("--maximum-false-accept", type=float, required=True)
    args = parser.parse_args()
    observed = _raw_json(_bounded_read(args.observations), "observations")
    if set(observed) != {"observations"} or type(observed["observations"]) is not list:
        raise ValueError("invalid observed plan record collection")
    records = observed["observations"]
    if len(records) > 256 or any(
        type(item) is not dict
        or not {"case_id", "status"} <= set(item)
        or not set(item) <= {"case_id", "status", "agent_tool_calls"}
        for item in records
    ):
        raise ValueError("invalid observed plan record collection")
    report = calibrate_source_pinned_paper_no_fit_e0(
        _bounded_read(args.manifest), _bounded_read(args.cases),
        _bounded_read(args.gold), _bounded_read(args.development),
        _bounded_read(args.native_inventory),
        observations=tuple(PaperPlanObservation(**record) for record in records),
        limits=NoFitDiagnosticLimits(
            args.minimum_per_language, args.maximum_false_refusal,
            args.maximum_false_accept,
        ),
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
