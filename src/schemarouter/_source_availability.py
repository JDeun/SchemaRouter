"""Shared source availability, independent of either ranking implementation."""

from __future__ import annotations

from collections.abc import Callable

from .models import EndpointSpec, ToolSpec


class _SnapshotFingerprints:
    """Hashes for exact detached catalog objects owned by one index snapshot."""

    def __init__(self, tools: tuple[ToolSpec, ...]) -> None:
        # Keep the objects alive: an unrelated fresh source must never reuse
        # a cached fingerprint merely because Python recycled an object ID.
        self._entries = {id(tool): (tool, tool.fingerprint) for tool in tools}

    def get(self, tool: ToolSpec) -> str | None:
        entry = self._entries.get(id(tool))
        return entry[1] if entry is not None and entry[0] is tool else None


class _SourceAvailability:
    """One host-owned predicate and the optional legacy snapshot acceleration.

    Fresh native registry reads never become members of the lexical snapshot.
    A cache miss hashes the supplied authoritative source; the executor still
    decides current cooldown using the exact contract fingerprint.
    """

    def __init__(
        self, predicate: Callable[[ToolSpec, EndpointSpec], bool] | None = None,
    ) -> None:
        self.predicate = predicate
        self.snapshot: _SnapshotFingerprints | None = None

    def fingerprint(self, tool: ToolSpec) -> str:
        snapshot = self.snapshot
        cached = snapshot.get(tool) if snapshot is not None else None
        return cached if cached is not None else tool.fingerprint
