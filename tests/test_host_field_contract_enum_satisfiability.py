"""Host field contracts must be satisfiable by a single declared API call."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.host_field_contract import (
    HostFieldContract,
    RequiredEnumValue,
    select_authorized_field_contract,
)

VIEWER = PrincipalContext(subject="verified-host-viewer", roles=("viewer",))


def _router(parameters: list[tuple[str, dict]]) -> SchemaRouter:
    router = SchemaRouter(
        authorization_policy=AuthorizationPolicy(
            rules=(
                AuthorizationRule(
                    name="viewer-read",
                    effect="allow",
                    operation="*.*",
                    roles_any=("viewer",),
                ),
            ),
            default_effect="deny",
        ),
    )
    router.add_tool(ToolSpec(
        name="billing",
        description="Read transaction status",
        endpoints=[
            EndpointSpec(
                name="read",
                description="Read a transaction status",
                read_only=True,
                destructive=False,
                parameters=[
                    ParameterSpec(
                        name=name, location="query", json_schema=schema,
                    )
                    for name, schema in parameters
                ],
                output_fields=[FieldSpec(name="receipt")],
            ),
        ],
    ))
    return router


@pytest.mark.parametrize(
    ("parameters", "required", "expected"),
    [
        pytest.param(
            [("state", {"type": "string", "enum": ["paid", "unpaid"]})],
            [("state", "paid"), ("state", "unpaid")],
            "no_contract_match",
            id="contradictory-scalar-values-abstain",
        ),
        pytest.param(
            [("state", {"type": "string", "enum": ["paid", "unpaid"]})],
            [("state", "paid")],
            "unique_contract_match",
            id="single-scalar-value-unchanged",
        ),
        pytest.param(
            [
                ("state", {"type": "string", "enum": ["paid", "unpaid"]}),
                ("region", {"type": "string", "enum": ["apac", "emea"]}),
            ],
            [("state", "paid"), ("region", "apac")],
            "unique_contract_match",
            id="two-independent-scalar-parameters",
        ),
        pytest.param(
            [(
                "hourly",
                {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["wave_height", "ocean_current_velocity"],
                    },
                },
            )],
            [
                ("hourly", "wave_height"),
                ("hourly", "ocean_current_velocity"),
            ],
            "unique_contract_match",
            id="two-array-items-can-coexist",
        ),
        pytest.param(
            [(
                "hourly",
                {
                    "type": "array",
                    "maxItems": 1,
                    "items": {
                        "type": "string",
                        "enum": ["wave_height", "ocean_current_velocity"],
                    },
                },
            )],
            [
                ("hourly", "wave_height"),
                ("hourly", "ocean_current_velocity"),
            ],
            "no_contract_match",
            id="max-items-one-cannot-expose-two-values",
        ),
        pytest.param(
            [(
                "hourly",
                {
                    "type": "array",
                    "maxItems": 2,
                    "items": {
                        "type": "string",
                        "enum": ["wave_height", "ocean_current_velocity"],
                    },
                },
            )],
            [
                ("hourly", "wave_height"),
                ("hourly", "ocean_current_velocity"),
            ],
            "unique_contract_match",
            id="max-items-two-allows-two-distinct-values",
        ),
        pytest.param(
            [(
                "hourly",
                {"type": "array", "items": {"type": "number", "enum": ["x", "y"]}},
            )],
            [("hourly", "x"), ("hourly", "y")],
            "no_contract_match",
            id="contradictory-numeric-item-type-does-not-match",
        ),
    ],
)
def test_enum_conjunction_requires_one_satisfiable_call(
    parameters: list[tuple[str, dict]],
    required: list[tuple[str, str]],
    expected: str,
) -> None:
    router = _router(parameters)

    def must_not_execute(*args, **kwargs):
        raise AssertionError("field-contract diagnostics must never dispatch")

    router.plan = must_not_execute
    router.execute = must_not_execute
    receipt = select_authorized_field_contract(
        router,
        "check the exact provider-declared fields",
        principal=VIEWER,
        contract=HostFieldContract(
            operation="read",
            required_enums=[
                RequiredEnumValue(parameter=name, value=value)
                for name, value in required
            ],
        ),
        k=8,
    )
    assert receipt.reason == expected
    assert receipt.disposition == (
        "selected" if expected == "unique_contract_match" else "abstained"
    )
    assert receipt.selected_route_id == (
        "billing.read" if expected == "unique_contract_match" else None
    )


@pytest.mark.parametrize(
    ("schema", "required", "reason"),
    [
        pytest.param(
            {"type": "string", "enum": ["paid"], "not": {"const": "paid"}},
            ["paid"], "no_contract_match", id="not-excludes-enumerated-value",
        ),
        pytest.param(
            {"type": "string", "enum": ["paid"], "allOf": [
                {"pattern": "^unpaid$"},
            ]},
            ["paid"], "no_contract_match", id="composed-restriction-unsupported",
        ),
        pytest.param(
            {"type": "string", "enum": ["paid"], "pattern": "^unpaid$"},
            ["paid"], "no_contract_match", id="regex-restriction-unsupported",
        ),
        pytest.param(
            {"type": "string", "enum": ["paid"], "const": "unpaid"},
            ["paid"], "no_contract_match", id="contradictory-scalar-const",
        ),
        pytest.param(
            {
                "type": "array", "minItems": 3, "maxItems": 2,
                "items": {"type": "string", "enum": ["a", "b", "c"]},
            },
            ["a", "b"], "no_contract_match", id="impossible-array-bounds",
        ),
        pytest.param(
            {
                "type": "array", "minItems": 3, "uniqueItems": True,
                "items": {"type": "string", "enum": ["a", "b"]},
            },
            ["a", "b"], "no_contract_match", id="insufficient-unique-items",
        ),
        pytest.param(
            {
                "type": "array", "uniqueItems": True, "minItems": 2,
                "maxItems": 2,
                "items": {
                    "type": "string", "enum": ["a", "b"], "pattern": "^a$",
                },
            },
            ["a", "b"], "no_contract_match", id="array-item-extra-constraint",
        ),
        pytest.param(
            {
                "type": "array", "uniqueItems": True, "minItems": 2,
                "maxItems": 2,
                "items": {"type": "string", "enum": ["a", "b"]},
            },
            ["a", "b"], "unique_contract_match", id="verified-unique-array",
        ),
        pytest.param(
            {
                "type": "string", "enum": ["paid", "unpaid"],
                "const": "paid", "title": "Billing state",
                "description": "Only published billing states",
            },
            ["paid"], "unique_contract_match", id="matching-scalar-const",
        ),
        pytest.param(
            {"type": "array", "minItems": True,
             "items": {"type": "string", "enum": ["a"]}},
            ["a"], "no_contract_match", id="boolean-array-length-rejected",
        ),
    ],
)
def test_unhandled_json_schema_constraints_never_prove_field_fit(
    schema: dict, required: list[str], reason: str,
) -> None:
    router = _router([("state", schema)])

    def must_not_dispatch(*_args, **_kwargs):
        raise AssertionError("a read-only schema match must not dispatch")

    router.execute = must_not_dispatch
    router.plan = must_not_dispatch
    result = select_authorized_field_contract(
        router, "exact field-contract proof",
        principal=VIEWER,
        contract=HostFieldContract(
            operation="read",
            required_enums=[
                RequiredEnumValue(parameter="state", value=value)
                for value in required
            ],
        ),
        k=5,
    )
    assert result.reason == reason
    assert result.selected_route_id == (
        "billing.read" if reason == "unique_contract_match" else None
    )
