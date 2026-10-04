"""Privacy-safe authorization decision audit events for trusted host sinks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

AuthorizationAuditEffect = Literal["allow", "deny"]


@dataclass(frozen=True)
class AuthorizationAuditEvent:
    """Redacted authorization decision metadata.

    Principal claims and trusted-filter values are intentionally absent. Hosts may
    attach their own opaque audit identifier through the callback closure.
    """

    effect: AuthorizationAuditEffect
    operation: str
    decision_source: Literal["rule", "default", "missing_principal", "missing_capability"]
    rule_name: str | None = None
    data_scope_rule_name: str | None = None
    visible_field_count: int | None = None
    trusted_filter_fields: tuple[str, ...] = ()
    allowed_relationship_count: int | None = None
    max_hops: int | None = None
    tool: str | None = None
    endpoint: str | None = None


AuthorizationAuditHook = Callable[[AuthorizationAuditEvent], None]
