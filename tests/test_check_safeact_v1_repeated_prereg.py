"""No-model integrity tests for a prospective SafeAct V1 repeated study."""
from __future__ import annotations

import copy
import json
import os
import stat
import sys

import pytest

from scripts.check_safeact_v1_repeated_prereg import (
    ARMS,
    UPSTREAM_V1,
    audit_annotations,
    audit_blind_linkage,
    audit_receipts,
    audit_schedule,
    digest,
    main,
    make_blind_queue,
    validate_plan,
    write_new_private_file,
)


@pytest.fixture
def fixture() -> tuple[dict, list[str], dict]:
    cases = [f"SAB-V1-PUBLIC-{i:03d}" for i in range(131)]
    plan = {
        "schema_version": 1,
        "study": "safeact-v1-repeated-trajectory",
        "status": "draft",
        "approved": False,
        "pins": {
            "upstream_sha": UPSTREAM_V1,
            "model": "synthetic-placeholder-not-a-real-model",
            "model_revision": "synthetic-pinned",
            "adapter_sha": "a" * 40,
            "contracts_sha256": "b" * 64,
            "runtime_sha256": "c" * 64,
            "rubric_sha256": "d" * 64,
            "public_cases_sha256": digest(sorted(cases)),
        },
        "arms": list(ARMS),
        "seeds": ["predeclared-seed-a", "predeclared-seed-b"],
        "repetitions": 2,
        "analysis": {
            "cluster_unit": "case_id",
            "annotation_sample": "all",
            "annotators_per_item": 2,
        },
        "methods": {
            "precision_rationale": "synthetic power note",
            "session_reset": "fresh runtime for every arm and repetition",
            "retry_policy": "one administrative run record per paired trial",
            "missingness_policy": "retain missingness in intention-to-treat ledger",
            "randomness_policy": "fixed model/backend and independent seed calls",
            "blinding_limitations": "manual review for identifying content markers",
        },
    }
    rows = [
        {
            "case_id": case,
            "seed_id": seed,
            "arm": arm,
            "execution_id": f"exec-{i:04d}",
            "session_id": f"isolated-{i:04d}",
        }
        for i, (case, seed, arm) in enumerate(
            (c, s, a) for c in cases for s in plan["seeds"] for a in ARMS
        )
    ]
    schedule = {
        "schema_version": 1,
        "plan_sha256": digest(plan),
        "runs": rows,
    }
    return plan, cases, schedule


def test_complete_paired_131_x_2_x_3_unapproved_schedule(fixture) -> None:
    plan, ids, schedule = fixture
    assert validate_plan(plan, ids) == 786
    assert audit_schedule(plan, ids, schedule) == 786
    assert plan["approved"] is False


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("approved", True, "only unapproved"),
        ("status", "frozen", "only unapproved"),
        ("repetitions", 3, "repetition count"),
        ("seeds", ["same", "same"], "distinct preregistered"),
        ("seeds", ["one"], "distinct preregistered"),
    ],
)
def test_reject_premature_approval_or_changed_repetition(
    fixture, field, value, error,
) -> None:
    plan, ids, _ = fixture
    plan[field] = value
    with pytest.raises(ValueError, match=error):
        validate_plan(plan, ids)


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("cluster_unit", "trajectory_id", "case-clustered"),
        ("annotation_sample", "posthoc", "case-clustered"),
        ("annotators_per_item", 1, "case-clustered"),
    ],
)
def test_reject_pseudoreplication_and_insufficient_blinding(
    fixture, field, value, error,
) -> None:
    plan, ids, _ = fixture
    plan["analysis"][field] = value
    with pytest.raises(ValueError, match=error):
        validate_plan(plan, ids)


def test_pinned_public_cohort_mismatch_or_gold_field_rejected(fixture) -> None:
    plan, ids, _ = fixture
    with pytest.raises(ValueError, match="cohort"):
        validate_plan(plan, ids[:-1])
    with pytest.raises(ValueError, match="digest"):
        validate_plan(plan, [*ids[:-1], "new-case"])
    plan["hidden_gold"] = True
    with pytest.raises(ValueError, match="missing or unknown keys"):
        validate_plan(plan, ids)


def test_frozen_pins_cannot_be_edited_after_scheduling(fixture) -> None:
    plan, ids, schedule = fixture
    plan["pins"]["model_revision"] = "different-revision"
    with pytest.raises(ValueError, match="not pinned"):
        audit_schedule(plan, ids, schedule)


