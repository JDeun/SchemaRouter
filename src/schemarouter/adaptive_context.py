from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

from .canonical_json import canonical_json_sha256, canonical_json_text


def _route_id(tool: str, endpoint: str) -> str:
    tool = tool.strip()
    endpoint = endpoint.strip()
    if not tool or not endpoint:
        raise ValueError("tool and endpoint must be non-empty")
    return f"{tool}.{endpoint}"


def _capability_key(
    tool: str,
    endpoint: str,
    endpoint_fingerprint: str | None = None,
) -> str:
    route = _route_id(tool, endpoint)
    if endpoint_fingerprint is None:
        return route
    fingerprint = endpoint_fingerprint.strip()
    if not fingerprint:
        raise ValueError("endpoint_fingerprint must be non-empty when supplied")
    return f"{route}@{fingerprint}"


_SUCCESS_COUNT_CAP = 1


def _drop_superseded_fingerprint_keys(
    keys: set[str] | Counter[str],
    route: str,
    *,
    keep: str | None = None,
) -> None:
    prefix = f"{route}@"
    stale = [key for key in keys if key.startswith(prefix) and key != keep]
    for key in stale:
        if isinstance(keys, Counter):
            del keys[key]
        else:
            keys.discard(key)


def _legacy_compacted_fingerprint_keys(keys: Iterable[str]) -> set[str]:
    """Deterministically compact old checkpoints that retained many fingerprints per route."""

    retained: set[str] = set()
    fingerprinted: dict[str, str] = {}
    for key in sorted(keys):
        if "@" not in key:
            retained.add(key)
            continue
        route, _fingerprint = key.split("@", 1)
        # Legacy payloads did not persist generation order. Keep one deterministic fingerprint.
        # If it is not the current fingerprint, callers conservatively get a miss/re-injection.
        fingerprinted[route] = key
    retained.update(fingerprinted.values())
    return retained


@dataclass
class SuccessfulCapabilityHistory:
    """Local successful-execution counts used as an optional routing prior.

    This object records only explicit successful executions. It intentionally
    has no knowledge of authorization or health; callers must apply those
    hard constraints before consulting the prior.
    """

    _counts: Counter[str] = field(default_factory=Counter)

    def record_success(
        self,
        tool: str,
        endpoint: str,
        *,
        endpoint_fingerprint: str | None = None,
    ) -> None:
        route = _route_id(tool, endpoint)
        key = _capability_key(tool, endpoint, endpoint_fingerprint)
        if endpoint_fingerprint is not None:
            _drop_superseded_fingerprint_keys(self._counts, route, keep=key)
        self._counts[key] = min(_SUCCESS_COUNT_CAP, self._counts[key] + 1)

    def forget(self, tool: str, endpoint: str) -> None:
        """Drop legacy and fingerprinted adaptive state for one removed route."""

        route = _route_id(tool, endpoint)
        self._counts.pop(route, None)
        _drop_superseded_fingerprint_keys(self._counts, route)

    def count(
        self,
        tool: str,
        endpoint: str,
        *,
        endpoint_fingerprint: str | None = None,
    ) -> int:
        exact = _capability_key(tool, endpoint, endpoint_fingerprint)
        if exact in self._counts:
            return self._counts[exact]
        route = _route_id(tool, endpoint)
        if endpoint_fingerprint is not None and route in self._counts:
            return self._counts[route]
        if endpoint_fingerprint is not None:
            return 0
        return self._counts[route]

    def snapshot(self) -> dict[str, int]:
        return dict(sorted(self._counts.items()))

    def reset(self) -> None:
        self._counts.clear()

    def dumps(self) -> str:
        return canonical_json_text(self.snapshot())

    def digest(self) -> str:
        return canonical_json_sha256(self.snapshot())

    @classmethod
    def loads(cls, payload: str) -> SuccessfulCapabilityHistory:
        raw = json.loads(payload)
        if not isinstance(raw, dict):
            raise ValueError("successful capability history must be a JSON object")
        validated: dict[str, int] = {}
        for route, value in raw.items():
            if not isinstance(route, str) or "." not in route:
                raise ValueError("history route ids must be '<tool>.<endpoint>' strings")
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("history counts must be non-negative integers")
            if value:
                validated[route] = min(_SUCCESS_COUNT_CAP, value)

        history = cls()
        retained = _legacy_compacted_fingerprint_keys(validated)
        for route in sorted(retained):
            history._counts[route] = validated[route]
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

    def decision(
        self,
        tool: str,
        endpoint: str,
        *,
        endpoint_fingerprint: str | None = None,
    ) -> SchemaExposureDecision:
        route = _route_id(tool, endpoint)
        key = _capability_key(tool, endpoint, endpoint_fingerprint)
        if key in self._exposed or (
            endpoint_fingerprint is not None and route in self._exposed
        ):
            return SchemaExposureDecision(route, False, "already_exposed")
        return SchemaExposureDecision(route, True, "not_exposed")

    def mark_exposed(
        self,
        tool: str,
        endpoint: str,
        *,
        endpoint_fingerprint: str | None = None,
    ) -> None:
        route = _route_id(tool, endpoint)
        key = _capability_key(tool, endpoint, endpoint_fingerprint)
        if endpoint_fingerprint is not None:
            _drop_superseded_fingerprint_keys(self._exposed, route, keep=key)
        self._exposed.add(key)

    def forget(self, tool: str, endpoint: str) -> None:
        """Drop legacy and fingerprinted exposure state for one removed route."""

        route = _route_id(tool, endpoint)
        self._exposed.discard(route)
        _drop_superseded_fingerprint_keys(self._exposed, route)

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
        return canonical_json_text(self.snapshot())

    def digest(self) -> str:
        return canonical_json_sha256(self.snapshot())

    @classmethod
    def loads(cls, payload: str) -> SessionSchemaExposure:
        raw = json.loads(payload)
        if not isinstance(raw, dict):
            raise ValueError("session schema exposure must be a JSON object")
        if set(raw) != {"compaction_epoch", "exposed_routes"}:
            raise ValueError(
                "session schema exposure requires compaction_epoch and exposed_routes"
            )
        epoch = raw["compaction_epoch"]
        routes = raw["exposed_routes"]
        if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
            raise ValueError("compaction_epoch must be a non-negative integer")
        if not isinstance(routes, list) or not all(isinstance(x, str) and "." in x for x in routes):
            raise ValueError("exposed_routes must be route-id strings")
        state = cls(compaction_epoch=epoch)
        state._exposed.update(_legacy_compacted_fingerprint_keys(routes))
        return state


