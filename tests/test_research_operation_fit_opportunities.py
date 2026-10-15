"""Registry and improvement discovery unit tests with synthetic evidence only."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.research_operation_fit_conveyor import load_inputs
from scripts.research_operation_fit_opportunities import (
    EXPECTED_IDS,
    compile_opportunities,
    load_registry,
)


def reports() -> tuple[dict, dict]:
    plan, corpus, digest = load_inputs()
    rows = [{
        "case_id": item["id"],
        "language": item["language"],
        "kind": item["kind"],
        "expected_operation": item["expected_operation"],
        "predicted_operation": (
            item["expected_operation"] if item["kind"] == "supported" else None
        ),
        "latency_ms": 1.0,
    } for item in corpus["cases"]]
    baseline = {
        "model_key": "lexical_baseline",
        "independent_validation": False,
        "grants_execution_authority": False,
        "corpus_sha256": digest,
        "rows": copy.deepcopy(rows),
    }
    forced = copy.deepcopy(rows)
    for row in forced:
        if row["kind"] == "unsupported":
            row["predicted_operation"] = "search"
    gated = copy.deepcopy(rows)
    for row in gated:
        if row["kind"] == "unsupported":
            row["predicted_operation"] = "search"
    nli = {
        "model_key": "multilingual_nli",
        "model_id": plan["candidates"][1]["model"],
        "model_revision": plan["candidates"][1]["revision"],
        "no_tool_execution": True,
        "arms": {
            key: {
                "corpus_sha256": digest,
                "independent_validation": False,
                "grants_execution_authority": False,
                "rows": value,
            }
            for key, value in (
                ("nli_forced", forced), ("nli_diagnostic_gate", gated)
            )
        },
    }
    return baseline, nli


def test_registry_all_13_are_classified_without_hidden_auto_dispatch() -> None:
    registry = load_registry()
    assert len(registry["entries"]) == 13
    assert tuple(x["id"] for x in registry["entries"]) == EXPECTED_IDS
    assert registry["automatic_dispatch_enabled"] is False
    assert registry["independent_qualification"] is False
    assert registry["product_promotion"] is False
    assert sum(x["status"] == "active_stage" for x in registry["entries"]) == 2
    assert sum(x["status"] == "completed_reference" for x in registry["entries"]) == 4
    assert sum(x["status"] == "blocked" for x in registry["entries"]) == 5
    assert sum(x["status"] == "incomparable_frozen_reference"
               for x in registry["entries"]) == 2


@pytest.mark.parametrize("tamper", [
    "dispatch", "wrong_status", "missing_arm", "invented_run",
    "corpus_drift", "enable_holdout", "unverified_reference",
])
def test_registry_never_promotes_or_replays_historical_arms(
    tmp_path: Path, tamper: str,
) -> None:
    registry = load_registry()
    damaged = copy.deepcopy(registry)
    rows = damaged["entries"]
    if tamper == "dispatch":
        damaged["automatic_dispatch_enabled"] = True
    elif tamper == "wrong_status":
        rows[8]["status"] = "active_stage"
    elif tamper == "missing_arm":
        rows.pop()
    elif tamper == "invented_run":
        rows[0]["workflow"] = "unreviewed-workflow.yml"
    elif tamper == "corpus_drift":
        rows[2]["corpus_sha256"] = "0" * 64
    elif tamper == "enable_holdout":
        damaged["independent_qualification"] = True
    elif tamper == "unverified_reference":
        rows[2]["artifact_id"] = None
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(damaged), encoding="utf-8")
    with pytest.raises(ValueError):
        load_registry(path)


def test_opportunity_report_joins_same_run_cases_without_claiming_improvement() -> None:
    baseline, nli = reports()
    # A correct lexical answer with an NLI wrong route is a hypothesis,
    # not an independently demonstrated new improvement.
    nli["arms"]["nli_forced"]["rows"][0]["predicted_operation"] = "delete"
    nli["arms"]["nli_diagnostic_gate"]["rows"][0]["predicted_operation"] = None
    result = compile_opportunities(baseline, nli)
    assert result["status"] == "DEVELOPMENT_ERROR_ANALYSIS_ONLY"
    assert result["contrast"]["by_language"]["en"][
        "baseline_correct_nli_wrong"
    ] == 1
    assert result["contrast"]["by_language"]["en"][
        "gated_supported_refused"
    ] == 1
    assert len(result["historical_reference_only"]) == 4
    assert len(result["non_comparable_or_blocked"]) == 7
    assert result["no_automatic_experiment_dispatch"] is True
    assert result["no_independent_qualification"] is True
    assert result["may_promote_to_product"] is False
    assert result["may_merge_release"] is False
    assert result["may_execute_tools"] is False
    assert all(item["status"] == "PROPOSED_UNAPPROVED_NO_AUTO_EXECUTION"
               for item in result["improvement_hypotheses"])


@pytest.mark.parametrize("tamper", [
    "wrong_model", "wrong_corpus", "missing_case", "forged_gold",
    "untrusted_authority", "incomplete_arm", "bogus_prediction",
])
def test_opportunities_reject_corrupted_evidence(tamper: str) -> None:
    baseline, nli = reports()
    if tamper == "wrong_model":
        nli["model_revision"] = "latest"
    elif tamper == "wrong_corpus":
        baseline["corpus_sha256"] = "0" * 64
    elif tamper == "missing_case":
        nli["arms"]["nli_forced"]["rows"].pop()
    elif tamper == "forged_gold":
        baseline["rows"][0]["expected_operation"] = "lookup"
    elif tamper == "untrusted_authority":
        nli["arms"]["nli_forced"]["grants_execution_authority"] = True
    elif tamper == "incomplete_arm":
        nli["arms"].pop("nli_diagnostic_gate")
    elif tamper == "bogus_prediction":
        nli["arms"]["nli_forced"]["rows"][0][
            "predicted_operation"
        ] = "transfer_money"
    with pytest.raises(ValueError):
        compile_opportunities(baseline, nli)
