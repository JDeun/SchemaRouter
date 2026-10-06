import json

import pytest
from pydantic import ValidationError

from schemarouter._document_loading import DocumentLimitError
from schemarouter.authorization_config import (
    AuthorizationPolicyConfig,
    lint_authorization_config,
    load_authorization_policy,
    normalized_authorization_json,
    parse_authorization_policy,
)
from schemarouter.storage import PersistedDocumentLimits


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


def test_normalized_json_is_deterministic() -> None:
    rendered = normalized_authorization_json(example())
    assert rendered == normalized_authorization_json(json.loads(rendered))
    assert '"version": 1' in rendered


def _document_limits(**overrides: int) -> PersistedDocumentLimits:
    values = {
        "max_bytes": 4096,
        "max_depth": 16,
        "max_nodes": 1000,
        "max_list_items": 100,
        "max_map_items": 100,
        "max_aliases": 8,
        "max_anchors": 8,
    }
    values.update(overrides)
    return PersistedDocumentLimits(**values)


def test_policy_json_loading_enforces_document_budgets() -> None:
    document = json.dumps(example())

    with pytest.raises(DocumentLimitError, match="byte limit"):
        parse_authorization_policy(
            document,
            document_limits=_document_limits(max_bytes=32),
        )

    with pytest.raises(DocumentLimitError, match="list cardinality"):
        parse_authorization_policy(
            document,
            document_limits=_document_limits(max_list_items=0 + 1),
        )


def test_policy_yaml_rejects_alias_expansion_and_cycles() -> None:
    pytest.importorskip("yaml")

    alias_heavy = """
version: 1
default_effect: deny
base: &base
  effect: allow
  operation: public.read
rules:
  - *base
  - *base
"""
    with pytest.raises(DocumentLimitError, match="alias limit"):
        parse_authorization_policy(
            alias_heavy,
            format="yaml",
            document_limits=_document_limits(max_aliases=1),
        )

    cyclic = """
version: 1
default_effect: deny
rules: &rules
  - effect: allow
    operation: public.read
    roles_any: *rules
"""
    with pytest.raises(DocumentLimitError, match="cyclic sequence"):
        parse_authorization_policy(
            cyclic,
            format="yaml",
            document_limits=_document_limits(),
        )


def test_policy_file_read_is_bounded_before_parsing(tmp_path) -> None:
    source = tmp_path / "policy.json"
    source.write_text(json.dumps(example()), encoding="utf-8")

    with pytest.raises(DocumentLimitError, match="byte limit"):
        load_authorization_policy(
            source,
            document_limits=_document_limits(max_bytes=32),
        )
