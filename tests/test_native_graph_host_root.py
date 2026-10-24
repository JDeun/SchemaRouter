"""Opt-in host-owned source inputs: never infer them from G5 query text."""

from __future__ import annotations

from typing import Any

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
    compile_paper_typed_tool_plan,
)
from schemarouter.capability_contracts import CapabilityFieldContract
from schemarouter.errors import PolicyViolationError, SchemaValidationError
from schemarouter.field_group_retrieval import NativeDeclaredFieldGroup
from schemarouter.native_graph_execution import execute_native_graph_one_hop
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex

ACTOR = PrincipalContext(subject="host", roles=("reader",))
GROUP = NativeDeclaredFieldGroup(
    aliases=("post username", "게시물 작성자 계정", "投稿者ユーザー名"),
    required_fields=(CapabilityFieldContract(
        semantic_id="demo.username", json_schema={"type": "string"},
    ),),
    source_type="demo_rest",
    license="approved-demo",
)
ROUTE = "posts.by_id"


def _setup(
    *,
    input_schema: dict[str, Any] | None = None,
    source_params: list[ParameterSpec] | None = None,
) -> tuple[SchemaRouter, list[tuple[str, dict[str, Any]]]]:
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.*", roles_any=("reader",),
        ),),
    ))
    seen: list[tuple[str, dict[str, Any]]] = []
    params = source_params if source_params is not None else [
        ParameterSpec(
            name="post_id", required=True, json_schema={"type": "integer"},
        ),
    ]
    envelope = input_schema if input_schema is not None else {
        "type": "object",
        "properties": {p.name: p.json_schema for p in params},
        "required": [p.name for p in params if p.required],
    }
    producer = ToolSpec(
        name="posts", source_type="demo_rest", license="approved-demo",
        endpoints=[EndpointSpec(
            name="by_id", read_only=True,
            parameters=params,
            input_schema=envelope,
            output_fields=[FieldSpec(
                name="userId", identifier=True,
                semantic_id="demo.user_id", json_schema={"type": "integer"},
            )],
            output_schema={
                "type": "object",
                "properties": {"userId": {"type": "integer"}},
                "required": ["userId"],
            },
        )],
    )
    target = ToolSpec(
        name="users", source_type="demo_rest", license="approved-demo",
        endpoints=[EndpointSpec(
            name="by_id", read_only=True,
            parameters=[ParameterSpec(
                name="user_id", required=True, semantic_id="demo.user_id",
                json_schema={"type": "integer"},
            )],
            input_schema={
                "type": "object",
                "properties": {"user_id": {"type": "integer"}},
                "required": ["user_id"],
            },
            output_fields=[FieldSpec(
                name="username", semantic_id="demo.username",
                json_schema={"type": "string"},
            )],
            output_schema={
                "type": "object",
                "properties": {"username": {"type": "string"}},
                "required": ["username"],
            },
        )],
    )

    def source(endpoint: str, args: dict[str, Any]) -> dict[str, Any]:
        assert endpoint == "by_id"
        seen.append(("post", dict(args)))
        return {"userId": 1}

    def consumer(endpoint: str, args: dict[str, Any]) -> dict[str, Any]:
        assert endpoint == "by_id"
        seen.append(("user", dict(args)))
        return {"username": "demo"}

    router.add_bound_tool(producer, source)
    router.add_bound_tool(target, consumer)
    return router, seen


def _index(router: SchemaRouter, *, allow: bool) -> NativeSchemaGraphIndex:
    return NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
        approved_host_roots=frozenset({ROUTE}) if allow else frozenset(),
    )


def test_original_paper_typed_plan_keeps_host_root_and_consumer_inputs_deferred():
    """Host-approved graph roots still require actual host values at runtime."""
    router, seen = _setup()
    graph = _index(router, allow=True)
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="demo.username", aliases=GROUP.aliases,
        required_fields=GROUP.required_fields,
        source_type=GROUP.source_type, license=GROUP.license,
    ),))
    paper = compile_paper_typed_tool_plan(
        router, GROUP.aliases[1], principal=ACTOR, catalog=catalog, index=graph,
    )
    assert paper.status == "requires_observation"
    assert not paper.executable_authority
    assert [entry.route_id for entry in paper.calls] == ["posts.by_id", "users.by_id"]
    assert paper.calls[0].call.arguments == {}
    assert paper.calls[0].call.missing_required_arguments == ["post_id"]
    assert paper.calls[1].call.arguments == {}
    assert paper.calls[1].call.missing_required_arguments == ["user_id"]
    assert paper.bindings[0].parameter == "user_id"
    assert paper.bindings[0].producer_field == "userId"
    assert seen == []


