"""#1771: user-owned schema routing, without any provider data execution."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperUnderstanding,
    ParameterSpec,
    SchemaFieldRoutingSession,
    SchemaRouter,
    SQLiteRegistry,
    ToolSpec,
    retrieve_paper_field_coverage,
)
from schemarouter.errors import PolicyViolationError
from schemarouter.paper_query_understanding import compile_model_query
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    ALIASES,
    GROUP,
    LEFT,
    RIGHT,
    ROOT,
    build_fixture,
)


def _catalog() -> NativeConceptCatalog:
    return NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="crm.customer_fields",
        aliases=ALIASES,
        required_fields=GROUP.required_fields,
        source_type=GROUP.source_type,
        license=GROUP.license,
    ),))


def _revised_catalog() -> NativeConceptCatalog:
    return NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="crm.customer_fields",
        aliases=("account owner", "계정 담당자", "アカウント担当者"),
        required_fields=GROUP.required_fields,
        source_type=GROUP.source_type,
        license=GROUP.license,
    ),))


def test_visible_field_review_bootstraps_without_preapproved_concept_catalog(monkeypatch):
    router = build_fixture(500)
    session = router.prepare_field_routing()

    def forbidden(*args, **kwargs):
        pytest.fail("review and owner catalog approval must never call providers")

    with monkeypatch.context() as scope:
        scope.setattr(router.executor, "execute", forbidden)
        scope.setattr(router.executor, "execute_call", forbidden)
        review = session.inspect_visible_fields(principal=ACTOR, limit=64)
        assert any(route.route_id == LEFT for route in review.routes)
        with pytest.raises(PolicyViolationError, match="catalog|review"):
            _ = session.catalog_revision_id
        with pytest.raises(PolicyViolationError, match="catalog|review"):
            session.discover(ALIASES[0], principal=ACTOR)
        with pytest.raises(PolicyViolationError, match="catalog|review"):
            session.compile(ALIASES[0], principal=ACTOR)
        with pytest.raises(PolicyViolationError, match="catalog|review"):
            session.compile_understood(
                PaperUnderstanding(intent_id="crm.review"),
                principal=ACTOR,
                intent_registry=PaperIntentRegistry(intents=(
                    PaperIntentDeclaration(
                        intent_id="crm.review", required_concept_ids=(
                            "crm.customer_fields",
                        ),
                    ),
                )),
            )

        activated = session.revise_catalog(catalog=_catalog())
        assert activated.snapshot_id == session.snapshot_id
        assert activated._index is session._index
        assert activated.discover(ALIASES[0], principal=ACTOR).status == "complete"
        with pytest.raises(PolicyViolationError, match="catalog|review"):
            session.discover(ALIASES[0], principal=ACTOR)


@pytest.mark.asyncio
async def test_review_only_session_rejects_model_calls_before_owner_approval():
    session = build_fixture(500).prepare_field_routing()

    async def forbidden_model(_payload):
        pytest.fail("unapproved review session cannot call a model")

    with pytest.raises(PolicyViolationError, match="catalog|review"):
        await session.acompile_query(
            "customer owner", principal=ACTOR,
            model=forbidden_model,
            intent_registry=PaperIntentRegistry(intents=(
                PaperIntentDeclaration(
                    intent_id="crm.review", required_concept_ids=(
                        "crm.customer_fields",
                    ),
                ),
            )),
            model_visible_intent_ids=("crm.review",),
            model_visible_concept_ids=("crm.customer_fields",),
        )


@pytest.mark.asyncio
async def test_direct_model_compiler_requires_approved_catalog_before_model():
    """The standalone compiler must enforce the same review-only gate."""
    review_only = build_fixture(500).prepare_field_routing()

    async def forbidden_model(_payload):
        pytest.fail("unapproved session must never expose a model menu")

    with pytest.raises(PolicyViolationError, match="catalog"):
        await compile_model_query(
            review_only, "customer owner", principal=ACTOR,
            model=forbidden_model,
            intent_registry=PaperIntentRegistry(intents=(
                PaperIntentDeclaration(
                    intent_id="crm.review", required_concept_ids=(
                        "crm.customer_fields",
                    ),
                ),
            )),
            model_visible_intent_ids=("crm.review",),
            model_visible_concept_ids=("crm.customer_fields",),
        )


def test_review_only_session_can_refresh_before_owner_catalog_approval():
    router = build_fixture(500)
    review_session = router.prepare_field_routing()
    router.add_tool(ToolSpec(
        name="extra_review_source", source_type="crm", license="owner-approved",
        endpoints=[EndpointSpec(name="read", read_only=True, output_fields=[
            FieldSpec(name="reference", semantic_id="crm.reference",
                      json_schema={"type": "string"}),
        ])],
    ))
    refreshed = review_session.refresh()
    page = refreshed.inspect_visible_fields(
        principal=ACTOR, after_route="extra_", limit=32,
    )
    assert any(item.route_id == "extra_review_source.read" for item in page.routes)
    assert refreshed.revise_catalog(catalog=_catalog()).discover(
        ALIASES[0], principal=ACTOR,
    ).status == "complete"
    with pytest.raises(PolicyViolationError, match="stale|changed|source"):
        review_session.inspect_visible_fields(principal=ACTOR)


def test_visible_field_review_pages_source_proven_metadata_without_provider_io(
    monkeypatch,
):
    router = build_fixture(500, mixed_scope=True)
    session = router.prepare_field_routing(catalog=_catalog())

    def forbidden(*args, **kwargs):
        pytest.fail("field review must not scan the registry or execute data tools")

    with monkeypatch.context() as scope:
        scope.setattr(router.registry, "tools", forbidden)
        scope.setattr(router.registry, "keys", forbidden)
        scope.setattr(router.executor, "execute", forbidden)
        scope.setattr(router.executor, "execute_call", forbidden)
        pages = []
        cursor = None
        for _ in range(12):
            page = session.inspect_visible_fields(
                principal=ACTOR, after_route=cursor, limit=64,
            )
            pages.append(page)
            assert page.snapshot_id == session.snapshot_id
            assert not page.executable_authority
            assert len(page.routes) <= 64
            if page.next_after_route is None:
                break
            cursor = page.next_after_route
        else:
            pytest.fail("bounded review pagination did not terminate")

    found = {route.route_id: route for page in pages for route in page.routes}
    assert len(found) == sum(len(page.routes) for page in pages)
    assert list(found) == sorted(found)
    assert LEFT in found and RIGHT in found and ROOT in found
    assert "fork_status_denied.read" not in found
    assert "fork_owner_hidden.read" not in found
    assert tuple((f.name, f.semantic_id, f.json_type) for f in found[LEFT].fields) == (
        ("status", "crm.fork_status", "string"),
    )
    assert found[LEFT].source_type == "crm"
    assert found[LEFT].license == "host-reviewed-synthetic"
    assert not found[LEFT].fields[0].identifier


def test_visible_field_review_includes_typed_inputs_before_catalog_approval():
    """Missing input projection breaks review-first P2 authoring."""
    router = build_fixture(500)
    review_only = router.prepare_field_routing()
    page = review_only.inspect_visible_fields(
        principal=ACTOR, after_route="fork_", limit=64,
    )
    routes = {route.route_id: route for route in page.routes}
    assert routes[ROOT].parameters_meta == ()
    assert tuple((param.name, param.required, param.location, param.json_types)
                 for param in routes[RIGHT].parameters_meta) == (
        ("customer_id", True, "argument", ("string",)),
    )
    assert routes[LEFT].parameters_meta == routes[RIGHT].parameters_meta

    approved = review_only.revise_catalog(catalog=_catalog())
    planned = approved.compile(ALIASES[0], principal=ACTOR)
    compiled = {call.route_id: call.parameters_meta for call in planned.calls}
    assert compiled[LEFT] == routes[LEFT].parameters_meta
    assert compiled[RIGHT] == routes[RIGHT].parameters_meta
    assert not page.executable_authority


def test_visible_field_review_hides_scoped_parameter_aliases_and_annotations():
    """Denied output aliases must not be repeated as input metadata."""
    secret = "internal_alias_do_not_disclose"
    router = build_fixture(500)
    tool = router.registry.get("fork_owner")
    parameter = tool.endpoints[0].parameters[0]
    parameter.description = f"secret credential {secret}"
    parameter.wire_name = f"X-{secret}"
    parameter.aliases = [secret]
    tool.endpoints[0].parameters.append(ParameterSpec(
        name=secret, json_schema={"type": "string"},
    ))
    tool.endpoints[0].output_fields.append(FieldSpec(
        name="private_col", aliases=[secret],
        json_schema={"type": "string"},
    ))
    router.add_tool(tool, replace=True)
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(effect="allow", operation="*.read",
                                 roles_any=("reader",)),),
        data_rules=(DataScopeRule(
            operation=RIGHT, roles_any=("reader",),
            hidden_fields=("private_col",),
        ),),
    )
    page = router.prepare_field_routing().inspect_visible_fields(
        principal=ACTOR, after_route="fork_", limit=64,
    )
    route = next(route for route in page.routes if route.route_id == RIGHT)
    assert tuple((p.name, p.json_types) for p in route.parameters_meta) == (
        ("customer_id", ("string",)),
    )
    assert secret not in repr(route)
    assert "credential" not in repr(route)


def test_visible_field_review_refuses_oversized_input_inventory():
    """A maliciously wide declared input shape cannot bypass page budgets."""
    router = build_fixture(500)
    router.add_tool(ToolSpec(
        name="wide_input_review", source_type="crm", license="approved",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            parameters=[ParameterSpec(
                name=f"input_{index}", json_schema={"type": "string"},
            ) for index in range(513)],
            output_fields=[FieldSpec(
                name="public", semantic_id="crm.public",
                json_schema={"type": "string"},
            )],
        )],
    ))
    with pytest.raises(PolicyViolationError, match="budget|bound|large"):
        router.prepare_field_routing().inspect_visible_fields(
            principal=ACTOR, after_route="wide_input", limit=1,
        )


def test_visible_field_review_refuses_oversized_parameter_name_bytes():
    router = build_fixture(500)
    router.add_tool(ToolSpec(
        name="wide_byte_input", source_type="crm", license="approved",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            parameters=[ParameterSpec(
                name="long_" + "가" * 22000,
                json_schema={"type": "string"},
            )],
            output_fields=[FieldSpec(
                name="public", semantic_id="crm.public",
                json_schema={"type": "string"},
            )],
        )],
    ))
    with pytest.raises(PolicyViolationError, match="budget|bound|large"):
        router.prepare_field_routing().inspect_visible_fields(
            principal=ACTOR, after_route="wide_byte", limit=1,
        )


def test_visible_field_review_refuses_inflight_input_shape_change(monkeypatch):
    """A live input projection changing after the first page pass is stale."""
    router = build_fixture(500)
    session = router.prepare_field_routing()
    original = router._data_scope_endpoint_view
    seen = 0

    def scoped_input_churn(principal, tool, endpoint):
        nonlocal seen
        visible = original(principal, tool, endpoint)
        if visible is not None and tool.name == "fork_owner":
            visible = visible.model_copy(deep=True)
            seen += 1
            if seen >= 2:
                visible.parameters[0].location = "query"
        return visible

    monkeypatch.setattr(router, "_data_scope_endpoint_view", scoped_input_churn)
    with pytest.raises(PolicyViolationError, match="changed|eligibility"):
        session.inspect_visible_fields(
            principal=ACTOR, after_route="fork_", limit=64,
        )


def test_visible_field_review_suppresses_restricted_source_provenance():
    router = build_fixture(500)
    router.add_tool(ToolSpec(
        name="scoped_review", source_type="private_name", license="private_name",
        endpoints=[EndpointSpec(name="read", read_only=True, output_fields=[
            FieldSpec(name="public_name", semantic_id="crm.public_name",
                      json_schema={"type": "string"}),
            FieldSpec(name="private_name", semantic_id="crm.private_name",
                      json_schema={"type": "string"}),
        ])],
    ))
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(effect="allow", operation="*.read",
                                 roles_any=("reader",)),),
        data_rules=(DataScopeRule(
            operation="scoped_review.read", roles_any=("reader",),
            hidden_fields=("private_name",),
        ),),
    )
    session = router.prepare_field_routing(catalog=_catalog())
    page = session.inspect_visible_fields(
        principal=ACTOR, after_route="scoped_", limit=64,
    )
    reviewed = next(route for route in page.routes
                    if route.route_id == "scoped_review.read")
    assert tuple(field.name for field in reviewed.fields) == ("public_name",)
    assert reviewed.source_type is None and reviewed.license is None
    assert "private_name" not in repr(reviewed)


def test_visible_field_review_omits_route_identifiers_echoing_hidden_fields():
    router = build_fixture(500)
    router.add_tool(ToolSpec(
        name="private_name_probe", source_type="crm", license="approved",
        endpoints=[EndpointSpec(name="read", read_only=True, output_fields=[
            FieldSpec(name="public_name", semantic_id="crm.public_name",
                      json_schema={"type": "string"}),
            FieldSpec(name="private_name", semantic_id="crm.private_name",
                      json_schema={"type": "string"}),
        ])],
    ))
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(effect="allow", operation="*.read",
                                 roles_any=("reader",)),),
        data_rules=(DataScopeRule(
            operation="private_name_probe.read", roles_any=("reader",),
            hidden_fields=("private_name",),
        ),),
    )
    page = router.prepare_field_routing().inspect_visible_fields(
        principal=ACTOR, after_route="private", limit=64,
    )
    assert all("private_name" not in route.route_id for route in page.routes)


def test_visible_field_review_5000_routes_stays_bounded_and_source_pinned():
    router = build_fixture(5000)
    session = router.prepare_field_routing(catalog=_catalog())
    first = session.inspect_visible_fields(principal=ACTOR, limit=5)
    assert first.snapshot_id == session.snapshot_id
    assert len(first.routes) == 5
    assert first.next_after_route is not None
    assert first.next_after_route.startswith("sr1:")
    assert len(first.next_after_route) == 68
    second = session.inspect_visible_fields(
        principal=ACTOR, after_route=first.next_after_route, limit=5,
    )
    assert len(second.routes) == 5
    assert set(item.route_id for item in first.routes).isdisjoint(
        item.route_id for item in second.routes
    )
    assert first.routes[-1].route_id < second.routes[0].route_id


def test_visible_field_review_cursor_handles_valid_long_registered_route_ids():
    router = build_fixture(500)
    long_names = ("z" * 270, "z" * 271)
    for name in long_names:
        router.add_tool(ToolSpec(
            name=name, source_type="crm", license="host-reviewed-synthetic",
            endpoints=[EndpointSpec(name="read", read_only=True, output_fields=[
                FieldSpec(name="public_value", semantic_id="crm.public_value",
                          json_schema={"type": "string"}),
            ])],
        ))
    session = router.prepare_field_routing()
    first = session.inspect_visible_fields(
        principal=ACTOR, after_route="y", limit=1,
    )
    assert [item.route_id for item in first.routes] == [long_names[0] + ".read"]
    assert first.next_after_route is not None
    assert len(first.next_after_route) <= 256
    second = session.inspect_visible_fields(
        principal=ACTOR, after_route=first.next_after_route, limit=1,
    )
    assert [item.route_id for item in second.routes] == [long_names[1] + ".read"]
    assert second.next_after_route is None

    with pytest.raises(ValueError, match="cursor"):
        session.inspect_visible_fields(
            principal=ACTOR, after_route="sr1:" + "0" * 64,
        )


def test_visible_field_review_cursor_handles_odd_but_registered_route_names():
    router = build_fixture(500)
    source_names = ("z\nsource", "z final ")
    for name in source_names:
        router.add_tool(ToolSpec(
            name=name, source_type="crm", license="host-reviewed-synthetic",
            endpoints=[EndpointSpec(name="read", read_only=True, output_fields=[
                FieldSpec(name="public_value", semantic_id="crm.public_value",
                          json_schema={"type": "string"}),
            ])],
        ))
    session = router.prepare_field_routing()
    seen = []
    cursor = "y"
    for _ in source_names:
        page = session.inspect_visible_fields(
            principal=ACTOR, after_route=cursor, limit=1,
        )
        assert len(page.routes) == 1
        seen.append(page.routes[0].route_id)
        cursor = page.next_after_route
    assert seen == sorted(name + ".read" for name in source_names)
    assert cursor is None


def test_visible_field_review_refuses_unbounded_field_payload():
    router = build_fixture(500)
    router.add_tool(ToolSpec(
        name="wide_review", source_type="crm", license="host-reviewed-synthetic",
        endpoints=[EndpointSpec(name="read", read_only=True, output_fields=[
            FieldSpec(name=f"column_{index}", semantic_id=f"crm.column_{index}",
                      json_schema={"type": "string"})
            for index in range(513)
        ])],
    ))
    session = router.prepare_field_routing()
    with pytest.raises(PolicyViolationError, match="budget|bound|large"):
        session.inspect_visible_fields(
            principal=ACTOR, after_route="v", limit=1,
        )


def test_visible_field_review_fails_closed_on_stale_schema_and_policy_mutation():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    denied = session.inspect_visible_fields(principal=ACTOR, limit=64)
    assert denied.routes == () and denied.next_after_route is None

    router.add_tool(ToolSpec(
        name="new_review_tool", endpoints=[EndpointSpec(name="noop")],
    ))
    with pytest.raises(PolicyViolationError, match="stale|changed|source"):
        session.inspect_visible_fields(principal=ACTOR)


def test_visible_field_review_fails_on_inflight_health_policy_change():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    once = False

    def revoke_during_review(tool, endpoint):
        nonlocal once
        if not once:
            once = True
            router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return True

    router.planner.availability_predicate = revoke_during_review
    with pytest.raises(PolicyViolationError, match="changed|policy|authorization"):
        session.inspect_visible_fields(principal=ACTOR)


def test_visible_field_review_detects_one_shot_mutable_availability_revocation():
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(effect="allow", operation="*.read",
                                 roles_any=("reader",)),),
    ))
    for name in ("a", "b", "c"):
        router.add_tool(ToolSpec(
            name=name, source_type="crm", license="approved",
            endpoints=[EndpointSpec(name="read", read_only=True, output_fields=[
                FieldSpec(name="public", semantic_id="opaque.a",
                          json_schema={"type": "string"}),
            ])],
        ))
    session = router.prepare_field_routing()
    first_available = True
    checks_of_b = 0

    def revoke_previous_route_once(tool, _endpoint):
        nonlocal first_available, checks_of_b
        if tool.name == "b":
            checks_of_b += 1
            if checks_of_b == 2:
                first_available = False
        return first_available if tool.name == "a" else True

    router.planner.availability_predicate = revoke_previous_route_once
    with pytest.raises(PolicyViolationError, match="eligibility|changed"):
        session.inspect_visible_fields(principal=ACTOR, limit=2)


def test_visible_field_review_suppresses_sensitive_callback_errors():
    router = build_fixture(500)
    session = router.prepare_field_routing()

    def forbidden_diagnostic(_tool, _endpoint):
        raise PolicyViolationError("private SSN field in provider callback")

    router.planner.availability_predicate = forbidden_diagnostic
    with pytest.raises(PolicyViolationError) as caught:
        session.inspect_visible_fields(principal=ACTOR)
    assert "private" not in str(caught.value)
    assert "SSN" not in str(caught.value)


def test_visible_field_review_callback_cannot_forge_hidden_field_semantics():
    router = build_fixture(500)
    router.add_tool(ToolSpec(
        name="callback_review", source_type="crm", license="approved",
        endpoints=[EndpointSpec(name="read", read_only=True, output_fields=[
            FieldSpec(name="public", semantic_id="opaque.a",
                      json_schema={"type": "string"}),
            FieldSpec(name="secret", semantic_id="opaque.b",
                      json_schema={"type": "string"}),
        ])],
    ))
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(effect="allow", operation="*.read",
                                 roles_any=("reader",)),),
        data_rules=(DataScopeRule(
            operation="callback_review.read", roles_any=("reader",),
            hidden_fields=("secret",),
        ),),
    )
    session = router.prepare_field_routing()

    def mutate_callback_view(tool, endpoint):
        if tool.name == "callback_review":
            endpoint.output_fields[0].semantic_id = "opaque.b"
        return True

    router.planner.availability_predicate = mutate_callback_view
    page = session.inspect_visible_fields(principal=ACTOR, limit=64)
    visible = next(route for route in page.routes
                   if route.route_id == "callback_review.read")
    assert [(field.name, field.semantic_id) for field in visible.fields] == [
        ("public", "opaque.a"),
    ]


@pytest.mark.parametrize("limit,after_route", [
    (0, None), (65, None), (True, None), (1.0, None),
    (32, ""), (32, " x"), (32, "bad\nroute"), (32, 7),
    (32, "sr1:not-a-valid-token"),
])
def test_visible_field_review_rejects_unbounded_page_inputs(limit, after_route):
    session = build_fixture(500).prepare_field_routing(catalog=_catalog())
    with pytest.raises(ValueError, match="page|cursor|limit"):
        session.inspect_visible_fields(
            principal=ACTOR, limit=limit, after_route=after_route,
        )


def test_revise_catalog_reuses_attested_graph_without_rebuild_or_provider_io(
    monkeypatch,
):
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    new_catalog = _revised_catalog()
    original_catalog_id = session.catalog_revision_id

    def forbidden(*args, **kwargs):
        pytest.fail("catalog-only revision must not rescan schemas or query providers")

    with monkeypatch.context() as scope:
        scope.setattr(NativeSchemaPostingIndex, "build", forbidden)
        scope.setattr(NativeSchemaGraphIndex, "build", forbidden)
        scope.setattr(router.registry, "tools", forbidden)
        scope.setattr(router.registry, "keys", forbidden)
        scope.setattr(router.executor, "execute", forbidden)
        scope.setattr(router.executor, "execute_call", forbidden)
        revised = session.revise_catalog(catalog=new_catalog)
        for query in new_catalog.concepts[0].aliases:
            assert revised.discover(query, principal=ACTOR).status == "complete"
            assert {call.route_id for call in revised.compile(
                query, principal=ACTOR,
            ).calls} == {ROOT, LEFT, RIGHT}

    assert revised is not session
    assert revised._index is session._index
    assert revised._index.approved_host_roots == frozenset()
    assert revised.snapshot_id == session.snapshot_id
    assert revised.catalog_revision_id != original_catalog_id
    assert revised.catalog_revision_id == session.revise_catalog(
        catalog=_revised_catalog(),
    ).catalog_revision_id
    assert session.discover(ALIASES[0], principal=ACTOR).status == "complete"
    with pytest.raises(ValueError, match="no declared concept"):
        revised.discover(ALIASES[0], principal=ACTOR)


def test_revise_catalog_detaches_new_caller_owned_catalog():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    amended = _revised_catalog()
    revised = session.revise_catalog(catalog=amended)
    amended.concepts = _catalog().concepts
    assert revised.discover("account owner", principal=ACTOR).status == "complete"
    assert revised.catalog_revision_id != session.catalog_revision_id


def test_revise_catalog_keeps_explicit_approved_host_roots():
    router = build_fixture(500)
    session = router.prepare_field_routing(
        catalog=_catalog(), approved_host_roots=frozenset({RIGHT}),
    )
    revised = session.revise_catalog(catalog=_revised_catalog())
    assert revised._index is session._index
    assert revised._index.approved_host_roots == frozenset({RIGHT})


def test_revise_catalog_revision_digest_ignores_qualifier_dict_insertion_order():
    owner_payload = _revised_catalog().model_dump(mode="python")
    first = NativeConceptCatalog.model_validate(owner_payload, strict=True)
    reordered = NativeConceptCatalog.model_validate(owner_payload, strict=True)
    first.concepts[0].required_fields[0].qualifiers = {
        "region": "KR", "tier": "standard",
    }
    reordered.concepts[0].required_fields[0].qualifiers = {
        "tier": "standard", "region": "KR",
    }
    router = build_fixture(500)
    prepared = router.prepare_field_routing(catalog=first)
    revised = prepared.revise_catalog(catalog=reordered)
    assert revised.catalog_revision_id == prepared.catalog_revision_id


def test_revise_catalog_rejects_unreviewed_inputs_and_stale_sources():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    with pytest.raises(ValueError, match="catalog"):
        session.revise_catalog(catalog={"concepts": []})

    malformed = _revised_catalog()
    object.__setattr__(malformed, "concepts", ())
    with pytest.raises(ValueError, match="catalog|concept"):
        session.revise_catalog(catalog=malformed)

    router.add_tool(ToolSpec(
        name="new_empty_tool", endpoints=[EndpointSpec(name="noop")],
    ))
    with pytest.raises(PolicyViolationError, match="stale|changed|source"):
        session.revise_catalog(catalog=_revised_catalog())


def test_revise_catalog_rejects_inflight_nested_policy_mutation(monkeypatch):
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    policy = router.authorization_policy
    assert policy is not None
    amended = _revised_catalog()
    real_dump = NativeConceptCatalog.model_dump

    def mutate_policy_during_copy(self, *args, **kwargs):
        data = real_dump(self, *args, **kwargs)
        if self is amended:
            policy._rule_index.partitions[("synthetic", None, None)] = (0,)
        return data

    monkeypatch.setattr(NativeConceptCatalog, "model_dump", mutate_policy_during_copy)
    with pytest.raises(PolicyViolationError, match="policy|authorization"):
        session.revise_catalog(catalog=amended)


def test_revise_catalog_rejects_inflight_schema_revision(monkeypatch):
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    amended = _revised_catalog()
    real_dump = NativeConceptCatalog.model_dump

    def change_registry_during_copy(self, *args, **kwargs):
        data = real_dump(self, *args, **kwargs)
        if self is amended:
            router.add_tool(ToolSpec(
                name="mid_copy_tool", endpoints=[EndpointSpec(name="noop")],
            ))
        return data

    monkeypatch.setattr(NativeConceptCatalog, "model_dump", change_registry_during_copy)
    with pytest.raises(PolicyViolationError, match="stale|changed|source"):
        session.revise_catalog(catalog=amended)


def test_revise_catalog_rejects_inflight_policy_identity_swap(monkeypatch):
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    amended = _revised_catalog()
    real_dump = NativeConceptCatalog.model_dump

    def change_policy_during_copy(self, *args, **kwargs):
        data = real_dump(self, *args, **kwargs)
        if self is amended:
            router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return data

    monkeypatch.setattr(NativeConceptCatalog, "model_dump", change_policy_during_copy)
    with pytest.raises(PolicyViolationError, match="policy|authorization"):
        session.revise_catalog(catalog=amended)


@pytest.mark.parametrize("query", ALIASES)
def test_prepared_session_discovers_complete_native_field_routes(query):
    router = build_fixture(500, mixed_scope=True)
    session = router.prepare_field_routing(catalog=_catalog())
    assert isinstance(session, SchemaFieldRoutingSession)
    assert session.indexed_route_count == 500
    assert "fork_origin" not in repr(session)
    assert "crm.customer_fields" not in repr(session)
    result = session.discover(query, principal=ACTOR)
    assert result.status == "complete"
    assert not result.executable_authority
    assert {route.route_id for route in result.alternatives[0].routes} == {
        ROOT, LEFT, RIGHT,
    }
    fields = {route.route_id: route.output_fields
              for route in result.alternatives[0].routes}
    assert fields == {
        ROOT: ("customer_id",), LEFT: ("status",), RIGHT: ("owner",),
    }


def test_prepared_session_reuses_compiled_index_and_exposes_field_metadata(
    monkeypatch,
):
    router = build_fixture(500)
    builds = []
    from schemarouter import native_semantic_index

    original = native_semantic_index.NativeSchemaPostingIndex.build.__func__

    def tracked(cls, registry):
        builds.append(registry.version)
        return original(cls, registry)

    monkeypatch.setattr(
        native_semantic_index.NativeSchemaPostingIndex,
        "build", classmethod(tracked),
    )
    session = router.prepare_field_routing(catalog=_catalog())
    before = router.retrieve_authorized(ALIASES[0], principal=ACTOR)
    assert all(session.discover(q, principal=ACTOR).status == "complete"
               for q in ALIASES)
    typed = session.compile(ALIASES[1], principal=ACTOR)
    assert typed.status == "requires_observation"
    assert not typed.executable_authority
    assert {item.route_id for item in typed.calls} == {ROOT, LEFT, RIGHT}
    assert {(item.route_id, meta.name, meta.source_type, meta.license)
            for item in typed.calls for meta in item.fields_meta} == {
        (ROOT, "customer_id", "crm", "host-reviewed-synthetic"),
        (LEFT, "status", "crm", "host-reviewed-synthetic"),
        (RIGHT, "owner", "crm", "host-reviewed-synthetic"),
    }
    assert {(typed.calls[b.consumer_call_index].route_id, b.parameter,
             typed.calls[b.producer_call_index].route_id, b.producer_field)
            for b in typed.bindings} == {
        (LEFT, "customer_id", ROOT, "customer_id"),
        (RIGHT, "customer_id", ROOT, "customer_id"),
    }
    assert builds == [router.registry.version]
    assert router.retrieve_authorized(ALIASES[0], principal=ACTOR) == before


def test_prepared_session_never_calls_provider_executors(monkeypatch):
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())

    def forbidden(*args, **kwargs):
        raise AssertionError("field discovery must not execute data calls")

    monkeypatch.setattr(router.executor, "execute", forbidden)
    monkeypatch.setattr(router.executor, "execute_call", forbidden)
    assert session.discover(ALIASES[0], principal=ACTOR).status == "complete"
    assert session.compile(ALIASES[0], principal=ACTOR).calls


def test_prepared_session_does_not_rebuild_authorized_full_catalog_per_query(
    monkeypatch,
):
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())

    def forbidden(*args, **kwargs):
        raise AssertionError("prepared field routing must reuse indexed candidates")

    monkeypatch.setattr(router, "_scoped_analysis_registry", forbidden)
    for query in ALIASES:
        assert session.discover(query, principal=ACTOR).status == "complete"
    assert session.compile(ALIASES[0], principal=ACTOR).calls


@pytest.mark.parametrize("route_count,mixed", [(500, True), (5000, False)])
def test_indexed_session_matches_preexisting_field_proof_across_catalog_sizes(
    route_count, mixed,
):
    router = build_fixture(route_count, mixed_scope=mixed)
    catalog = _catalog()
    session = router.prepare_field_routing(catalog=catalog)
    legacy_index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    for query in ALIASES:
        expected = retrieve_paper_field_coverage(
            router, query, principal=ACTOR, catalog=catalog, index=legacy_index,
        )
        assert session.discover(query, principal=ACTOR) == expected


def test_prepared_session_is_not_affected_by_callers_mutable_catalog():
    router = build_fixture(500)
    catalog = _catalog()
    session = router.prepare_field_routing(catalog=catalog)
    catalog.concepts = (NativeDeclaredConcept(
        concept_id="crm.customer_fields", aliases=("unrelated customer query",),
        required_fields=GROUP.required_fields, source_type=GROUP.source_type,
        license=GROUP.license,
    ),)
    assert session.discover(ALIASES[0], principal=ACTOR).status == "complete"


def test_prepared_session_fails_closed_when_registry_changes():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    from schemarouter import EndpointSpec

    router.add_tool(ToolSpec(
        name="new_empty_tool", endpoints=[EndpointSpec(name="noop")],
    ))
    with pytest.raises(PolicyViolationError, match="stale|changed|source"):
        session.discover(ALIASES[0], principal=ACTOR)
    with pytest.raises(PolicyViolationError, match="stale|changed|source"):
        session.compile(ALIASES[0], principal=ACTOR)
    assert router.prepare_field_routing(catalog=_catalog()).discover(
        ALIASES[0], principal=ACTOR,
    ).status == "complete"


def test_prepared_session_journal_refresh_preserves_original_and_matches_rebuild(
    monkeypatch,
):
    router = build_fixture(500, mixed_scope=True)
    session = router.prepare_field_routing(catalog=_catalog())
    original_snapshot = session.snapshot_id
    router.add_tool(ToolSpec(
        name="new_empty_tool", endpoints=[EndpointSpec(name="noop")],
    ))
    reference = router.prepare_field_routing(catalog=_catalog())

    def forbidden(*args, **kwargs):
        pytest.fail("journal session refresh must not rebuild or execute providers")

    with monkeypatch.context() as scope:
        scope.setattr(NativeSchemaPostingIndex, "build", forbidden)
        scope.setattr(NativeSchemaGraphIndex, "build", forbidden)
        scope.setattr(router.registry, "tools", forbidden)
        scope.setattr(router.registry, "keys", forbidden)
        scope.setattr(router.executor, "execute", forbidden)
        scope.setattr(router.executor, "execute_call", forbidden)
        refreshed = session.refresh()
        for query in ALIASES:
            assert refreshed.discover(query, principal=ACTOR) == reference.discover(
                query, principal=ACTOR,
            )
            assert refreshed.compile(query, principal=ACTOR) == reference.compile(
                query, principal=ACTOR,
            )

    assert refreshed is not session
    assert refreshed.snapshot_id == reference.snapshot_id != original_snapshot
    assert refreshed.indexed_route_count == 501
    with pytest.raises(PolicyViolationError, match="stale|changed|source"):
        session.discover(ALIASES[0], principal=ACTOR)


def test_prepared_session_verified_hint_refresh_rejects_omissions():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    with pytest.raises(PolicyViolationError, match="newer|changed|source"):
        session.refresh()
    router.add_tool(ToolSpec(
        name="new_empty_tool", endpoints=[EndpointSpec(name="noop")],
    ))
    with pytest.raises((ValueError, PolicyViolationError)):
        session.refresh(changed_tool_keys=())
    with pytest.raises(PolicyViolationError, match="changed|unknown|verify"):
        session.refresh(changed_tool_keys=("fork_origin",))
    refreshed = session.refresh(changed_tool_keys=("new_empty_tool",))
    assert refreshed.snapshot_id == router.prepare_field_routing(
        catalog=_catalog(),
    ).snapshot_id
    assert refreshed.discover(ALIASES[0], principal=ACTOR).status == "complete"


def test_prepared_session_refresh_refuses_inflight_authorization_policy_swap(
    monkeypatch,
):
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    router.add_tool(ToolSpec(
        name="new_empty_tool", endpoints=[EndpointSpec(name="noop")],
    ))
    real_refresh = NativeSchemaGraphIndex.refresh_from_inmemory_journal.__func__

    def swap_policy(cls, previous, registry):
        updated = real_refresh(cls, previous, registry)
        router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return updated

    monkeypatch.setattr(
        NativeSchemaGraphIndex, "refresh_from_inmemory_journal",
        classmethod(swap_policy),
    )
    with pytest.raises(PolicyViolationError, match="policy|authorization"):
        session.refresh()


def test_prepared_session_refresh_refuses_same_policy_nested_index_mutation(
    monkeypatch,
):
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    policy = router.authorization_policy
    assert policy is not None
    router.add_tool(ToolSpec(
        name="new_empty_tool", endpoints=[EndpointSpec(name="noop")],
    ))
    original = NativeSchemaGraphIndex.refresh_from_inmemory_journal.__func__

    def mutate_nested_index(cls, previous, registry):
        updated = original(cls, previous, registry)
        policy._rule_index.partitions[("synthetic", None, None)] = (0,)
        return updated

    monkeypatch.setattr(
        NativeSchemaGraphIndex, "refresh_from_inmemory_journal",
        classmethod(mutate_nested_index),
    )
    with pytest.raises(PolicyViolationError, match="policy|authorization"):
        session.refresh()


def test_prepared_session_custom_registry_requires_verified_explicit_delta():
    class CustomInMemoryRegistry(InMemoryRegistry):
        pass

    fixture = build_fixture(500)
    registry = CustomInMemoryRegistry()
    router = SchemaRouter(
        registry=registry, authorization_policy=fixture.authorization_policy,
    )
    for name in ("fork_origin", "fork_status", "fork_owner"):
        router.add_tool(fixture.registry.get(name))
    session = router.prepare_field_routing(catalog=_catalog())
    router.add_tool(ToolSpec(
        name="new_empty_tool", endpoints=[EndpointSpec(name="noop")],
    ))
    with pytest.raises(PolicyViolationError, match="custom registry"):
        session.refresh()
    new_session = session.refresh(changed_tool_keys=("new_empty_tool",))
    oracle = router.prepare_field_routing(catalog=_catalog())
    assert new_session.snapshot_id == oracle.snapshot_id
    assert new_session.discover(ALIASES[0], principal=ACTOR) == oracle.discover(
        ALIASES[0], principal=ACTOR,
    )


def test_prepared_session_refresh_wires_exact_sqlite_journal():
    fixture = build_fixture(500)
    with SQLiteRegistry(":memory:") as sqlite:
        router = SchemaRouter(
            registry=sqlite, authorization_policy=fixture.authorization_policy,
        )
        for name in ("fork_origin", "fork_status", "fork_owner"):
            router.add_tool(fixture.registry.get(name))
        original = router.prepare_field_routing(catalog=_catalog())
        owner = sqlite.get("fork_owner")
        owner.endpoint("read").output_fields[0].semantic_id = "crm.unrelated"
        sqlite.register(owner, replace=True)
        refreshed = original.refresh()
        oracle = router.prepare_field_routing(catalog=_catalog())
        assert refreshed.snapshot_id == oracle.snapshot_id
        assert refreshed.discover(ALIASES[0], principal=ACTOR) == oracle.discover(
            ALIASES[0], principal=ACTOR,
        )
        assert refreshed._index.graph.edges == oracle._index.graph.edges
        assert refreshed._index.field_index.postings == oracle._index.field_index.postings


def test_prepared_session_real_producer_delete_and_restore_refresh_graph():
    router = build_fixture(500)
    assert isinstance(router.registry, InMemoryRegistry)
    original_owner = router.registry.get("fork_owner")
    initial = router.prepare_field_routing(catalog=_catalog())
    assert initial.discover(ALIASES[0], principal=ACTOR).status == "complete"

    router.registry.unregister("fork_owner")
    removed = initial.refresh()
    missing_oracle = router.prepare_field_routing(catalog=_catalog())
    for query in ALIASES:
        assert removed.discover(query, principal=ACTOR) == missing_oracle.discover(
            query, principal=ACTOR,
        )
    assert removed._index.graph.edges == missing_oracle._index.graph.edges
    assert removed._index.field_index.postings == missing_oracle._index.field_index.postings
    assert removed.discover(ALIASES[0], principal=ACTOR).status != "complete"

    router.add_tool(original_owner)
    restored = removed.refresh()
    restored_oracle = router.prepare_field_routing(catalog=_catalog())
    for query in ALIASES:
        assert restored.discover(query, principal=ACTOR) == restored_oracle.discover(
            query, principal=ACTOR,
        )
        assert restored.compile(query, principal=ACTOR) == restored_oracle.compile(
            query, principal=ACTOR,
        )
    assert restored._index.graph.edges == restored_oracle._index.graph.edges
    assert restored._index.field_index.postings == restored_oracle._index.field_index.postings


def test_prepared_session_refresh_rejects_removed_approved_host_root():
    router = build_fixture(500)
    assert isinstance(router.registry, InMemoryRegistry)
    session = router.prepare_field_routing(
        catalog=_catalog(), approved_host_roots=frozenset({RIGHT}),
    )
    router.registry.unregister("fork_owner")
    with pytest.raises((ValueError, PolicyViolationError), match="host|approved"):
        session.refresh()


def test_prepared_session_refresh_refuses_unbounded_native_journal():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    for n in range(65):
        router.add_tool(ToolSpec(
            name=f"added_{n}", endpoints=[EndpointSpec(name="noop")],
        ))
    with pytest.raises(PolicyViolationError, match="delta|version|history|journal"):
        session.refresh()


def test_prepared_session_honors_current_source_policy_revocation():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=_catalog())
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="deny", operation="*.read", roles_any=("reader",),
        ),),
    )
    receipt = session.discover(ALIASES[0], principal=ACTOR)
    assert receipt.status == "no_proven_hit"
    assert receipt.alternatives == ()


def test_prepared_session_rejects_unknown_alias_without_guessing_fields():
    session = build_fixture(500).prepare_field_routing(catalog=_catalog())
    with pytest.raises(ValueError, match="no declared concept"):
        session.discover("unsupported customer request", principal=ACTOR)
    with pytest.raises(ValueError, match="no declared concept"):
        session.compile("unsupported customer request", principal=ACTOR)


@pytest.mark.parametrize("bad_k", [0, 4, 6, True, 5.0])
def test_prepared_session_preserves_original_exact_k5(bad_k):
    session = build_fixture(500).prepare_field_routing(catalog=_catalog())
    with pytest.raises(ValueError, match="K5"):
        session.discover(ALIASES[0], principal=ACTOR, k=bad_k)


def test_prepared_session_rejects_unreviewed_catalog_and_root_inputs():
    router = build_fixture(500)
    with pytest.raises(ValueError):
        router.prepare_field_routing(catalog={"concepts": []})
    with pytest.raises(ValueError):
        router.prepare_field_routing(catalog=_catalog(), approved_host_roots={ROOT})


def test_prepared_session_does_not_exist_as_a_default_retrieval_mode():
    router: SchemaRouter = build_fixture(500)
    before = router.retrieve_authorized(ALIASES[0], principal=ACTOR)
    _ = router.prepare_field_routing(catalog=_catalog())
    after = router.retrieve_authorized(ALIASES[0], principal=ACTOR)
    assert after == before
