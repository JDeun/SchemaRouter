"""Registered source-shape routing contracts, not natural-language accuracy evidence."""
from __future__ import annotations

from copy import deepcopy

import pytest

from schemarouter import (
    AuthorizationPolicy,
    CapabilityFieldContract,
    DataScopeRule,
    EndpointSpec,
    ExecutionPlan,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    ToolCall,
    ToolSpec,
    UnitNormalizationSpec,
)
from schemarouter.errors import PolicyViolationError
from schemarouter.field_group_retrieval import _scalar_contract

ACTOR = PrincipalContext(subject="shape-review", roles=("reader",))
SHAPES = [
    {"type": ["string", "null"]},
    {"anyOf": [{"type": "string"}, {"type": "null"}]},
    {"type": "array", "items": {"type": "string"}},
    {"type": "object", "properties": {"label": {"type": "string"}},
     "required": ["label"], "additionalProperties": False},
    {"type": "object", "additionalProperties": {"type": "string"}},
    {"$defs": {"Value": {"type": "string"}}, "$ref": "#/$defs/Value"},
    {"definitions": {"Value": {"type": "string"}}, "$ref": "#/definitions/Value"},
]


def source(schema, *, wildcard=False, host=False, unit=False):
    from schemarouter import ParameterSpec

    field = FieldSpec(name="value", semantic_id="shape.value", identifier=True,
        path=["rows", "*", "value"] if wildcard else ["payload", "value"],
        result_path=["rows", "*", "answer"] if wildcard else ["answer"],
        json_schema=deepcopy(schema), unit="m" if unit else None,
        unit_normalization=UnitNormalizationSpec(canonical_unit="cm", dimension="length",
            scale=100, offset=0) if unit else None)
    contract = CapabilityFieldContract.from_field(field)
    assert contract is not None
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="shape.value", aliases=("requested value",), required_fields=(contract,),
        source_type="shapes", license="reviewed",
    ),))
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(default_effect="allow"))
    router.add_tool(ToolSpec(name="shapes", source_type="shapes", license="reviewed",
        endpoints=[EndpointSpec(name="read", read_only=True, output_fields=[field],
            input_schema={"type": "object", "properties": {"key": {"type": "string"}},
                "required": ["key"]} if host else {},
            parameters=[ParameterSpec(name="key", required=True,
                json_schema={"type": "string"})] if host else [],
        )]))
    session = router.prepare_field_routing(catalog=catalog,
        approved_host_roots=frozenset({"shapes.read"}) if host else frozenset())
    return router, session, field


@pytest.mark.parametrize("schema", SHAPES)
@pytest.mark.parametrize("wildcard", (False, True))
@pytest.mark.asyncio
async def test_public_query_maps_general_json_response_shape(schema, wildcard):
    router, session, field = source(schema, wildcard=wildcard)
    page = session.inspect_visible_fields(principal=ACTOR)
    assert page.routes[0].fields[0].semantic_id == "shape.value"
    intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id="information.lookup", required_concept_ids=(),
    ),))
    plan = await session.acompile_query("requested value", principal=ACTOR,
        model=lambda _: {"intent_id": "information.lookup", "needs": [
            {"concept": "requested value"},
        ]}, intent_registry=intents, model_visible_intent_ids=("information.lookup",))
    assert plan.status == "ready" and plan.coverage.complete
    call, = plan.calls
    assert call.call.fields == ["value"]
    meta, = call.fields_meta
    assert meta.source_path == tuple(field.projection_path)
    assert meta.result_path == tuple(field.result_projection_path)
    assert meta.json_schema == schema
    assert not _scalar_contract(schema)
    assert all(not item.produces for item in session._index._source_contracts)
    # The normal registry refresh path must not lose newly indexable shapes.
    original = router.registry.get("shapes")
    original.endpoint("read").output_fields[0].description = "refreshed review"
    router.registry.register(original.model_copy(deep=True), replace=True)
    refreshed = session.refresh()
    assert refreshed.compile("requested value", principal=ACTOR).status == "ready"


@pytest.mark.parametrize("schema", SHAPES)
def test_approved_general_response_is_direct_only_and_host_input_stays_scalar(schema):
    _, session, _ = source(schema, host=True)
    assert all(not item.produces for item in session._index._source_contracts)
    plan = session.compile("requested value", principal=ACTOR,
        host_source_arguments={"shapes.read": {"key": "host"}})
    assert plan.status == "ready" and plan.calls[0].call.arguments == {"key": "host"}
    with pytest.raises((ValueError, PolicyViolationError)):
        session.compile("requested value", principal=ACTOR,
            host_source_arguments={"shapes.read": {"key": ["not scalar"]}})


def test_numeric_array_units_reuse_canonical_contract_and_wildcard_paths():
    schema = {"type": ["array", "null"], "items": {"type": ["number", "null"]}}
    _, session, _ = source(schema, wildcard=True, unit=True)
    plan = session.compile("requested value", principal=ACTOR)
    assert plan.status == "ready"
    meta, = plan.calls[0].fields_meta
    assert meta.unit == "cm" and meta.source_unit == "m"
    assert meta.json_schema == schema
    assert meta.source_path == ("rows", "*", "value")


