"""Privacy-safe authorization decision audit events for trusted host sinks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

AuthorizationAuditEffect = Literal["allow", "deny"]
AuthorizationAuditPhase = Literal["plan", "execution", "export"]
AuthorizationAuditMode = Literal["best_effort", "strict"]


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


@dataclass(frozen=True)
class AuthorizationAuditDeliverySnapshot:
    """Process-local health for the trusted authorization audit delivery boundary."""

    mode: AuthorizationAuditMode
    configured: bool
    failure_count: int = 0
    last_error_type: str | None = None
    last_delivery_succeeded: bool | None = None


AuthorizationAuditHook = Callable[[AuthorizationAuditEvent], None]
