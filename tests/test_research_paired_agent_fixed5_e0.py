"""Synthetic-only paired E0 comparison; no independent model accuracy."""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from scripts.research_paired_agent_fixed5_e0 import aggregate_paired_e0

SECRET = "private-task-query-and-result-SECRET-1482"
IDS = ("1" * 64, "2" * 64, "3" * 64)
REV = "a" * 40
SRC = "b" * 64
SPLIT = "c" * 64
ARMS = ("lexical_k5", "e5_k5", "hybrid_k5")
TASKS = [
    {"task_hmac_sha256": IDS[0], "language": "en",
     "task_stratum": "read", "supported": True},
    {"task_hmac_sha256": IDS[1], "language": "ko",
     "task_stratum": "multi", "supported": True},
    {"task_hmac_sha256": IDS[2], "language": "ja",
     "task_stratum": "ood", "supported": False},
]


def fixture():
    meta = {
        "source_revision": REV,
        "source_sha256": SRC,
        "split_sha256": SPLIT,
        "model_revision": "synthetic-only-no-real-model",
        "model_runtime": "synthetic-agent-pytest",
        "hardware": "linux-x86_64-cpu-e0",
        "split_name": "synthetic-dev-only",
        "seed": 20261017, "max_k": 5,
    }
    manifest = {
        "schema_version": 1,
        "evidence_tier": "E0_SYNTHETIC_DEV_ONLY",
        "independent_e2_qualified": False,
        "arms": list(ARMS),
        "tasks": copy.deepcopy(TASKS),
        **meta,
    }
    runs = {}
    for arm in ARMS:
        rows = []
        for idx, task in enumerate(TASKS):
            # Deliberately synthetic scores: these are schema contracts,
            # NOT newly measured lexical, E5, or hybrid agent accuracy.
            passed = (idx == 0) or (idx == 1 and arm != "lexical_k5")
            if idx == 2:
                stages = ["unsupported_tool_executed"]
            elif passed:
                stages = ["passed"]
            else:
                stages = ["agent_final_before_task_completion"]
            rows.append({
                "schema_version": "e0-stage-observations-v1",
                "evidence_tier": "E0_SYNTHETIC_DEV_ONLY",
                "independent_e2_qualified": False,
                "condition": "EVAL-FIXED5-OPTIN",
                "source_revision": REV,
                "source_sha256": SRC,
                "task_hmac_sha256": task["task_hmac_sha256"],
                "language": task["language"],
                "seed": 20261017,
                "passed": passed,
                "supported": task["supported"],
                "task_complete": passed and task["supported"],
                "observed_stages": stages,
                "visible_candidate_counts": [5],
                "input_tokens": 100 + idx,
                "tool_schema_tokens": 50,
                "tool_call_count": 1,
                "candidate_selection_latency_ms": 1.0,
                "episode_wall_latency_ms": 10.0,
                "unauthorized_destructive_executions": 0,
                # Canaries from hostile/accidental raw row; aggregate must
                # never echo nonallowlisted user/model/tool content.
                "query": SECRET,
                "raw_provider_exception": SECRET,
                "attempts": [{"arguments": {"password": SECRET}}],
                "final_text": SECRET,
            })
        runs[arm] = {
            "arm": arm,
            "evidence_tier": "E0_SYNTHETIC_DEV_ONLY",
            **meta,
            "rows": rows,
        }
    return manifest, runs


def test_paired_three_arm_e0_report_reuses_task_cluster_bootstrap():
    manifest, runs = fixture()
    result = aggregate_paired_e0(manifest, runs)
    assert result["arms"] == list(ARMS)
    assert result["task_count"] == 3
    assert result["publication_gate_passed"] is False
    assert result["independent_e2_qualified"] is False
    assert result["decision"] == "E0_DESCRIPTIVE_ONLY_NOT_INDEPENDENT_E2"
    assert result["summary"]["lexical_k5"]["task_pass_rate"] == pytest.approx(1 / 3)
    assert result["summary"]["e5_k5"]["task_pass_rate"] == pytest.approx(2 / 3)
    paired = result["paired_task_pass_delta_vs_lexical_k5"]
    assert paired["e5_k5"]["delta"] == pytest.approx(1 / 3)
    assert paired["hybrid_k5"]["delta"] == pytest.approx(1 / 3)
    assert paired["e5_k5"]["cluster_unit"] == "semantic_task_id"
    assert result["summary"]["e5_k5"]["by_language"]["ko"]["pass_rate"] == 1
    assert result["summary"]["e5_k5"]["unsupported_executed_observed"] == 1
    public = json.dumps(result, ensure_ascii=False)
    assert SECRET not in public
    assert IDS[0] not in public
    assert "attempts" not in public
    assert "final_text" not in public


