from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal

from pydantic import Field

from .capability_contracts import CapabilityContract
from .capability_graph import CapabilityDependencyGraph, build_capability_dependency_graph
from .models import StrictModel

SnapshotComparison = Literal["identical", "successor"]
CAPABILITY_SNAPSHOT_DOCUMENT_VERSION = "1.0"
LEGACY_CAPABILITY_SNAPSHOT_DOCUMENT_VERSION = "legacy-unversioned"


class CapabilitySourceRevision(StrictModel):
    provider: str
    access_method: str | None = None
    schema_revision: str | None = None
    schema_fingerprint: str


class CapabilityGraphSnapshot(StrictModel):
    snapshot_id: str
    contracts: tuple[CapabilityContract, ...]
    sources: tuple[CapabilitySourceRevision, ...] = ()
    builder_version: str | None = None
    built_at: datetime | None = None

    def build_graph(self) -> CapabilityDependencyGraph:
        return build_capability_dependency_graph(list(self.contracts))


class CapabilitySnapshotDocument(StrictModel):
    format_version: str = CAPABILITY_SNAPSHOT_DOCUMENT_VERSION
    document_digest: str
    snapshot: CapabilityGraphSnapshot


class CapabilitySnapshotMigrationRecord(StrictModel):
    from_format: str
    to_format: str
    source_digest: str
    result_digest: str
    migrated: bool


class CapabilitySnapshotMigrationResult(StrictModel):
    document: CapabilitySnapshotDocument
    migration: CapabilitySnapshotMigrationRecord


class CapabilitySnapshotDiff(StrictModel):
    comparison: SnapshotComparison
    old_snapshot_id: str
    new_snapshot_id: str
    added_capability_ids: tuple[str, ...] = ()
    removed_capability_ids: tuple[str, ...] = ()
    changed_capability_ids: tuple[str, ...] = ()


def _snapshot_payload(
    contracts: list[CapabilityContract],
    sources: list[CapabilitySourceRevision],
    builder_version: str | None,
) -> dict[str, object]:
    return {
        "contracts": [
            item.model_dump(mode="json")
            for item in sorted(contracts, key=lambda item: item.capability_id)
        ],
        "sources": [
            item.model_dump(mode="json")
            for item in sorted(
                sources,
                key=lambda item: (
                    item.provider,
                    item.access_method or "",
                    item.schema_fingerprint,
                ),
            )
        ],
        "builder_version": builder_version,
    }


