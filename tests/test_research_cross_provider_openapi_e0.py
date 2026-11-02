"""Genuine cross-provider source integrity, scope, and no-grant regression."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.research_cross_provider_openapi_e0 import (
    EVIDENCE_TIER,
    FORECAST_PATH,
    PIRATE_COMMIT,
    PIRATE_LICENSE_BLOB,
    PIRATE_LICENSE_BYTES,
    PIRATE_LICENSE_SHA256,
    PIRATE_SPEC_BLOB,
    PIRATE_SPEC_BYTES,
    PIRATE_SPEC_SHA256,
    audit_cross_provider_source,
    compile_official_pirate_weather_source,
)
from scripts.research_official_openapi_snapshot_e0 import FIXTURE_DIR


def _bytes() -> tuple[bytes, bytes]:
    base = FIXTURE_DIR / f"pirate-weather-{PIRATE_COMMIT[:8]}"
    return (
        Path(str(base) + "-openapi.yaml").read_bytes(),
        Path(str(base) + "-LICENSE.txt").read_bytes(),
    )


def test_real_pirate_source_and_apache_notice_sha256_and_git_blob() -> None:
    source, notice = _bytes()
    for raw, size, digest, blob in (
        (source, PIRATE_SPEC_BYTES, PIRATE_SPEC_SHA256, PIRATE_SPEC_BLOB),
        (notice, PIRATE_LICENSE_BYTES, PIRATE_LICENSE_SHA256, PIRATE_LICENSE_BLOB),
    ):
        assert len(raw) == size
        assert hashlib.sha256(raw).hexdigest() == digest
        git_payload = b"blob " + str(len(raw)).encode("ascii") + bytes((0,)) + raw
        assert hashlib.sha1(git_payload).hexdigest() == blob


def test_real_native_source_preserves_secret_required_inputs() -> None:
    source, notice = _bytes()
    tool = compile_official_pirate_weather_source(source, notice)
    assert tool.license is None
    assert tool.source_type is None
    ep = tool.endpoints[0]
    assert ep.name == "Weather"
    assert ep.path == FORECAST_PATH
    assert ep.read_only is True
    assert ep.destructive is not True
    assert {"api_key", "lat_and_long_or_time"}.issubset({
        p.name for p in ep.parameters if p.required
    })
    assert all(not f.semantic_id for f in ep.output_fields)


def test_real_two_provider_catalog_never_infers_cross_source_permission() -> None:
    report = audit_cross_provider_source()
    assert report["evidence_tier"] == EVIDENCE_TIER
    assert report["registered_native_routes"] == 3
    assert report["unauthorized_cross_provider_edges"] == 0
    assert report["provider_runtime_calls"] == 0
    for field in (
        "independent_e2_qualified",
        "publisher_gold_verified",
        "model_quality_verified",
        "execution_authority",
        "default_routing_changed",
    ):
        assert report[field] is False
    assert len(report["provider_commits"]) == 2
    assert len(report["provider_git_blobs"]) == 2


@pytest.mark.parametrize("which", ("openapi", "license"))
@pytest.mark.parametrize("mutation", ("bitflip", "append", "truncate"))
def test_publisher_source_or_license_mutation_is_rejected(which: str, mutation: str) -> None:
    source, notice = _bytes()
    altered = bytearray(source if which == "openapi" else notice)
    if mutation == "bitflip":
        altered[len(altered) // 2] ^= 1
    elif mutation == "append":
        altered.append(32)
    else:
        altered.pop()
    with pytest.raises(ValueError, match="snapshot"):
        compile_official_pirate_weather_source(
            bytes(altered) if which == "openapi" else source,
            bytes(altered) if which == "license" else notice,
        )


def test_cross_provider_audit_rejects_local_fixture_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.research_cross_provider_openapi_e0 as mod

    # Both legitimate providers must be present so this tests a poisoned
    # Pirate Weather source, rather than trivially missing Ollama files.
    source, notice = _bytes()
    ollama = FIXTURE_DIR / f"ollama-{mod.OLLAMA_COMMIT[:8]}"
    target_ollama = tmp_path / f"ollama-{mod.OLLAMA_COMMIT[:8]}"
    for suffix in ("-openapi.yaml", "-LICENSE.txt"):
        Path(str(target_ollama) + suffix).write_bytes(
            Path(str(ollama) + suffix).read_bytes()
        )
    pirate = tmp_path / f"pirate-weather-{PIRATE_COMMIT[:8]}"
    Path(str(pirate) + "-openapi.yaml").write_bytes(source + b" ")
    Path(str(pirate) + "-LICENSE.txt").write_bytes(notice)
    monkeypatch.setattr(mod, "FIXTURE_DIR", tmp_path)
    with pytest.raises(ValueError, match="snapshot"):
        audit_cross_provider_source()


def test_pinned_real_provider_removal_and_restore_refreshes_canonical_index() -> None:
    from scripts import research_cross_provider_openapi_e0 as mod

    receipt = mod.audit_cross_provider_churn_e0()
    assert receipt["stage_route_counts"] == [3, 2, 3]
    assert receipt["distinct_registry_versions"] == 3
    assert receipt["distinct_index_snapshots"] == 3
    assert receipt["stale_index_rejections"] == 2
    assert receipt["journal_rebuild_matches"] is True
    assert receipt["untrusted_semantic_postings"] == 0
    assert receipt["unauthorized_cross_provider_edges"] == 0
    assert receipt["provider_runtime_calls"] == 0
    assert receipt["execution_authority"] is False
    assert receipt["independent_e2_qualified"] is False


def test_real_provider_churn_rejects_stale_journal_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from schemarouter.native_graph_index import NativeSchemaGraphIndex
    from scripts import research_cross_provider_openapi_e0 as mod

    monkeypatch.setattr(
        NativeSchemaGraphIndex,
        "refresh_from_inmemory_journal",
        classmethod(lambda cls, previous, registry: previous),
    )
    with pytest.raises(ValueError, match="journal|refresh|snapshot"):
        mod.audit_cross_provider_churn_e0()