@pytest.mark.parametrize("wildcard", (False, True))
@pytest.mark.asyncio
async def test_hidden_source_descendant_blocks_parent_with_disjoint_result_path(wildcard):
    prefix = ["rows", "*"] if wildcard else ["profile"]
    fields = [
        FieldSpec(name="container", path=prefix + (["profile"] if wildcard else []),
            result_path=prefix + ["answer"] if wildcard else ["answer"],
            semantic_id="shape.value", json_schema={"type": "object"}),
        FieldSpec(name="hidden_alias", path=prefix + (["profile"] if wildcard else []) + ["secret"],
            result_path=prefix + ["hidden_copy"], json_schema={"type": "string"}),
        FieldSpec(name="safe", json_schema={"type": "string"}),
    ]
    policy = AuthorizationPolicy(default_effect="allow", data_rules=(DataScopeRule(
        operation="shapes.read", roles_any=("reader",), hidden_fields=("hidden_alias",),
    ),))
    router = SchemaRouter(authorization_policy=policy)
    tool = ToolSpec(name="shapes", source_type="shapes", license="reviewed",
        endpoints=[EndpointSpec(name="read", read_only=True, output_fields=fields)])
    router.add_tool(tool)
    endpoint = tool.endpoint("read")
    call = ToolCall(tool="shapes", endpoint="read", fields=["container"],
        tool_fingerprint=tool.fingerprint, schema_fingerprint=endpoint.fingerprint)
    with pytest.raises(PolicyViolationError):
        policy.validate_data_scope(ACTOR, tool, endpoint, call)
    scoped = router._data_scope_endpoint_view(ACTOR, tool, endpoint)
    assert scoped is not None
    assert [f.name for f in scoped.output_fields] == ["safe"]
    invocations = []

    def provider(**kwargs):
        invocations.append(kwargs)
        return {"profile": {"secret": "PRIVATE"}}

    router.executor.bind(tool.key, provider)
    plan = ExecutionPlan(query="container", registry_version=router.registry.version,
        calls=[call])
    with pytest.raises(PolicyViolationError):
        await router.execute(plan, config=RunConfig(principal=ACTOR))
    assert invocations == []
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="shape.value", aliases=("requested value",), source_type="shapes",
        license="reviewed", required_fields=(CapabilityFieldContract(
            semantic_id="shape.value", json_schema={"type": "object"},
        ),),
    ),))
    session = router.prepare_field_routing(catalog=catalog)
    assert session.inspect_visible_fields(principal=ACTOR).routes == ()
    assert session.compile("requested value", principal=ACTOR).status == "no_proven_hit"


@pytest.mark.parametrize("schema", [
    {}, {"unknown": "shape"}, {"type": "invalid"},
    {"anyOf": [{}]}, {"allOf": [True]},
    {"anyOf": [{"type": "string"}, {}]},
    {"$defs": {"Value": {}}, "$ref": "#/$defs/Value"},
    {"type": "array", "items": {"type": "string", "enum": []}},
    {"$ref": "https://example.invalid/schema"}, {"$ref": "#/$defs/missing"},
    {"$defs": {"Value": {"$ref": "#/$defs/Value"}}, "$ref": "#/$defs/Value"},
])
def test_unproved_response_contract_stays_rejected(schema):
    with pytest.raises(ValueError):
        source(schema)


@pytest.mark.parametrize("required,produced", [
    ({"type": "string"}, {"type": ["string", "null"]}),
    ({"type": "string", "oneOf": [{"const": "X"}]}, {"type": "string"}),
    ({"type": "array", "items": {"type": "string"}},
     {"type": "array", "items": {"type": "integer"}}),
    ({"type": "object", "properties": {"label": {"type": "string"}}, "required": ["label"]},
     {"type": "object", "properties": {"label": {"type": "string"}}}),
    ({"type": "object", "additionalProperties": {"type": "string"}},
     {"type": "object", "additionalProperties": {"type": "integer"}}),
    ({"$defs": {"Value": {"type": "string"}}, "$ref": "#/$defs/Value"},
     {"$defs": {"Value": {"type": "integer"}}, "$ref": "#/$defs/Value"}),
    ({"anyOf": [{"type": "string"}, {"type": "null"}]}, {"type": "integer"}),
])
def test_general_json_assertion_mismatch_is_not_a_proven_field(required, produced):
    from schemarouter.field_group_retrieval import _compatible_field

    assert not _compatible_field(
        CapabilityFieldContract(semantic_id="shape.value", json_schema=required),
        FieldSpec(name="value", semantic_id="shape.value", json_schema=produced),
    )


