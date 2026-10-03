from __future__ import annotations

import pytest

from schemarouter.authorization import PrincipalContext
from schemarouter.data_scope import (
    DataScopePolicy,
    DataScopeRule,
    PrincipalScopedRegistry,
    TrustedDataPredicate,
)
from schemarouter.errors import PolicyViolationError, RegistrationError
from schemarouter.models import EndpointSpec, FieldSpec, ParameterSpec, ToolSpec
from schemarouter.registry import InMemoryRegistry


def _tool() -> ToolSpec:
    return ToolSpec(
        name="employees",
        namespace="company",
        provider="company",
        access_mode="sqlite",
        source_type="database",
        endpoints=[
            EndpointSpec(
                name="select",
                read_only=True,
                destructive=False,
                output_fields=[
                    FieldSpec(name="id", json_schema={"type": "integer"}),
                    FieldSpec(name="name", json_schema={"type": "string"}),
                    FieldSpec(name="department", json_schema={"type": "string"}),
                    FieldSpec(name="salary", json_schema={"type": "number"}),
                ],
                output_schema={
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                            "department": {"type": "string"},
                            "salary": {"type": "number"},
                        },
                    },
                },
            )
        ],
    )


def _policy() -> DataScopePolicy:
    return DataScopePolicy(
        rules=(
            DataScopeRule(
                name="executive",
                operation="company.employees.select",
                roles_any=("executive",),
                allow_fields=("*",),
            ),
            DataScopeRule(
                name="manager-department",
                operation="company.employees.select",
                roles_any=("manager",),
                allow_fields=("id", "name", "department", "salary"),
                trusted_predicates=(
                    TrustedDataPredicate(
                        field="department",
                        source="departments",
                        operator="in",
                    ),
                ),
            ),
            DataScopeRule(
                name="employee-department",
                operation="company.employees.select",
                roles_any=("employee",),
                allow_fields=("id", "name", "department"),
                deny_fields=("salary",),
                trusted_predicates=(
                    TrustedDataPredicate(
                        field="department",
                        source="departments",
                        operator="in",
                    ),
                ),
            ),
        )
    )


def test_employee_field_scope_hides_salary_and_resolves_department_filter() -> None:
    tool = _tool()
    endpoint = tool.endpoint("select")
    principal = PrincipalContext(
        subject="alice",
        roles=("employee",),
        departments=("engineering",),
    )

    decision = _policy().evaluate(principal, tool, endpoint)

    assert decision.matched is True
    assert decision.rule_name == "employee-department"
    assert decision.visible_fields == ("id", "name", "department")
    assert len(decision.trusted_predicates) == 1
    predicate = decision.trusted_predicates[0]
    assert predicate.field == "department"
    assert predicate.operator == "in"
    assert predicate.value == ("engineering",)


def test_manager_can_see_salary_but_only_for_trusted_departments() -> None:
    tool = _tool()
    endpoint = tool.endpoint("select")
    principal = PrincipalContext(
        subject="manager-1",
        roles=("manager",),
        departments=("sales", "engineering"),
    )

    decision = _policy().evaluate(principal, tool, endpoint)

    assert decision.visible_fields == ("id", "name", "department", "salary")
    assert decision.trusted_predicates[0].value == ("sales", "engineering")


def test_executive_rule_can_expose_all_declared_fields_without_row_predicate() -> None:
    tool = _tool()
    endpoint = tool.endpoint("select")
    principal = PrincipalContext(subject="ceo", roles=("executive",))

    decision = _policy().evaluate(principal, tool, endpoint)

    assert decision.visible_fields == ("id", "name", "department", "salary")
    assert decision.trusted_predicates == ()


def test_unmatched_principal_is_fail_closed() -> None:
    tool = _tool()
    endpoint = tool.endpoint("select")
    principal = PrincipalContext(subject="contractor", roles=("contractor",))

    decision = _policy().evaluate(principal, tool, endpoint)

    assert decision.matched is False
    assert decision.visible_fields == ()
    with pytest.raises(PolicyViolationError, match="data scope denied"):
        _policy().trusted_predicates(principal, tool, endpoint)


def test_hidden_or_empty_field_projection_is_denied() -> None:
    tool = _tool()
    endpoint = tool.endpoint("select")
    principal = PrincipalContext(
        subject="alice",
        roles=("employee",),
        departments=("engineering",),
    )

    policy = _policy()
    policy.validate_fields(principal, tool, endpoint, ["id", "name"])

    with pytest.raises(PolicyViolationError, match="requested fields"):
        policy.validate_fields(principal, tool, endpoint, ["id", "salary"])

    with pytest.raises(PolicyViolationError, match="requested fields"):
        policy.validate_fields(principal, tool, endpoint, [])


def test_attribute_backed_predicate_requires_present_verified_claim() -> None:
    predicate = TrustedDataPredicate(
        field="tenant_id",
        source="attribute",
        attribute="tenant_id",
    )
    principal = PrincipalContext(subject="alice")

    with pytest.raises(
        PolicyViolationError,
        match="cannot be resolved",
    ):
        predicate.resolve(principal)


