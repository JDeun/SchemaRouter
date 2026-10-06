from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, field
from fnmatch import fnmatchcase
from typing import Any, Literal

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
class TrustedFilterBinding:
    """Bind one hidden data predicate to a verified principal claim."""

    field: str
    principal_value: str

    def __post_init__(self) -> None:
        if not self.field.strip():
            raise ValueError("trusted filter field must be non-empty")
        if not self.principal_value.strip():
            raise ValueError("trusted filter principal_value must be non-empty")

    def resolve(self, principal: PrincipalContext) -> Any:
        source = self.principal_value
        if source == "subject":
            return principal.subject
        if source == "role":
            return tuple(principal.roles)
        if source == "department":
            return tuple(principal.departments)
        if source == "team":
            return tuple(principal.teams)
        if source.startswith("attribute:"):
            key = source.split(":", 1)[1]
            if not key or key not in principal.attributes:
                raise PolicyViolationError("authorization denied for requested data scope")
            return principal.attributes[key]
        raise ValueError(
            "trusted filter principal_value must be subject, role, department, team, "
            "or attribute:<name>"
        )


@dataclass(frozen=True)
class DataScopeRule:
    """Principal-aware data-scope restriction applied after capability authorization.

    The first matching rule wins. visible_fields=None means fields are unrestricted,
    while an empty tuple means no output fields are visible. Trusted filters never
    become model-visible parameters.
    """

    operation: str = "*"
    name: str | None = None
    provider: str | None = None
    access_mode: str | None = None
    roles_any: tuple[str, ...] = ()
    roles_all: tuple[str, ...] = ()
    departments_any: tuple[str, ...] = ()
    teams_any: tuple[str, ...] = ()
    attributes: tuple[tuple[str, str], ...] = ()
    visible_fields: tuple[str, ...] | None = None
    hidden_fields: tuple[str, ...] = ()
    trusted_filters: tuple[TrustedFilterBinding, ...] = ()
    allowed_relationships: tuple[str, ...] | None = None
    max_hops: int | None = None

    def __post_init__(self) -> None:
        if not self.operation.strip():
            raise ValueError("data-scope operation pattern must be non-empty")
        for values in (
            self.roles_any,
            self.roles_all,
            self.departments_any,
            self.teams_any,
        ):
            if any(not value.strip() for value in values):
                raise ValueError("data-scope principal selectors must be non-empty")
        if any(not key.strip() for key, _ in self.attributes):
            raise ValueError("data-scope attribute names must be non-empty")
        if self.visible_fields is not None and any(
            not value.strip() for value in self.visible_fields
        ):
            raise ValueError("visible_fields must contain non-empty names")
        if any(not value.strip() for value in self.hidden_fields):
            raise ValueError("hidden_fields must contain non-empty names")
        if self.visible_fields is not None and set(self.visible_fields).intersection(
            self.hidden_fields
        ):
            raise ValueError("visible_fields and hidden_fields must not overlap")
        if self.allowed_relationships is not None and any(
            not value.strip() for value in self.allowed_relationships
        ):
            raise ValueError("allowed_relationships must contain non-empty names")
        if self.max_hops is not None and self.max_hops < 1:
            raise ValueError("max_hops must be >= 1 when provided")

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


@dataclass(frozen=True)
class DataScopeDecision:
    """Resolved data restrictions for one principal and one endpoint."""

    operation: str
    rule_name: str | None = None
    visible_fields: frozenset[str] | None = None
    trusted_filters: tuple[tuple[str, Any], ...] = ()
    allowed_relationships: frozenset[str] | None = None
    max_hops: int | None = None

    def filter_dict(self) -> dict[str, Any]:
        return dict(self.trusted_filters)


_CURRENT_DATA_SCOPE: ContextVar[DataScopeDecision | None] = ContextVar(
    "schemarouter_current_data_scope",
    default=None,
)


@contextmanager
def _data_scope_execution_context(scope: DataScopeDecision | None):
    token = _CURRENT_DATA_SCOPE.set(scope)
    try:
        yield
    finally:
        _CURRENT_DATA_SCOPE.reset(token)


