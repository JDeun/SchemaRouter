"""Strict SafeAct V1 contract source hash regression tests."""
from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.verify_safeact_v1_sources import verify_sources


def _doc(path: str, sha256: str | None) -> dict[str, object]:
    source = {"kind": "public_policy", "path": path}
    if sha256 is not None:
        source["sha256"] = sha256
    return {"contracts": [{"action": "refund_issue", "sources": [source]}]}


def test_matching_public_source_passes(tmp_path: Path) -> None:
    source = tmp_path / "policy.json"
    source.write_text("independent public policy", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert verify_sources(_doc("policy.json", digest), tmp_path) == []


def test_source_tampering_fails(tmp_path: Path) -> None:
    source = tmp_path / "policy.json"
    source.write_text("original", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    source.write_text("changed", encoding="utf-8")
    errors = verify_sources(_doc("policy.json", digest), tmp_path)
    assert any("sha256 mismatch" in e for e in errors)


def test_unpinned_source_fails(tmp_path: Path) -> None:
    (tmp_path / "policy.json").write_text("public", encoding="utf-8")
    assert any("frozen sha256" in e for e in verify_sources(_doc("policy.json", None), tmp_path))


def test_symlink_source_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "real.json"
    source.write_text("public", encoding="utf-8")
    (tmp_path / "linked.json").symlink_to(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert any("symlink" in e for e in verify_sources(_doc("linked.json", digest), tmp_path))


def test_matching_hash_cannot_authorize_hidden_evaluator_source(tmp_path: Path) -> None:
    source = tmp_path / "checkout" / "env" / "case_manifest.json"
    source.parent.mkdir(parents=True)
    source.write_text("hidden gold", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    errors = verify_sources(_doc("checkout/env/case_manifest.json", digest), tmp_path)
    assert any("forbidden evaluator source" in e for e in errors)
