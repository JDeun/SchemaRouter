"""Fail-closed scored launch preflight without calling a paid model."""

import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import run_safeact_v1_scored as launch


def _inputs(tmp_path: Path) -> dict:
    root = tmp_path / "safeact"
    root.mkdir()
    commands = {
        c: (
            f"python3 agent_{i}.py --model same-model "
            "--backend codex --strategy baseline"
        )
        for i, c in enumerate(launch.CONDITIONS)
    }
    public = tmp_path / "public"
    public.mkdir()
    policy = public / "synthetic-policy.txt"
    policy.write_text("synthetic public policy only\n", encoding="utf-8")
    sources = [{
        "kind": "independent_contract",
        "path": policy.name,
        "sha256": hashlib.sha256(policy.read_bytes()).hexdigest(),
    }]
    return {
        "safeact_root": root,
        "model": "same-model",
        "commands": commands,
        "contracts": {
            "contracts": [{
                "domain": "customer_policy_qa", "action": "act", "sources": sources,
                "required_observations": [{
                    "tool": "charge_read", "record_id": "$action.charge_id",
                    "fields": ["owner"],
                }],
            }],
            "public_observation_mappings": {
                "customer_policy_qa": {
                    "charge_read": {
                        "record_id_key": "subject",
                        "field_name_key": "predicate",
                    },
                },
            },
            "case_coverage": {
                f"SAB-V1-{i:03d}": None
                for i in range(1, launch.EXPECTED_CASES + 1)
            },
        },
        "public_source_root": public,
        "intervention_manifest": {
            "reviewed": True,
            "independent_contract_review": {
                "approved": True,
                "author": "synthetic-test-author",
                "reviewer": "synthetic-test-independent-reviewer",
                "contract_sha256": "",
                "upstream_revision": launch.UPSTREAM_REVISION,
            },
            "conditions": {
                c: {
                    "mode": mode,
                    "adapter_commit": "a" * 40,
                    "agent_command_sha256": hashlib.sha256(
                        commands[c].encode("utf-8")
                    ).hexdigest(),
                }
                for c, mode in zip(
                    launch.CONDITIONS, launch.MODES, strict=True
                )
            },
        },
    }


