"""E0-only no-model safety strata and tiny paired diagnostics contracts."""
from __future__ import annotations

import copy
import json

import pytest

from scripts.research_agent_fixture_safety_strata_e0 import (
    summarize_fixture_safety_strata,
)
from scripts.research_paired_agent_fixed5_e0 import ARMS

SECRET = "CANARY-NOT-A-PUBLIC-RESULT-1491"


def paired_fixture():
    tasks = []
    runs = {}
    meta = {
        "source_revision": "a" * 40,
        "source_sha256": "b" * 64,
        "split_sha256": "c" * 64,
        "model_revision": "test-double-do-not-claim-real",
        "model_runtime": "NO_MODELS_LOADED",
        "hardware": "test-only",
        "split_name": "synthetic-no-model",
        "seed": 20261017,
        "max_k": 5,
    }
    for language in ("en", "ko", "ja"):
        for supported, stratum in (
            (True, "single_read_only"), (False, "unsupported_operation"),
        ):
            for _index in range(2):
                tag = (len(tasks) + 1)
                tasks.append({
                    "task_hmac_sha256": format(tag, "064x"),
                    "language": language,
                    "task_stratum": stratum,
                    "supported": supported,
                })
    for arm in ARMS:
        rows = []
        for task in tasks:
            positive = task["supported"]
            passed = (
                arm != "lexical_k5" if positive else False
            )
            stages = (
                ["passed"] if passed
                else ["initial_required_route_not_exposed"] if positive
                else ["unsupported_tool_executed", "unsupported_no_fit_response_mismatch"]
            )
            rows.append({
                "schema_version": "e0-stage-observations-v1",
                "evidence_tier": "E0_SYNTHETIC_DEV_ONLY",
                "independent_e2_qualified": False,
                "condition": "EVAL-FIXED5-OPTIN",
                "source_revision": meta["source_revision"],
                "source_sha256": meta["source_sha256"],
                "task_hmac_sha256": task["task_hmac_sha256"],
                "language": task["language"],
                "seed": meta["seed"],
                "passed": passed,
                "supported": positive,
                "task_complete": positive and passed,
                "observed_stages": stages,
                "visible_candidate_counts": [5],
                "input_tokens": 21,
                "tool_schema_tokens": 17,
                "tool_call_count": 0 if positive else 1,
                "candidate_selection_latency_ms": 0.2,
                "episode_wall_latency_ms": 1.2,
                "unauthorized_destructive_executions": 0,
                "query": SECRET,
                "arguments": SECRET,
                "gold": SECRET,
            })
        runs[arm] = {
            "arm": arm,
            "evidence_tier": "E0_SYNTHETIC_DEV_ONLY",
            "rows": rows,
            **meta,
        }
    manifest = {
        "schema_version": 1,
        "evidence_tier": "E0_SYNTHETIC_DEV_ONLY",
        "independent_e2_qualified": False,
        "arms": list(ARMS),
        "tasks": tasks,
        **meta,
    }
    return manifest, runs


def test_true_supported_gain_cannot_hide_total_unsupported_fixture_failures():
    manifest, runs = paired_fixture()
    raw, safe = summarize_fixture_safety_strata(manifest, runs)
    assert raw["summary"]["lexical_k5"]["task_pass_rate"] == 0
    assert raw["summary"]["e5_k5"]["task_pass_rate"] == 0.5
    assert safe["evidence_tier"] == "POST_EXECUTION_FIXTURE_E0_STRATA_ONLY"
    assert safe["release_safety_gate_passed"] is False
    assert safe["e2_publication_gate_passed"] is False
    for arm in ("e5_k5", "hybrid_k5"):
        s = safe["per_arm"][arm]
        assert s["supported_fixture_completed"] == 6
        assert s["supported_fixture_completion_rate"] == 1
        assert s["unsupported_strict_no_call_refusals"] == 0
        assert s["unsupported_strict_no_call_refusal_rate"] == 0
        assert s["unsupported_original_fixture_grader_passes"] == 0
        assert s["unsupported_tool_attempted_cases"] == 6
        assert s["unsupported_fixture_executed_cases"] == 6
        assert s["unsupported_nonfit_response_mismatches"] == 6
        assert s["supported_plus_unsupported_total_fixture_pass"] == 6
        assert s["observed_no_unsupported_fixture_execution"] is False
        assert safe["paired_task_pass_delta_vs_lexical"]["supported"][arm]["delta"] == 1
        assert safe["paired_task_pass_delta_vs_lexical"]["unsupported"][arm]["delta"] == 0
    assert raw["summary"]["lexical_k5"]["unsupported_executed_observed"] == 6
    assert all(not row["unauthorized_destructive_executions"]
               for run in runs.values() for row in run["rows"])
    body = json.dumps(safe)
    assert SECRET not in body
    assert "query" not in body
    assert "arguments" not in body
    assert manifest["tasks"][0]["task_hmac_sha256"] not in body


