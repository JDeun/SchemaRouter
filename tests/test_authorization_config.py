import json

import pytest
from pydantic import ValidationError

from schemarouter.authorization_config import (
    AuthorizationPolicyConfig,
    lint_authorization_config,
    load_authorization_policy,
    normalized_authorization_json,
    parse_authorization_policy,
)
from schemarouter.document_loading import DocumentLimitError, DocumentLimits


def example() -> dict:
    return {
        "version": 1,
        "default_effect": "deny",
        "rules": [
            {
                "name": "employees",
                "effect": "allow",
                "operation": "company.employees.select",
                "roles_any": ["employee", "manager", "executive"],
            }
        ],
        "data_rules": [
            {
                "name": "employee-scope",
                "operation": "company.employees.select",
                "roles_any": ["employee"],
                "visible_fields": ["id", "name"],
                "trusted_filters": [
                    {
                        "field": "department",
                        "principal_value": "attribute:department",
                    }
                ],
            }
        ],
    }


def test_declarative_policy_builds_frozen_runtime_objects() -> None:
    policy = parse_authorization_policy(json.dumps(example()))
    assert policy.default_effect == "deny"
    assert policy.rules[0].name == "employees"
    assert policy.data_rules[0].visible_fields == ("id", "name")
    assert policy.data_rules[0].trusted_filters[0].principal_value == (
        "attribute:department"
    )


def test_unknown_keys_fail_closed() -> None:
    data = example()
    data["rules"][0]["model_can_edit"] = True
    with pytest.raises(ValidationError):
        parse_authorization_policy(data)


def test_contradictory_field_scope_fails_closed() -> None:
    data = example()
    data["data_rules"][0]["hidden_fields"] = ["name"]
    with pytest.raises(ValidationError, match="contradict"):
        parse_authorization_policy(data)


def test_invalid_trusted_filter_source_fails_closed() -> None:
    data = example()
    data["data_rules"][0]["trusted_filters"][0]["principal_value"] = "jwt:department"
    with pytest.raises(ValidationError, match="principal_value"):
        parse_authorization_policy(data)


def test_lint_rejects_duplicate_and_unreachable_rules() -> None:
    data = example()
    data["rules"] = [
        {"name": "catch", "effect": "deny", "operation": "*"},
        {"name": "catch", "effect": "allow", "operation": "public.*"},
    ]
    config = AuthorizationPolicyConfig.model_validate(data)
    issues = lint_authorization_config(config)
    assert any("duplicate names" in issue for issue in issues)
    assert any("unreachable" in issue for issue in issues)
    with pytest.raises(ValueError, match="lint failed"):
        parse_authorization_policy(data)


def test_lint_reports_named_shadowed_and_duplicate_matchers() -> None:
    data = example()
    data["rules"] = [
        {
            "name": "company-allow",
            "effect": "allow",
            "operation": "company.*",
        },
        {
            "name": "payroll-deny",
            "effect": "deny",
            "operation": "company.payroll.*",
        },
        {
            "name": "company-duplicate",
            "effect": "deny",
            "operation": "company.*",
        },
    ]
    data["data_rules"] = [
        {
            "name": "company-scope",
            "operation": "company.*",
            "visible_fields": ["id"],
        },
        {
            "name": "payroll-scope",
            "operation": "company.payroll.*",
            "visible_fields": [],
        },
    ]

    issues = lint_authorization_config(AuthorizationPolicyConfig.model_validate(data))

    assert any(
        "rules[1] ('payroll-deny') is shadowed by rules[0] ('company-allow')"
        in issue
        for issue in issues
    )
    assert any(
        "rules[2] ('company-duplicate') duplicates match conditions of "
        "rules[0] ('company-allow')" in issue
        for issue in issues
    )
    assert any(
        "data_rules[1] ('payroll-scope') is shadowed by "
        "data_rules[0] ('company-scope')" in issue
        for issue in issues
    )


def test_normalized_json_is_deterministic() -> None:
    rendered = normalized_authorization_json(example())
    assert rendered == normalized_authorization_json(json.loads(rendered))
    assert '"version": 1' in rendered


def test_authorization_policy_parsing_enforces_json_document_limits() -> None:
    document = json.dumps(example())
    with pytest.raises(DocumentLimitError, match="encoded-size"):
        parse_authorization_policy(
            document,
            document_limits=DocumentLimits(max_bytes=len(document.encode("utf-8")) - 1),
        )


def test_authorization_policy_yaml_alias_budget_fails_closed() -> None:
    pytest.importorskip("yaml")
    document = """
version: 1
default_effect: deny
base: &base {effect: allow, operation: public.read}
rules:
  - *base
  - *base
"""
    with pytest.raises(DocumentLimitError, match="alias"):
        parse_authorization_policy(
            document,
            format="yaml",
            document_limits=DocumentLimits(max_yaml_aliases=1),
        )


def test_authorization_policy_file_read_is_bounded(tmp_path) -> None:
    source = tmp_path / "policy.json"
    source.write_text(json.dumps(example()), encoding="utf-8")

    with pytest.raises(DocumentLimitError, match="encoded-size"):
        load_authorization_policy(
            source,
            document_limits=DocumentLimits(max_bytes=16),
        )
