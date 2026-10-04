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
from .models import StrictModel


class TrustedFilterConfig(StrictModel):
    field: str
    principal_value: str

    @model_validator(mode="after")
    def validate_source(self) -> TrustedFilterConfig:
        TrustedFilterBinding(field=self.field, principal_value=self.principal_value)
        if self.principal_value.startswith("attribute:") and not self.principal_value[10:]:
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


def lint_authorization_config(config: AuthorizationPolicyConfig) -> tuple[str, ...]:
    issues: list[str] = []
    for label, items in (("rules", config.rules), ("data_rules", config.data_rules)):
        duplicates = _duplicate_names(items)
        if duplicates:
            issues.append(f"{label} contain duplicate names: {', '.join(duplicates)}")

    for index, rule in enumerate(config.rules):
        if rule.operation == "*" and not any(
            (
                rule.provider,
                rule.access_mode,
                rule.roles_any,
                rule.roles_all,
                rule.departments_any,
                rule.teams_any,
                rule.attributes,
            )
        ):
            if index < len(config.rules) - 1:
                issues.append(
                    f"rules[{index}] is an unconditional catch-all; later rules are unreachable"
                )

    for index, rule in enumerate(config.data_rules):
        if rule.operation == "*" and not any(
            (
                rule.provider,
                rule.access_mode,
                rule.roles_any,
                rule.roles_all,
                rule.departments_any,
                rule.teams_any,
                rule.attributes,
            )
        ):
            if index < len(config.data_rules) - 1:
                issues.append(
                    f"data_rules[{index}] is an unconditional catch-all; later rules are unreachable"
                )
    return tuple(issues)


def parse_authorization_policy(
    value: str | bytes | dict[str, Any],
    *,
    format: Literal["json", "yaml"] = "json",
    lint: bool = True,
) -> AuthorizationPolicy:
    if isinstance(value, dict):
        raw = value
    elif format == "json":
        raw = json.loads(value)
    else:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError(
                "YAML policy loading requires the optional PyYAML package"
            ) from exc
        raw = yaml.safe_load(value)

    config = AuthorizationPolicyConfig.model_validate(raw)
    issues = lint_authorization_config(config)
    if lint and issues:
        raise ValueError("authorization policy lint failed: " + "; ".join(issues))
    return config.build()


def load_authorization_policy(
    path: str | Path,
    *,
    lint: bool = True,
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
        policy_path.read_text(encoding="utf-8"),
        format=format,
        lint=lint,
    )


def normalized_authorization_json(
    value: AuthorizationPolicyConfig | str | bytes | dict[str, Any],
) -> str:
    config = (
        value
        if isinstance(value, AuthorizationPolicyConfig)
        else AuthorizationPolicyConfig.model_validate(
            json.loads(value) if isinstance(value, (str, bytes)) else value
        )
    )
    return json.dumps(
        config.model_dump(mode="json", exclude_none=True),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
