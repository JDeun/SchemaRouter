"""Offline adapter contract smoke plus strict source byte/identity controls."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.research_open_meteo_real_openapi_dev import (
    SOURCE_COMMIT,
    SOURCE_NAMES,
    evaluate,
    git_blob_sha1,
    load_contracts,
    ranked_score_diagnostic,
)


def fake_publisher_files(tmp_path: Path) -> Path:
    source = tmp_path / "publisher"
    source.mkdir()
    docs = {}
    for name in SOURCE_NAMES:
        text = f"""openapi: 3.1.0
info:
  title: Publisher-like synthetic {name}
  version: 1.0.0
paths:
  /v1/{name}:
    get:
      summary: Get {name} observational records
      responses:
        '200':
          description: Synthetic result
          content:
            application/json:
              schema:
                type: object
                properties:
                  source:
                    type: string
"""
        payload = text.encode()
        (source / f"{name}.yml").write_bytes(payload)
        docs[name] = {
            "path": f"openapi/{name}.yml",
            "git_blob_sha1": git_blob_sha1(payload),
        }
    manifest = {
        "provider_repository": "open-meteo/open-meteo",
        "source_commit": SOURCE_COMMIT,
        "real_provider_authored_spec": True,
        "independently_authored_query_labels": False,
        "may_release": False, "docs": docs,
    }
    (tmp_path / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8",
    )
    # Dummy docs and matching in-memory manifest are ONLY unit test fixtures.
    # Production Actions requires actual pinned external Git blob hashes.
    return tmp_path / "manifest.json"


def test_finite_publisher_like_adapter_smoke(tmp_path: Path) -> None:
    manifest = fake_publisher_files(tmp_path)
    sources, failures, evidence = load_contracts(manifest, tmp_path / "publisher")
    assert len(sources) == 9
    assert failures == []
    assert all(row["status"] == "parsed" for row in evidence.values())
    report = evaluate(manifest, tmp_path / "publisher")
    assert report["supported_cases"] == 27
    assert report["unsupported_cases"] == 9
    assert report["scope"]["may_release"] is False
    assert report["scope"]["tool_or_live_api_invocations"] is False
    assert report["registered_routes"] == 9
    assert report["scope"]["independently_labelled_queries"] is False


def test_fails_closed_on_provider_byte_drift(tmp_path: Path) -> None:
    manifest = fake_publisher_files(tmp_path)
    path = tmp_path / "publisher" / "elevation.yml"
    path.write_bytes(path.read_bytes() + b"# changed without source commit\n")
    with pytest.raises(ValueError, match="byte drift"):
        load_contracts(manifest, tmp_path / "publisher")


def test_fails_closed_on_untrusted_source_provenance(tmp_path: Path) -> None:
    manifest = fake_publisher_files(tmp_path)
    obj = json.loads(manifest.read_text(encoding="utf-8"))
    for key, wrong in (
        ("source_commit", "untrusted-head"),
        ("may_release", True),
        ("independently_authored_query_labels", True),
    ):
        mutated = dict(obj)
        mutated[key] = wrong
        manifest.write_text(json.dumps(mutated), encoding="utf-8")
        with pytest.raises(ValueError, match="provenance"):
            load_contracts(manifest, tmp_path / "publisher")


def test_blob_identity_includes_length_and_contents() -> None:
    assert git_blob_sha1(b"x") != git_blob_sha1(b"x\n")
    assert len(git_blob_sha1(b"abc")) == 40


def test_zero_score_ties_are_not_counted_as_semantic_recall() -> None:
    empty_signal = SimpleNamespace(candidates=[
        SimpleNamespace(score=0.0, selection_source="deterministic"),
        SimpleNamespace(score=0.0, selection_source="deterministic"),
    ])
    diagnostic = ranked_score_diagnostic(empty_signal)
    assert diagnostic["all_nonpositive"] is True
    assert diagnostic["top1_score"] == 0.0
    assert diagnostic["top1_tie_count"] == 2

    nonzero = SimpleNamespace(candidates=[
        SimpleNamespace(score=2.0, selection_source="lexical"),
        SimpleNamespace(score=0.0, selection_source="deterministic"),
    ])
    assert ranked_score_diagnostic(nonzero)["all_nonpositive"] is False
    invalid = SimpleNamespace(candidates=[
        SimpleNamespace(score=float("nan"), selection_source="deterministic"),
    ])
    with pytest.raises(ValueError, match="non-finite"):
        ranked_score_diagnostic(invalid)
