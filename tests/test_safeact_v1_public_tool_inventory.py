"""Anti-leakage regressions for read-only public tool identity inventory."""

import hashlib
import shutil
from pathlib import Path

import pytest

from scripts.inventory_safeact_v1_public_tools import PUBLIC_DOMAINS, build_inventory


def _fixture(tmp_path: Path) -> Path:
    for domain in PUBLIC_DOMAINS:
        folder = tmp_path / "templates" / domain / "tools"
        folder.mkdir(parents=True)
        (folder / f"{domain}_read.py").write_text("def read(): return 1\n")
        (folder / "mock_tool.py").write_text("mock = True\n")
        (folder / "_tool_common.py").write_text("private = True\n")
        if domain != "ops_code_agent":
            policies = tmp_path / "templates" / domain / "world" / "policies"
            policies.mkdir(parents=True)
            (policies / "public_policy.md").write_text("generic policy only\n")
        (tmp_path / "env" / domain / "world").mkdir(parents=True)
        (tmp_path / "env" / domain / "world" / "hidden.json").write_text(
            "forbidden-evaluator-payload"
        )
    return tmp_path


def test_only_public_tool_filenames_and_hashes_without_gold(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    inventory = build_inventory(root)
    assert inventory["scored_experiment"] is False
    assert inventory["human_reviewed"] is False
    assert inventory["independently_authored_contracts"] is False
    assert inventory["case_coverage"] is None
    assert len(inventory["tools"]) == len(PUBLIC_DOMAINS)
    for record in inventory["tools"]:
        assert record["source_path"].startswith("templates/")
        assert "/tools/" in record["source_path"]
        assert len(record["source_sha256"]) == 64
        assert record["source_sha256"] == hashlib.sha256(
            (root / record["source_path"]).read_bytes()
        ).hexdigest()
    assert "forbidden-evaluator-payload" not in str(inventory)
    assert "mock_tool" not in str(inventory)
    assert inventory["policy_candidates_are_contracts"] is False
    assert inventory["policy_candidates_are_runtime_observations"] is False
    assert inventory["domains_without_policy_directory"] == ["ops_code_agent"]
    assert len(inventory["public_policy_candidates"]) == len(PUBLIC_DOMAINS) - 1
    for policy in inventory["public_policy_candidates"]:
        assert policy["source_path"].startswith("templates/")
        assert "/world/policies/" in policy["source_path"]
        assert policy["source_sha256"] == hashlib.sha256(
            (root / policy["source_path"]).read_bytes()
        ).hexdigest()


def test_tool_symlink_is_rejected(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    folder = root / "templates" / PUBLIC_DOMAINS[0] / "tools"
    (folder / "danger.py").symlink_to(
        root / "env" / PUBLIC_DOMAINS[0] / "world" / "hidden.json"
    )
    with pytest.raises(ValueError, match="unsafe public tool path"):
        build_inventory(root)


def test_absent_domain_is_rejected(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    shutil.rmtree(root / "templates" / PUBLIC_DOMAINS[0])
    with pytest.raises(ValueError, match="missing or symlinked"):
        build_inventory(root)

def test_policy_symlink_is_rejected_before_hashing(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    folder = root / "templates" / PUBLIC_DOMAINS[0] / "world" / "policies"
    (folder / "hidden.json").symlink_to(
        root / "env" / PUBLIC_DOMAINS[0] / "world" / "hidden.json"
    )
    with pytest.raises(ValueError, match="unsafe public policy candidate"):
        build_inventory(root)


def test_policy_directory_symlink_is_rejected(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    folder = root / "templates" / "ops_code_agent" / "world"
    folder.mkdir(parents=True)
    (folder / "policies").symlink_to(
        root / "env" / PUBLIC_DOMAINS[0] / "world", target_is_directory=True
    )
    with pytest.raises(ValueError, match="symlinked public policy directory"):
        build_inventory(root)


def test_nested_world_state_is_not_inventoried(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    other = root / "templates" / PUBLIC_DOMAINS[0] / "world" / "payments"
    other.mkdir(parents=True)
    (other / "private.json").write_text("not-a-public-policy", encoding="utf-8")
    inventory = build_inventory(root)
    assert "not-a-public-policy" not in str(inventory)
    assert not any(
        "/payments/" in item["source_path"]
        for item in inventory["public_policy_candidates"]
    )