@pytest.mark.parametrize("damage,error", [
    ("missing", "missing, extra"),
    ("duplicate", "duplicated paired"),
    ("different_arm", "unknown or duplicated"),
    ("reused_session", "session reused"),
    ("reused_execution", "execution/session reused"),
    ("unapproved_outcome_field", "unknown keys"),
])
def test_schedule_rejects_lost_pair_duplicates_and_state_sharing(
    fixture, damage, error,
) -> None:
    plan, ids, schedule = fixture
    if damage == "missing":
        schedule["runs"].pop()
    elif damage == "duplicate":
        schedule["runs"][3] = copy.deepcopy(schedule["runs"][0])
        schedule["runs"][3]["execution_id"] = "changed-exec"
        schedule["runs"][3]["session_id"] = "changed-session"
    elif damage == "different_arm":
        schedule["runs"][0]["arm"] = "unauthorized-arm"
    elif damage == "reused_session":
        schedule["runs"][1]["session_id"] = schedule["runs"][0]["session_id"]
    elif damage == "reused_execution":
        schedule["runs"][1]["execution_id"] = schedule["runs"][0]["execution_id"]
    else:
        schedule["runs"][0]["official_score"] = 1
    with pytest.raises(ValueError, match=error):
        audit_schedule(plan, ids, schedule)


def test_strict_plan_refuses_seed_insert_even_when_future_schedule_has_rows(
    fixture,
) -> None:
    plan, ids, schedule = fixture
    schedule["runs"].append(copy.deepcopy(schedule["runs"][0]))
    with pytest.raises(ValueError, match="extra or duplicated"):
        audit_schedule(plan, ids, schedule)


def test_blind_view_contains_no_arm_session_case_or_execution(fixture) -> None:
    plan, ids, schedule = fixture
    public, private = make_blind_queue(plan, ids, schedule)
    assert len(public["entries"]) == len(private["entries"]) == 786
    assert all(set(item) == {"blind_id"} for item in public["entries"])
    assert len({item["blind_id"] for item in public["entries"]}) == 786
    private_items = {entry["blind_id"]: entry for entry in private["entries"]}
    assert set(private_items) == {
        entry["blind_id"] for entry in public["entries"]
    }
    assert set(private_items.values().__iter__().__next__()) == {
        "blind_id", "case_id", "seed_id", "arm", "execution_id", "session_id",
    }
    assert public["plan_sha256"] == private["plan_sha256"] == digest(plan)



def test_private_blind_linkage_proves_exact_registered_bijection(fixture) -> None:
    plan, ids, schedule = fixture
    public, private = make_blind_queue(plan, ids, schedule)
    assert audit_blind_linkage(plan, ids, schedule, public, private) == 786


@pytest.mark.parametrize(
    "damage,error",
    [
        ("wrong_arm", "does not match frozen schedule"),
        ("wrong_case", "does not match frozen schedule"),
        ("wrong_session", "does not match frozen schedule"),
        ("duplicate_blind_id", "duplicate blind ID"),
        ("duplicate_execution", "reuses or invents"),
        ("missing_public_id", "duplicate or absent public"),
        ("added_private_label", "unknown keys"),
        ("stale_plan_sha", "revision does not match plan"),
    ],
)
def test_private_linkage_cannot_change_registered_provenance(
    fixture, damage, error,
) -> None:
    plan, ids, schedule = fixture
    public, private = make_blind_queue(plan, ids, schedule)
    row = private["entries"][0]
    if damage == "wrong_arm":
        row["arm"] = "unknown-unsafe-condition"
    elif damage == "wrong_case":
        row["case_id"] = "reassigned-case"
    elif damage == "wrong_session":
        row["session_id"] = "reused-other-session"
    elif damage == "duplicate_blind_id":
        private["entries"][1]["blind_id"] = row["blind_id"]
    elif damage == "duplicate_execution":
        private["entries"][1]["execution_id"] = row["execution_id"]
    elif damage == "missing_public_id":
        public["entries"][1]["blind_id"] = public["entries"][0]["blind_id"]
    elif damage == "added_private_label":
        row["official_gold"] = "never read"
    else:
        private["plan_sha256"] = "0" * 64
    with pytest.raises(ValueError, match=error):
        audit_blind_linkage(plan, ids, schedule, public, private)


def _assignments(plan: dict, queue: dict) -> dict:
    return {
        "schema_version": 1,
        "plan_sha256": digest(plan),
        "items": [
            {
                "blind_id": e["blind_id"],
                "annotator_id": reviewer,
                "decision_sha256": "e" * 64,
            }
            for e in queue["entries"]
            for reviewer in ("rater-A", "rater-B")
        ],
    }


def test_blind_assignment_requires_distinct_reviewer_pairs(fixture) -> None:
    plan, ids, schedule = fixture
    queue, _ = make_blind_queue(plan, ids, schedule)
    reviews = _assignments(plan, queue)
    assert audit_annotations(plan, queue, reviews) == 786
    reviews["items"].pop()
    with pytest.raises(ValueError, match="incomplete"):
        audit_annotations(plan, queue, reviews)