@pytest.mark.parametrize("schema", SHAPES)
def test_scoped_shape_details_are_not_recovered_from_hidden_raw_registry(schema):
    router, session, _ = source(schema)
    tool = router.registry.get("shapes")
    tool.endpoint("read").output_fields.append(
        FieldSpec(name="secret", json_schema={"type": "string"}),
    )
    router.registry.register(tool, replace=True)
    router.authorization_policy = AuthorizationPolicy(default_effect="allow",
        data_rules=(DataScopeRule(
            operation="shapes.read", roles_any=("reader",), hidden_fields=("secret",),
        ),),
    )
    # Build with current policy; this is not an authority-refresh bypass.
    session = router.prepare_field_routing(catalog=session._catalog)
    page = session.inspect_visible_fields(principal=ACTOR)
    for route in page.routes:
        private_keys = {"$defs", "$ref", "properties", "items", "anyOf"}
        assert all(not (field.json_schema.keys() & private_keys) for field in route.fields)
    plan = session.compile("requested value", principal=ACTOR)
    assert plan.status == ("ready" if schema == {"type": ["string", "null"]} else "no_proven_hit")


def test_review_contract_copy_cannot_mutate_source_or_plan():
    router, session, _ = source(SHAPES[2])
    page = session.inspect_visible_fields(principal=ACTOR)
    page.routes[0].fields[0].json_schema["items"]["type"] = "integer"
    assert router.registry.get("shapes").endpoint("read").output_fields[0].json_schema == SHAPES[2]
    plan = session.compile("requested value", principal=ACTOR)
    assert plan.calls[0].fields_meta[0].json_schema == SHAPES[2]


def test_hidden_wildcard_descendant_blocks_whole_array_but_keeps_safe_leaf():
    fields = [
        FieldSpec(name="rows", path=["rows"], result_path=["answer"],
            json_schema={"type": "array", "items": {"type": "object"}}),
        FieldSpec(name="private", path=["rows", "*", "secret"],
            result_path=["secret_copy", "*", "value"], json_schema={"type": "string"}),
        FieldSpec(name="public", path=["rows", "*", "label"],
            result_path=["public_copy", "*", "value"], json_schema={"type": "string"}),
    ]
    tool = ToolSpec(name="shapes", endpoints=[EndpointSpec(name="read", read_only=True,
        output_fields=fields)])
    policy = AuthorizationPolicy(default_effect="allow", data_rules=(DataScopeRule(
        operation="shapes.read", hidden_fields=("private",),
    ),))
    assert policy.data_scope(ACTOR, tool, tool.endpoint("read")).visible_fields == {"public"}


@pytest.mark.parametrize("schema", SHAPES[:3])
def test_general_response_eligibility_never_widens_host_input_shapes(schema):
    from schemarouter import ParameterSpec

    router, session, _ = source({"type": "object"})
    tool = router.registry.get("shapes")
    endpoint = tool.endpoint("read")
    endpoint.parameters = [ParameterSpec(name="key", required=True, json_schema=schema)]
    endpoint.input_schema = {"type": "object", "properties": {"key": schema}, "required": ["key"]}
    router.registry.register(tool, replace=True)
    with pytest.raises(ValueError, match="invalid explicit host-approved source"):
        router.prepare_field_routing(catalog=session._catalog,
            approved_host_roots=frozenset({"shapes.read"}))


def test_response_reference_expansion_is_bounded_without_network_or_dag_skip():
    from schemarouter.field_group_retrieval import _response_contract

    definitions = {"leaf": {"type": "string"}}
    for index in range(15):
        previous = "leaf" if index == 0 else f"node{index - 1}"
        definitions[f"node{index}"] = {"allOf": [
            {"$ref": f"#/$defs/{previous}"}, {"$ref": f"#/$defs/{previous}"},
        ]}
    assert not _response_contract({"$defs": definitions, "$ref": "#/$defs/node14"})


@pytest.mark.parametrize("schema", [
    {}, {"anyOf": [{}]}, {"allOf": [True]},
    {"anyOf": [{"type": "string"}, {}]},
    {"$defs": {"Value": {}}, "$ref": "#/$defs/Value"},
])
def test_generic_comparator_keeps_untyped_wrappers_unknown(schema):
    from schemarouter import compare_capability_fields

    contract = CapabilityFieldContract(semantic_id="shape.value", json_schema=schema)
    assert compare_capability_fields(contract, contract).status == "unknown"


@pytest.mark.parametrize("ref", ("#/$defs/Node", "https://example.invalid/remote"))
def test_generic_comparator_cannot_promote_recursive_or_external_typed_ref_target(ref):
    from schemarouter import compare_capability_fields
    from schemarouter.field_group_retrieval import _response_contract

    schema = {"$defs": {"Node": {"type": "string", "$ref": ref}}, "$ref": "#/$defs/Node"}
    contract = CapabilityFieldContract(semantic_id="shape.value", json_schema=schema)
    assert not _response_contract(schema)
    assert compare_capability_fields(contract, contract).status == "unknown"
