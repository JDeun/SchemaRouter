"""Official GitHub REST 651 original GETs, source-pinned and never executable."""
from __future__ import annotations

from pathlib import Path

import pytest

from schemarouter.native_graph_index import NativeSchemaGraphIndex


@pytest.fixture(scope="module")
def source_bytes() -> tuple[bytes, bytes]:
    from scripts import research_official_github_get_e0 as mod

    base = mod.FIXTURE_DIR / "github-rest-755ee33b"
    return (
        Path(str(base) + "-api.github.com.2022-11-28.json.gz").read_bytes(),
        Path(str(base) + "-LICENSE.md").read_bytes(),
    )


def test_real_official_github_source_and_original_mit_license(
    source_bytes: tuple[bytes, bytes],
) -> None:
    from scripts import research_official_github_get_e0 as mod

    document = mod.parse_pinned_github_rest_source(*source_bytes)
    assert document["openapi"] == "3.0.3"
    assert document["info"]["title"] == "GitHub v3 REST API"
    assert len(document["paths"]) == 823
    assert sum("get" in v for v in document["paths"].values()) == 651


@pytest.mark.parametrize("target", ("archive", "license"))
@pytest.mark.parametrize("mutation", ("flip", "append", "truncate"))
def test_source_or_license_byte_mutation_never_loads(
    source_bytes: tuple[bytes, bytes], target: str, mutation: str,
) -> None:
    from scripts import research_official_github_get_e0 as mod

    archive, notice = source_bytes
    changed = bytearray(archive if target == "archive" else notice)
    if mutation == "flip":
        changed[len(changed) // 2] ^= 1
    elif mutation == "append":
        changed.append(10)
    else:
        changed.pop()
    with pytest.raises(ValueError, match="pinned|original|snapshot"):
        mod.parse_pinned_github_rest_source(
            bytes(changed) if target == "archive" else archive,
            bytes(changed) if target == "license" else notice,
        )


def test_real_github_get_bundle_keeps_all_651_source_operations(
    source_bytes: tuple[bytes, bytes],
) -> None:
    from scripts import research_official_github_get_e0 as mod

    document = mod.parse_pinned_github_rest_source(*source_bytes)
    bundle = mod.compile_official_github_get_bundle_e0(document)
    assert len(bundle.endpoints) == 651
    assert len({endpoint.name for endpoint in bundle.endpoints}) == 651
    assert all(e.method == "GET" and e.read_only and not e.destructive for e in bundle.endpoints)
    assert bundle.source_type is None and bundle.license is None
    assert all(not field.semantic_id for e in bundle.endpoints for field in e.output_fields)


@pytest.fixture(scope="module")
def churn_receipt() -> dict:
    from scripts.research_official_github_get_e0 import audit_official_github_get_churn_e0

    return audit_official_github_get_churn_e0()


def test_actual_github_source_provider_remove_restore_is_atomically_indexed(
    churn_receipt: dict,
) -> None:
    assert churn_receipt["original_github_get_routes"] == 651
    assert churn_receipt["original_github_source_paths"] == 823
    assert churn_receipt["mixed_publisher_route_counts"] == [654, 3, 654]
    assert churn_receipt["stale_index_rejections"] == 2
    assert churn_receipt["distinct_source_versions"] == 3
    assert churn_receipt["distinct_index_snapshots"] == 3
    assert churn_receipt["journal_matches_full_rebuild"] is True
    assert churn_receipt["original_source_manifest_matches"] is True
    assert churn_receipt["untrusted_semantic_postings"] == 0
    assert churn_receipt["unauthorized_dependency_edges"] == 0
    assert churn_receipt["provider_runtime_calls"] == 0
    assert churn_receipt["execution_authority"] is False
    assert churn_receipt["publisher_gold_verified"] is False
    assert churn_receipt["independent_e2_qualified"] is False


def test_provider_churn_rejects_noop_journal_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.research_official_github_get_e0 import audit_official_github_get_churn_e0

    monkeypatch.setattr(
        NativeSchemaGraphIndex, "refresh_from_inmemory_journal",
        classmethod(lambda cls, previous, registry: previous),
    )
    with pytest.raises(ValueError, match="stale|journal|snapshot"):
        audit_official_github_get_churn_e0()
