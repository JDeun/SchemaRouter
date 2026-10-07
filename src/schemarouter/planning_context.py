from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import EndpointSpec, PlanRequest, QueryIntent, ToolSpec


class CandidateIndexSnapshot(Protocol):
    """Read-only candidate-index surface carried by a registry snapshot."""

    version: int
    tools: tuple[ToolSpec, ...]

    def all_endpoint_pairs(self) -> tuple[tuple[ToolSpec, EndpointSpec], ...]: ...

    def endpoint_pairs(
        self,
        request: PlanRequest,
        intent: QueryIntent,
    ) -> tuple[tuple[ToolSpec, EndpointSpec], ...]: ...

    def tool_fingerprint(self, tool: ToolSpec) -> str | None: ...

    @property
    def declared_semantics(self) -> frozenset[str]: ...


@dataclass(frozen=True, slots=True)
class RegistrySnapshot:
    """One coherent immutable registry view used by a planning operation."""

    version: int
    tools: tuple[ToolSpec, ...]
    index: CandidateIndexSnapshot | None = None

    def all_endpoint_pairs(self) -> tuple[tuple[ToolSpec, EndpointSpec], ...]:
        if self.index is not None:
            return self.index.all_endpoint_pairs()
        return tuple(
            (tool, endpoint)
            for tool in self.tools
            for endpoint in tool.endpoints
        )

    def tool_fingerprint(self, tool: ToolSpec) -> str | None:
        if self.index is None:
            return None
        return self.index.tool_fingerprint(tool)


@dataclass(frozen=True, slots=True)
class SnapshotToolRegistry:
    """Read-only ToolRegistry-compatible view over one immutable planning snapshot."""

    snapshot: RegistrySnapshot

    @property
    def version(self) -> int:
        return self.snapshot.version

    def register(self, tool: ToolSpec, *, replace: bool = False) -> str:
        del tool, replace
        raise TypeError("registry snapshot is read-only")

    def get(self, key: str) -> ToolSpec:
        for tool in self.snapshot.tools:
            if tool.key == key:
                return tool.model_copy(deep=True)
        raise KeyError(key)

    def tools(self) -> tuple[ToolSpec, ...]:
        return tuple(tool.model_copy(deep=True) for tool in self.snapshot.tools)

    def keys(self) -> tuple[str, ...]:
        return tuple(tool.key for tool in self.snapshot.tools)

    def endpoint(self, tool_key: str, endpoint_name: str) -> EndpointSpec:
        return self.get(tool_key).endpoint(endpoint_name).model_copy(deep=True)


@dataclass(frozen=True, slots=True)
class PlanningContext:
    """Request, analyzed intent, and exact registry snapshot for one operation."""

    request: PlanRequest
    intent: QueryIntent
    registry: RegistrySnapshot