def _current_data_scope() -> DataScopeDecision | None:
    return _CURRENT_DATA_SCOPE.get()


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


_GLOB_META = frozenset("*?[")


def _literal_operation_root(pattern: str) -> str | None:
    root = pattern.split(".", 1)[0]
    if any(char in root for char in _GLOB_META):
        return None
    return root


@dataclass(frozen=True)
class _CompiledRuleIndex:
    """Order-preserving partitions for first-match authorization rules."""

    rules: tuple[Any, ...]
    partitions: dict[
        tuple[str | None, str | None, str | None],
        tuple[int, ...],
    ]

    @classmethod
    def build(cls, rules: tuple[Any, ...]) -> _CompiledRuleIndex:
        pending: dict[
            tuple[str | None, str | None, str | None],
            list[int],
        ] = {}
        for index, rule in enumerate(rules):
            key = (
                rule.provider,
                rule.access_mode,
                _literal_operation_root(rule.operation),
            )
            pending.setdefault(key, []).append(index)
        return cls(
            rules=rules,
            partitions={key: tuple(indexes) for key, indexes in pending.items()},
        )

    def candidates(
        self,
        *,
        operation: str,
        provider: str | None,
        access_mode: str | None,
    ) -> tuple[Any, ...]:
        operation_root = operation.split(".", 1)[0]
        keys = {
            (provider_key, access_key, root_key)
            for provider_key in (provider, None)
            for access_key in (access_mode, None)
            for root_key in (operation_root, None)
        }
        indexes: set[int] = set()
        for key in keys:
            indexes.update(self.partitions.get(key, ()))
        return tuple(self.rules[index] for index in sorted(indexes))


_GLOB_META = frozenset("*?[")


def _literal_operation_root(pattern: str) -> str | None:
    root = pattern.split(".", 1)[0]
    if any(char in root for char in _GLOB_META):
        return None
    return root


@dataclass(frozen=True)
class _CompiledRuleIndex:
    """Order-preserving partitions for first-match authorization rules."""

    rules: tuple[Any, ...]
    partitions: dict[
        tuple[str | None, str | None, str | None],
        tuple[int, ...],
    ]

    @classmethod
    def build(cls, rules: tuple[Any, ...]) -> _CompiledRuleIndex:
        pending: dict[
            tuple[str | None, str | None, str | None],
            list[int],
        ] = {}
        for index, rule in enumerate(rules):
            key = (
                rule.provider,
                rule.access_mode,
                _literal_operation_root(rule.operation),
            )
            pending.setdefault(key, []).append(index)
        return cls(
            rules=rules,
            partitions={key: tuple(indexes) for key, indexes in pending.items()},
        )

    def candidates(
        self,
        *,
        operation: str,
        provider: str | None,
        access_mode: str | None,
    ) -> tuple[Any, ...]:
        operation_root = operation.split(".", 1)[0]
        keys = {
            (provider_key, access_key, root_key)
            for provider_key in (provider, None)
            for access_key in (access_mode, None)
            for root_key in (operation_root, None)
        }
        indexes: set[int] = set()
        for key in keys:
            indexes.update(self.partitions.get(key, ()))
        return tuple(self.rules[index] for index in sorted(indexes))