def test_subject_and_attribute_predicates_resolve_without_model_arguments() -> None:
    principal = PrincipalContext(
        subject="user-123",
        attributes={"tenant_id": "tenant-7"},
    )
    subject = TrustedDataPredicate(field="owner_id", source="subject")
    tenant = TrustedDataPredicate(
        field="tenant_id",
        source="attribute",
        attribute="tenant_id",
    )

    assert subject.resolve(principal) == "user-123"
    assert tenant.resolve(principal) == "tenant-7"


def test_field_globs_can_hide_sensitive_columns_without_listing_every_safe_field() -> None:
    tool = _tool()
    endpoint = tool.endpoint("select")
    principal = PrincipalContext(
        subject="auditor",
        roles=("auditor",),
    )
    policy = DataScopePolicy(
        rules=(
            DataScopeRule(
                name="auditor",
                operation="company.employees.*",
                roles_any=("auditor",),
                allow_fields=("*",),
                deny_fields=("salary",),
            ),
        )
    )

    assert policy.visible_fields(principal, tool, endpoint) == (
        "id",
        "name",
        "department",
    )


def test_rule_can_match_provider_and_access_mode() -> None:
    tool = _tool()
    endpoint = tool.endpoint("select")
    principal = PrincipalContext(subject="alice", roles=("employee",))
    policy = DataScopePolicy(
        rules=(
            DataScopeRule(
                name="wrong-provider",
                operation="*",
                provider="other",
                roles_any=("employee",),
                allow_fields=("*",),
            ),
            DataScopeRule(
                name="sqlite-company",
                operation="*",
                provider="company",
                access_mode="sqlite",
                roles_any=("employee",),
                allow_fields=("id",),
            ),
        )
    )

    decision = policy.evaluate(principal, tool, endpoint)
    assert decision.rule_name == "sqlite-company"
    assert decision.visible_fields == ("id",)


def test_principal_scoped_registry_projects_fields_before_analyzer_access() -> None:
    tool = _tool()
    endpoint = tool.endpoint("select")
    endpoint.parameters = [
        ParameterSpec(
            name="id",
            json_schema={"type": "integer"},
            location="argument",
        ),
        ParameterSpec(
            name="salary",
            json_schema={"type": "number"},
            location="argument",
        ),
        ParameterSpec(
            name="limit",
            json_schema={"type": "integer"},
            location="argument",
        ),
    ]
    registry = InMemoryRegistry()
    registry.register(tool)

    principal = PrincipalContext(
        subject="alice",
        roles=("employee",),
        departments=("engineering",),
    )
    scoped = PrincipalScopedRegistry(
        registry,
        principal=principal,
        data_scope_policy=_policy(),
    )

    visible = scoped.get("company.employees").endpoint("select")
    assert [field.name for field in visible.output_fields] == [
        "id",
        "name",
        "department",
    ]
    assert [parameter.name for parameter in visible.parameters] == ["id", "limit"]
    assert set(visible.output_schema["items"]["properties"]) == {
        "id",
        "name",
        "department",
    }
    assert scoped.original_tool_fingerprint("company.employees") == registry.get(
        "company.employees"
    ).fingerprint
    assert scoped.original_endpoint_fingerprint(
        "company.employees",
        "select",
    ) == registry.endpoint("company.employees", "select").fingerprint


def test_principal_scoped_registry_removes_unmatched_database_capability() -> None:
    registry = InMemoryRegistry()
    registry.register(_tool())
    principal = PrincipalContext(subject="contractor", roles=("contractor",))

    scoped = PrincipalScopedRegistry(
        registry,
        principal=principal,
        data_scope_policy=_policy(),
    )

    assert scoped.keys() == ()


def test_principal_scoped_registry_applies_capability_authorization_first() -> None:
    from schemarouter.authorization import AuthorizationPolicy, AuthorizationRule

    registry = InMemoryRegistry()
    registry.register(_tool())
    principal = PrincipalContext(
        subject="alice",
        roles=("employee",),
        departments=("engineering",),
    )
    authorization = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="deny",
                operation="company.employees.select",
                roles_any=("employee",),
            ),
        )
    )

    scoped = PrincipalScopedRegistry(
        registry,
        principal=principal,
        authorization_policy=authorization,
        data_scope_policy=_policy(),
    )

    assert scoped.keys() == ()


def test_principal_scoped_registry_is_read_only() -> None:
    registry = InMemoryRegistry()
    registry.register(_tool())
    principal = PrincipalContext(subject="ceo", roles=("executive",))
    scoped = PrincipalScopedRegistry(
        registry,
        principal=principal,
        data_scope_policy=_policy(),
    )

    with pytest.raises(RegistrationError, match="read-only"):
        scoped.register(_tool())


def test_multi_value_claim_predicate_requires_in_operator() -> None:
    with pytest.raises(ValueError, match="requires operator='in'"):
        TrustedDataPredicate(
            field="department",
            source="departments",
            operator="eq",
        )
