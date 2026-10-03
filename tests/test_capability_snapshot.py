from datetime import datetime, timezone

import pytest

from schemarouter.capability_contracts import CapabilityContract, CapabilityFieldContract
from schemarouter.capability_snapshot import (
    CapabilitySourceRevision,
    build_capability_snapshot,
    compare_capability_snapshots,
    require_snapshot,
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
