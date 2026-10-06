"""Privacy-safe authorization decision audit events for trusted host sinks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Literal

AuthorizationAuditEffect = Literal["allow", "deny"]
AuthorizationAuditPhase = Literal["plan", "execution", "export"]
AuthorizationAuditDeliveryMode = Literal["best_effort", "strict"]


@dataclass(frozen=True)
class AuthorizationAuditEvent:
    """Redacted authorization decision metadata.

    Principal claims and trusted-filter values are intentionally absent. Hosts may
    correlate decisions with their own opaque principal audit identifier.
    """

    effect: AuthorizationAuditEffect
    operation: str
    decision_source: Literal["rule", "default", "missing_principal", "missing_capability"]
    run_id: str
    phase: AuthorizationAuditPhase
    principal_audit_id: str | None = None
    rule_name: str | None = None
    data_scope_rule_name: str | None = None
    visible_field_count: int | None = None
    trusted_filter_fields: tuple[str, ...] = ()
    allowed_relationship_count: int | None = None
    max_hops: int | None = None
    tool: str | None = None
    endpoint: str | None = None


AuthorizationAuditHook = Callable[[AuthorizationAuditEvent], None]


@dataclass(frozen=True)
class AuthorizationAuditDeliveryStatus:
    """Privacy-safe health snapshot for audit-event delivery."""

    mode: AuthorizationAuditDeliveryMode
    sink_configured: bool
    healthy: bool
    delivered_events: int
    failed_deliveries: int
    consecutive_failures: int
    last_failure_effect: AuthorizationAuditEffect | None = None
    last_failure_phase: AuthorizationAuditPhase | None = None
    last_failure_operation: str | None = None
    last_failure_error_type: str | None = None


class AuthorizationAuditDeliveryMonitor:
    """Thread-safe delivery counters that never retain principal claims or filter values."""

    def __init__(
        self,
        *,
        mode: AuthorizationAuditDeliveryMode,
        sink_configured: bool,
    ) -> None:
        if mode not in {"best_effort", "strict"}:
            raise ValueError(
                "authorization_audit_delivery_mode must be 'best_effort' or 'strict'"
            )
        self.mode = mode
        self.sink_configured = sink_configured
        self._lock = Lock()
        self._delivered_events = 0
        self._failed_deliveries = 0
        self._consecutive_failures = 0
        self._last_failure_effect: AuthorizationAuditEffect | None = None
        self._last_failure_phase: AuthorizationAuditPhase | None = None
        self._last_failure_operation: str | None = None
        self._last_failure_error_type: str | None = None

    def record_success(self) -> None:
        with self._lock:
            self._delivered_events += 1
            self._consecutive_failures = 0

    def record_failure(
        self,
        event: AuthorizationAuditEvent,
        error: Exception,
    ) -> None:
        with self._lock:
            self._failed_deliveries += 1
            self._consecutive_failures += 1
            self._last_failure_effect = event.effect
            self._last_failure_phase = event.phase
            self._last_failure_operation = event.operation
            self._last_failure_error_type = type(error).__name__

    def snapshot(self) -> AuthorizationAuditDeliveryStatus:
        with self._lock:
            return AuthorizationAuditDeliveryStatus(
                mode=self.mode,
                sink_configured=self.sink_configured,
                healthy=self._consecutive_failures == 0,
                delivered_events=self._delivered_events,
                failed_deliveries=self._failed_deliveries,
                consecutive_failures=self._consecutive_failures,
                last_failure_effect=self._last_failure_effect,
                last_failure_phase=self._last_failure_phase,
                last_failure_operation=self._last_failure_operation,
                last_failure_error_type=self._last_failure_error_type,
            )
