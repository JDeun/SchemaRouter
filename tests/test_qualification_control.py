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