@pytest.mark.parametrize(("level", "key", "value", "match"), (
    ("manifest", "independent_e2_qualified", True, "independent E2"),
    ("manifest", "evidence_tier", "INDEPENDENT_E2", "independent E2"),
    ("manifest", "arms", ["lexical_k5", "e5_k5"], "unregistered arms"),
    ("manifest", "max_k", 10, "fixed K"),
    ("manifest", "model_revision", "", "comparable model_revision"),
    ("manifest", "source_sha256", "bad", "source_sha256"),
    ("manifest", "split_sha256", "bad", "split_sha256"),
    ("manifest", "seed", True, "seed"),
    ("run", "source_revision", "d" * 40, "drift"),
    ("run", "model_revision", "other-model", "drift"),
    ("run", "hardware", "other-hardware", "drift"),
    ("run", "max_k", 6, "drift"),
    ("run", "split_sha256", "d" * 64, "drift"),
    ("run", "seed", 88, "drift"),
    ("row", "condition", "SR-5", "E0 trace"),
    ("row", "source_sha256", "d" * 64, "E0 trace"),
    ("row", "independent_e2_qualified", True, "E0 trace"),
    ("row", "visible_candidate_counts", [6], "fixed-K5"),
    ("row", "visible_candidate_counts", [5, 6], "fixed-K5"),
    ("row", "tool_schema_tokens", -1, "nonnegative integer"),
    ("row", "candidate_selection_latency_ms", float("nan"), "finite nonnegative"),
    ("row", "unauthorized_destructive_executions", 1, "STOP"),
))
def test_invalid_evidence_cannot_be_qualified_or_silently_paired(
    level, key, value, match,
):
    manifest, runs = fixture()
    target = (manifest if level == "manifest"
              else runs["e5_k5"] if level == "run"
              else runs["e5_k5"]["rows"][0])
    target[key] = value
    with pytest.raises(ValueError, match=match):
        aggregate_paired_e0(manifest, runs)


def test_mismatched_task_cohort_missing_duplicates_and_language_drift():
    manifest, runs = fixture()
    runs["e5_k5"]["rows"][0] = copy.deepcopy(runs["e5_k5"]["rows"][1])
    with pytest.raises(ValueError, match="duplicate paired task"):
        aggregate_paired_e0(manifest, runs)

    manifest, runs = fixture()
    runs["e5_k5"]["rows"].pop()
    with pytest.raises(ValueError, match="incomplete"):
        aggregate_paired_e0(manifest, runs)

    manifest, runs = fixture()
    runs["e5_k5"]["rows"][0]["language"] = "ja"
    with pytest.raises(ValueError, match="label drift"):
        aggregate_paired_e0(manifest, runs)


def test_task_id_duplicate_and_splits_forbidden():
    manifest, runs = fixture()
    manifest["tasks"][1]["task_hmac_sha256"] = manifest["tasks"][0]["task_hmac_sha256"]
    with pytest.raises(ValueError, match="duplicate task"):
        aggregate_paired_e0(manifest, runs)

    manifest, runs = fixture()
    manifest["tasks"][2]["language"] = "fr"
    with pytest.raises(ValueError, match="EN/KO/JA"):
        aggregate_paired_e0(manifest, runs)


def test_missing_arm_fails_without_implicit_gold_aware_replacement():
    manifest, runs = fixture()
    del runs["hybrid_k5"]
    with pytest.raises(ValueError, match="exactly three"):
        aggregate_paired_e0(manifest, runs)


def test_no_false_broad_claim_when_every_synthetic_task_passes():
    manifest, runs = fixture()
    for arm in runs.values():
        for row in arm["rows"]:
            row["passed"] = True
            row["observed_stages"] = ["passed"]
    result = aggregate_paired_e0(manifest, runs)
    assert result["summary"]["e5_k5"]["task_pass_rate"] == 1
    assert result["publication_gate_passed"] is False
    assert result["independent_e2_qualified"] is False


def _attach_trace_receipts(manifest, runs):
    receipts = {
        "split_sha256": manifest["split_sha256"],
        **{
            f"{key}_sha256": hashlib.sha256(
                manifest[key].encode("utf-8"),
            ).hexdigest()
            for key in ("model_revision", "model_runtime", "hardware")
        },
    }
    for run in runs.values():
        for row in run["rows"]:
            row.update(receipts)
    return receipts


def test_paired_trace_receipts_match_manifest_and_legacy_still_works():
    legacy_manifest, legacy_runs = fixture()
    assert aggregate_paired_e0(legacy_manifest, legacy_runs)
    manifest, runs = fixture()
    receipts = _attach_trace_receipts(manifest, runs)
    assert len(receipts) == 4
    assert aggregate_paired_e0(manifest, runs)["task_count"] == len(TASKS)


@pytest.mark.parametrize("name", (
    "split_sha256", "model_revision_sha256",
    "model_runtime_sha256", "hardware_sha256",
))
def test_paired_trace_rejects_tampered_cohort_receipt(name):
    manifest, runs = fixture()
    _attach_trace_receipts(manifest, runs)
    runs["e5_k5"]["rows"][0][name] = "0" * 64
    with pytest.raises(ValueError, match="cohort provenance drift"):
        aggregate_paired_e0(manifest, runs)


def test_paired_trace_rejects_partial_or_cross_arm_receipt_versions():
    manifest, runs = fixture()
    _attach_trace_receipts(manifest, runs)
    del runs["lexical_k5"]["rows"][0]["hardware_sha256"]
    with pytest.raises(ValueError, match="cohort provenance drift"):
        aggregate_paired_e0(manifest, runs)

    manifest, runs = fixture()
    _attach_trace_receipts(manifest, runs)
    for row in runs["hybrid_k5"]["rows"]:
        for name in (
            "split_sha256", "model_revision_sha256",
            "model_runtime_sha256", "hardware_sha256",
        ):
            del row[name]
    with pytest.raises(ValueError, match="mix E0 trace receipt versions"):
        aggregate_paired_e0(manifest, runs)
