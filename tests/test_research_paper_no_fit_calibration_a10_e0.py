"""Synthetic RED/GREEN contract for source-pinned Algorithm 1 A10 diagnostics."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import replace

import pytest
from test_research_paper_paired_agent_e0 import (
    factory as a7_factory,
)
from test_research_paper_paired_agent_e0 import (
    kwargs as a7_kwargs,
)
from test_research_paper_paired_agent_e0 import (
    task as a7_task,
)
from test_research_paper_scoped_agent_real_e0 import model_result, source

from scripts.research_paper_measured_episode_e0 import (
    PaperMeteredAgentEpisode,
    PaperStageMeasurement,
)
from scripts.research_paper_no_fit_calibration_a10_e0 import (
    NoFitDiagnosticLimits,
    PaperPlanObservation,
    calibrate_source_pinned_paper_no_fit_e0,
    observation_from_paper_paired_agent_e0,
)
from scripts.research_paper_paired_agent_e0 import PaperPairedAgentE0, run_paper_paired_agent_e0
from scripts.research_task_disposition_rubric_e0 import KINDS, LANGUAGES

SECRET = "SENSITIVE-PUBLISHER-SECRET-FOR-LEAK-CHECK"


def _raw(obj: dict) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _fixture() -> tuple[tuple[bytes, ...], tuple[PaperPlanObservation, ...]]:
    cases = {"cases": [
        {"id": f"case-{i:02}", "language": language,
         "query": f"Original {language} task {kind} sequence {i} {SECRET}",
         "role": "reader", "expected_kind": kind}
        for i, (language, kind) in enumerate(
            ((language, kind) for language in LANGUAGES for kind in KINDS),
            start=1,
        )
    ]}
    gold = {"cases": [
        {"id": case["id"], "expected_kind": case["expected_kind"],
         "role": case["role"], "native_authority_sha256": "b" * 64,
         "gold_reference_sha256": "a" * 64}
        for case in cases["cases"]
    ]}
    dev = {"cases": [{"id": "dev-01", "query": "Separate original prior development request"}]}
    inventory = _raw({"tool": SECRET})
    manifest = {
        "schema_version": 1, "intake_kind": "unscored_native_e2",
        "provider_repository": "research/native", "provider_commit": "c" * 40,
        "native_tool_inventory_sha256": _sha(inventory),
        "case_bytes_sha256": _sha(_raw(cases)),
        "gold_bytes_sha256": _sha(_raw(gold)),
        "development_bytes_sha256": _sha(_raw(dev)),
        "split_id": "independent-split", "case_author": "publisher-author",
        "gold_reviewer": "independent-reviewer", "license_spdx": "Apache-2.0",
        "source_permission_review": "attested",
        "case_language_origin": "publisher_original_not_translated",
    }
    statuses = {
        "supported": "no_proven_hit", "unsupported": "ready",
        "required_input_missing": "requires_arguments",
        "ambiguous": "ambiguous_paths",
        "opaque_unavailable": "no_proven_hit",
    }
    observations = tuple(
        PaperPlanObservation(case["id"], statuses[case["expected_kind"]])
        for case in cases["cases"]
    )
    return (
        (_raw(manifest), _raw(cases), _raw(gold), _raw(dev), inventory),
        observations,
    )


def _run(
    source: tuple[bytes, ...],
    observations: tuple[PaperPlanObservation, ...],
    limits: NoFitDiagnosticLimits | None = None,
) -> dict:
    return calibrate_source_pinned_paper_no_fit_e0(
        *source, observations=observations,
        limits=limits or NoFitDiagnosticLimits(1, 0.25, 0.25),
    )


def test_complete_source_pinned_multilingual_diagnostic_has_only_aggregates():
    source, observations = _fixture()
    report = _run(source, observations)
    assert report["status"] == "STRUCTURAL_DIAGNOSTIC_ONLY"
    assert report["case_count"] == 15
    assert report["source_inventory_bytes_sha256_match"] is True
    assert report["source_author_license_verified"] is False
    assert report["independent_e2_qualified"] is False
    assert report["global_capability_absence_proven"] is False
    assert report["candidate_within_declared_limits"] is False
    assert report["totals"]["supported_false_refusal"] == 3
    assert report["totals"]["unsupported_false_accept"] == 3
    assert report["totals"]["supported_denominator"] == 3
    assert report["totals"]["unsupported_denominator"] == 3
    assert report["totals"]["source_no_proven_hit"] == 6
    assert report["totals"]["deferred"] == 3
    for language in LANGUAGES:
        part = report["by_language"][language]
        assert part["supported_false_refusal_rate"] == 1.0
        assert part["unsupported_false_accept_rate"] == 1.0
        assert part["supported_denominator"] == 1
        assert part["unsupported_denominator"] == 1
    serialized = json.dumps(report, ensure_ascii=False)
    for forbidden in (SECRET, "case-01", "publisher-author", "Original en task"):
        assert forbidden not in serialized


def test_deferrals_are_not_conflated_with_false_accept_or_global_no_fit():
    source, observations = _fixture()
    observations = tuple(
        replace(o, status="requires_observation") if o.case_id in {
            "case-01", "case-02", "case-06", "case-07"
        } else o for o in observations
    )
    result = _run(source, observations)
    assert result["totals"]["supported_false_refusal"] == 1
    assert result["totals"]["unsupported_false_accept"] == 1
    assert result["totals"]["deferred"] == 7
    assert result["global_capability_absence_proven"] is False


@pytest.mark.parametrize("mutator", [
    lambda source, observations: (source, observations[:-1]),
    lambda source, observations: (source, observations + (observations[0],)),
    lambda source, observations: (source, observations[:-1] +
                                  (PaperPlanObservation("foreign-id", "ready"),)),
    lambda source, observations: (source, observations[:-1] +
                                  (PaperPlanObservation("case-15", "no_global_fit"),)),
    lambda source, observations: (source, observations[:-1] +
                                  (PaperPlanObservation("case-15", "READY"),)),
    lambda source, observations: (source[:-1] + (b"different inventory",), observations),
    lambda source, observations: (
        source[:1] + (source[1] + b" ",) + source[2:], observations),
])
def test_bad_ids_status_or_frozen_source_bytes_fail_closed(mutator):
    source, observations = _fixture()
    bad_source, bad_obs = mutator(source, observations)
    with pytest.raises(ValueError) as error:
        _run(bad_source, bad_obs)
    assert SECRET not in str(error.value)


@pytest.mark.parametrize("limits", [
    NoFitDiagnosticLimits(0, 0.1, 0.2),
    NoFitDiagnosticLimits(True, 0.1, 0.2),
    NoFitDiagnosticLimits(1, -0.1, 0.2),
    NoFitDiagnosticLimits(1, 0.1, 1.1),
    NoFitDiagnosticLimits(1, float("nan"), 0.2),
])
def test_invalid_pregated_limits_rejected(limits):
    source, observations = _fixture()
    with pytest.raises(ValueError):
        _run(source, observations, limits)


def test_small_diagnostic_cohort_never_claims_calibrated_quality():
    source, observations = _fixture()
    report = _run(source, observations, NoFitDiagnosticLimits(20, 0.0, 0.0))
    assert report["status"] == "INSUFFICIENT_DENOMINATORS"
    assert report["candidate_within_declared_limits"] is None
    assert report["independent_e2_qualified"] is False


def test_observations_are_exact_typed_records():
    source, observations = _fixture()
    with pytest.raises(ValueError):
        _run(source, observations[:-1] + ({"case_id": "case-15", "status": "ready"},))
    with pytest.raises(ValueError):
        _run(source, list(observations))


def test_optional_host_observed_tool_attempts_are_not_guessed_from_plan():
    source, observations = _fixture()
    result = _run(source, observations)
    assert result["totals"]["agent_tool_attempts_missing_cases"] == 15
    assert result["totals"]["unsupported_observed_tool_attempt_rate"] is None

    measured = tuple(
        replace(o, agent_tool_calls=(1 if o.case_id in ("case-02", "case-01") else 0))
        for o in observations
    )
    measured_result = _run(source, measured)
    assert measured_result["totals"]["agent_tool_attempts_missing_cases"] == 0
    assert measured_result["totals"]["agent_tool_attempts_total"] == 2
    assert measured_result["totals"]["unsupported_observed_tool_attempt_cases"] == 1
    assert measured_result["totals"]["unsupported_observed_tool_attempt_rate"] == 1 / 3
    assert measured_result["totals"]["plan_abstained_but_agent_attempted"] == 1


@pytest.mark.parametrize("invalid", [True, -1, 0.5, "1"])
def test_host_tool_attempt_observation_requires_real_nonnegative_integer(invalid):
    source, observations = _fixture()
    with pytest.raises(ValueError):
        _run(source, (replace(observations[0], agent_tool_calls=invalid), *observations[1:]))


def test_perfect_synthetic_outcomes_can_only_pass_unqualified_diagnostic():
    source, observations = _fixture()
    observations = tuple(
        replace(o, status=("ready" if o.case_id in {
            "case-01", "case-06", "case-11"
        } else "no_proven_hit")) if o.case_id in {
            "case-01", "case-02", "case-06", "case-07", "case-11", "case-12"
        } else o for o in observations
    )
    report = _run(source, observations, NoFitDiagnosticLimits(1, 0.0, 0.0))
    assert report["candidate_within_declared_limits"] is True
    assert report["gold_independently_reviewed"] is False
    assert report["release_qualified"] is False
    assert report["independent_e2_qualified"] is False


def test_command_line_consumes_exact_streams_without_echoing_private_source(tmp_path):
    source, observations = _fixture()
    paths = []
    for name, contents in zip(
        ("manifest", "cases", "gold", "development", "native-inventory"),
        source, strict=True,
    ):
        target = tmp_path / f"{name}.json"
        target.write_bytes(contents)
        paths.extend((f"--{name}", str(target)))
    outcome_path = tmp_path / "observations.json"
    outcome_path.write_bytes(_raw({"observations": [
        {"case_id": o.case_id, "status": o.status} for o in observations
    ]}))
    command = [
        sys.executable, "-m", "scripts.research_paper_no_fit_calibration_a10_e0",
        *paths, "--observations", str(outcome_path),
        "--minimum-per-language", "1", "--maximum-false-refusal", "0.2",
        "--maximum-false-accept", "0.2",
    ]
    process = subprocess.run(command, capture_output=True, text=True, check=True)
    receipt = json.loads(process.stdout)
    assert receipt["case_count"] == 15
    assert receipt["qualification_gate"] == "BLOCKED_EXTERNAL"
    assert SECRET not in process.stdout
    assert "case-01" not in process.stdout


def _paired(decision: str, attempts: int) -> PaperPairedAgentE0:
    measurement = PaperStageMeasurement(
        understand_called=True, understand_model_callback_wall_latency_ms=1.0,
        understand_request_utf8_bytes=1,
        understand_input_tokens_provider_reported=None,
        understand_output_tokens_provider_reported=None,
        agent_input_tokens_reported=0, agent_output_tokens_reported=0,
        agent_tool_schema_tokens_reported=0,
        agent_tool_schema_utf8_bytes_exposed=0,
        agent_wall_latency_ms=0.0, total_wall_latency_ms=1.0,
    )
    return PaperPairedAgentE0(
        baseline={}, baseline_tool_schema_utf8_bytes_exposed=0,
        paper=PaperMeteredAgentEpisode(
            decision=decision, episode={"tool_call_count": attempts},
            measurement=measurement,
        ),
    )


def test_actual_paired_A7_case_projection_preserves_unclassified_abstain():
    source, observations = _fixture()
    paired = _paired("abstain", 1)
    actual = observation_from_paper_paired_agent_e0("case-02", paired)
    assert actual == PaperPlanObservation("case-02", "abstain_unclassified", 1)
    scored = tuple(actual if o.case_id == actual.case_id else o for o in observations)
    result = _run(source, scored)
    assert result["totals"]["source_no_proven_hit"] == 6
    assert result["totals"]["unclassified_abstention"] == 1
    assert result["totals"]["unsupported_observed_tool_attempt_cases"] == 1
    assert result["totals"]["plan_abstained_but_agent_attempted"] == 1
    assert result["totals"]["unsupported_false_accept"] == 2


@pytest.mark.parametrize(("decision", "status"), (
    ("offer", "ready"),
    ("request_arguments", "requires_arguments"),
    ("request_observation", "requires_observation"),
    ("abstain", "abstain_unclassified"),
))
def test_paired_decision_projection_is_lossless_about_missing_exact_plan_status(
    decision, status,
):
    observed = observation_from_paper_paired_agent_e0("case-01", _paired(decision, 0))
    assert observed.status == status


@pytest.mark.parametrize("invalid", [True, -1, "0", None])
def test_paired_projection_requires_actual_host_call_count(invalid):
    with pytest.raises(ValueError):
        observation_from_paper_paired_agent_e0("case-01", _paired("offer", invalid))


def test_paired_projection_cannot_elevate_gold_or_independent_e2():
    base = _paired("offer", 0)
    with pytest.raises(ValueError):
        observation_from_paper_paired_agent_e0(
            "case-01", replace(base, independent_e2_qualified=True),
        )
    with pytest.raises(ValueError):
        observation_from_paper_paired_agent_e0("case-01", replace(base, paper=replace(
            base.paper, episode={"tool_call_count": 0, "supported": True},
        )))
    with pytest.raises(ValueError):
        observation_from_paper_paired_agent_e0("case-01", _paired("not_plan_decision", 0))


@pytest.mark.asyncio
async def test_real_a7_pair_produces_host_observed_a10_candidate_without_gold():
    view, index = source()
    pair = await run_paper_paired_agent_e0(
        lambda _payload: model_result(), a7_factory,
        **a7_kwargs(view, index, a7_task()),
    )
    observed = observation_from_paper_paired_agent_e0("source-matched-by-host", pair)
    assert observed.status == "ready"
    assert observed.agent_tool_calls == pair.paper.episode["tool_call_count"] == 1
    assert "supported" not in pair.paper.episode
