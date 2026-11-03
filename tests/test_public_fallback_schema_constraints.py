"""Real public fallback/corroboration must preserve the requested field schema."""
from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator

from schemarouter import (
    AuthorizationPolicy,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    InvocationUnavailableError,
    PlanRequest,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    ToolSpec,
    UnitNormalizationSpec,
    compare_capability_fields,
)
from schemarouter.validation import json_schemas_compatible

CASES = (
    ({"type": "string", "enum": ["open"]},
     {"type": "string", "enum": ["closed"]}, "open", "closed", False),
    ({"type": "boolean", "const": True},
     {"type": "boolean", "const": False}, True, False, False),
    ({"type": "number", "minimum": 0},
     {"type": "number", "minimum": -10}, 1, -1, False),
    ({"type": "string", "pattern": "^ok-"},
     {"type": "string", "pattern": "^bad-"}, "ok-value", "bad-value", False),
    ({"type": "array", "items": {"type": "number", "minimum": 0}},
     {"type": "array", "items": {"type": "number", "minimum": -1}}, [1], [-.5], False),
    ({"type": "array", "minItems": 1, "items": {"type": "integer"}},
     {"type": "array", "items": {"type": "integer"}}, [1], [], False),
    ({"type": "array", "items": False},
     {"type": "array", "items": True}, [], [1], False),
    ({"type": "array", "items": True},
     {"type": "array", "items": {"type": "integer"}}, [1.5], [2], True),
    ({"type": "number"}, {"type": "integer", "minimum": 0}, 1, 2, True),
    ({"type": "number", "minimum": 1, "description": "Primary declaration"},
     {"type": "integer", "minimum": 1.0, "description": "Backup declaration"}, 1, 2, True),
    ({"type": "number", "enum": [1]},
     {"type": "number", "enum": [1.0]}, 1, 1.0, True),
    ({"type": "array", "items": {"type": "number"}},
     {"type": "array", "items": {"type": "integer"}}, [1], [2], True),
)


def _router(
    required, candidate, primary_value, backup_value, mode, *, units=False, output_schema=None,
):
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(default_effect="allow"))
    invoked = []
    for name, schema, value in (
        ("primary", required, primary_value), ("backup", candidate, backup_value),
    ):
        field = FieldSpec(name="value", semantic_id="measurement.value", json_schema=schema)
        if units:
            field.unit = "m" if name == "primary" else "dm"
            field.unit_normalization = UnitNormalizationSpec(
                dimension="length", canonical_unit="m", scale=1 if name == "primary" else .1,
            )

        def invoke(endpoint, arguments, _name=name, _value=value):
            invoked.append(_name)
            if _name == "primary" and mode == "fallback":
                raise InvocationUnavailableError("primary unavailable")
            return {"value": _value}

        router.add_bound_tool(ToolSpec(
            name=name, provider=name, source_type="measurements", license="host-reviewed",
            endpoints=[EndpointSpec(name="read", description="measurement value",
                                    read_only=True, output_fields=[field],
                                    output_schema=output_schema or {})],
        ), invoke)
    return router, invoked


async def _check_public_dispatch(router, invoked, mode, allowed, required):
    actor = PrincipalContext(subject="reader")
    plan = router.plan_executable_authorized(PlanRequest(
        query="measurement value", preferred_tools=["primary"],
        fallback_scope="cross_provider" if mode == "fallback" else "disabled",
        retrieval_mode="corroborate" if mode == "corroborate" else "coverage",
        max_calls=2 if mode == "corroborate" else 1,
    ), principal=actor)
    route = plan.fallback_route(0)
    actual = (
        [call.tool for call in route.alternatives] if route is not None else []
    ) if mode == "fallback" else [call.tool for call in plan.calls[1:]]
    assert actual == (["backup"] if allowed else [])
    assert invoked == [], "Planning must not invoke either registered provider"
    if mode == "fallback" and not allowed:
        with pytest.raises(InvocationUnavailableError):
            await router.execute(plan, config=RunConfig(principal=actor))
        assert invoked == ["primary"], "An incompatible backup must never be dispatched"
    else:
        results = await router.execute(plan, config=RunConfig(principal=actor))
        assert invoked == (["primary", "backup"] if allowed else ["primary"])
        for result in results:
            Draft202012Validator(required).validate(result.data["value"])


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ("fallback", "corroborate"))
@pytest.mark.parametrize("required,candidate,primary_value,backup_value,allowed", CASES)
async def test_public_provider_substitution_preserves_schema_assertions(
    mode, required, candidate, primary_value, backup_value, allowed,
):
    router, invoked = _router(required, candidate, primary_value, backup_value, mode)
    await _check_public_dispatch(router, invoked, mode, allowed, required)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ("fallback", "corroborate"))
