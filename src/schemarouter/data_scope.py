from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Literal

from .authorization import PrincipalContext
from .errors import PolicyViolationError
from .models import EndpointSpec, ToolSpec


TrustedPredicateOperator = Literal["eq", "in"]
TrustedValueSource = Literal[
    "subject",
    "attribute",
    "roles",
    "departments",
    "teams",
    "constant",
]


@dataclass(frozen=True)
class TrustedDataPredicate:
    """One host-derived data predicate that model arguments cannot override."""

    field: str
    source: TrustedValueSource
    operator: TrustedPredicateOperator = "eq"
    attribute: str | None = None
    constant: str | int | float | bool | None = None

    def __post_init__(self) -> None:
        if not self.field.strip():
            raise ValueError("trusted data predicate field must be non-empty")
        if self.source == "attribute":
            if self.attribute is None or not self.attribute.strip():
                raise ValueError(
                    "attribute-backed trusted data predicate requires attribute name"
                )
        elif self.attribute is not None:
            raise ValueError(
                "trusted data predicate attribute is only valid for source='attribute'"
            )
        if self.source == "constant":
            if self.constant is None:
                raise ValueError(
                    "constant-backed trusted data predicate requires constant value"
                )
        elif self.constant is not None:
            raise ValueError(
                "trusted data predicate constant is only valid for source='constant'"
            )
        if self.source in {"roles", "departments", "teams"} and self.operator != "in":
            raise ValueError(
                f"{self.source}-backed trusted data predicate requires operator='in'"
            )

    def resolve(
        self,
        principal: PrincipalContext,
    ) -> str | int | float | bool | tuple[str, ...]:
        if self.source == "subject":
            return principal.subject
        if self.source == "attribute":
            assert self.attribute is not None
            try:
                return principal.attributes[self.attribute]
            except KeyError as exc:
                raise PolicyViolationError(
                    "trusted data predicate cannot be resolved for principal"
                ) from exc
        if self.source == "roles":
            if not principal.roles:
                raise PolicyViolationError(
                    "trusted data predicate cannot be resolved for principal"
                )
            return tuple(principal.roles)
        if self.source == "departments":
            if not principal.departments:
                raise PolicyViolationError(
                    "trusted data predicate cannot be resolved for principal"
                )
            return tuple(principal.departments)
        if self.source == "teams":
            if not principal.teams:
                raise PolicyViolationError(
                    "trusted data predicate cannot be resolved for principal"
                )
            return tuple(principal.teams)
        assert self.source == "constant"
        assert self.constant is not None
        return self.constant


@dataclass(frozen=True)
class ResolvedDataPredicate:
    """Resolved trusted predicate passed only to a trusted adapter/invoker."""

    field: str
    operator: TrustedPredicateOperator
    value: str | int | float | bool | tuple[str, ...]


@dataclass(frozen=True)
class DataScopeRule:
    """Principal-aware field visibility and trusted row/filter constraints."""

    operation: str = "*"
    name: str | None = None
    provider: str | None = None
    access_mode: str | None = None
    roles_any: tuple[str, ...] = ()
    roles_all: tuple[str, ...] = ()
    departments_any: tuple[str, ...] = ()
    teams_any: tuple[str, ...] = ()
    attributes: tuple[tuple[str, str], ...] = ()
    allow_fields: tuple[str, ...] = ("*",)
    deny_fields: tuple[str, ...] = ()
    trusted_predicates: tuple[TrustedDataPredicate, ...] = ()

    def __post_init__(self) -> None:
        if not self.operation.strip():
            raise ValueError("data-scope operation pattern must be non-empty")
        for values in (
            self.roles_any,
            self.roles_all,
            self.departments_any,
            self.teams_any,
            self.allow_fields,
            self.deny_fields,
        ):
            if any(not value.strip() for value in values):
                raise ValueError("data-scope selectors must be non-empty")
        if any(not key.strip() for key, _ in self.attributes):
            raise ValueError("data-scope attribute names must be non-empty")

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
    ) -> bool:
        operation = f"{tool.key}.{endpoint.name}"
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
    ) -> bool:
        return self.matches_principal(principal) and self.matches_resource(tool, endpoint)

    def visible_fields(self, endpoint: EndpointSpec) -> tuple[str, ...]:
        declared = tuple(field.name for field in endpoint.output_fields)
        allowed = tuple(
            field
            for field in declared
            if any(fnmatchcase(field, pattern) for pattern in self.allow_fields)
        )
        denied = {
            field
            for field in allowed
            if any(fnmatchcase(field, pattern) for pattern in self.deny_fields)
        }
        return tuple(field for field in allowed if field not in denied)

    def resolve_predicates(
        self,
        principal: PrincipalContext,
    ) -> tuple[ResolvedDataPredicate, ...]:
        return tuple(
            ResolvedDataPredicate(
                field=predicate.field,
                operator=predicate.operator,
                value=predicate.resolve(principal),
            )
            for predicate in self.trusted_predicates
        )


@dataclass(frozen=True)
class DataScopeDecision:
    operation: str
    rule_name: str | None
    visible_fields: tuple[str, ...]
    trusted_predicates: tuple[ResolvedDataPredicate, ...]
    matched: bool


@dataclass(frozen=True)
class DataScopePolicy:
    """Fail-closed field and data-scope policy for model-visible data capabilities."""

    rules: tuple[DataScopeRule, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "rules", tuple(self.rules))

    def evaluate(
        self,
        principal: PrincipalContext,
        tool: ToolSpec,
        endpoint: EndpointSpec,
    ) -> DataScopeDecision:
        operation = f"{tool.key}.{endpoint.name}"
        rule = next(
            (
                candidate
                for candidate in self.rules
                if candidate.matches(principal, tool, endpoint)
            ),
            None,
        )
        if rule is None:
            return DataScopeDecision(
                operation=operation,
                rule_name=None,
                visible_fields=(),
                trusted_predicates=(),
                matched=False,
            )
        return DataScopeDecision(
            operation=operation,
            rule_name=rule.name,
            visible_fields=rule.visible_fields(endpoint),
            trusted_predicates=rule.resolve_predicates(principal),
            matched=True,
        )

    def visible_fields(
        self,
        principal: PrincipalContext,
        tool: ToolSpec,
        endpoint: EndpointSpec,
    ) -> tuple[str, ...]:
        return self.evaluate(principal, tool, endpoint).visible_fields

    def trusted_predicates(
        self,
        principal: PrincipalContext,
        tool: ToolSpec,
        endpoint: EndpointSpec,
    ) -> tuple[ResolvedDataPredicate, ...]:
        decision = self.evaluate(principal, tool, endpoint)
        if not decision.matched:
            raise PolicyViolationError("data scope denied for requested capability")
        return decision.trusted_predicates

    def validate_fields(
        self,
        principal: PrincipalContext,
        tool: ToolSpec,
        endpoint: EndpointSpec,
        fields: tuple[str, ...] | list[str],
    ) -> None:
        decision = self.evaluate(principal, tool, endpoint)
        if not decision.matched:
            raise PolicyViolationError("data scope denied for requested capability")
        visible = set(decision.visible_fields)
        requested = set(fields)
        if not requested or not requested.issubset(visible):
            raise PolicyViolationError("data scope denied for requested fields")