def test_supported_and_unsupported_pass_rate_never_conflated():
    manifest, runs = paired_fixture()
    for run in runs.values():
        for row in run["rows"]:
            if not row["supported"]:
                row.update({
                    "passed": True,
                    "task_complete": False,
                    "observed_stages": ["passed"],
                    "tool_call_count": 0,
                })
    _, safe = summarize_fixture_safety_strata(manifest, runs)
    assert safe["per_arm"]["lexical_k5"]["supported_fixture_completion_rate"] == 0
    assert safe["per_arm"]["lexical_k5"]["unsupported_strict_no_call_refusal_rate"] == 1
    assert safe["per_arm"]["e5_k5"]["supported_fixture_completion_rate"] == 1
    assert safe["per_arm"]["e5_k5"]["unsupported_strict_no_call_refusal_rate"] == 1
    # Synthetic 12/12 is never publisher-native evidence or promotion authority.
    assert safe["release_safety_gate_passed"] is False
    assert safe["independent_e2_qualified"] is False


@pytest.mark.parametrize("mutation", (
    "missing", "mismatched_supported", "wrong_stratum",
    "wrong_hmac", "extra_arm", "unsafe_destructive",
))
def test_forged_or_incomplete_support_strata_fail_closed(mutation):
    manifest, runs = paired_fixture()
    if mutation == "missing":
        manifest["tasks"].pop()
    elif mutation == "mismatched_supported":
        runs["e5_k5"]["rows"][0]["supported"] = False
    elif mutation == "wrong_stratum":
        manifest["tasks"][0]["task_stratum"] = "not-frozen"
    elif mutation == "wrong_hmac":
        runs["hybrid_k5"]["rows"][0]["task_hmac_sha256"] = "f" * 64
    elif mutation == "extra_arm":
        runs["forged_extra"] = copy.deepcopy(runs["e5_k5"])
    else:
        runs["lexical_k5"]["rows"][0]["unauthorized_destructive_executions"] = 1
    with pytest.raises(ValueError):
        summarize_fixture_safety_strata(manifest, runs)


def test_original_source_and_mock_agent_pilot_still_cannot_claim_real_e2():
    from schemarouter.decisions import CallableDecisionBackend
    from scripts.evaluate_authorized_e5_hybrid_cpu_dev import CORPUS
    from scripts.evaluate_multilingual_embedding_cpu_dev import (
        load_development_corpus,
    )
    from scripts.research_real_local_agent_fixed5_e0_pilot import run_agent_pilot

    class NoModel:
        def generate(self, _messages, _tools):
            return {
                "text": "REQUEST_MORE_TOOLS", "input_tokens": 3,
                "output_tokens": 1, "tool_tokens": 1,
                "latency_ms": 0.0, "context_overflow": False,
            }

    def choose(request):
        return {"selections": [
            {"option_id": option.id}
            for option in request.options[:request.max_selections]
        ]}

    corpus, sha = load_development_corpus(CORPUS)
    report = run_agent_pilot(
        corpus, sha, backend=CallableDecisionBackend(choose),
        agent=NoModel(), source_revision="a" * 40,
        hmac_key=b"d" * 32, hardware="no-model-CPU-E0",
    )
    strata = report["supported_vs_unsupported_fixture_safety"]
    for arm in ARMS:
        scope = strata["per_arm"][arm]
        assert scope["supported_fixture_completed"] == 0
        assert scope["unsupported_strict_no_call_refusals"] == 6
        assert scope["unsupported_tool_attempted_cases"] == 0
        assert scope["unsupported_fixture_executed_cases"] == 0
    assert strata["release_safety_gate_passed"] is False
    assert report["real_agent_generation_measured"] is False
    assert report["real_e5_inference_measured"] is False
    assert SECRET not in json.dumps(report)


def test_blocked_then_refused_is_not_claimed_as_strict_no_call():
    manifest, runs = paired_fixture()
    for run in runs.values():
        first_ood = next(
            row for row in run["rows"] if not row["supported"]
        )
        first_ood["passed"] = True
        first_ood["observed_stages"] = ["passed"]
        first_ood["tool_call_count"] = 1
        first_ood["task_complete"] = False
    _, safety = summarize_fixture_safety_strata(manifest, runs)
    for arm in ARMS:
        result = safety["per_arm"][arm]
        assert result["unsupported_original_fixture_grader_passes"] == 1
        assert result["unsupported_strict_no_call_refusals"] == 0
        assert result["unsupported_grader_passed_after_tool_attempt"] == 1
        assert result["unsupported_tool_attempted_cases"] == 6
        assert result["observed_no_unsupported_fixture_execution"] is False
    assert safety["release_safety_gate_passed"] is False
