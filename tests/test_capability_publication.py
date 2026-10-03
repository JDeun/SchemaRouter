from __future__ import annotations

import threading
from datetime import datetime, timezone

import pytest

import schemarouter.capability_publication as publication_module
from schemarouter import (
    CapabilityContract,
    CapabilityFieldContract,
    CapabilityPublicationConflictError,
    CapabilitySnapshotStore,
    CapabilitySourceRevision,
    build_capability_dependency_graph,
)


def _field(semantic_id: str) -> CapabilityFieldContract:
    return CapabilityFieldContract(
        semantic_id=semantic_id,
        json_schema={"type": "string"},
    )


def _contracts(version: int = 1) -> list[CapabilityContract]:
    producer_fields = [_field("resource.id")]
    if version >= 2:
        producer_fields.append(_field("resource.extra"))
    return [
        CapabilityContract(
            capability_id="producer",
            produces=producer_fields,
        ),
        CapabilityContract(
            capability_id="consumer",
            requires=[_field("resource.id")],
        ),
    ]


def _source(fingerprint: str = "source-v1") -> CapabilitySourceRevision:
    return CapabilitySourceRevision(
        provider="materials",
        access_method="rest",
        schema_revision=fingerprint,
        schema_fingerprint=fingerprint,
    )


def test_incremental_publication_matches_clean_full_rebuild() -> None:
    store = CapabilitySnapshotStore.from_contracts(
        _contracts(1),
        sources=[_source()],
        builder_version="1",
    )
    before = store.read()

    published = store.compare_and_publish(
        _contracts(2),
        sources=[_source("source-v2")],
        expected_revision=before.publication_revision,
        expected_snapshot_id=before.snapshot.snapshot_id,
    )

    assert published.rebuild_mode == "incremental"
    assert published.publication_revision == 2
    assert published.provenance.predecessor_snapshot_id == before.snapshot.snapshot_id
    assert published.provenance.successor_snapshot_id == published.snapshot.snapshot_id
    assert published.graph == build_capability_dependency_graph(_contracts(2))
    assert store.read() == published


def test_source_only_successor_reuses_contract_graph() -> None:
    store = CapabilitySnapshotStore.from_contracts(
        _contracts(),
        sources=[_source("source-v1")],
    )
    before = store.read()

    published = store.compare_and_publish(
        _contracts(),
        sources=[_source("source-v2")],
        expected_revision=1,
    )

    assert published.rebuild_mode == "source_only"
    assert published.graph == before.graph
    assert published.snapshot.snapshot_id != before.snapshot.snapshot_id
    assert published.drift is not None
    assert published.drift.compatibility == "identical"


def test_identical_health_independent_update_does_not_change_snapshot_identity() -> None:
    store = CapabilitySnapshotStore.from_contracts(
        _contracts(),
        sources=[_source()],
        built_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    before = store.read()

    # Runtime health is intentionally not an input. A later build timestamp alone
    # cannot alter immutable contract snapshot identity or publication revision.
    returned = store.compare_and_publish(
        _contracts(),
        sources=[_source()],
        built_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        expected_revision=1,
    )

    assert returned.rebuild_mode == "unchanged"
    assert returned.snapshot.snapshot_id == before.snapshot.snapshot_id
    assert store.publication_revision == 1
    assert store.snapshot_id == before.snapshot.snapshot_id


def test_stale_compare_and_swap_fails_without_mutating_active_publication() -> None:
    store = CapabilitySnapshotStore.from_contracts(_contracts())
    before = store.read()

    with pytest.raises(CapabilityPublicationConflictError, match="revision changed"):
        store.compare_and_publish(
            _contracts(2),
            expected_revision=99,
        )

    assert store.read() == before

    with pytest.raises(CapabilityPublicationConflictError, match="snapshot changed"):
        store.compare_and_publish(
            _contracts(2),
            expected_snapshot_id="stale-snapshot",
        )

    assert store.read() == before


def test_failed_validation_keeps_predecessor_active() -> None:
    fail_successors = False

    def validator(publication) -> None:
        if fail_successors and publication.publication_revision > 1:
            raise ValueError("synthetic persistence/publication failure")

    store = CapabilitySnapshotStore.from_contracts(
        _contracts(),
        validator=validator,
    )
    before = store.read()
    fail_successors = True

    with pytest.raises(ValueError, match="synthetic"):
        store.compare_and_publish(_contracts(2))

    assert store.read() == before


def test_incremental_failure_falls_back_to_full_rebuild(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = CapabilitySnapshotStore.from_contracts(_contracts())

    def fail_incremental(*args, **kwargs):
        del args, kwargs
        raise ValueError("cannot prove incremental safety")

    monkeypatch.setattr(
        publication_module,
        "update_capability_dependency_graph",
        fail_incremental,
    )

    published = store.compare_and_publish(_contracts(2))

    assert published.rebuild_mode == "full"
    assert published.graph == build_capability_dependency_graph(_contracts(2))


def test_duplicate_source_identity_fails_closed_without_publication() -> None:
    store = CapabilitySnapshotStore.from_contracts(
        _contracts(),
        sources=[_source()],
    )
    before = store.read()

    with pytest.raises(ValueError, match="unique provider/access_method"):
        store.compare_and_publish(
            _contracts(2),
            sources=[_source("one"), _source("two")],
        )

    assert store.read() == before


def test_atomic_readers_never_observe_half_published_successor() -> None:
    entered_validator = threading.Event()
    release_validator = threading.Event()

    def validator(publication) -> None:
        if publication.publication_revision > 1:
            entered_validator.set()
            assert release_validator.wait(timeout=5)

    store = CapabilitySnapshotStore.from_contracts(
        _contracts(),
        validator=validator,
    )
    before = store.read()
    writer_error: list[BaseException] = []

    def writer() -> None:
        try:
            store.compare_and_publish(
                _contracts(2),
                expected_revision=before.publication_revision,
            )
        except BaseException as exc:  # pragma: no cover - asserted below.
            writer_error.append(exc)

    thread = threading.Thread(target=writer)
    thread.start()
    assert entered_validator.wait(timeout=5)

    # Publication is not assigned before validation completes. The private active
    # reference therefore remains the complete predecessor while the writer is blocked.
    assert store._publication.snapshot.snapshot_id == before.snapshot.snapshot_id

    release_validator.set()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert writer_error == []

    after = store.read()
    assert after.publication_revision == 2
    assert after.snapshot.snapshot_id != before.snapshot.snapshot_id
    assert after.graph == build_capability_dependency_graph(_contracts(2))


def test_force_full_rebuild_is_explicit_and_validated() -> None:
    store = CapabilitySnapshotStore.from_contracts(_contracts())

    published = store.compare_and_publish(
        _contracts(2),
        force_full_rebuild=True,
    )

    assert published.rebuild_mode == "full"
    assert published.graph == build_capability_dependency_graph(_contracts(2))
