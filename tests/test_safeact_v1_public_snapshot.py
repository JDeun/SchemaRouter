"""Public policy source snapshots must fail closed on gold and tampering."""

from pathlib import Path

from scripts.verify_safeact_v1_public_snapshot import UPSTREAM, audit, git_blob_sha


def _fixture(tmp_path: Path):
    path = "templates/customer_policy_qa/world/policies/refunds.md"
    local, upstream = tmp_path / "sources", tmp_path / "pinned"
    for root in (local, upstream):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("synthetic policy, no evaluator gold\n", encoding="utf-8")
    doc = {
        "kind": "safeact_v1_unreviewed_public_policy_snapshot",
        "upstream_revision": UPSTREAM,
        "contracts_authored": False,
        "independently_approved": False,
        "scored_run_authorized": False,
        "sources": [{
            "path": path,
            "source_git_blob_sha1": git_blob_sha((local / path).read_bytes())
        }],
    }
    return doc, local, upstream, path


def test_pinned_public_policy_passes(tmp_path: Path) -> None:
    doc, local, upstream, _ = _fixture(tmp_path)
    assert audit(doc, local, upstream) == []


def test_hidden_evaluator_path_and_changed_bytes_fail(tmp_path: Path) -> None:
    doc, local, upstream, path = _fixture(tmp_path)
    doc["sources"][0]["path"] = "env/case_manifest.json"
    assert any("forbidden" in e for e in audit(doc, local, upstream))
    doc, local, upstream, path = _fixture(tmp_path)
    (local / path).write_text("changed")
    assert any("mismatch" in e for e in audit(doc, local, upstream))


def test_unreviewed_never_self_approves_or_follows_symlinks(tmp_path: Path) -> None:
    doc, local, upstream, path = _fixture(tmp_path)
    doc["independently_approved"] = True
    assert audit(doc, local, upstream)
    doc, local, upstream, path = _fixture(tmp_path)
    (local / path).unlink()
    (local / path).symlink_to(upstream / path)
    assert any("symlinked" in e for e in audit(doc, local, upstream))


def test_extra_files_and_duplicate_paths_fail(tmp_path: Path) -> None:
    doc, local, upstream, path = _fixture(tmp_path)
    (local / "hidden.json").write_text("evaluator")
    assert any("undeclared" in e for e in audit(doc, local, upstream))
    (local / "hidden.json").unlink()
    doc["sources"].append(dict(doc["sources"][0]))
    assert any("duplicate" in e for e in audit(doc, local, upstream))
