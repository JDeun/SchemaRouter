from __future__ import annotations

import hashlib
import json

from pydantic import Field

from .capability_contracts import CapabilityContract
from .capability_graph import CapabilityDependencyGraph
from .models import StrictModel


class CapabilityGraphSnapshot(StrictModel):
    snapshot_id: str
    graph: CapabilityDependencyGraph
    contracts: tuple[CapabilityContract, ...]
    source_schema_fingerprints: dict[str, str] = Field(default_factory=dict)
    build_metadata: dict[str, str] = Field(default_factory=dict)


class CapabilitySnapshotComparison(StrictModel):
    identical: bool
    old_snapshot_id: str
    new_snapshot_id: str
    added_capability_ids: tuple[str, ...] = ()
    removed_capability_ids: tuple[str, ...] = ()
    changed_capability_ids: tuple[str, ...] = ()


def _canonical_digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def create_capability_graph_snapshot(
    graph: CapabilityDependencyGraph,
    contracts: list[CapabilityContract],
    *,
    source_schema_fingerprints: dict[str, str] | None = None,
    build_metadata: dict[str, str] | None = None,
) -> CapabilityGraphSnapshot:
    """Create immutable routing-contract state; live health is intentionally excluded."""

    ordered_contracts = tuple(sorted(contracts, key=lambda item: item.capability_id))
    payload = {
        "graph": graph.model_dump(mode="json"),
        "contracts": [item.model_dump(mode="json") for item in ordered_contracts],
        "source_schema_fingerprints": dict(source_schema_fingerprints or {}),
        "build_metadata": dict(build_metadata or {}),
    }
    return CapabilityGraphSnapshot(
        snapshot_id=_canonical_digest(payload),
        graph=graph.model_copy(deep=True),
        contracts=ordered_contracts,
        source_schema_fingerprints=dict(source_schema_fingerprints or {}),
        build_metadata=dict(build_metadata or {}),
    )


def require_capability_snapshot(
    snapshot: CapabilityGraphSnapshot,
    requested_snapshot_id: str,
) -> CapabilityGraphSnapshot:
    """Fail closed when a retrieval/runtime request is pinned to another snapshot."""

    if snapshot.snapshot_id != requested_snapshot_id:
        raise ValueError(
            f"capability snapshot mismatch: requested {requested_snapshot_id!r}, "
            f"loaded {snapshot.snapshot_id!r}"
        )
    return snapshot


def compare_capability_snapshots(
    old: CapabilityGraphSnapshot,
    new: CapabilityGraphSnapshot,
) -> CapabilitySnapshotComparison:
    old_contracts = {item.capability_id: item for item in old.contracts}
    new_contracts = {item.capability_id: item for item in new.contracts}
    common = old_contracts.keys() & new_contracts.keys()
    changed = tuple(sorted(
        capability_id
        for capability_id in common
        if old_contracts[capability_id] != new_contracts[capability_id]
    ))
    return CapabilitySnapshotComparison(
        identical=old.snapshot_id == new.snapshot_id,
        old_snapshot_id=old.snapshot_id,
        new_snapshot_id=new.snapshot_id,
        added_capability_ids=tuple(sorted(new_contracts.keys() - old_contracts.keys())),
        removed_capability_ids=tuple(sorted(old_contracts.keys() - new_contracts.keys())),
        changed_capability_ids=changed,
    )
