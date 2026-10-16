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
