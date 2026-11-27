"""Router-owned source availability and authoritative contract fingerprints."""

from __future__ import annotations

from collections.abc import Callable

from .models import EndpointSpec, ToolSpec


class _SourceAvailability:
    """Host-owned availability predicate; fingerprints always use the supplied source."""

    def __init__(
        self, predicate: Callable[[ToolSpec, EndpointSpec], bool] | None = None,
    ) -> None:
        self.predicate = predicate

    def fingerprint(self, tool: ToolSpec) -> str:
        return tool.fingerprint
