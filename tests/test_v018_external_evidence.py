"""No-model tests for release-evidence publication honesty."""

from __future__ import annotations

import copy
import json

import pytest

from scripts.validate_v018_external_evidence import DEFAULT_PATH, validate


def _original():
    return json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))


def test_external_suite_inventory_has_no_unverified_independent_pass():
    manifest = _original()
    validate(manifest)
    assert len(manifest["suite"]) == 8
    assert {row["independent_verdict"] for row in manifest["suite"]} == {
        "BLOCKED_EXTERNAL"
    }
    assert all(
        "heldout" not in row["evidence_class"].lower()
        for row in manifest["suite"]
    )


@pytest.mark.parametrize(
    "field,bad",
    [
        ("schema_version", True),
        ("historical_frozen_runs_unchanged", False),
        ("release_target", "0.17.0"),
    ],
)
def test_rejects_corrupt_release_manifest(field, bad):
    m = _original()
    m[field] = bad
    with pytest.raises(ValueError):
        validate(m)


def test_cannot_promote_dev_run_to_independent_confirmation():
    m = _original()
    m["suite"][0]["independent_verdict"] = "PASS"
    with pytest.raises(ValueError, match="independent"):
        validate(m)


def test_independent_confirmation_does_not_accept_forged_digests():
    m = _original()
    row = m["suite"][0]
    row.update(
        independent_verdict="VALID_NEGATIVE",
        independent_run_id=row["run_id"],
        independent_artifact_sha256="not-a-sha",
        independent_case_sha256="f" * 64,
        independent_gold_review=True,
    )
    with pytest.raises(ValueError, match="digest"):
        validate(m)


def test_wrong_run_reference_or_boolean_run_id_is_not_provenance():
    source = _original()
    for field, value in (
        ("run_id", True),
        ("run_url", "https://github.com/JDeun/SchemaRouter/actions/runs/0"),
    ):
        m = copy.deepcopy(source)
        m["suite"][0][field] = value
        with pytest.raises(ValueError):
            validate(m)


def test_empty_source_or_duplicate_suite_fails_closed():
    source = _original()
    for mutate in (
        lambda m: m["suite"].append(copy.deepcopy(m["suite"][0])),
        lambda m: m["suite"][0].update(source=""),
        lambda m: m["suite"][0].update(evidence_class="independent"),
    ):
        m = copy.deepcopy(source)
        mutate(m)
        with pytest.raises(ValueError):
            validate(m)


def test_dev_pass_requires_authentic_run_reference():
    m = _original()
    m["suite"][2]["run_id"] = None
    m["suite"][2]["run_url"] = None
    with pytest.raises(ValueError, match="verified run"):
        validate(m)


def test_artifact_id_must_have_valid_sha256():
    m = _original()
    m["suite"][0]["artifact_sha256"] = "unverified"
    with pytest.raises(ValueError, match="SHA-256"):
        validate(m)


def test_independent_verdict_rejects_missing_review_or_dev_evidence_reuse():
    original = _original()
    row = original["suite"][0]
    assert row["run_id"] is not None
    independent = {
        "independent_verdict": "VALID_NEGATIVE",
        "independent_run_id": row["run_id"] + 42,
        "independent_artifact_sha256": "a" * 64,
        "independent_case_sha256": "b" * 64,
        "independent_gold_review": True,
    }

    m = copy.deepcopy(original)
    m["suite"][0].update(independent)
    # This is a *syntactically acceptable* provenance claim, not evidence
    # that a third party has genuinely authored, signed or scored the cases.
    validate(m)

    m = copy.deepcopy(original)
    m["suite"][0].update(independent, independent_gold_review=False)
    with pytest.raises(ValueError, match="independent_gold_review"):
        validate(m)

    m = copy.deepcopy(original)
    m["suite"][0].update(independent, independent_run_id=row["run_id"])
    with pytest.raises(ValueError, match="reuses DEV run"):
        validate(m)

    m = copy.deepcopy(original)
    m["suite"][0].update(
        independent, independent_artifact_sha256=row["artifact_sha256"]
    )
    with pytest.raises(ValueError, match="reuses DEV digest"):
        validate(m)


def test_independent_review_must_be_literal_true_and_run_not_boolean():
    for value in (1, "true", None):
        m = _original()
        m["suite"][0].update(
            independent_verdict="PASS",
            independent_run_id=99999999,
            independent_artifact_sha256="a" * 64,
            independent_case_sha256="b" * 64,
            independent_gold_review=value,
        )
        with pytest.raises(ValueError, match="independent_gold_review"):
            validate(m)

    m = _original()
    m["suite"][0].update(
        independent_verdict="PASS",
        independent_run_id=True,
        independent_artifact_sha256="a" * 64,
        independent_case_sha256="b" * 64,
        independent_gold_review=True,
    )
    with pytest.raises(ValueError, match="independent run"):
        validate(m)
