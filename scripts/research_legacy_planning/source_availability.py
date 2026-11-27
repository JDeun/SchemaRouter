"""Historical lexical snapshot acceleration; never imported by the installed product."""

from __future__ import annotations

from collections.abc import Callable

from schemarouter._source_availability import _SourceAvailability
from schemarouter.models import EndpointSpec, ToolSpec


class _SnapshotFingerprints:
    """Hashes for exact detached catalog objects owned by one index snapshot."""

    def __init__(self, tools: tuple[ToolSpec, ...]) -> None:
        # Keep the objects alive: an unrelated fresh source must never reuse
        # a cached fingerprint merely because Python recycled an object ID.
        self._entries = {id(tool): (tool, tool.fingerprint) for tool in tools}

    def get(self, tool: ToolSpec) -> str | None:
        entry = self._entries.get(id(tool))
        return entry[1] if entry is not None and entry[0] is tool else None



class _LegacySourceAvailability(_SourceAvailability):
    """Research-only cache for exact objects in the lexical candidate index."""

    def __init__(
        self, predicate: Callable[[ToolSpec, EndpointSpec], bool] | None = None,
    ) -> None:
        super().__init__(predicate)
        self.snapshot: _SnapshotFingerprints | None = None

    def fingerprint(self, tool: ToolSpec) -> str:
        snapshot = self.snapshot
        cached = snapshot.get(tool) if snapshot is not None else None
        return cached if cached is not None else tool.fingerprint
