"""No-network E0 central egress linearization model, NEVER a deployable proxy.

No sockets, credentials, identity verification, persistence, HTTP forwarding,
provider requests, uptime, model calls or E2 evidence. An in-process lock
models an atomic transition. The synthetic_handoff is test-only instrumentation.
Never use this class for product authorization or actual provider egress.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from threading import RLock
from typing import Literal

from scripts.research_live_health_model_menu_e1 import GEO, WEATHER

_FIXED_ROUTES = frozenset((GEO, WEATHER))
Decision = Literal[
    "synthetic_handoff", "operator_revoked", "stale_epoch",
    "identity_or_scope_denied", "allowance_exhausted",
    "duplicate_request", "synthetic_handoff_failed",
]


@dataclass(frozen=True)
class SyntheticEgressRequestE0:
    """Labels in a trusted test fixture; not authenticated IAM claims."""

    tenant: str
    workload: str
    route_id: str
    source_fingerprint: str
    request_id: str
    epoch: int


class CentralEgressLinearizationModelE0:
    """Abstract single-gateway admit/revoke ordering, not a real service."""

    def __init__(
        self, *,
        provisioned: Mapping[tuple[str, str, str], str],
        attempts_per_route: int,
    ) -> None:
        if (
            type(attempts_per_route) is not int
            or not 1 <= attempts_per_route <= 2
            or not isinstance(provisioned, Mapping)
            or not provisioned
            or any(
                not isinstance(key, tuple)
                or len(key) != 3
                or any(type(value) is not str or not value for value in key)
                or key[2] not in _FIXED_ROUTES
                or type(fingerprint) is not str
                or not fingerprint
                for key, fingerprint in provisioned.items()
            )
        ):
            raise ValueError("fixed explicitly provisioned E0 authority required")
        self._provisioned = dict(provisioned)
        self._cap = attempts_per_route
        self._lock = RLock()
        self._epoch = 1
        self._revoked = False
        self._seen: set[tuple[str, str]] = set()
        self._spent: Counter[str] = Counter()
        self._handoffs = 0

    @property
    def epoch(self) -> int:
        with self._lock:
            return self._epoch

    @property
    def forwarded_synthetic_attempts(self) -> int:
        with self._lock:
            return self._handoffs

    def spent_by_route(self) -> dict[str, int]:
        with self._lock:
            return {"geocoding": self._spent[GEO], "forecast": self._spent[WEATHER]}

    def revoke(self) -> bool:
        """E0 abstract operator transition, NOT actual operator IAM."""
        with self._lock:
            if self._revoked:
                return False
            self._revoked = True
            self._epoch += 1
            return True

    def admit_and_handoff(
        self,
        request: SyntheticEgressRequestE0, *,
        synthetic_handoff: Callable[[], None],
    ) -> Decision:
        """Synchronize final admission with a SYNTHETIC outgoing handoff.

        The synthetic handoff begins while holding the central lock. In
        production the trusted gateway must own actual provider egress.
        It cannot un-send a previously admitted/in-flight remote request.
        """
        if not isinstance(request, SyntheticEgressRequestE0) or not callable(
            synthetic_handoff
        ):
            raise ValueError("trusted synthetic E0 request and sink required")
        with self._lock:
            if self._revoked:
                return "operator_revoked"
            if type(request.epoch) is not int or request.epoch != self._epoch:
                return "stale_epoch"
            key = (request.tenant, request.workload, request.route_id)
            if (
                any(type(k) is not str or not k for k in key)
                or request.route_id not in _FIXED_ROUTES
                or type(request.source_fingerprint) is not str
                or self._provisioned.get(key) != request.source_fingerprint
                or type(request.request_id) is not str
                or not request.request_id
                or len(request.request_id) > 128
            ):
                return "identity_or_scope_denied"
            unique_id = (request.tenant, request.request_id)
            if unique_id in self._seen:
                return "duplicate_request"
            if self._spent[request.route_id] >= self._cap:
                return "allowance_exhausted"
            self._seen.add(unique_id)
            self._spent[request.route_id] += 1
            self._handoffs += 1
            try:
                synthetic_handoff()
            except Exception:
                return "synthetic_handoff_failed"
            return "synthetic_handoff"
