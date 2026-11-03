"""Original scalar assertions survive field discovery, planning and native execution."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeDeclaredFieldGroup,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
    UnitNormalizationSpec,
    observe_and_execute_paper_plan,
    retrieve_authorized_field_group,
)
from schemarouter.errors import SchemaValidationError
from schemarouter.field_group_retrieval import _scalar_contract

ALIASES = ("record value", "레코드 값", "レコードの値")
READER = PrincipalContext(subject="reader", roles=("reader",))
SCALARS = [
    ({"type": "string", "enum": ["open", "closed"]}, "open", "cancelled"),
    ({"type": "integer", "minimum": 1, "maximum": 10}, 5, 11),
    ({"type": "integer", "minimum": 0, "multipleOf": 2}, 4, 3),
    ({"type": "number", "exclusiveMinimum": 0, "maximum": 1}, 0.5, 0),
    ({"type": "string", "minLength": 3, "maxLength": 8, "pattern": "^[A-Z]+$"},
     "OPEN", "lower"),
    ({"type": "boolean", "const": True}, True, False),
]


def _fixture(schema, value):
    required = CapabilityFieldContract(semantic_id="record.value", json_schema=schema)
    group = NativeDeclaredFieldGroup(
        aliases=ALIASES, required_fields=(required,),
        source_type="records", license="host-reviewed",
    )
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="record.value", aliases=ALIASES, required_fields=(required,),
        source_type="records", license="host-reviewed",
    ),))
    seen = []
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader", "viewer"),
        ),),
        data_rules=(DataScopeRule(
            operation="records.read", roles_any=("viewer",), hidden_fields=("value",),
        ),),
    ))

    def invoke(endpoint, arguments):
        seen.append((endpoint, dict(arguments)))
        return {"record_id": "record-1", "value": value, "unused": "omit"}

    router.add_bound_tool(ToolSpec(
        name="records", source_type="records", license="host-reviewed",
        endpoints=[EndpointSpec(
            name="read", read_only=True, output_fields=[
                FieldSpec(name="record_id", semantic_id="record.id", identifier=True,
                          json_schema={"type": "string"}),
                FieldSpec(name="value", semantic_id="record.value", json_schema=schema),
                FieldSpec(name="unused", json_schema={"type": "string"}),
            ],
        )],
    ), invoke)
    return router, group, catalog, seen


@pytest.mark.parametrize("schema,valid,invalid", SCALARS)
@pytest.mark.parametrize("query", ALIASES)
async def test_constrained_scalar_survives_public_field_routing_and_execution(
    schema, valid, invalid, query,
):
    router, group, catalog, seen = _fixture(schema, valid)
    baseline = router.retrieve_authorized(query, principal=READER)
    assert [candidate.route_id for candidate in retrieve_authorized_field_group(
        router, query, principal=READER, group=group,
    ).candidates] == ["records.read"]
    session = router.prepare_field_routing(catalog=catalog)
    assert session.discover(query, principal=READER).status == "complete"
    plan = session.compile(query, principal=READER)
    assert plan.status == "ready"
    assert plan.calls[0].call.fields == ["record_id", "value"]
    assert seen == []
    result, = await session.aexecute_direct(query, principal=READER)
    assert result.data == {"record_id": "record-1", "value": valid}
    assert seen == [("read", {})]
    assert router.retrieve_authorized(query, principal=READER) == baseline


@pytest.mark.parametrize("schema,valid,invalid", SCALARS)
async def test_original_scalar_assertions_still_validate_actual_provider_values(
    schema, valid, invalid,
):
    router, _group, catalog, seen = _fixture(schema, invalid)
    session = router.prepare_field_routing(catalog=catalog)
    with pytest.raises(SchemaValidationError):
        await session.aexecute_direct(ALIASES[0], principal=READER)
    assert seen == [("read", {})]


@pytest.mark.parametrize("principal", [
    PrincipalContext(subject="guest", roles=("guest",)),
    PrincipalContext(subject="viewer", roles=("viewer",)),
])
def test_scalar_assertions_never_bypass_principal_or_hidden_field_scope(principal):
    router, group, catalog, seen = _fixture(SCALARS[0][0], "open")
    assert not retrieve_authorized_field_group(
        router, ALIASES[0], principal=principal, group=group,
    ).candidates
    session = router.prepare_field_routing(catalog=catalog)
    assert session.discover(ALIASES[0], principal=principal).status == "no_proven_hit"
    assert seen == []


@pytest.mark.parametrize("schema", [
    {"type": "number", "minimum": float("nan")},
    {"type": "string", "enum": []},
    {"type": "integer", "minimum": "zero"},
    {"type": "number", "multipleOf": 0},
    {"type": "string", "pattern": "(a+)+$"},
    {"type": "string", "pattern": "x" * 257},
    {"type": "string", "oneOf": [{"const": "open"}]},
    {"type": "string", "$ref": "https://invalid.test/schema"},
    {"type": ["string", "null"]},
])
def test_malformed_or_unproven_scalar_schemas_are_rejected(schema):
    assert not _scalar_contract(schema)


def test_schema_validation_rechecks_mutated_content_and_live_authorization():
    schema = {"type": "string", "enum": ["open", "closed"]}
    assert _scalar_contract(schema)
    schema["enum"].clear()
    assert not _scalar_contract(schema)
    schema["enum"].append("open")
    router, _group, catalog, seen = _fixture(schema, "open")
    session = router.prepare_field_routing(catalog=catalog)
    assert session.discover(ALIASES[0], principal=READER).status == "complete"
    router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    assert session.discover(ALIASES[0], principal=READER).status == "no_proven_hit"
    assert seen == []


def test_affine_normalization_does_not_reuse_untransformed_numeric_bounds():
    schema = {"type": "number", "minimum": 0}
    router, group, catalog, seen = _fixture(schema, 5)
    source = router.registry.get("records")
    value = source.endpoint("read").output_fields[1]
    value.unit = "degC"
    value.unit_normalization = UnitNormalizationSpec(
        dimension="temperature", canonical_unit="K", scale=1, offset=273.15,
    )
    router.registry.register(source, replace=True)
    assert not retrieve_authorized_field_group(
        router, ALIASES[0], principal=READER, group=group,
    ).candidates
    assert router.prepare_field_routing(catalog=catalog).discover(
        ALIASES[0], principal=READER,
    ).status == "no_proven_hit"
    assert seen == []


async def test_canonical_unit_bounds_reach_public_field_plan_and_execution():
    router, _group, _catalog, seen = _fixture(
        {"type": "number", "minimum": 0, "maximum": 100}, 25,
    )
    source = router.registry.get("records")
    value = source.endpoint("read").output_fields[1]
    value.unit = "degC"
    value.unit_normalization = UnitNormalizationSpec(
        dimension="temperature", canonical_unit="K", scale=1, offset=273.15,
    )
    invoker = router.executor._binding_snapshot("records").invoker
    assert invoker is not None
    router.add_bound_tool(source, invoker, replace=True)
    required = CapabilityFieldContract(
        semantic_id="record.value", unit="K", dimension="temperature",
        json_schema={"type": "number", "minimum": 273.15, "maximum": 373.15},
    )
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="record.value", aliases=ALIASES, required_fields=(required,),
        source_type="records", license="host-reviewed",
    ),))
    session = router.prepare_field_routing(catalog=catalog)
    plan = session.compile(ALIASES[0], principal=READER)
    assert plan.status == "ready"
    value_meta = next(field for field in plan.calls[0].fields_meta if field.name == "value")
    assert value_meta.source_unit == "degC" and value_meta.unit == "K"
    result, = await session.aexecute_direct(ALIASES[0], principal=READER)
    assert result.data == {"record_id": "record-1", "value": 298.15}
    assert seen == [("read", {})]


async def test_constrained_identifier_flows_through_original_producer_and_consumer():
    schema, valid, _invalid = SCALARS[0]
    router, _group, catalog, seen = _fixture(schema, valid)
    identifier_schema = {"type": "string", "minLength": 8, "pattern": "^record-[0-9]+$"}
    consumer = router.registry.get("records")
    endpoint = consumer.endpoint("read")
    endpoint.parameters = [ParameterSpec(
        name="record_id", semantic_id="record.id", required=True,
        json_schema=identifier_schema,
    )]
    endpoint.input_schema = {
        "type": "object", "properties": {"record_id": identifier_schema},
        "required": ["record_id"], "additionalProperties": False,
    }

    def consume(name, arguments):
        assert arguments == {"record_id": "record-1"}
        seen.append(("consumer", dict(arguments)))
        return {"record_id": arguments["record_id"], "value": valid, "unused": "omit"}

    router.add_bound_tool(consumer, consume, replace=True)
    def produce(name, arguments):
        seen.append(("producer", dict(arguments)))
        return {"record_id": "record-1"}

    router.add_bound_tool(ToolSpec(
        name="root", source_type="records", license="host-reviewed",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            output_schema={"type": "object", "properties": {
                "record_id": identifier_schema,
            }, "required": ["record_id"]},
            output_fields=[FieldSpec(
                name="record_id", semantic_id="record.id", identifier=True,
                json_schema=identifier_schema,
            )],
        )],
    ), produce)
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    output = await observe_and_execute_paper_plan(
        router, ALIASES[0], principal=READER, catalog=catalog, index=index,
    )
    assert seen == [("producer", {}), ("consumer", {"record_id": "record-1"})]
    assert output.producer.data == {"record_id": "record-1"}
    assert output.consumers[0].data == {"record_id": "record-1", "value": valid}