@dataclass(frozen=True)
class AuthorizationDecision:
    effect: AuthorizationEffect
    source: Literal["rule", "default"]
    operation: str
    rule_name: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class AuthorizationPolicy:
    """Deny-by-default capability authorization plus optional data-scope rules."""

    rules: tuple[AuthorizationRule, ...] = ()
    default_effect: AuthorizationEffect = "deny"
    data_rules: tuple[DataScopeRule, ...] = ()
    _rule_index: _CompiledRuleIndex = field(
        init=False,
        repr=False,
        compare=False,
        hash=False,
    )
    _data_rule_index: _CompiledRuleIndex = field(
        init=False,
        repr=False,
        compare=False,
        hash=False,
    )
    _rule_index: _CompiledRuleIndex = field(
        init=False,
        repr=False,
        compare=False,
        hash=False,
    )
    _data_rule_index: _CompiledRuleIndex = field(
        init=False,
        repr=False,
        compare=False,
        hash=False,
    )

    def __post_init__(self) -> None:
        if self.default_effect not in {"allow", "deny"}:
            raise ValueError("authorization default_effect must be allow or deny")
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(self, "data_rules", tuple(self.data_rules))
        object.__setattr__(self, "_rule_index", _CompiledRuleIndex.build(self.rules))
        object.__setattr__(
            self,
            "_data_rule_index",
            _CompiledRuleIndex.build(self.data_rules),
        )
        object.__setattr__(self, "_rule_index", _CompiledRuleIndex.build(self.rules))
        object.__setattr__(
            self,
            "_data_rule_index",
            _CompiledRuleIndex.build(self.data_rules),
        )

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
                for candidate in self._rule_index.candidates(
                    operation=operation,
                    provider=tool.provider,
                    access_mode=tool.access_mode,
                )
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
        self.validate_data_scope(principal, tool, endpoint, call)

    def data_scope(
        self,
        principal: PrincipalContext,
        tool: ToolSpec,
        endpoint: EndpointSpec,
    ) -> DataScopeDecision:
        operation = f"{tool.key}.{endpoint.name}"
        rule = next(
            (
                candidate
                for candidate in self._data_rule_index.candidates(
                    operation=operation,
                    provider=tool.provider,
                    access_mode=tool.access_mode,
                )
                if candidate.matches(principal, tool, endpoint)
            ),
            None,
        )
        if rule is None:
            return DataScopeDecision(operation=operation)

        declared_fields = {field.name for field in endpoint.output_fields}
        unknown_hidden = sorted(set(rule.hidden_fields) - declared_fields)
        if unknown_hidden:
            raise PolicyViolationError("authorization denied for requested data scope")
        if rule.visible_fields is None:
            visible_set = set(declared_fields)
        else:
            unknown = sorted(set(rule.visible_fields) - declared_fields)
            if unknown:
                raise PolicyViolationError("authorization denied for requested data scope")
            visible_set = set(rule.visible_fields)
        visible_set.difference_update(rule.hidden_fields)

        filters = tuple(
            (binding.field, binding.resolve(principal))
            for binding in rule.trusted_filters
        )
        return DataScopeDecision(
            operation=operation,
            rule_name=rule.name,
            visible_fields=frozenset(visible_set),
            trusted_filters=filters,
            allowed_relationships=(
                None
                if rule.allowed_relationships is None
                else frozenset(rule.allowed_relationships)
            ),
            max_hops=rule.max_hops,
        )

    def validate_data_scope(
        self,
        principal: PrincipalContext,
        tool: ToolSpec,
        endpoint: EndpointSpec,
        call: ToolCall,
    ) -> DataScopeDecision:
        scope = self.data_scope(principal, tool, endpoint)
        if scope.visible_fields is not None:
            selected = set(call.fields)
            if not selected.issubset(scope.visible_fields):
                raise PolicyViolationError("authorization denied for requested data scope")

        requested_relationships = call.arguments.get("relationship_types")
        if (
            scope.allowed_relationships is not None
            and requested_relationships is not None
        ):
            if not isinstance(requested_relationships, list) or not all(
                isinstance(value, str) for value in requested_relationships
            ):
                raise PolicyViolationError("authorization denied for requested data scope")
            if not set(requested_relationships).issubset(scope.allowed_relationships):
                raise PolicyViolationError("authorization denied for requested data scope")

        requested_hops = call.arguments.get("max_hops")
        if scope.max_hops is not None and requested_hops is not None:
            try:
                if int(requested_hops) > scope.max_hops:
                    raise PolicyViolationError(
                        "authorization denied for requested data scope"
                    )
            except (TypeError, ValueError) as exc:
                raise PolicyViolationError(
                    "authorization denied for requested data scope"
                ) from exc
        return scope