def _digest_payload(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()


def build_capability_snapshot(
    contracts: list[CapabilityContract],
    *,
    sources: list[CapabilitySourceRevision] | None = None,
    builder_version: str | None = None,
    built_at: datetime | None = None,
) -> CapabilityGraphSnapshot:
    """Create an immutable, reproducible graph snapshot.

    Runtime health is intentionally absent from the digest and snapshot model.
    """

    source_items = list(sources or [])
    payload = _snapshot_payload(contracts, source_items, builder_version)
    snapshot_id = _digest_payload(payload)
    return CapabilityGraphSnapshot(
        snapshot_id=snapshot_id,
        contracts=tuple(sorted(contracts, key=lambda item: item.capability_id)),
        sources=tuple(sorted(
            source_items,
            key=lambda item: (
                item.provider,
                item.access_method or "",
                item.schema_fingerprint,
            ),
        )),
        builder_version=builder_version,
        built_at=built_at,
    )


def validate_capability_snapshot(
    snapshot: CapabilityGraphSnapshot,
) -> CapabilityGraphSnapshot:
    capability_ids = [item.capability_id for item in snapshot.contracts]
    if len(capability_ids) != len(set(capability_ids)):
        raise ValueError("capability snapshot contains duplicate capability IDs")

    source_ids = [
        (item.provider, item.access_method or "")
        for item in snapshot.sources
    ]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("capability snapshot contains duplicate source identities")

    rebuilt = build_capability_snapshot(
        list(snapshot.contracts),
        sources=list(snapshot.sources),
        builder_version=snapshot.builder_version,
        built_at=snapshot.built_at,
    )
    if rebuilt.snapshot_id != snapshot.snapshot_id:
        raise ValueError("capability snapshot digest mismatch")
    return snapshot


def build_capability_snapshot_document(
    snapshot: CapabilityGraphSnapshot,
) -> CapabilitySnapshotDocument:
    validate_capability_snapshot(snapshot)
    payload = {
        "format_version": CAPABILITY_SNAPSHOT_DOCUMENT_VERSION,
        "snapshot": snapshot.model_dump(mode="json"),
    }
    return CapabilitySnapshotDocument(
        format_version=CAPABILITY_SNAPSHOT_DOCUMENT_VERSION,
        document_digest=_digest_payload(payload),
        snapshot=snapshot.model_copy(deep=True),
    )


def serialize_capability_snapshot(
    snapshot: CapabilityGraphSnapshot | CapabilitySnapshotDocument,
) -> str:
    document = (
        snapshot
        if isinstance(snapshot, CapabilitySnapshotDocument)
        else build_capability_snapshot_document(snapshot)
    )
    return json.dumps(
        document.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _validate_snapshot_document(
    document: CapabilitySnapshotDocument,
) -> CapabilitySnapshotDocument:
    if document.format_version != CAPABILITY_SNAPSHOT_DOCUMENT_VERSION:
        raise ValueError(
            f"unsupported capability snapshot format: {document.format_version}"
        )
    validate_capability_snapshot(document.snapshot)
    expected = _digest_payload(
        {
            "format_version": document.format_version,
            "snapshot": document.snapshot.model_dump(mode="json"),
        }
    )
    if expected != document.document_digest:
        raise ValueError("capability snapshot document digest mismatch")
    return document


def migrate_capability_snapshot(
    document: str,
) -> CapabilitySnapshotMigrationResult:
    raw = json.loads(document)
    if not isinstance(raw, dict):
        raise ValueError("capability snapshot document must be a JSON object")

    if "format_version" in raw:
        version = raw.get("format_version")
        if version != CAPABILITY_SNAPSHOT_DOCUMENT_VERSION:
            raise ValueError(f"unsupported capability snapshot format: {version}")
        current = CapabilitySnapshotDocument.model_validate(raw)
        _validate_snapshot_document(current)
        return CapabilitySnapshotMigrationResult(
            document=current,
            migration=CapabilitySnapshotMigrationRecord(
                from_format=current.format_version,
                to_format=current.format_version,
                source_digest=current.document_digest,
                result_digest=current.document_digest,
                migrated=False,
            ),
        )

    # Before the document envelope existed, callers could persist the public
    # CapabilityGraphSnapshot model directly. Treat that exact JSON shape as the
    # supported legacy representation and validate its snapshot_id before wrapping it.
    legacy = CapabilityGraphSnapshot.model_validate(raw)
    validate_capability_snapshot(legacy)
    source_digest = _digest_payload(raw)
    current = build_capability_snapshot_document(legacy)
    return CapabilitySnapshotMigrationResult(
        document=current,
        migration=CapabilitySnapshotMigrationRecord(
            from_format=LEGACY_CAPABILITY_SNAPSHOT_DOCUMENT_VERSION,
            to_format=CAPABILITY_SNAPSHOT_DOCUMENT_VERSION,
            source_digest=source_digest,
            result_digest=current.document_digest,
            migrated=True,
        ),
    )


def load_capability_snapshot(document: str) -> CapabilityGraphSnapshot:
    return migrate_capability_snapshot(document).document.snapshot


def compare_capability_snapshots(
    old: CapabilityGraphSnapshot,
    new: CapabilityGraphSnapshot,
) -> CapabilitySnapshotDiff:
    old_by_id = {item.capability_id: item for item in old.contracts}
    new_by_id = {item.capability_id: item for item in new.contracts}
    common = old_by_id.keys() & new_by_id.keys()
    changed = tuple(sorted(
        capability_id
        for capability_id in common
        if old_by_id[capability_id] != new_by_id[capability_id]
    ))
    return CapabilitySnapshotDiff(
        comparison="identical" if old.snapshot_id == new.snapshot_id else "successor",
        old_snapshot_id=old.snapshot_id,
        new_snapshot_id=new.snapshot_id,
        added_capability_ids=tuple(sorted(new_by_id.keys() - old_by_id.keys())),
        removed_capability_ids=tuple(sorted(old_by_id.keys() - new_by_id.keys())),
        changed_capability_ids=changed,
    )


def require_snapshot(
    requested_snapshot_id: str,
    snapshot: CapabilityGraphSnapshot,
) -> CapabilityGraphSnapshot:
    """Fail closed when a retrieval request is pinned to another graph revision."""

    if requested_snapshot_id != snapshot.snapshot_id:
        raise ValueError(
            "requested capability snapshot does not match the loaded graph snapshot"
        )
    return snapshot
