"""Offline G3: source-pinned native input ontology into canonical G2 graph."""
from __future__ import annotations

from dataclasses import replace

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.capability_contracts import CapabilityFieldContract
from scripts.research_native_semantic_graph_g3 import (
    ApprovedNativeRouteG3,
    NativeGraphGoalG3,
    retrieve_native_semantic_paths_g3,
)
from scripts.research_verified_graph_paths_g2 import (
    DeclaredGraphGoalG2,
    DeclaredInputBindingG2,
    retrieve_verified_graph_paths_g2,
)

ANALYST = PrincipalContext(subject="researcher", roles=("analyst",))
VIEWER = PrincipalContext(subject="scoped-user", roles=("viewer",))
ALIASES = ("citation status and priority", "인용 상태와 우선순위", "引用状態と優先度")
ROUTES = ("papers.read", "citations.read", "claims.read")


def _field(name: str, semantic: str, *, identifier: bool = False) -> FieldSpec:
    return FieldSpec(name=name, semantic_id=semantic,
                     json_schema={"type": "string"}, identifier=identifier)


def _router(
    *, missing_native: bool = False, incompatible: bool = False,
    extra_input_constraint: bool = False, other_root: bool = False,
) -> SchemaRouter:
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("analyst", "viewer"),
        ),),
        data_rules=(DataScopeRule(
            operation="papers.read", roles_any=("viewer",),
            hidden_fields=("paper_id",),
        ),),
    ))

    def register(name: str, endpoint: EndpointSpec) -> None:
        router.add_tool(ToolSpec(
            name=name, source_type="scholarly_reference",
            license="fixture-host-reviewed", endpoints=[endpoint],
        ))

    register("papers", EndpointSpec(
        name="read", read_only=True, output_fields=[
            _field("paper_id", "scholarly.paper_id", identifier=True),
        ],
    ))
    register("citations", EndpointSpec(
        name="read", read_only=True, parameters=[ParameterSpec(
            name="paper_id", required=True,
            semantic_id=None if missing_native else "scholarly.paper_id",
            json_schema={"type": "integer" if incompatible else "string"},
        )],
        input_schema=(
            {"type": "object",
             "properties": {"paper_id": {"type": "string"}},
             "required": ["paper_id"], "additionalProperties": False}
            if extra_input_constraint else {}
        ),
        output_fields=[
            _field("citation_id", "scholarly.citation_id", identifier=True),
        ],
    ))
    register("claims", EndpointSpec(
        name="read", read_only=True, parameters=[ParameterSpec(
            name="citation_id", required=True,
            semantic_id="scholarly.citation_id",
            json_schema={"type": "string"},
        )],
        output_fields=[
            _field("status", "scholarly.citation_status"),
            _field("priority", "scholarly.citation_priority"),
        ],
    ))
    if other_root:
        register("unaudited", EndpointSpec(
            name="read", read_only=True, output_fields=[
                _field("paper_id", "scholarly.paper_id", identifier=True),
            ],
        ))
    return router


def _approvals(router: SchemaRouter) -> tuple[ApprovedNativeRouteG3, ...]:
    approvals = []
    for route_id in ROUTES:
        key, endpoint_name = route_id.split(".")
        tool = router.registry.get(key)
        approvals.append(ApprovedNativeRouteG3(
            route_id=route_id,
            expected_tool_fingerprint=tool.fingerprint,
            expected_endpoint_fingerprint=tool.endpoint(endpoint_name).fingerprint,
        ))
    return tuple(approvals)


def _goal(router: SchemaRouter) -> NativeGraphGoalG3:
    return NativeGraphGoalG3(
        aliases=ALIASES,
        target_route_id="claims.read",
        required_outputs=(
            CapabilityFieldContract(semantic_id="scholarly.citation_status",
                                    json_schema={"type": "string"}),
            CapabilityFieldContract(semantic_id="scholarly.citation_priority",
                                    json_schema={"type": "string"}),
        ),
        approved_routes=_approvals(router),
    )