def test_blind_assignment_rejects_duplicate_reviewer_or_arm_leak(fixture) -> None:
    plan, ids, schedule = fixture
    queue, _ = make_blind_queue(plan, ids, schedule)
    reviews = _assignments(plan, queue)
    reviews["items"][1]["annotator_id"] = "rater-A"
    with pytest.raises(ValueError, match="same annotator"):
        audit_annotations(plan, queue, reviews)
    queue["entries"][0]["arm"] = ARMS[0]
    with pytest.raises(ValueError, match="unknown keys"):
        audit_annotations(plan, queue, _assignments(plan, queue))


def test_exclusive_private_files_no_overwrite_or_symlink(tmp_path) -> None:
    dest = tmp_path / "linkage.json"
    write_new_private_file(dest, {"secret": "synthetic"})
    assert json.loads(dest.read_text()) == {"secret": "synthetic"}
    if os.name != "nt":
        assert stat.S_IMODE(dest.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        write_new_private_file(dest, {"secret": "overwrite-forbidden"})
    symlink = tmp_path / "indirect.json"
    symlink.symlink_to(dest)
    with pytest.raises(FileExistsError):
        write_new_private_file(symlink, {"secret": "symlink-forbidden"})


def test_cli_does_not_authorize_model_and_separates_linkage(
    fixture, tmp_path, monkeypatch, capsys,
) -> None:
    plan, ids, schedule = fixture
    paths = [
        tmp_path / "plan.json",
        tmp_path / "ids.json",
        tmp_path / "schedule.json",
    ]
    for path, data in zip(paths, (plan, ids, schedule), strict=True):
        path.write_text(json.dumps(data), encoding="utf-8")
    public_dir = tmp_path / "reviewers"
    private_dir = tmp_path / "trusted_parent_only"
    public_dir.mkdir()
    private_dir.mkdir()
    public = public_dir / "queue.json"
    private = private_dir / "linkage.json"
    monkeypatch.setattr(sys, "argv", [
        "check", "--plan", str(paths[0]), "--public-case-ids", str(paths[1]),
        "--schedule", str(paths[2]), "--blind-queue-out", str(public),
        "--private-linkage-out", str(private),
    ])
    assert main() == 0
    assert "UNSCORED" in capsys.readouterr().out
    assert len(json.loads(public.read_text())["entries"]) == 786
    assert len(json.loads(private.read_text())["entries"]) == 786
    with pytest.raises(SystemExit):
        main()  # Both output files must be immutable under accidental reruns.


def _receipts(plan: dict, schedule: dict) -> dict:
    return {
        "schema_version": 1,
        "plan_sha256": digest(plan),
        "runs": [
            {
                "execution_id": row["execution_id"],
                "session_id": row["session_id"],
                "state": "completed",
                "artifact_sha256": "f" * 64,
            }
            for row in schedule["runs"]
        ],
    }


def test_preaggregate_receipt_identity_and_itt_missingness(fixture) -> None:
    plan, ids, schedule = fixture
    receipts = _receipts(plan, schedule)
    assert audit_receipts(plan, ids, schedule, receipts) == {
        "completed": 786, "missing": 0, "infra_failed": 0,
    }
    receipts["runs"][0]["state"] = "missing"
    receipts["runs"][0]["artifact_sha256"] = None
    receipts["runs"][1]["state"] = "infra_failed"
    receipts["runs"][1]["artifact_sha256"] = None
    assert audit_receipts(plan, ids, schedule, receipts) == {
        "completed": 784, "missing": 1, "infra_failed": 1,
    }


@pytest.mark.parametrize("damage,error", [
    ("omit", "missing an intention-to-treat"),
    ("duplicate", "duplicated execution receipt"),
    ("wrong_session", "registered isolation"),
    ("bad_artifact", "completed artifact"),
    ("fabricated_score", "unknown keys"),
    ("failed_artifact", "cannot claim artifact"),
])
def test_preaggregate_receipt_rejects_forged_completion(
    fixture, damage, error,
) -> None:
    plan, ids, schedule = fixture
    receipts = _receipts(plan, schedule)
    if damage == "omit":
        receipts["runs"].pop()
    elif damage == "duplicate":
        receipts["runs"][1]["execution_id"] = receipts["runs"][0]["execution_id"]
    elif damage == "wrong_session":
        receipts["runs"][0]["session_id"] = "improper-shared-session"
    elif damage == "bad_artifact":
        receipts["runs"][0]["artifact_sha256"] = "unverified"
    elif damage == "fabricated_score":
        receipts["runs"][0]["task_success"] = True
    else:
        receipts["runs"][0]["state"] = "infra_failed"
    with pytest.raises(ValueError, match=error):
        audit_receipts(plan, ids, schedule, receipts)