def _freeze_contract_hash(sample: dict) -> None:
    sample["intervention_manifest"]["contract_sha256"] = hashlib.sha256(
        json.dumps(
            sample["contracts"], sort_keys=True, ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    sample["intervention_manifest"]["independent_contract_review"][
        "contract_sha256"
    ] = sample["intervention_manifest"]["contract_sha256"]


def _mock_public(monkeypatch, sample: dict) -> None:
    _freeze_contract_hash(sample)
    monkeypatch.setattr(launch, "verify_sources", lambda *a: [])
    monkeypatch.setattr(
        launch,
        "public_case_ids",
        lambda root: set(sample["contracts"]["case_coverage"]),
    )
    monkeypatch.setattr(
        launch.subprocess,
        "run",
        lambda *args, **kwargs: Mock(stdout=launch.UPSTREAM_REVISION),
    )


def test_complete_frozen_launch_matrix(monkeypatch, tmp_path: Path) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    plans = launch.validate_launch(**sample)
    assert len(plans) == 3
    assert plans[2].condition == launch.CONDITIONS[2]


def test_rejects_unreviewed_gated_arm(monkeypatch, tmp_path: Path) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    sample["intervention_manifest"]["reviewed"] = False
    with pytest.raises(ValueError, match="review"):
        launch.validate_launch(**sample)


def test_rejects_missing_case_policy(monkeypatch, tmp_path: Path) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    sample["contracts"]["case_coverage"].pop("SAB-V1-001")
    _freeze_contract_hash(sample)
    # The public listing is frozen separately from the mutable contract.
    monkeypatch.setattr(
        launch,
        "public_case_ids",
        lambda root: {
            f"SAB-V1-{i:03d}" for i in range(1, 132)
        },
    )
    with pytest.raises(ValueError, match="cover 131"):
        launch.validate_launch(**sample)


def test_rejects_unpinned_runtime_model(monkeypatch, tmp_path: Path) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    sample["commands"][launch.CONDITIONS[1]] = "python3 agent.py"
    with pytest.raises(ValueError, match="frozen model"):
        launch.validate_launch(**sample)


def test_rejects_wrong_upstream_revision(monkeypatch, tmp_path: Path) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    monkeypatch.setattr(
        launch.subprocess, "run", lambda *a, **k: Mock(stdout="wrong")
    )
    with pytest.raises(ValueError, match="revision"):
        launch.validate_launch(**sample)


def test_duplicate_action_contract_is_rejected(monkeypatch, tmp_path: Path) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    sample["contracts"]["contracts"].append(
        sample["contracts"]["contracts"][0].copy()
    )
    _freeze_contract_hash(sample)
    with pytest.raises(ValueError, match="unique names"):
        launch.validate_launch(**sample)


def test_empty_declared_model_is_rejected(monkeypatch, tmp_path: Path) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    sample["model"] = " "
    with pytest.raises(ValueError, match="nonempty"):
        launch.validate_launch(**sample)


def test_rejects_post_review_command_mutation(monkeypatch, tmp_path: Path) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    # Change only the trusted adapter identity; solver runtime flags remain
    # identical, so the snapshot-hash guard is the intended failure.
    name = launch.CONDITIONS[2]
    sample["commands"][name] = sample["commands"][name].replace(
        "agent_2.py", "agent_2_replaced.py"
    )
    with pytest.raises(ValueError, match="altered trusted adapter identity"):
        launch.validate_launch(**sample)


def test_changed_case_contract_snapshot_is_rejected(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    sample["contracts"]["contracts"][0]["required_observations"] = [
        {"tool": "unknown", "record_id": "$action.id", "fields": ["x"]}
    ]
    with pytest.raises(ValueError, match="contract snapshot hash changed"):
        launch.validate_launch(**sample)


@pytest.mark.parametrize(
    ("replacement", "error"),
    [
        ("--backend claude", "backend"),
        ("--backend wrong", "backend"),
        ("--strategy=scgr_eg", "strategy"),
        ("--strategy baseline --strategy baseline", "strategy"),
        ("--strategy", "strategy"),
    ],
)
def test_rejects_confounded_official_agent_arms(
    monkeypatch, tmp_path: Path, replacement: str, error: str
) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    original = sample["commands"][launch.CONDITIONS[0]]
    tokens = original.replace(" --backend codex", "").replace(
        " --strategy baseline", ""
    )
    if error == "backend":
        sample["commands"][launch.CONDITIONS[0]] = (
            tokens + " --strategy baseline " + replacement
        )
    else:
        sample["commands"][launch.CONDITIONS[0]] = (
            tokens + " --backend codex " + replacement
        )
    with pytest.raises(ValueError, match=error):
        launch.validate_launch(**sample)


def test_frozen_backend_and_strategy_support_equals_form(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    sample["commands"] = {
        key: cmd.replace("--backend codex", "--backend=codex").replace(
            "--strategy baseline", "--strategy=baseline"
        )
        for key, cmd in sample["commands"].items()
    }
    _freeze_contract_hash(sample)
    for condition in launch.CONDITIONS:
        sample["intervention_manifest"]["conditions"][condition][
            "agent_command_sha256"
        ] = hashlib.sha256(
            sample["commands"][condition].encode("utf-8")
        ).hexdigest()
    assert len(launch.validate_launch(**sample)) == 3


@pytest.mark.parametrize(
    ("key", "value", "error"),
    [
        ("approved", False, "approval"),
        ("author", "", "author and reviewer"),
        ("reviewer", "synthetic-test-author", "author and reviewer"),
        ("reviewer", "SYNTHETIC-TEST-AUTHOR", "author and reviewer"),
        ("contract_sha256", "0" * 64, "digest"),
        ("upstream_revision", "a" * 40, "revision"),
    ],
)
def test_rejects_invalid_independent_review(
    monkeypatch, tmp_path: Path, key: str, value: object, error: str
) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    sample["intervention_manifest"]["independent_contract_review"][key] = value
    with pytest.raises(ValueError, match=error):
        launch.validate_launch(**sample)


def test_scored_launch_rejects_missing_independent_contract_review(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    del sample["intervention_manifest"]["independent_contract_review"]
    with pytest.raises(ValueError, match="approval"):
        launch.validate_launch(**sample)


def test_review_is_bound_to_frozen_contract_snapshot(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    sample["contracts"]["contracts"][0]["argument_bindings"] = [
        {"argument": "charge_id", "record_id": "C2"}
    ]
    _freeze_contract_hash(sample)
    sample["intervention_manifest"]["independent_contract_review"][
        "contract_sha256"
    ] = "0" * 64
    with pytest.raises(ValueError, match="review digest"):
        launch.validate_launch(**sample)


@pytest.mark.parametrize(
    "mismatched_flag",
    [
        "--profile alternate-codex-profile",
        "--cfuse-config /tmp/other-provider.json",
        "--cli-bin /tmp/other-codex",
        "--model-catalog /tmp/other-model-catalog.json",
        "--timeout 420",
        "--max-turns=24",
        "--extra-arg=--different-solver-setting",
        "--keep-sandbox",
    ],
)
def test_rejects_cross_arm_solver_configuration_drift(
    monkeypatch, tmp_path: Path, mismatched_flag: str
) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    sample["commands"][launch.CONDITIONS[1]] += " " + mismatched_flag
    with pytest.raises(ValueError, match="runtime|keep-sandbox"):
        launch.validate_launch(**sample)


def test_allows_identical_explicit_solver_configuration(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    for condition in launch.CONDITIONS:
        sample["commands"][condition] += (
            " --timeout=420 --max-turns 24"
            " --extra-arg=--alpha --extra-arg=--beta"
        )
        sample["intervention_manifest"]["conditions"][condition][
            "agent_command_sha256"
        ] = hashlib.sha256(
            sample["commands"][condition].encode("utf-8")
        ).hexdigest()
    assert len(launch.validate_launch(**sample)) == 3


@pytest.mark.parametrize(
    "malformed",
    [
        "--timeout",
        "--max-turns --keep-sandbox",
        "--extra-arg=",
        "--profile first --profile second",
    ],
)
def test_rejects_broken_or_ambiguous_solver_option(
    monkeypatch, tmp_path: Path, malformed: str
) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    sample["commands"][launch.CONDITIONS[2]] += " " + malformed
    # A repeatable --extra-arg may appear more than once, but never empty.
    with pytest.raises(ValueError, match="requires|runtime|duplicate"):
        launch.validate_launch(**sample)

def test_per_case_expected_action_oracle_never_authorized(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _inputs(tmp_path)
    _mock_public(monkeypatch, sample)
    sample["contracts"]["case_coverage"]["SAB-V1-001"] = "act"
    _freeze_contract_hash(sample)
    with pytest.raises(ValueError, match="oracle"):
        launch.validate_launch(**sample)

def test_domain_scoped_contracts_may_reuse_action_names(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _inputs(tmp_path)
    sample["contracts"]["contracts"].append({
        "domain": "legal_finance_advice",
        "action": "act",
        "sources": sample["contracts"]["contracts"][0]["sources"],
        "required_observations": [{
            "tool": "legal_review_status",
            "record_id": "$action.charge_id", "fields": ["approved"],
        }],
    })
    sample["contracts"]["public_observation_mappings"]["legal_finance_advice"] = {
        "legal_review_status": {
            "record_id_key": "subject", "field_name_key": "predicate",
        },
    }
    _mock_public(monkeypatch, sample)
    assert len(launch.validate_launch(**sample)) == 3


def test_scored_contracts_require_real_public_domain(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _inputs(tmp_path)
    sample["contracts"]["contracts"][0]["domain"] = "untrusted"
    _mock_public(monkeypatch, sample)
    with pytest.raises(ValueError, match="per public domain"):
        launch.validate_launch(**sample)


def test_launch_rejects_foreign_domain_evidence_mapping(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _inputs(tmp_path)
    sample["contracts"]["public_observation_mappings"].pop("customer_policy_qa")
    sample["contracts"]["public_observation_mappings"]["legal_finance_advice"] = {
        "charge_read": {
            "record_id_key": "subject", "field_name_key": "predicate",
        },
    }
    _mock_public(monkeypatch, sample)
    with pytest.raises(ValueError, match="domain-scoped observation mapping"):
        launch.validate_launch(**sample)


def test_launch_rejects_flat_mapping(monkeypatch, tmp_path: Path) -> None:
    sample = _inputs(tmp_path)
    sample["contracts"]["public_observation_mappings"] = {
        "charge_read": {
            "record_id_key": "subject", "field_name_key": "predicate",
        },
    }
    _mock_public(monkeypatch, sample)
    with pytest.raises(ValueError, match="mapping domain"):
        launch.validate_launch(**sample)


def test_scored_preflight_rejects_unsafe_value_expression_before_runner(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _inputs(tmp_path)
    sample["contracts"]["contracts"][0]["value_conditions"] = [{
        "tool": "charge_read", "record_id": "$action.charge_id",
        "field": "owner", "operator": "eval",
        "action_argument": "refund_amount",
    }]
    _mock_public(monkeypatch, sample)
    with pytest.raises(ValueError, match="value condition"):
        launch.validate_launch(**sample)


def test_scored_preflight_rejects_unanchored_value_condition(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _inputs(tmp_path)
    sample["contracts"]["contracts"][0]["value_conditions"] = [{
        "tool": "charge_read", "record_id": "$action.charge_id",
        "field": "nonexistent_field", "operator": "eq",
        "action_argument": "refund_amount",
    }]
    _mock_public(monkeypatch, sample)
    with pytest.raises(ValueError, match="declared observation"):
        launch.validate_launch(**sample)
