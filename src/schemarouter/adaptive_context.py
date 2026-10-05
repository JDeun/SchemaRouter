from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import json
from typing import Iterable


def _route_id(tool: str, endpoint: str) -> str:
    tool = tool.strip()
    endpoint = endpoint.strip()
    if not tool or not endpoint:
        raise ValueError("tool and endpoint must be non-empty")
    return f"{tool}.{endpoint}"


@dataclass
class SuccessfulCapabilityHistory:
    """Local successful-execution counts used as an optional routing prior.

    This object records only explicit successful executions. It intentionally
    has no knowledge of authorization or health; callers must apply those
    hard constraints before consulting the prior.
    """

    _counts: Counter[str] = field(default_factory=Counter)

    def record_success(self, tool: str, endpoint: str) -> None:
        self._counts[_route_id(tool, endpoint)] += 1

    def count(self, tool: str, endpoint: str) -> int:
        return self._counts[_route_id(tool, endpoint)]

    def snapshot(self) -> dict[str, int]:
        return dict(sorted(self._counts.items()))

    def reset(self) -> None:
        self._counts.clear()

    def dumps(self) -> str:
        return json.dumps(self.snapshot(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def loads(cls, payload: str) -> "SuccessfulCapabilityHistory":
        raw = json.loads(payload)
        if not isinstance(raw, dict):
            raise ValueError("successful capability history must be a JSON object")
        history = cls()
        for route, value in raw.items():
            if not isinstance(route, str) or "." not in route:
                raise ValueError("history route ids must be '<tool>.<endpoint>' strings")
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("history counts must be non-negative integers")
            if value:
                history._counts[route] = value
        return history


@dataclass(frozen=True)
class SchemaExposureDecision:
    route_id: str
    inject: bool
    reason: str


@dataclass
class SessionSchemaExposure:
    """Session-local record of capability schemas currently known to context.

    A host integration explicitly reports compaction. SchemaRouter does not
    attempt to infer compaction from conversation text.
    """

    _exposed: set[str] = field(default_factory=set)
    compaction_epoch: int = 0

    def decision(self, tool: str, endpoint: str) -> SchemaExposureDecision:
        route = _route_id(tool, endpoint)
        if route in self._exposed:
            return SchemaExposureDecision(route, False, "already_exposed")
        return SchemaExposureDecision(route, True, "not_exposed")

    def mark_exposed(self, tool: str, endpoint: str) -> None:
        self._exposed.add(_route_id(tool, endpoint))

    def mark_many_exposed(self, routes: Iterable[tuple[str, str]]) -> None:
        for tool, endpoint in routes:
            self.mark_exposed(tool, endpoint)

    def compacted(self) -> None:
        self._exposed.clear()
        self.compaction_epoch += 1

    def reset(self) -> None:
        self._exposed.clear()
        self.compaction_epoch = 0

    def snapshot(self) -> dict[str, object]:
        return {
            "compaction_epoch": self.compaction_epoch,
            "exposed_routes": sorted(self._exposed),
        }

    def dumps(self) -> str:
        return json.dumps(self.snapshot(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def loads(cls, payload: str) -> "SessionSchemaExposure":
        raw = json.loads(payload)
        if not isinstance(raw, dict):
            raise ValueError("session schema exposure must be a JSON object")
        epoch = raw.get("compaction_epoch", 0)
        routes = raw.get("exposed_routes", [])
        if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
            raise ValueError("compaction_epoch must be a non-negative integer")
        if not isinstance(routes, list) or not all(isinstance(x, str) and "." in x for x in routes):
            raise ValueError("exposed_routes must be route-id strings")
        state = cls(compaction_epoch=epoch)
        state._exposed.update(routes)
        return state