def test_unapproved_host_root_stays_non_proven_in_paper_compiler():
    router, seen = _setup()
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="demo.username", aliases=GROUP.aliases,
        required_fields=GROUP.required_fields,
        source_type=GROUP.source_type, license=GROUP.license,
    ),))
    paper = compile_paper_typed_tool_plan(
        router, GROUP.aliases[0], principal=ACTOR, catalog=catalog,
        index=_index(router, allow=False),
    )
    assert paper.status == "no_proven_hit"
    assert paper.calls == () and paper.bindings == ()
    assert seen == []


def test_root_with_required_inputs_is_not_discoverable_without_explicit_opt_in() -> None:
    router, seen = _setup()
    graph = _index(router, allow=False)
    assert graph.lookup(
        router, GROUP.aliases[0], group=GROUP, principal=ACTOR,
    ).status == "no_proven_hit"
    assert seen == []


@pytest.mark.asyncio
@pytest.mark.parametrize("query", GROUP.aliases)
async def test_host_inputs_enable_two_real_authorized_local_calls(query: str) -> None:
    router, seen = _setup()
    graph = _index(router, allow=True)
    found = graph.lookup(router, query, group=GROUP, principal=ACTOR)
    assert found.status == "complete"
    assert len(found.candidates) == 1
    edge = found.candidates[0]
    assert edge.source_root_parameters == ("post_id",)
    assert edge.parameter_bindings == (("user_id", "userId"),)
    result = await execute_native_graph_one_hop(
        graph, router, query=query, group=GROUP, principal=ACTOR,
        candidate=edge, source_arguments={"post_id": 1},
    )
    assert seen == [
        ("post", {"post_id": 1}),
        ("user", {"user_id": 1}),
    ]
    assert result.consumer.data == {"username": "demo"}
    assert not result.independent_provider_identity_verified
    assert not result.independent_agent_e2


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_args", [
    None, {}, {"post_id": "1"}, {"post_id": None},
    {"post_id": True}, {"post_id": 1, "admin": 1},
    {"post_id": []}, {"post_id": 1.0},
])
async def test_absent_or_incompatible_host_inputs_do_not_invoke_any_tool(
    bad_args: dict[str, Any] | None,
) -> None:
    router, seen = _setup()
    graph = _index(router, allow=True)
    edge = graph.lookup(
        router, GROUP.aliases[0], group=GROUP, principal=ACTOR,
    ).candidates[0]
    with pytest.raises((SchemaValidationError, ValueError)):
        await execute_native_graph_one_hop(
            graph, router, query=GROUP.aliases[0], group=GROUP,
            principal=ACTOR, candidate=edge, source_arguments=bad_args,
        )
    assert seen == []


@pytest.mark.asyncio
async def test_original_empty_root_does_not_accept_extra_host_inputs() -> None:
    router, seen = _setup(source_params=[], input_schema={})
    graph = _index(router, allow=False)
    edge = graph.lookup(
        router, GROUP.aliases[0], group=GROUP, principal=ACTOR,
    ).candidates[0]
    with pytest.raises(SchemaValidationError, match="rejects extra"):
        await execute_native_graph_one_hop(
            graph, router, query=GROUP.aliases[0], group=GROUP,
            principal=ACTOR, candidate=edge, source_arguments={"post_id": 1},
        )
    assert seen == []


@pytest.mark.parametrize("bad_schema", [
    {
        "type": "object",
        "properties": {"post_id": {"type": "integer"}},
        "required": ["post_id"],
        "additionalProperties": False,
    },
    {"type": "object", "properties": {"post_id": {"type": "integer"}}},
])
def test_explicit_host_root_does_not_strip_or_guess_provider_schema(
    bad_schema: dict[str, Any],
) -> None:
    router, seen = _setup(input_schema=bad_schema)
    with pytest.raises(ValueError, match="invalid explicit host-approved"):
        _index(router, allow=True)
    assert seen == []


def test_unreviewed_or_unknown_host_root_cannot_be_published() -> None:
    router, seen = _setup()
    with pytest.raises(ValueError, match="not accepted"):
        NativeSchemaGraphIndex.build(
            NativeSchemaPostingIndex.build(router.registry),
            approved_host_roots=frozenset({"unknown.operation"}),
        )
    assert seen == []


@pytest.mark.asyncio
async def test_new_registry_revision_invalidates_host_root_before_execution() -> None:
    router, seen = _setup()
    graph = _index(router, allow=True)
    edge = graph.lookup(
        router, GROUP.aliases[0], group=GROUP, principal=ACTOR,
    ).candidates[0]
    replacement = router.registry.get("posts")
    replacement.endpoint("by_id").description = "changed root source"
    router.registry.register(replacement, replace=True)
    with pytest.raises(PolicyViolationError, match="changed|stale|drift"):
        await execute_native_graph_one_hop(
            graph, router, query=GROUP.aliases[0],
            group=GROUP, principal=ACTOR, candidate=edge,
            source_arguments={"post_id": 1},
        )
    assert seen == []
