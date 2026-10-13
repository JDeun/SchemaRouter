"""Offline synthetic negative controls for HYSET independent retraining #795."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.validate_hyset_retraining_manifest import (
    PINNED_HYSET_SHA,
    SPLITS,
    load_manifest,
    validate_manifest,
)

MANIFEST = Path(
    "benchmarks/external-validation-hyset-retrain-dev-v1/manifest.json"
)


def development():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def ready_inputs(*, eta=0, with_checkpoint=False):
    m = deepcopy(development())
    m["status"] = "frozen_pre_scoring"
    m["governance"]["frozen_before_scoring"] = True
    m["encoder"]["revision"] = "a" * 40
    m["data"]["toolbench_source_revision"] = "b" * 40
    m["data"]["toolbench_digest"] = "c" * 64
    mode = "annotation_only_eta0" if eta == 0 else "execution_reward_eta03"
    m["training"]["primary_configuration"] = {
        "encoder_type": "qwen",
        "d_z": 1536,
        "eta": eta,
        "mode": mode,
        "command": (
            "./train_hyset.sh --encoder_type qwen --d_z 1536 "
            f"--seed 42 --eta {eta}"
            + (" --reward_cache pinned-public-cache.json" if eta == 0.3 else "")
        ),
    }
    if eta == 0.3:
        m["training"]["reward_cache_digest"] = "d" * 64
    if with_checkpoint:
        m["training"]["checkpoint_sha256"] = "e" * 64
    return m


def test_committed_unfrozen_dev_manifest_reports_no_scoring_authority():
    report = validate_manifest(development())
    assert report["status"] == "DEVELOPMENT_UNSCORED"
    assert report["scoring_authorized"] is False
    assert report["independent_reviewer_approved"] is False
    assert report["native_hyset_execution_performed"] is False
    assert report["paper_checkpoint_reproduction_claim_allowed"] is False
    assert report["upstream_commit"] == PINNED_HYSET_SHA
    assert report["split_count"] == 6


@pytest.mark.parametrize(("field", "value", "reason"), [
    ("paper_checkpoint_available", True, "paper checkpoint availability"),
    ("paper_checkpoint_available", 0, "paper checkpoint availability"),
    ("result_label", "HYSET paper best.pt reproduced", "independently retrained"),
    ("commit", "0" * 40, "deviates from pinned"),
])
def test_dev_claims_and_upstream_pin_cannot_drift(field, value, reason):
    m = development()
    m["upstream"][field] = value
    with pytest.raises(ValueError, match=reason):
        validate_manifest(m)


@pytest.mark.parametrize(("field", "value"), [
    ("paper_checkpoint_reproduction_claim_allowed", True),
    ("heldout_tuning_allowed", 0),
    ("failed_training_and_oom_are_reportable_results", False),
    ("frozen_before_scoring", True),
])
def test_development_governance_remains_unfrozen_and_truthful(field, value):
    m = development()
    m["governance"][field] = value
    with pytest.raises(ValueError):
        validate_manifest(m)


def test_exact_six_official_heldout_paths_are_required():
    m = development()
    assert m["data"]["heldout_split_paths"] == list(SPLITS)
    for change in ("omit", "duplicate", "substitute"):
        altered = deepcopy(m)
        paths = altered["data"]["heldout_split_paths"]
        if change == "omit":
            paths.pop()
        elif change == "duplicate":
            paths[-1] = paths[0]
        else:
            paths[0] = "external/stabletoolbench/solvable_queries/G1.json"
        with pytest.raises(ValueError, match="six exact"):
            validate_manifest(altered)


def test_training_preflight_rejects_missing_public_artifact_pins():
    draft = development()
    with pytest.raises(ValueError, match="explicitly frozen"):
        validate_manifest(draft, stage="training")
    valid = ready_inputs()
    for path in (
        ("encoder", "revision"),
        ("data", "toolbench_source_revision"),
        ("data", "toolbench_digest"),
        ("training", "primary_configuration"),
    ):
        altered = deepcopy(valid)
        altered[path[0]][path[1]] = None
        with pytest.raises(ValueError):
            validate_manifest(altered, stage="training")


@pytest.mark.parametrize("eta", [0, 0.3])
def test_stage_gates_consistent_annonly_or_cache_backed_retraining(eta):
    data = ready_inputs(eta=eta)
    report = validate_manifest(data, stage="training")
    assert report["scoring_authorized"] is False
    assert report["independent_reviewer_approved"] is False
    assert report["status"] == "STRUCTURAL_INPUTS_ONLY_NOT_EXTERNALLY_REVIEWED"
    with pytest.raises(ValueError, match="retrained checkpoint"):
        validate_manifest(data, stage="evaluation")
    data["training"]["checkpoint_sha256"] = "f" * 64
    evaluation = validate_manifest(data, stage="evaluation")
    assert evaluation["scoring_authorized"] is False


@pytest.mark.parametrize(("mutation", "reason"), [
    (
        lambda m: m["training"]["primary_configuration"].update(
            eta=0.3
        ),
        "execution-reward",
    ),
    (
        lambda m: m["training"]["primary_configuration"].update(
            mode="paper-best.pt"
        ),
        "ablation label",
    ),
    (
        lambda m: m["training"].update(reward_cache_digest="e" * 64),
        "must not claim an execution reward cache",
    ),
    (
        lambda m: m["training"]["primary_configuration"].update(
            d_z=768
        ),
        "encoder type/d_z",
    ),
    (
        lambda m: m["training"]["primary_configuration"].update(
            eta=True
        ),
        "numeric, finite",
    ),
    (
        lambda m: m["training"]["primary_configuration"].update(
            eta=10 ** 1000
        ),
        "numeric, finite",
    ),
    (
        lambda m: m["training"]["primary_configuration"].update(
            eta="0"
        ),
        "numeric, finite",
    ),
    (
        lambda m: m["training"]["primary_configuration"].update(
            command="python fake_trainer.py"
        ),
        "public train_hyset.sh",
    ),
])
def test_annotation_ablation_does_not_silently_change_training_recipe(
    mutation, reason,
):
    data = ready_inputs(eta=0)
    mutation(data)
    with pytest.raises(ValueError, match=reason):
        validate_manifest(data, stage="training")


def test_reward_training_requires_actual_pinned_reward_cache():
    data = ready_inputs(eta=0.3)
    data["training"]["reward_cache_digest"] = None
    with pytest.raises(ValueError, match="reward cache"):
        validate_manifest(data, stage="training")


def test_evaluation_rejects_missing_training_checkpoint_and_paper_claim():
    data = ready_inputs(with_checkpoint=True)
    data["training"]["checkpoint_sha256"] = None
    with pytest.raises(ValueError, match="retrained checkpoint"):
        validate_manifest(data, stage="evaluation")
    data = ready_inputs(with_checkpoint=True)
    data["governance"]["paper_checkpoint_reproduction_claim_allowed"] = True
    with pytest.raises(ValueError, match="paper checkpoint claim"):
        validate_manifest(data, stage="evaluation")


def test_draft_still_cannot_masquerade_as_partially_pinned_retraining():
    data = development()
    data["encoder"]["revision"] = "a" * 40
    with pytest.raises(ValueError, match="masquerade"):
        validate_manifest(data, stage="development")


@pytest.mark.parametrize("text", [
    '{"schema_version":1,"schema_version":1}',
    '{"encoder":{"revision":null,"revision":"a"}}',
    '{"training":{"eta":NaN}}',
    '{"training":{"eta":Infinity}}',
])
def test_json_parser_rejects_duplicate_keys_and_nonfinite_constants(
    tmp_path: Path, text: str,
):
    file = tmp_path / "manifest.json"
    file.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate|nonfinite"):
        load_manifest(file)


def test_read_only_preflight_never_writes_artifact_or_runs_native_model(
    tmp_path: Path,
):
    file = tmp_path / "manifest.json"
    file.write_text(json.dumps(development()), encoding="utf-8")
    before = file.read_bytes()
    report = validate_manifest(load_manifest(file), stage="development")
    assert report["native_hyset_execution_performed"] is False
    assert report["scoring_authorized"] is False
    assert file.read_bytes() == before
    assert sorted(x.name for x in tmp_path.iterdir()) == ["manifest.json"]



@pytest.mark.parametrize(("command", "reason"), [
    (
        "./train_hyset.sh --encoder_type qwen --d_z 1536 --seed 42",
        "explicit --eta required",
    ),
    (
        "./train_hyset.sh --encoder_type bert --d_z 1536 --seed 42 --eta 0",
        "must match encoder, d_z and seed",
    ),
    (
        "./train_hyset.sh --encoder_type qwen --d_z 768 --seed 42 --eta 0",
        "must match encoder, d_z and seed",
    ),
    (
        "./train_hyset.sh --encoder_type qwen --d_z 1536 --seed 43 --eta 0",
        "must match encoder, d_z and seed",
    ),
    (
        "./train_hyset.sh --encoder_type qwen --d_z 1536 --seed 42 --eta 0.3",
        "native --eta does not match",
    ),
    (
        "./train_hyset.sh --encoder_type qwen --d_z 1536 --seed 42 --eta 0 "
        "--reward_cache forbidden-cache.json",
        "must not load a reward cache",
    ),
    (
        "./train_hyset.sh --encoder_type qwen --d_z 1536 --seed 42 --eta 0 "
        "--eta 0.3",
        "duplicate",
    ),
    (
        "./train_hyset.sh --encoder_type qwen --d_z 1536 --seed 42 --eta 0 "
        "--test_id_dir a-different-test-directory",
        "unknown",
    ),
    (
        "./train_hyset.sh --encoder_type qwen --d_z 1536 --seed 42 --eta 0 "
        "&& python3 fake_runner.py",
        "shell operator",
    ),
    (
        "python3 fake_train_hyset.sh --encoder_type qwen --d_z 1536 "
        "--seed 42 --eta 0",
        "invoke the pinned",
    ),
])
def test_native_train_argv_must_match_declared_frozen_configuration(
    command, reason,
):
    data = ready_inputs(eta=0)
    data["training"]["primary_configuration"]["command"] = command
    with pytest.raises(ValueError, match=reason):
        validate_manifest(data, stage="training")


def test_eta03_native_command_must_actually_supply_a_reward_cache():
    data = ready_inputs(eta=0.3)
    command = data["training"]["primary_configuration"]["command"]
    data["training"]["primary_configuration"]["command"] = command.replace(
        " --reward_cache pinned-public-cache.json", ""
    )
    with pytest.raises(ValueError, match="command must declare a reward cache"):
        validate_manifest(data, stage="training")


def test_native_train_command_accepts_explicit_equals_form_without_shell():
    data = ready_inputs(eta=0)
    data["training"]["primary_configuration"]["command"] = (
        "./train_hyset.sh --encoder_type=qwen --d_z=1536 --seed=42 --eta=0"
    )
    result = validate_manifest(data, stage="training")
    assert result["scoring_authorized"] is False
    assert result["native_hyset_execution_performed"] is False
