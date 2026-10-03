from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import Field

from .capability_contracts import CapabilityContract
from .capability_graph import CapabilityDependencyGraph
from .models import StrictModel

CapabilityDriftCompatibility = Literal["identical", "compatible", "breaking"]


class CapabilityDriftChange(StrictModel):
    capability_id: str
    kind: Literal["added", "removed", "contract_changed"]
    compatibility: CapabilityDriftCompatibility
    old_fingerprint: str | None = None
    new_fingerprint: str | None = None


class CapabilityGraphDrift(StrictModel):
    compatibility: CapabilityDriftCompatibility
    changes: list[CapabilityDriftChange] = Field(default_factory=list)
    invalidated_capability_ids: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.changes)


def capability_contract_fingerprint(contract: CapabilityContract) -> str:
    """Return the deterministic Pydantic fingerprint for a capability contract."""

    payload = json.dumps(
        contract.model_dump(mode="json", exclude_none=False, by_alias=True),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def compare_capability_graph_snapshot(
    graph: CapabilityDependencyGraph,
    old: list[CapabilityContract],
    new: list[CapabilityContract],
) -> CapabilityGraphDrift:
    """Identify contract drift and the graph nodes whose cached edges are stale.

    This is diagnostic/invalidation metadata only. It never migrates execution or
    authorizes a capability that the host did not already expose.
    """

    old_by_id = {item.capability_id: item for item in old}
    new_by_id = {item.capability_id: item for item in new}
    if len(old_by_id) != len(old) or len(new_by_id) != len(new):
        raise ValueError("capability_id values must be unique")

    changes: list[CapabilityDriftChange] = []
    directly_invalidated: set[str] = set()

    for capability_id in sorted(old_by_id.keys() - new_by_id.keys()):
        changes.append(CapabilityDriftChange(
            capability_id=capability_id,
            kind="removed",
            compatibility="breaking",
            old_fingerprint=capability_contract_fingerprint(old_by_id[capability_id]),
        ))
        directly_invalidated.add(capability_id)

    for capability_id in sorted(new_by_id.keys() - old_by_id.keys()):
        changes.append(CapabilityDriftChange(
            capability_id=capability_id,
            kind="added",
            compatibility="compatible",
            new_fingerprint=capability_contract_fingerprint(new_by_id[capability_id]),
        ))
        directly_invalidated.add(capability_id)

    for capability_id in sorted(old_by_id.keys() & new_by_id.keys()):
        old_fingerprint = capability_contract_fingerprint(old_by_id[capability_id])
        new_fingerprint = capability_contract_fingerprint(new_by_id[capability_id])
        if old_fingerprint == new_fingerprint:
            continue
        changes.append(CapabilityDriftChange(
            capability_id=capability_id,
            kind="contract_changed",
            compatibility="breaking",
            old_fingerprint=old_fingerprint,
            new_fingerprint=new_fingerprint,
        ))
        directly_invalidated.add(capability_id)

    invalidated = set(directly_invalidated)
    # Existing edges touching a changed contract must be recomputed. One hop is
    # sufficient because only incident compatibility decisions depend on it.
    for capability_id in tuple(directly_invalidated):
        invalidated.update(graph.predecessors(capability_id))
        invalidated.update(graph.successors(capability_id))

    compatibility: CapabilityDriftCompatibility
    if any(change.compatibility == "breaking" for change in changes):
        compatibility = "breaking"
    elif changes:
        compatibility = "compatible"
    else:
        compatibility = "identical"

    return CapabilityGraphDrift(
        compatibility=compatibility,
        changes=changes,
        invalidated_capability_ids=tuple(sorted(invalidated)),
    )
