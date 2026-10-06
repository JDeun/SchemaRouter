"""Strict declarative loading and linting for trusted authorization policy config."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from .authorization import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    TrustedFilterBinding,
)
from .document_loading import (
    DocumentLimits,
    load_bounded_json,
    load_bounded_yaml,
    read_bounded_text,
    validate_bounded_structure,
)
from .models import StrictModel


class TrustedFilterConfig(StrictModel):
    field: str
    principal_value: str

    @model_validator(mode="after")
    def validate_source(self) -> TrustedFilterConfig:
        valid = self.principal_value in {"subject", "role", "department", "team"}
        attribute = self.principal_value.startswith("attribute:")
        if not valid and not attribute:
            raise ValueError("invalid trusted-filter principal_value")
        if attribute and not self.principal_value[10:]:
            raise ValueError("attribute trusted-filter source must name an attribute")
        return self

    def build(self) -> TrustedFilterBinding:
        return TrustedFilterBinding(
            field=self.field,
            principal_value=self.principal_value,
        )


class AuthorizationRuleConfig(StrictModel):
    name: str | None = None
    effect: Literal["allow", "deny"]
    operation: str = "*"
    provider: str | None = None
    access_mode: str | None = None
    roles_any: tuple[str, ...] = ()
    roles_all: tuple[str, ...] = ()
    departments_any: tuple[str, ...] = ()
    teams_any: tuple[str, ...] = ()
    attributes: dict[str, str] = Field(default_factory=dict)

    def build(self) -> AuthorizationRule:
        return AuthorizationRule(
            name=self.name,
            effect=self.effect,
            operation=self.operation,
            provider=self.provider,
            access_mode=self.access_mode,
            roles_any=self.roles_any,
            roles_all=self.roles_all,
            departments_any=self.departments_any,
            teams_any=self.teams_any,
            attributes=tuple(sorted(self.attributes.items())),
        )


class DataScopeRuleConfig(StrictModel):
    name: str | None = None
    operation: str = "*"
    provider: str | None = None
    access_mode: str | None = None
    roles_any: tuple[str, ...] = ()
    roles_all: tuple[str, ...] = ()
    departments_any: tuple[str, ...] = ()
    teams_any: tuple[str, ...] = ()
    attributes: dict[str, str] = Field(default_factory=dict)
    visible_fields: tuple[str, ...] | None = None
    hidden_fields: tuple[str, ...] = ()
    trusted_filters: tuple[TrustedFilterConfig, ...] = ()
    allowed_relationships: tuple[str, ...] | None = None
    max_hops: int | None = None

    @model_validator(mode="after")
    def validate_field_scope(self) -> DataScopeRuleConfig:
        if self.visible_fields is not None:
            overlap = sorted(set(self.visible_fields).intersection(self.hidden_fields))
            if overlap:
                raise ValueError(
                    "visible_fields and hidden_fields contradict for: "
                    + ", ".join(overlap)
                )
        return self

    def build(self) -> DataScopeRule:
        return DataScopeRule(
            name=self.name,
            operation=self.operation,
            provider=self.provider,
            access_mode=self.access_mode,
            roles_any=self.roles_any,
            roles_all=self.roles_all,
            departments_any=self.departments_any,
            teams_any=self.teams_any,
            attributes=tuple(sorted(self.attributes.items())),
            visible_fields=self.visible_fields,
            hidden_fields=self.hidden_fields,
            trusted_filters=tuple(item.build() for item in self.trusted_filters),
            allowed_relationships=self.allowed_relationships,
            max_hops=self.max_hops,
        )


class AuthorizationPolicyConfig(StrictModel):
    version: Literal[1] = 1
    default_effect: Literal["allow", "deny"] = "deny"
    rules: tuple[AuthorizationRuleConfig, ...] = ()
    data_rules: tuple[DataScopeRuleConfig, ...] = ()

    def build(self) -> AuthorizationPolicy:
        return AuthorizationPolicy(
            default_effect=self.default_effect,
            rules=tuple(rule.build() for rule in self.rules),
            data_rules=tuple(rule.build() for rule in self.data_rules),
        )


def _duplicate_names(items: tuple[Any, ...]) -> list[str]:
    names = [item.name for item in items if item.name is not None]
    return sorted({name for name in names if names.count(name) > 1})


def _principal_signature(rule: Any) -> tuple[Any, ...]:
    return (
        tuple(sorted(rule.roles_any)),
        tuple(sorted(rule.roles_all)),
        tuple(sorted(rule.departments_any)),
        tuple(sorted(rule.teams_any)),
        tuple(sorted(rule.attributes.items())),
    )


def _principal_unconstrained(rule: Any) -> bool:
    return not any(_principal_signature(rule))


def _matcher_signature(rule: Any) -> tuple[Any, ...]:
    return (
        rule.operation,
        rule.provider,
        rule.access_mode,
        *_principal_signature(rule),
    )


def _operation_pattern_covers(earlier: str, later: str) -> bool:
    if earlier == "*" or earlier == later:
        return True
    if not earlier.endswith("*"):
        return False
    prefix = earlier[:-1]
    if any(char in prefix for char in "*?["):
        return False
    return later.startswith(prefix)


def _matcher_covers(earlier: Any, later: Any) -> bool:
    if not _operation_pattern_covers(earlier.operation, later.operation):
        return False
    if earlier.provider is not None and earlier.provider != later.provider:
        return False
    if earlier.access_mode is not None and earlier.access_mode != later.access_mode:
        return False
    return _principal_unconstrained(earlier) or (
        _principal_signature(earlier) == _principal_signature(later)
    )


def _rule_ref(label: str, index: int, rule: Any) -> str:
    suffix = f" ({rule.name!r})" if rule.name is not None else ""
    return f"{label}[{index}]{suffix}"


def _lint_shadowing(items: tuple[Any, ...], label: str) -> list[str]:
    issues: list[str] = []
    seen: dict[tuple[Any, ...], int] = {}
    for index, rule in enumerate(items):
        signature = _matcher_signature(rule)
        duplicate_index = seen.get(signature)
        if duplicate_index is not None:
            issues.append(
                f"{_rule_ref(label, index, rule)} duplicates match conditions of "
                f"{_rule_ref(label, duplicate_index, items[duplicate_index])}; "
                "the later rule is unreachable under first-match semantics"
            )
            continue
        seen[signature] = index

        for earlier_index, earlier in enumerate(items[:index]):
            if _matcher_covers(earlier, rule):
                issues.append(
                    f"{_rule_ref(label, index, rule)} is shadowed by "
                    f"{_rule_ref(label, earlier_index, earlier)} under first-match semantics; "
                    "the later rule is unreachable"
                )
                break
    return issues


def lint_authorization_config(config: AuthorizationPolicyConfig) -> tuple[str, ...]:
    issues: list[str] = []
    for label, items in (("rules", config.rules), ("data_rules", config.data_rules)):
        duplicates = _duplicate_names(items)
        if duplicates:
            issues.append(f"{label} contain duplicate names: {', '.join(duplicates)}")
        issues.extend(_lint_shadowing(items, label))
    return tuple(issues)

def parse_authorization_policy(
    value: str | bytes | dict[str, Any],
    *,
    format: Literal["json", "yaml"] = "json",
    lint: bool = True,
    document_limits: DocumentLimits | None = None,
) -> AuthorizationPolicy:
    if isinstance(value, dict):
        validate_bounded_structure(value, limits=document_limits)
        raw = value
    elif format == "json":
        raw = load_bounded_json(value, limits=document_limits)
    else:
        try:
            raw = load_bounded_yaml(value, limits=document_limits)
        except RuntimeError as exc:
            raise RuntimeError(
                "YAML policy loading requires the optional PyYAML package"
            ) from exc

    config = AuthorizationPolicyConfig.model_validate(raw)
    issues = lint_authorization_config(config)
    if lint and issues:
        raise ValueError("authorization policy lint failed: " + "; ".join(issues))
    return config.build()


def load_authorization_policy(
    path: str | Path,
    *,
    lint: bool = True,
    document_limits: DocumentLimits | None = None,
) -> AuthorizationPolicy:
    policy_path = Path(path)
    suffix = policy_path.suffix.lower()
    if suffix == ".json":
        format: Literal["json", "yaml"] = "json"
    elif suffix in {".yaml", ".yml"}:
        format = "yaml"
    else:
        raise ValueError("authorization policy path must end in .json, .yaml, or .yml")
    return parse_authorization_policy(
        read_bounded_text(policy_path, limits=document_limits),
        format=format,
        lint=lint,
        document_limits=document_limits,
    )


def normalized_authorization_json(
    value: AuthorizationPolicyConfig | str | bytes | dict[str, Any],
    *,
    document_limits: DocumentLimits | None = None,
) -> str:
    if isinstance(value, AuthorizationPolicyConfig):
        config = value
    else:
        if isinstance(value, (str, bytes)):
            raw = load_bounded_json(value, limits=document_limits)
        else:
            validate_bounded_structure(value, limits=document_limits)
            raw = value
        config = AuthorizationPolicyConfig.model_validate(raw)
    return json.dumps(
        config.model_dump(mode="json", exclude_none=True),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