@pytest.mark.parametrize("allowed", (True, False))
async def test_public_provider_substitution_compares_canonical_unit_bounds(mode, allowed):
    required = {"type": "number", "minimum": 0, "maximum": 1}
    candidate = {"type": "integer", "minimum": 0, "maximum": 10 if allowed else 20}
    router, invoked = _router(required, candidate, .5, 5 if allowed else 20, mode, units=True)
    await _check_public_dispatch(router, invoked, mode, allowed, required)


@pytest.mark.parametrize("keyword,required_value,candidate_value", (
    ("enum", [1], [True]), ("const", 1, True),
))
def test_public_fallback_does_not_treat_boolean_assertions_as_numeric(
    keyword, required_value, candidate_value,
):
    router, invoked = _router(
        {"type": "number", keyword: required_value},
        {"type": "number", keyword: candidate_value}, 1, True, "fallback",
    )
    plan = router.plan_executable_authorized(PlanRequest(
        query="measurement value", preferred_tools=["primary"], fallback_scope="cross_provider",
    ), principal=PrincipalContext(subject="reader"))
    assert plan.fallback_route(0) is None
    assert invoked == []


def test_opaque_assertions_cannot_change_meaning_when_array_items_narrow():
    required = {
        "type": "array", "items": {"type": ["number", "array"], "items": {"type": "number"}},
        "not": {"$ref": "#/items"},
    }
    candidate = {
        "type": "array", "items": {"type": ["number", "array"], "items": {"type": "integer"}},
        "not": {"$ref": "#/items"},
    }
    assert Draft202012Validator(candidate).is_valid([1.5])
    assert not Draft202012Validator(required).is_valid([1.5])
    assert not json_schemas_compatible(required, candidate)
    assert compare_capability_fields(
        CapabilityFieldContract(semantic_id="value", json_schema=required),
        CapabilityFieldContract(semantic_id="value", json_schema=candidate),
    ).status == "unknown"


def _boolean_items_reference_schemas():
    branches = [{"const": [1]}, {"not": {"$ref": "#/items"}}]
    return (
        {"type": "array", "items": True, "anyOf": branches},
        {"type": "array", "items": False, "anyOf": branches},
    )


def test_opaque_assertions_cannot_change_meaning_when_boolean_items_narrow():
    required, candidate = _boolean_items_reference_schemas()
    assert Draft202012Validator(required).is_valid([1])
    assert not Draft202012Validator(required).is_valid([])
    assert Draft202012Validator(candidate).is_valid([])
    assert not json_schemas_compatible(required, candidate)
    assert compare_capability_fields(
        CapabilityFieldContract(semantic_id="value", json_schema=required),
        CapabilityFieldContract(semantic_id="value", json_schema=candidate),
    ).status == "unknown"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ("fallback", "corroborate"))
async def test_public_fallback_preserves_opaque_assertions_with_boolean_items(mode):
    required, candidate = _boolean_items_reference_schemas()
    # Each field's local reference is evaluated against its own declared value schema.
    router, invoked = _router(required, candidate, [1], [], mode, output_schema={
        "type": "object", "properties": {"value": {"type": "array"}}, "required": ["value"],
    })
    await _check_public_dispatch(router, invoked, mode, False, required)