def apply_success_prior(retrieval, history: SuccessfulCapabilityHistory, *, weight: float = 0.0):
    """Return a re-ranked retrieval using successful-call history as a soft prior.

    The input retrieval is assumed to have already passed normal visibility,
    authorization and availability filtering. A zero weight is an exact no-op.
    """
    from .models import CapabilityRetrieval

    if weight < 0:
        raise ValueError("weight must be >= 0")
    if weight == 0 or len(retrieval.candidates) < 2:
        return retrieval

    ranked = sorted(
        retrieval.candidates,
        key=lambda candidate: (
            -(
                candidate.score
                + weight
                * min(
                    1.0,
                    math.log1p(
                        history.count(
                            candidate.tool,
                            candidate.endpoint,
                            endpoint_fingerprint=candidate.endpoint_fingerprint,
                        )
                    )
                    / math.log(2),
                )
            ),
            candidate.rank,
            candidate.route_id,
        ),
    )
    return CapabilityRetrieval(
        query=retrieval.query,
        registry_version=retrieval.registry_version,
        requested_k=retrieval.requested_k,
        total_ranked=retrieval.total_ranked,
        executable_only=retrieval.executable_only,
        candidates=[
            candidate.model_copy(update={"rank": rank})
            for rank, candidate in enumerate(ranked, start=1)
        ],
    )


def filter_unexposed_schemas(retrieval, exposure: SessionSchemaExposure):
    """Return only schemas not already exposed in the current context epoch."""
    from .models import CapabilityRetrieval

    candidates = [
        candidate
        for candidate in retrieval.candidates
        if exposure.decision(
            candidate.tool,
            candidate.endpoint,
            endpoint_fingerprint=candidate.endpoint_fingerprint,
        ).inject
    ]
    return CapabilityRetrieval(
        query=retrieval.query,
        registry_version=retrieval.registry_version,
        requested_k=retrieval.requested_k,
        total_ranked=retrieval.total_ranked,
        executable_only=retrieval.executable_only,
        candidates=[
            candidate.model_copy(update={"rank": rank})
            for rank, candidate in enumerate(candidates, start=1)
        ],
    )
