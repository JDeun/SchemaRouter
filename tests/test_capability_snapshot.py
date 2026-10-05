import hashlib
import json
from datetime import datetime, timezone

import pytest

from schemarouter.capability_contracts import (
    CapabilityContract,
    CapabilityFieldContract,
    CompatibilityContext,
    SemanticEquivalence,
)
from schemarouter.capability_snapshot import (
    CAPABILITY_SNAPSHOT_DOCUMENT_VERSION,
    LEGACY_CAPABILITY_SNAPSHOT_DOCUMENT_VERSION,
    CapabilitySourceRevision,
    build_capability_snapshot,
    build_capability_snapshot_document,
    compare_capability_snapshots,
    load_capability_snapshot,
    migrate_capability_snapshot,
    require_snapshot,
    serialize_capability_snapshot,
    validate_capability_snapshot,
)


def test_snapshot_digest_is_stable_across_order_and_build_time() -> None:
    a = CapabilityContract(capability_id="a")
    b = CapabilityContract(capability_id="b")
    source = CapabilitySourceRevision(
        provider="materials",
        access_method="rest",
        schema_revision="v1",
        schema_fingerprint="abc",
    )

    first = build_capability_snapshot(
        [a, b],
        sources=[source],
        builder_version="1",
        built_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    second = build_capability_snapshot(
        [b, a],
        sources=[source],
        builder_version="1",
        built_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )

    assert first.snapshot_id == second.snapshot_id


def test_snapshot_identity_and_graph_include_compatibility_context() -> None:
    producer = CapabilityContract(
        capability_id="producer",
        produces=[
            CapabilityFieldContract(
                semantic_id="material.identifier",
                json_schema={"type": "string"},
            )
        ],
    )
    consumer = CapabilityContract(
        capability_id="consumer",
        requires=[
            CapabilityFieldContract(
                semantic_id="resource.material_id",
                json_schema={"type": "string"},
            )
        ],
    )
    context = CompatibilityContext(
        semantic_equivalences=[
            SemanticEquivalence(
                canonical_id="resource.material_id",
                aliases={"material.identifier"},
            )
        ]
    )

    plain = build_capability_snapshot([producer, consumer])
    contextual = build_capability_snapshot(
        [producer, consumer],
        context=context,
    )

    assert contextual.snapshot_id != plain.snapshot_id
    assert plain.build_graph().edges == []
    assert contextual.build_graph().successors("producer") == ("consumer",)

    loaded = load_capability_snapshot(serialize_capability_snapshot(contextual))
    assert loaded == contextual
    assert loaded.build_graph() == contextual.build_graph()


def test_contract_drift_creates_successor_snapshot() -> None:
    old = build_capability_snapshot([
        CapabilityContract(capability_id="energy"),
    ])
    new = build_capability_snapshot([
        CapabilityContract(
            capability_id="energy",
            produces=[CapabilityFieldContract(semantic_id="energy")],
        ),
    ])

    diff = compare_capability_snapshots(old, new)

    assert diff.comparison == "successor"
    assert diff.changed_capability_ids == ("energy",)


def test_pinned_snapshot_fails_closed_on_mismatch() -> None:
    snapshot = build_capability_snapshot([CapabilityContract(capability_id="a")])

    assert require_snapshot(snapshot.snapshot_id, snapshot) is snapshot
    with pytest.raises(ValueError, match="does not match"):
        require_snapshot("another-snapshot", snapshot)


def test_runtime_health_is_not_snapshot_state() -> None:
    snapshot = build_capability_snapshot([CapabilityContract(capability_id="a")])

    assert "health" not in type(snapshot).model_fields
    assert snapshot.build_graph().capability_ids == ("a",)


def test_versioned_snapshot_document_round_trip() -> None:
    snapshot = build_capability_snapshot(
        [CapabilityContract(capability_id="a")],
        sources=[
            CapabilitySourceRevision(
                provider="materials",
                access_method="rest",
                schema_fingerprint="schema-1",
            )
        ],
    )
    document = build_capability_snapshot_document(snapshot)

    loaded = load_capability_snapshot(serialize_capability_snapshot(document))

    assert document.format_version == CAPABILITY_SNAPSHOT_DOCUMENT_VERSION
    assert loaded == snapshot


def test_version_1_0_snapshot_document_migrates_without_changing_context_free_identity() -> None:
    snapshot = build_capability_snapshot(
        [CapabilityContract(capability_id="a")],
        builder_version="legacy-builder",
    )
    snapshot_raw = snapshot.model_dump(mode="json")
    snapshot_raw.pop("compatibility_context", None)
    payload = {
        "format_version": "1.0",
        "snapshot": snapshot_raw,
    }
    digest = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()
    legacy = json.dumps(
        {
            "document_digest": digest,
            **payload,
        },
        sort_keys=True,
    )

    migrated = migrate_capability_snapshot(legacy)

    assert migrated.migration.from_format == "1.0"
    assert migrated.migration.to_format == CAPABILITY_SNAPSHOT_DOCUMENT_VERSION
    assert migrated.migration.migrated is True
    assert migrated.document.snapshot.snapshot_id == snapshot.snapshot_id
    assert migrated.document.snapshot.compatibility_context is None


def test_raw_legacy_snapshot_migrates_to_versioned_document() -> None:
    snapshot = build_capability_snapshot(
        [CapabilityContract(capability_id="a")],
        builder_version="legacy-builder",
    )
    legacy = json.dumps(
        snapshot.model_dump(mode="json"),
        sort_keys=True,
    )

    first = migrate_capability_snapshot(legacy)
    second = migrate_capability_snapshot(legacy)

    assert first == second
    assert first.migration.from_format == LEGACY_CAPABILITY_SNAPSHOT_DOCUMENT_VERSION
    assert first.migration.to_format == CAPABILITY_SNAPSHOT_DOCUMENT_VERSION
    assert first.migration.migrated is True
    assert first.document.snapshot == snapshot

    idempotent = migrate_capability_snapshot(
        serialize_capability_snapshot(first.document)
    )
    assert idempotent.document == first.document
    assert idempotent.migration.migrated is False


def test_tampered_raw_legacy_snapshot_fails_before_wrapping() -> None:
    snapshot = build_capability_snapshot(
        [CapabilityContract(capability_id="a")]
    )
    raw = snapshot.model_dump(mode="json")
    raw["snapshot_id"] = "tampered"

    with pytest.raises(ValueError, match="snapshot digest mismatch"):
        migrate_capability_snapshot(json.dumps(raw))


def test_tampered_versioned_snapshot_document_fails_digest_validation() -> None:
    snapshot = build_capability_snapshot(
        [CapabilityContract(capability_id="a")]
    )
    raw = json.loads(serialize_capability_snapshot(snapshot))
    raw["snapshot"]["builder_version"] = "tampered"

    with pytest.raises(ValueError, match="snapshot digest mismatch|document digest mismatch"):
        migrate_capability_snapshot(json.dumps(raw))


def test_unknown_snapshot_document_version_fails_closed() -> None:
    snapshot = build_capability_snapshot(
        [CapabilityContract(capability_id="a")]
    )
    raw = json.loads(serialize_capability_snapshot(snapshot))
    raw["format_version"] = "9.0"

    with pytest.raises(ValueError, match="unsupported"):
        migrate_capability_snapshot(json.dumps(raw))


def test_duplicate_snapshot_sources_fail_semantic_validation() -> None:
    source = CapabilitySourceRevision(
        provider="materials",
        access_method="rest",
        schema_fingerprint="one",
    )
    snapshot = build_capability_snapshot(
        [CapabilityContract(capability_id="a")],
        sources=[
            source,
            source.model_copy(update={"schema_fingerprint": "two"}),
        ],
    )

    with pytest.raises(ValueError, match="duplicate source"):
        validate_capability_snapshot(snapshot)
