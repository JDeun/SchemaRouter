from __future__ import annotations

from collections.abc import Iterable

from .errors import RegistrationError
from .models import EndpointSpec, ToolSpec


class InMemoryRegistry:
    """Versioned, collision-safe tool catalog."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._version = 0

    @property
    def version(self) -> int:
        return self._version

    def register(self, tool: ToolSpec, *, replace: bool = False) -> str:
        key = tool.key
        if key in self._tools and not replace:
            raise RegistrationError(f"tool {key!r} is already registered")
        self._tools[key] = tool
        self._version += 1
        return key

    def unregister(self, key: str) -> None:
        if key not in self._tools:
            raise KeyError(key)
        del self._tools[key]
        self._version += 1

    def get(self, key: str) -> ToolSpec:
        return self._tools[key]

    def tools(self) -> tuple[ToolSpec, ...]:
        return tuple(self._tools.values())

    def keys(self) -> tuple[str, ...]:
        return tuple(self._tools)

    def endpoint(self, tool_key: str, endpoint_name: str) -> EndpointSpec:
        return self.get(tool_key).endpoint(endpoint_name)

    def update_many(self, tools: Iterable[ToolSpec], *, replace: bool = False) -> None:
        staged = list(tools)
        staged_keys = [tool.key for tool in staged]
        if len(staged_keys) != len(set(staged_keys)):
            raise RegistrationError("duplicate tool keys in batch")
        if not replace:
            collisions = sorted(set(staged_keys) & set(self._tools))
            if collisions:
                raise RegistrationError(f"tools already registered: {', '.join(collisions)}")
        for tool in staged:
            self._tools[tool.key] = tool
        if staged:
            self._version += 1
