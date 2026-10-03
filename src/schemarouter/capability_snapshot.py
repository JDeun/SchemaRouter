from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal

from .capability_contracts import CapabilityContract
from .capability_graph import CapabilityDependencyGraph, build_capability_dependency_graph
from .models import StrictModel

SnapshotComparison = Literal["identical", "successor"]


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
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    snapshot_id = hashlib.sha256(encoded).hexdigest()
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