@pytest.mark.parametrize("query", ALIASES)
def test_native_semantics_reconstruct_exact_pinned_g2_path_without_host_map(query):
    router = _router()
    goal = _goal(router)
    paths = retrieve_native_semantic_paths_g3(
        router, query, principal=ANALYST, goal=goal,
    )
    assert len(paths) == 1
    assert paths[0].route_ids == ROUTES
    assert paths[0].target_output_fields == ("status", "priority")
    assert [(edge.producer_output_field, edge.consumer_input_parameter)
            for edge in paths[0].edges] == [
        ("paper_id", "paper_id"), ("citation_id", "citation_id"),
    ]
    # Parity uses the same canonical G2 graph, not a duplicate graph engine.
    old = DeclaredGraphGoalG2(
        aliases=ALIASES, target_route_id=goal.target_route_id,
        required_outputs=goal.required_outputs,
        bindings=tuple(
            DeclaredInputBindingG2(
                route_id=route_id, parameter_name=name, semantic_id=semantic,
                expected_endpoint_fingerprint=router.registry.get(
                    route_id.split(".")[0]
                ).endpoint("read").fingerprint,
            ) for route_id, name, semantic in (
                ("citations.read", "paper_id", "scholarly.paper_id"),
                ("claims.read", "citation_id", "scholarly.citation_id"),
            )
        ),
    )
    assert paths == retrieve_verified_graph_paths_g2(
        router, query, principal=ANALYST, goal=old,
        allowed_route_ids=frozenset(ROUTES),
    )


def test_unattested_matching_source_is_excluded_before_graph_build():
    router = _router(other_root=True)
    paths = retrieve_native_semantic_paths_g3(
        router, ALIASES[0], principal=ANALYST, goal=_goal(router),
    )
    assert len(paths) == 1
    assert paths[0].route_ids == ROUTES
    assert all("unaudited" not in route for route in paths[0].route_ids)


def test_principal_hidden_producer_does_not_expose_graph():
    router = _router()
    assert retrieve_native_semantic_paths_g3(
        router, ALIASES[0], principal=VIEWER, goal=_goal(router),
    ) == ()
    router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    assert retrieve_native_semantic_paths_g3(
        router, ALIASES[0], principal=ANALYST, goal=_goal(router),
    ) == ()


@pytest.mark.parametrize("options", [
    {"missing_native": True},
    {"incompatible": True},
    {"extra_input_constraint": True},
])
def test_missing_native_semantics_or_unproved_type_schema_abstains(options):
    router = _router(**options)
    assert retrieve_native_semantic_paths_g3(
        router, ALIASES[0], principal=ANALYST, goal=_goal(router),
    ) == ()


def test_tool_and_endpoint_fingerprint_attestation_fail_closed():
    router = _router()
    goal = _goal(router)
    first = goal.approved_routes[0]
    bad_tool = replace(first, expected_tool_fingerprint="stale-tool-revision")
    bad_endpoint = replace(first, expected_endpoint_fingerprint="stale-endpoint")
    for replacement in (bad_tool, bad_endpoint):
        changed = replace(
            goal, approved_routes=(replacement, *goal.approved_routes[1:]),
        )
        with pytest.raises(ValueError, match="source revision is stale"):
            retrieve_native_semantic_paths_g3(
                router, ALIASES[0], principal=ANALYST, goal=changed,
            )


def test_only_exact_host_aliases_and_k_budget_are_accepted():
    router = _router()
    goal = _goal(router)
    with pytest.raises(ValueError, match="query alias"):
        retrieve_native_semantic_paths_g3(
            router, "find unknown records", principal=ANALYST, goal=goal,
        )
    with pytest.raises(ValueError, match="exactly fixed K5"):
        retrieve_native_semantic_paths_g3(
            router, ALIASES[0], principal=ANALYST, goal=goal, k=6,
        )
    with pytest.raises(ValueError, match="invalid host-attested"):
        replace(goal, approved_routes=(
            goal.approved_routes[0], goal.approved_routes[0],
        ))
    with pytest.raises(ValueError, match="bounded native"):
        replace(goal.approved_routes[0], expected_tool_fingerprint="")


def test_graph_does_not_run_agent_planner_or_execution(monkeypatch):
    router = _router()
    def forbidden(*_args, **_kwargs):
        raise AssertionError("G3 is a nonexecuting catalog graph")
    monkeypatch.setattr(router, "plan", forbidden)
    monkeypatch.setattr(router, "execute", forbidden)
    assert retrieve_native_semantic_paths_g3(
        router, ALIASES[0], principal=ANALYST, goal=_goal(router),
    )
