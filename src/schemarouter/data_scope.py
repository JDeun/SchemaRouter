from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Literal

from .authorization import AuthorizationPolicy, PrincipalContext
from .errors import PolicyViolationError, RegistrationError
from .models import EndpointSpec, ToolSpec
from .registry import ToolRegistry


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


_CURRENT_DATA_SCOPES: ContextVar[dict[str, DataScopeDecision] | None] = ContextVar(
    "schemarouter_current_data_scopes",
    default=None,
)


@contextmanager
def _data_scope_execution_context(
    decisions: dict[str, DataScopeDecision] | None,
):
    token = _CURRENT_DATA_SCOPES.set(decisions)
    try:
        yield
    finally:
        _CURRENT_DATA_SCOPES.reset(token)


def _current_data_scope_decision(
    tool_key: str,
    endpoint_name: str,
) -> DataScopeDecision | None:
    decisions = _CURRENT_DATA_SCOPES.get()
    if not decisions:
        return None
    return decisions.get(f"{tool_key}.{endpoint_name}")


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



def _project_object_schema(
    schema: dict[str, object],
    visible_fields: set[str],
) -> dict[str, object]:
    projected = deepcopy(schema)
    target: dict[str, object] = projected

    if projected.get("type") == "array":
        items = projected.get("items")
        if isinstance(items, dict):
            target = items

    properties = target.get("properties")
    if isinstance(properties, dict):
        target["properties"] = {
            key: value
            for key, value in properties.items()
            if key in visible_fields
        }
    required = target.get("required")
    if isinstance(required, list):
        target["required"] = [
            value
            for value in required
            if isinstance(value, str) and value in visible_fields
        ]
    return projected


def _project_endpoint_fields(
    endpoint: EndpointSpec,
    visible_fields: tuple[str, ...],
) -> EndpointSpec:
    visible = set(visible_fields)
    declared = {field.name for field in endpoint.output_fields}

    parameters = []
    for parameter in endpoint.parameters:
        candidate_field = (
            parameter.name.removeprefix("filter__")
            if parameter.name.startswith("filter__")
            else parameter.name
        )
        if candidate_field in declared and candidate_field not in visible:
            continue
        parameters.append(parameter.model_copy(deep=True))

    server_projection = (
        endpoint.server_projection.model_copy(deep=True)
        if endpoint.server_projection is not None
        else None
    )
    if server_projection is not None:
        server_projection.field_map = {
            field: wire_name
            for field, wire_name in server_projection.field_map.items()
            if field in visible
        }

    projected = endpoint.model_copy(
        update={
            "parameters": parameters,
            "output_fields": [
                field.model_copy(deep=True)
                for field in endpoint.output_fields
                if field.name in visible
            ],
            "output_schema": _project_object_schema(
                endpoint.output_schema,
                visible,
            ),
            "server_projection": server_projection,
        },
        deep=True,
    )
    return EndpointSpec.model_validate(projected.model_dump(mode="python"))


class PrincipalScopedRegistry:
    """Read-only principal-scoped registry snapshot for analyzer/planner non-disclosure.

    Capability authorization removes whole endpoints. Data-scope authorization additionally
    projects database output fields and field-derived filter parameters before any analyzer
    receives the registry.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        principal: PrincipalContext,
        authorization_policy: AuthorizationPolicy | None = None,
        data_scope_policy: DataScopePolicy | None = None,
    ) -> None:
        self._version = registry.version
        self._tools: dict[str, ToolSpec] = {}
        self._original_tool_fingerprints: dict[str, str] = {}
        self._original_endpoint_fingerprints: dict[tuple[str, str], str] = {}

        for original_tool in registry.tools():
            projected_endpoints: list[EndpointSpec] = []
            for original_endpoint in original_tool.endpoints:
                if (
                    authorization_policy is not None
                    and not authorization_policy.visible(
                        principal,
                        original_tool,
                        original_endpoint,
                    )
                ):
                    continue

                projected_endpoint = original_endpoint.model_copy(deep=True)
                if (
                    data_scope_policy is not None
                    and original_tool.source_type == "database"
                ):
                    decision = data_scope_policy.evaluate(
                        principal,
                        original_tool,
                        original_endpoint,
                    )
                    if not decision.matched or not decision.visible_fields:
                        continue
                    projected_endpoint = _project_endpoint_fields(
                        original_endpoint,
                        decision.visible_fields,
                    )

                projected_endpoints.append(projected_endpoint)
                self._original_endpoint_fingerprints[
                    (original_tool.key, original_endpoint.name)
                ] = original_endpoint.fingerprint

            if not projected_endpoints:
                continue

            projected_tool = ToolSpec.model_validate(
                original_tool.model_copy(
                    update={"endpoints": projected_endpoints},
                    deep=True,
                ).model_dump(mode="python")
            )
            self._tools[projected_tool.key] = projected_tool
            self._original_tool_fingerprints[
                projected_tool.key
            ] = original_tool.fingerprint

    @property
    def version(self) -> int:
        return self._version

    def register(self, tool: ToolSpec, *, replace: bool = False) -> str:
        del tool, replace
        raise RegistrationError("principal-scoped registry is read-only")

    def get(self, key: str) -> ToolSpec:
        try:
            return self._tools[key].model_copy(deep=True)
        except KeyError as exc:
            raise KeyError(key) from exc

    def tools(self) -> tuple[ToolSpec, ...]:
        return tuple(tool.model_copy(deep=True) for tool in self._tools.values())

    def keys(self) -> tuple[str, ...]:
        return tuple(self._tools)

    def endpoint(self, tool_key: str, endpoint_name: str) -> EndpointSpec:
        return self.get(tool_key).endpoint(endpoint_name)

    def original_tool_fingerprint(self, tool_key: str) -> str:
        try:
            return self._original_tool_fingerprints[tool_key]
        except KeyError as exc:
            raise KeyError(tool_key) from exc

    def original_endpoint_fingerprint(
        self,
        tool_key: str,
        endpoint_name: str,
    ) -> str:
        try:
            return self._original_endpoint_fingerprints[(tool_key, endpoint_name)]
        except KeyError as exc:
            raise KeyError(f"{tool_key}.{endpoint_name}") from exc
