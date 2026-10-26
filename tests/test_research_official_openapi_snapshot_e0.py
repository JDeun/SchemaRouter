"""Immutable authentic provider source ingestion, without invented route grants."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.research_official_openapi_snapshot_e0 import (
    EVIDENCE_TIER,
    FIXTURE_DIR,
    LICENSE_BYTES,
    LICENSE_GIT_BLOB,
    LICENSE_SHA256,
    REVIEWED_READS,
    SCHEMA_BYTES,
    SCHEMA_GIT_BLOB,
    SCHEMA_SHA256,
    UPSTREAM_COMMIT,
    _scoped_original_document,
    audit_official_ollama_snapshot,
    compile_official_ollama_snapshot,
    parse_pinned_ollama_source,
)


def _bytes() -> tuple[bytes, bytes]:
    base = FIXTURE_DIR / f"ollama-{UPSTREAM_COMMIT[:8]}"
    return (
        Path(str(base) + "-openapi.yaml").read_bytes(),
        Path(str(base) + "-LICENSE.txt").read_bytes(),
    )


def test_original_provider_bytes_and_git_blobs_are_exactly_pinned() -> None:
    spec, notice = _bytes()
    for raw, size, sha256, blob in (
        (spec, SCHEMA_BYTES, SCHEMA_SHA256, SCHEMA_GIT_BLOB),
        (notice, LICENSE_BYTES, LICENSE_SHA256, LICENSE_GIT_BLOB),
    ):
        assert len(raw) == size
        assert hashlib.sha256(raw).hexdigest() == sha256
        assert hashlib.sha1(
            b"blob " + str(len(raw)).encode("ascii") + bytes((0,)) + raw
        ).hexdigest() == blob


def test_original_source_provenance_and_scope_are_not_invented() -> None:
    spec, notice = _bytes()
    doc = parse_pinned_ollama_source(spec, notice)
    assert doc["openapi"] == "3.1.0"
    assert doc["info"]["title"] == "Ollama API"
    assert doc["info"]["license"]["name"] == "MIT"
    sliced = _scoped_original_document(doc)
    assert set(sliced["paths"]) == set(REVIEWED_READS)
    for path, (operation, _) in REVIEWED_READS.items():
        assert sliced["paths"][path]["get"] == doc["paths"][path]["get"]
        assert sliced["paths"][path].keys() == {"get"}
        assert sliced["paths"][path]["get"]["operationId"] == operation


def test_real_openapi_converter_preserves_offline_no_grant_boundary() -> None:
    spec, notice = _bytes()
    converted = compile_official_ollama_snapshot(spec, notice)
    assert len(converted.endpoints) == 2
    assert not converted.source_type
    assert not converted.license
    for endpoint in converted.endpoints:
        assert endpoint.method == "GET"
        assert endpoint.read_only is True
        assert endpoint.destructive is not True
        assert all(not field.semantic_id for field in endpoint.output_fields)
    report = audit_official_ollama_snapshot()
    assert report["evidence_tier"] == EVIDENCE_TIER
    assert report["native_source_routes"] == 2
    assert report["source_semantic_reviewed"] is False
    assert report["execution_authority"] is False
    assert report["provider_live_io"] is False
    assert report["publisher_gold_verified"] is False
    assert report["independent_e2_qualified"] is False
    assert report["default_routing_changed"] is False


@pytest.mark.parametrize("which", ["schema", "license"])
@pytest.mark.parametrize("mutation", ["single-byte", "append", "truncate"])
def test_changed_upstream_snapshot_fails_closed(which: str, mutation: str) -> None:
    spec, notice = _bytes()
    if which == "schema":
        target = bytearray(spec)
    else:
        target = bytearray(notice)
    if mutation == "single-byte":
        target[len(target) // 2] ^= 1
    elif mutation == "append":
        target.extend(b" ")
    else:
        target.pop()
    changed = bytes(target)
    with pytest.raises(ValueError, match="snapshot"):
        parse_pinned_ollama_source(
            changed if which == "schema" else spec,
            changed if which == "license" else notice,
        )


def test_nonbytes_are_not_accepted_as_source_truth() -> None:
    _, notice = _bytes()
    with pytest.raises(ValueError, match="snapshot"):
        parse_pinned_ollama_source("not a native byte snapshot", notice)  # type: ignore[arg-type]


def test_snapshot_report_cannot_accept_unpinned_local_overwrite(tmp_path: Path) -> None:
    spec, notice = _bytes()
    src = tmp_path / "openapi.yaml"
    license_file = tmp_path / "LICENSE"
    src.write_bytes(spec + bytes((10,)))
    license_file.write_bytes(notice)
    with pytest.raises(ValueError, match="snapshot"):
        audit_official_ollama_snapshot(src, license_file)
