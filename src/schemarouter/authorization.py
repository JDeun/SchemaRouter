from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Literal

from pydantic import Field, model_validator

from .errors import PolicyViolationError
from .models import EndpointSpec, StrictModel, ToolCall, ToolSpec


class PrincipalContext(StrictModel):
    """Trusted identity claims supplied by the host application.

    SchemaRouter does not authenticate the subject. The host is responsible for verifying
    these claims before constructing this object.
    """

    subject: str
    roles: tuple[str, ...] = ()
    departments: tuple[str, ...] = ()
    teams: tuple[str, ...] = ()
    attributes: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_claims(self) -> PrincipalContext:
        if not self.subject.strip():
            raise ValueError("principal subject must be non-empty")
        for label, values in (
            ("roles", self.roles),
            ("departments", self.departments),
            ("teams", self.teams),
        ):
            normalized = tuple(value.strip() for value in values)
            if any(not value for value in normalized):
                raise ValueError(f"principal {label} must contain non-empty values")
            if len(normalized) != len(set(normalized)):
                raise ValueError(f"principal {label} must not contain duplicates")
            object.__setattr__(self, label, normalized)
        if any(not key.strip() for key in self.attributes):
            raise ValueError("principal attribute names must be non-empty")
        return self


_CURRENT_PRINCIPAL: ContextVar[PrincipalContext | None] = ContextVar(
    "schemarouter_current_principal",
    default=None,
)


@contextmanager
def _principal_execution_context(principal: PrincipalContext | None):
    """Bind trusted principal claims to the current async/thread execution context."""

    token = _CURRENT_PRINCIPAL.set(principal)
    try:
        yield
    finally:
        _CURRENT_PRINCIPAL.reset(token)


def _current_principal_context() -> PrincipalContext | None:
    return _CURRENT_PRINCIPAL.get()


AuthorizationEffect = Literal["allow", "deny"]


@dataclass(frozen=True)
class AuthorizationRule:
    """Trusted RBAC/ABAC rule over one capability surface.

    Rules are evaluated in declaration order and the first matching rule wins.
    Principal predicates are ANDed across categories and ORed within each *_any set.
    """

    effect: AuthorizationEffect
    operation: str = "*"
    name: str | None = None
    provider: str | None = None
    access_mode: str | None = None
    roles_any: tuple[str, ...] = ()
    roles_all: tuple[str, ...] = ()
    departments_any: tuple[str, ...] = ()
    teams_any: tuple[str, ...] = ()
    attributes: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.effect not in {"allow", "deny"}:
            raise ValueError("authorization effect must be allow or deny")
        if not self.operation.strip():
            raise ValueError("authorization operation pattern must be non-empty")
        for values in (
            self.roles_any,
            self.roles_all,
            self.departments_any,
            self.teams_any,
        ):
            if any(not value.strip() for value in values):
                raise ValueError("authorization principal selectors must be non-empty")
        if any(not key.strip() for key, _ in self.attributes):
            raise ValueError("authorization attribute names must be non-empty")

    def matches_principal(self, principal: PrincipalContext) -> bool:
        roles = set(principal.roles)
        departments = set(principal.departments)
        teams = set(principal.teams)
        if self.roles_any and not roles.intersection(self.roles_any):
            return False
        if self.roles_all and not set(self.roles_all).issubset(roles):
            return False
        if self.departments_any and not departments.intersection(self.departments_any):
            return False
        if self.teams_any and not teams.intersection(self.teams_any):
            return False
        if any(principal.attributes.get(key) != value for key, value in self.attributes):
            return False
        return True

    def matches_resource(
        self,
        tool: ToolSpec,
        endpoint: EndpointSpec,
        call: ToolCall | None = None,
    ) -> bool:
        operation = (
            f"{call.tool}.{call.endpoint}"
            if call is not None
            else f"{tool.key}.{endpoint.name}"
        )
        if not fnmatchcase(operation, self.operation):
            return False
        if self.provider is not None and tool.provider != self.provider:
            return False
        if self.access_mode is not None and tool.access_mode != self.access_mode:
            return False
        return True

    def matches(
        self,
        principal: PrincipalContext,
        tool: ToolSpec,
        endpoint: EndpointSpec,
        call: ToolCall | None = None,
    ) -> bool:
        return self.matches_principal(principal) and self.matches_resource(
            tool,
            endpoint,
            call,
        )


@dataclass(frozen=True)
class AuthorizationDecision:
    effect: AuthorizationEffect
    source: Literal["rule", "default"]
    operation: str
    rule_name: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class AuthorizationPolicy:
    """Deny-by-default principal-aware capability authorization."""

    rules: tuple[AuthorizationRule, ...] = ()
    default_effect: AuthorizationEffect = "deny"

    def __post_init__(self) -> None:
        if self.default_effect not in {"allow", "deny"}:
            raise ValueError("authorization default_effect must be allow or deny")
        object.__setattr__(self, "rules", tuple(self.rules))

    def evaluate(
        self,
        principal: PrincipalContext,
        tool: ToolSpec,
        endpoint: EndpointSpec,
        call: ToolCall | None = None,
    ) -> AuthorizationDecision:
        operation = (
            f"{call.tool}.{call.endpoint}"
            if call is not None
            else f"{tool.key}.{endpoint.name}"
        )
        rule = next(
            (
                candidate
                for candidate in self.rules
                if candidate.matches(principal, tool, endpoint, call)
            ),
            None,
        )
        if rule is not None:
            return AuthorizationDecision(
                effect=rule.effect,
                source="rule",
                operation=operation,
                rule_name=rule.name,
                reason=(
                    f"matched authorization rule {rule.name!r}"
                    if rule.name
                    else "matched authorization rule"
                ),
            )
        return AuthorizationDecision(
            effect=self.default_effect,
            source="default",
            operation=operation,
            reason=f"authorization default is {self.default_effect}",
        )

    def visible(
        self,
        principal: PrincipalContext,
        tool: ToolSpec,
        endpoint: EndpointSpec,
    ) -> bool:
        return self.evaluate(principal, tool, endpoint).effect == "allow"

    def validate(
        self,
        principal: PrincipalContext,
        tool: ToolSpec,
        endpoint: EndpointSpec,
        call: ToolCall,
    ) -> None:
        if self.evaluate(principal, tool, endpoint, call).effect != "allow":
            # Keep the exception intentionally generic so an untrusted caller does not
            # learn why a capability was denied or which principal predicate failed.
            raise PolicyViolationError("authorization denied for requested capability")
