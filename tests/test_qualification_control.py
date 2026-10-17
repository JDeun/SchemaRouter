"""Regression tests for immutable matrix coverage and honest evidence status."""
from __future__ import annotations

import copy
import json

import pytest

from scripts.qualification_control import (
    DASHBOARD,
    MATRIX,
    ROOT,
    load_control,
    render_dashboard,
    validate_control,
)


def snapshot():
    return load_control(), MATRIX.read_text(encoding="utf-8")


def test_19_matrix_rows_and_generated_dashboard():
    data, matrix = snapshot()
    validate_control(data, matrix)
    assert len(data["items"]) == 19
    assert len({item["id"] for item in data["items"]}) == 19
    assert DASHBOARD.read_text(encoding="utf-8") == render_dashboard(data)
    assert "Independent qualification: 0/19" in render_dashboard(data)
    assert "v0.18.0 release:** **HOLD**" in render_dashboard(data)
    assert ROOT.joinpath(data["source_matrix"]).is_file()


@pytest.mark.parametrize("mutation", (
    "missing", "duplicate", "priority", "unknown_state", "missing_owner",
    "no_blocker", "wrong_url", "fake_pass", "fake_evidence",
    "release_unlocked", "release_owner_missing",
    "promotion_owner_missing", "matrix_drift",
))
def test_malformed_or_unverified_ledger_fails_closed(mutation):
    data, matrix = snapshot()
    data = copy.deepcopy(data)
    item = data["items"][0]
    if mutation == "missing":
        data["items"].pop()
    elif mutation == "duplicate":
        data["items"][1]["id"] = item["id"]
    elif mutation == "priority":
        item["priority"] = "P2"
    elif mutation == "unknown_state":
        item["status"] = "PASS"
    elif mutation == "missing_owner":
        item["owner_issue"] = 0
    elif mutation == "no_blocker":
        item["blocker"] = ""
    elif mutation == "wrong_url":
        item["evidence_links"] = ["https://example.com/claim"]
    elif mutation == "fake_pass":
        item["status"] = "QUALIFIED"
    elif mutation == "fake_evidence":
        item["qualification"] = {"evidence_tier": "E2_INDEPENDENT"}
    elif mutation == "release_unlocked":
        data["release"]["decision"] = "PASS"
    elif mutation == "release_owner_missing":
        data["release"]["owners"] = [1345]
    elif mutation == "promotion_owner_missing":
        data["promotion"]["owners"] = [1339]
    else:
        matrix = matrix.replace("| G01 P0 |", "| G99 P0 |")
    with pytest.raises(ValueError, match="qualification ledger"):
        validate_control(data, matrix)


def test_qualified_needs_complete_separately_reviewed_evidence_envelope():
    data, matrix = snapshot()
    row = data["items"][0]
    row["status"] = "QUALIFIED"
    row["qualification"] = {
        "evidence_tier": "E2_INDEPENDENT",
        "run_url": "https://github.com/JDeun/SchemaRouter/actions/runs/42",
        "acceptance_record_url": "https://github.com/JDeun/SchemaRouter/issues/1346",
        "source_sha256": "a" * 64,
        "artifact_sha256": "b" * 64,
        "frozen_split_id": "blind-heldout-1",
        "independent_reviewer": "separate-author",
    }
    with pytest.raises(ValueError, match="qualification ledger"):
        validate_control(data, matrix)
    row["evidence_links"].append(row["qualification"]["run_url"])
    validate_control(data, matrix)
    assert "- [x] **G01 P0**" in render_dashboard(data)


def test_json_roundtrip_does_not_change_claims():
    data, matrix = snapshot()
    assert json.loads(json.dumps(data)) == data
    validate_control(data, matrix)


def _simulation_only_approval(owners):
    # Deliberately synthetic test metadata, never an external E2 claim.
    return {
        "approval_record_url": "https://github.com/JDeun/SchemaRouter/issues/1345",
        "exact_head_ci_url": "https://github.com/JDeun/SchemaRouter/actions/runs/42",
        "source_sha256": "a" * 64,
        "artifact_sha256": "b" * 64,
        "approved_by": "hypothetical-independent-reviewer",
        "approved_at": "2026-10-17",
        "signed_off_issue_ids": list(owners),
    }


@pytest.mark.parametrize("problem", (
    "missing_approval", "missing_hash", "unreviewed", "wrong_owners",
    "wrong_url", "approval_while_hold",
))
def test_release_gate_requires_reviewed_exact_head_evidence(problem):
    data, matrix = snapshot()
    gate = data["release"]
    gate["decision"] = "APPROVED"
    gate["approval"] = _simulation_only_approval(gate["owners"])
    if problem == "missing_approval":
        del gate["approval"]
    elif problem == "missing_hash":
        gate["approval"]["artifact_sha256"] = "bogus"
    elif problem == "unreviewed":
        gate["approval"]["approved_by"] = ""
    elif problem == "wrong_owners":
        gate["approval"]["signed_off_issue_ids"] = [1345]
    elif problem == "wrong_url":
        gate["approval"]["exact_head_ci_url"] = "https://example.invalid"
    else:
        gate["decision"] = "HOLD"
    with pytest.raises(ValueError, match="qualification ledger"):
        validate_control(data, matrix)


def test_separately_approved_release_does_not_claim_agent_e2_or_trigger_publish():
    data, matrix = snapshot()
    gate = data["release"]
    gate["decision"] = "APPROVED"
    gate["approval"] = _simulation_only_approval(gate["owners"])
    validate_control(data, matrix)
    summary = render_dashboard(data)
    assert "v0.18.0 release:** **APPROVED**" in summary
    assert "production model/default promotion:** **HOLD**" in summary
    assert "Independent qualification: 0/19" in summary


def test_model_promotion_requires_independent_p0_p1_evidence_for_every_gate():
    data, matrix = snapshot()
    gate = data["promotion"]
    gate["decision"] = "APPROVED"
    gate["approval"] = _simulation_only_approval(gate["owners"])
    with pytest.raises(ValueError, match="every P0/P1"):
        validate_control(data, matrix)

    # Structural acceptance can be tested with fake local artifacts;
    # it does not assert that any real case was independently reviewed.
    for item in data["items"]:
        if item["priority"] not in ("P0", "P1"):
            continue
        run_url = "https://github.com/JDeun/SchemaRouter/actions/runs/42"
        item["status"] = "QUALIFIED"
        item["evidence_links"].append(run_url)
        item["qualification"] = {
            "evidence_tier": "E2_INDEPENDENT",
            "run_url": run_url,
            "acceptance_record_url": (
                "https://github.com/JDeun/SchemaRouter/issues/1346"
            ),
            "source_sha256": "a" * 64,
            "artifact_sha256": "b" * 64,
            "frozen_split_id": "test-only",
            "independent_reviewer": "test-only",
        }
    validate_control(data, matrix)
    summary = render_dashboard(data)
    assert "production model/default promotion:** **APPROVED**" in summary
    assert "v0.18.0 release:** **HOLD**" in summary
