"""E0-only paper Algorithm 1 selector inside the already existing fixed5 loop.

The trusted task fixture stays with FrozenCorpusExecutor; the callback sees
only the original query and principal-visible source-native route IDs.
"""
from __future__ import annotations

import json
from pathlib import Path

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
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    PolicyViolationError,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
    compile_paper_field_toolcalls,
)
from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    run_generated_episode,
)
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    ALIASES,
    GROUP,
    LEFT,
    RIGHT,
    ROOT,
    build_fixture,
)
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_paper_field_fixed5_agent_bridge import (
    AuthorizedPaperFieldFixed5Selector,
)

QUERY = "customer status and owner"
PRINCIPAL = PrincipalContext(subject="reviewer", roles=("reader",))
CATALOG = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
    concept_id="crm.customer_paper_fields",
    aliases=(QUERY, "고객 상태와 담당자", "顧客状態と担当者"),
    required_fields=(
        CapabilityFieldContract(
            semantic_id="crm.fork_status", json_schema={"type": "string"},
        ),
        CapabilityFieldContract(
            semantic_id="crm.fork_owner", json_schema={"type": "string"},
        ),
    ),
    source_type="crm", license="host-reviewed-synthetic",
),))


def test_paper_bridge_is_required_by_dedicated_source_native_workflow():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/original-paper-field-coverage-e0.yml"
    ).read_text(encoding="utf-8")
    assert '"scripts/research_paper_field_fixed5_agent_bridge.py"' in workflow
    assert '"tests/test_research_paper_field_fixed5_agent_bridge.py"' in workflow
    assert (
        "pytest -q tests/test_research_paper_field_fixed5_agent_bridge.py"
        in workflow
    )
    assert (
        "pyright scripts/research_paper_field_fixed5_agent_bridge.py"
        in workflow
    )


def _direct_router(*, hidden: bool = False, alternatives: int = 1) -> SchemaRouter:
    rules = (AuthorizationRule(
        effect="allow", operation="*.read", roles_any=("reader",),
    ),)
    scope = (DataScopeRule(
        operation="complete_0.read", roles_any=("reader",),
        hidden_fields=("owner",),
    ),) if hidden else ()
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=rules, data_rules=scope,
    ))
    for index in range(alternatives):
        router.add_tool(ToolSpec(
            name=f"complete_{index}", source_type="crm",
            license="host-reviewed-synthetic",
            endpoints=[EndpointSpec(
                name="read", read_only=True, output_fields=[
                    FieldSpec(
                        name="status", semantic_id="crm.fork_status",
                        json_schema={"type": "string"},
                    ),
                    FieldSpec(
                        name="owner", semantic_id="crm.fork_owner",
                        json_schema={"type": "string"},
                    ),
                ],
            )],
        ))
    return router


def _index(router: SchemaRouter) -> NativeSchemaGraphIndex:
    return NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )


def _prepare(router, catalog=CATALOG, query=QUERY, principal=PRINCIPAL, *,
             indexed=True):
    view = capture_authorized_agent_tool_surface(
        router, query, principal=principal,
    )
    index = _index(router)
    selector = AuthorizedPaperFieldFixed5Selector(
        view, catalog, index, experimental_indexed_direct=indexed,
    )
    return view, index, selector


@pytest.mark.parametrize("indexed", [False, True])
def test_paper_direct_callback_matches_source_proven_p2_without_gold(indexed):
    router = _direct_router()
    view, index, selector = _prepare(router, indexed=indexed)
    names = selector(QUERY, view.visible_route_ids)
    plan = compile_paper_field_toolcalls(
        router, QUERY, principal=PRINCIPAL, catalog=CATALOG, index=index,
        experimental_indexed_direct=indexed,
    )
    assert names == ["complete_0.read"]
    assert names == [
        f"{call.tool}.{call.endpoint}" for call in plan.alternatives[0].calls
    ]
    assert plan.status == "complete"
    assert plan.alternatives[0].calls[0].fields == ["status", "owner"]
    assert plan.alternatives[0].calls[0].arguments == {}
    assert selector.last_status == "complete"
    assert selector.independent_quality_evidence is False
    assert selector.calibrated_no_fit is False
    assert selector.executable_authority is False


@pytest.mark.parametrize("indexed", [False, True])
def test_paper_same_root_typed_fork_is_not_fabricated_or_flattened(indexed):
    router = build_fixture(500, mixed_scope=True)
    assert GROUP.source_type is not None and GROUP.license is not None
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="crm.paper_fork", aliases=ALIASES,
        required_fields=GROUP.required_fields, source_type=GROUP.source_type,
        license=GROUP.license,
    ),))
    view, graph, selector = _prepare(
        router, catalog, ALIASES[0], ACTOR, indexed=indexed,
    )
    selected = selector(ALIASES[0], view.visible_route_ids)
    assert selected[0] == ROOT
    assert set(selected) == {ROOT, LEFT, RIGHT}
    plan = compile_paper_field_toolcalls(
        router, ALIASES[0], principal=ACTOR, catalog=catalog, index=graph,
        experimental_indexed_direct=indexed,
    )
    assert plan.status == "complete"
    assert len(plan.alternatives) == 1
    original = plan.alternatives[0]
    assert len(original.dependencies) == 2
    assert original.calls[0].tool == ROOT.split(".")[0]
    assert {
        f"{call.tool}.{call.endpoint}" for call in original.calls
    } == {ROOT, LEFT, RIGHT}
    assert all(call.arguments == {} for call in original.calls)
    assert original.calls[1].missing_required_arguments == ["customer_id"]
    assert original.calls[2].missing_required_arguments == ["customer_id"]


class ScriptedAgent:
    def __init__(self, turns: list[str]):
        self.turns = turns
        self.index = 0
        self.seen = []

    def generate(self, messages, tools):
        del messages
        self.seen.append(tools)
        content = self.turns[min(self.index, len(self.turns) - 1)]
        self.index += 1
        return {
            "text": content,
            "input_tokens": 5,
            "tool_tokens": 7,
            "output_tokens": 3,
            "latency_ms": 0.0,
            "context_overflow": False,
        }


class ObservationBoundAgent:
    """Deterministic E0 adapter: consumes tool messages, never task/gold.

    This tests observation-mediated argument flow, not LLM inference.
    """

    def __init__(self, root: str, left: str, right: str):
        self.routes = (root, left, right)
        self.index = 0
        self.observed_id: str | None = None
        self.bound_ids: list[str] = []

    def generate(self, messages, tools):
        del tools
        if self.index == 0:
            content = _call(self.routes[0], {})
        else:
            last = messages[-1]
            if last["role"] != "tool":
                content = "Done."
            else:
                payload = last["content"]
                prefix, suffix = "<tool_response>\n", "\n</tool_response>"
                if not payload.startswith(prefix) or not payload.endswith(suffix):
                    raise ValueError("unexpected scoped E0 observation envelope")
                observation = json.loads(payload[len(prefix):-len(suffix)])
                if observation.get("status") != "ok":
                    content = "Done."
                elif self.index == 1:
                    visible_id = observation.get("customer_id")
                    if type(visible_id) is str and visible_id:
                        self.observed_id = visible_id
                        self.bound_ids.append(visible_id)
                        content = _call(self.routes[1], {"customer_id": visible_id})
                    else:
                        content = "Done."
                elif self.index == 2 and self.observed_id is not None:
                    self.bound_ids.append(self.observed_id)
                    content = _call(self.routes[2], {"customer_id": self.observed_id})
                else:
                    content = "Done."
        self.index += 1
        return {
            "text": content, "input_tokens": 5, "tool_tokens": 7,
            "output_tokens": 3, "latency_ms": 0.0, "context_overflow": False,
        }


def _call(route, arguments):
    return "<tool_call>" + json.dumps({
        "name": route.replace(".", "__", 1), "arguments": arguments,
    }) + "</tool_call>"


def _task():
    return {
        "semantic_task_id": "e0-paper-direct-scripted-not-independent",
        "query": QUERY, "language": "en", "supported": True,
        "required_routes": ["complete_0.read"],
        "executor_fixture": {"steps": [{
            "route_id": "complete_0.read", "argument_rules": {},
            "observation": {"status": "ok", "owner": "reviewer"},
        }]},
    }


def test_paper_callback_inside_existing_agent_loop_keeps_frozen_executor():
    router = _direct_router()
    view, _, selector = _prepare(router)
    agent = ScriptedAgent([_call("complete_0.read", {}), "Done."])
    row = run_generated_episode(
        agent, router.registry, _task(), EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=selector,
        experimental_agent_tool_surface=view,
    )
    assert row["passed"] is True
    assert row["tool_call_count"] == 1
    assert row["visible_candidate_counts"] == [1]
    assert row["unauthorized_destructive_executions"] == 0
    assert max(len(tools) for tools in agent.seen) == 1
    assert "required_routes" not in json.dumps(view.public_trace(row))


def test_hidden_fields_and_unranked_six_alternatives_abstain_without_partial_menu():
    hidden = _direct_router(hidden=True)
    view, _, selector = _prepare(hidden)
    assert selector(QUERY, view.visible_route_ids) == []
    assert selector.calibrated_no_fit is False

    many = _direct_router(alternatives=6)
    view, _, selector = _prepare(many)
    assert selector(QUERY, view.visible_route_ids) == []
    assert selector.last_status == "over_k_unranked"


def test_multiple_complete_alternatives_do_not_gain_alphabetical_ranking():
    router = _direct_router(alternatives=2)
    view, _, selector = _prepare(router)
    assert selector(QUERY, view.visible_route_ids) == []
    assert selector.last_status == "multiple_unranked_alternatives"
    assert selector.calibrated_no_fit is False


def test_principal_denied_fields_do_not_disclose_original_routes():
    router = _direct_router()
    denied = PrincipalContext(subject="blocked", roles=("other",))
    view, _, selector = _prepare(router, principal=denied)
    assert view.visible_route_ids == ()
    assert selector(QUERY, view.visible_route_ids) == []
    assert selector.last_status == "no_proven_hit"


def test_frozen_comparators_still_reject_paper_selector():
    router = _direct_router()
    view, _, selector = _prepare(router)
    for condition in ("FULL", "SR-5", "SR-10", "SR-PROGRESSIVE", "ORACLE"):
        with pytest.raises(ValueError, match="isolated fixed5"):
            run_generated_episode(
                ScriptedAgent(["REQUEST_MORE_TOOLS"]),
                router.registry, _task(), condition,
                experimental_candidate_selector=selector,
                experimental_agent_tool_surface=view,
            )


def test_unsupported_no_call_is_safe_but_does_not_calibrate_no_fit():
    router = _direct_router()
    view, _, selector = _prepare(router)
    task = _task()
    task["supported"] = False
    task["required_routes"] = []
    task["executor_fixture"] = {"steps": []}
    row = run_generated_episode(
        ScriptedAgent(["REQUEST_MORE_TOOLS"]),
        router.registry, task, EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=selector,
        experimental_agent_tool_surface=view,
    )
    assert row["passed"] is True
    assert row["tool_call_count"] == 0
    assert selector.calibrated_no_fit is False
    assert selector.independent_quality_evidence is False


def test_existing_executor_runs_three_step_paper_fork_with_scripted_identifier():
    router = build_fixture(500, mixed_scope=True)
    assert GROUP.source_type is not None and GROUP.license is not None
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="crm.paper_fork", aliases=ALIASES,
        required_fields=GROUP.required_fields, source_type=GROUP.source_type,
        license=GROUP.license,
    ),))
    view, _, selector = _prepare(
        router, catalog, ALIASES[0], ACTOR, indexed=True,
    )
    source_routes = selector(ALIASES[0], view.visible_route_ids)
    assert set(source_routes) == {ROOT, LEFT, RIGHT}
    observations = {
        ROOT: {"status": "ok", "customer_id": "C-42"},
        LEFT: {"status": "ok"},
        RIGHT: {"status": "ok", "owner": "member"},
    }
    task = {
        "semantic_task_id": "e0-paper-three-step-not-independent",
        "query": ALIASES[0], "language": "en", "supported": True,
        "required_routes": [ROOT, LEFT, RIGHT],
        "executor_fixture": {"steps": [
            {"route_id": route, "argument_rules": (
                {} if route == ROOT else {"customer_id": {"eq": "C-42"}}
            ), "observation": observations[route]}
            for route in (ROOT, LEFT, RIGHT)
        ]},
    }
    agent = ScriptedAgent([
        _call(ROOT, {}),
        _call(LEFT, {"customer_id": "C-42"}),
        _call(RIGHT, {"customer_id": "C-42"}),
        "Done.",
    ])
    row = run_generated_episode(
        agent, router.registry, task, EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=selector,
        experimental_agent_tool_surface=view,
    )
    assert row["passed"] is True
    assert row["task_complete"] is True
    assert row["tool_call_count"] == 3
    assert row["visible_candidate_counts"] == [3]
    assert row["unauthorized_destructive_executions"] == 0
    assert max(len(tools) for tools in agent.seen) <= 3


@pytest.mark.parametrize("customer_id", ["C-42", "C-73"])
@pytest.mark.parametrize("expose_identifier", [True, False])
def test_paper_fork_agent_binds_consumer_arguments_from_visible_observation(
    customer_id, expose_identifier,
):
    router = build_fixture(500, mixed_scope=True)
    assert GROUP.source_type is not None and GROUP.license is not None
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="crm.paper_fork", aliases=ALIASES,
        required_fields=GROUP.required_fields, source_type=GROUP.source_type,
        license=GROUP.license,
    ),))
    view, _, selector = _prepare(
        router, catalog, ALIASES[0], ACTOR, indexed=True,
    )
    task = {
        "semantic_task_id": "e0-paper-observation-bound-not-independent",
        "query": ALIASES[0], "language": "en", "supported": True,
        "required_routes": [ROOT, LEFT, RIGHT],
        "executor_fixture": {"steps": [
            {"route_id": route, "argument_rules": (
                {} if route == ROOT else {"customer_id": {"eq": customer_id}}
            ), "observation": (
                ({"status": "ok", "customer_id": customer_id}
                 if expose_identifier else {"status": "ok"})
                if route == ROOT else {"status": "ok", "owner": "member"}
            )}
            for route in (ROOT, LEFT, RIGHT)
        ]},
    }
    agent = ObservationBoundAgent(ROOT, LEFT, RIGHT)
    row = run_generated_episode(
        agent, router.registry, task, EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=selector,
        experimental_agent_tool_surface=view,
    )
    assert row["passed"] is expose_identifier
    assert row["tool_call_count"] == (3 if expose_identifier else 1)
    assert agent.bound_ids == (
        [customer_id, customer_id] if expose_identifier else []
    )
    assert row["unauthorized_destructive_executions"] == 0


def test_forged_offered_routes_owner_mutation_and_source_changes_fail_closed():
    router = _direct_router()
    catalog = CATALOG.model_copy(deep=True)
    view, _, selector = _prepare(router, catalog)
    with pytest.raises(PolicyViolationError):
        selector(QUERY, ("foreign.route",))
    object.__setattr__(
        catalog.concepts[0], "aliases", ("different customer lookup",),
    )
    with pytest.raises(PolicyViolationError):
        selector(QUERY, view.visible_route_ids)

    router = _direct_router()
    view, _, selector = _prepare(router)
    router.add_tool(ToolSpec(
        name="revoked", endpoints=[EndpointSpec(name="read", read_only=True)],
    ))
    with pytest.raises(PolicyViolationError):
        selector(QUERY, view.visible_route_ids)


def test_unknown_query_and_bad_flag_are_not_source_authority():
    router = _direct_router()
    query = "unknown not a declared product field"
    view, _, selector = _prepare(router, query=query)
    assert selector(query, view.visible_route_ids) == []
    assert selector.last_status == "no_declared_concept_not_calibrated_no_fit"
    with pytest.raises(ValueError, match="boolean"):
        AuthorizedPaperFieldFixed5Selector(
            view, CATALOG, _index(router), experimental_indexed_direct=1,
        )


@pytest.mark.parametrize("indexed", [False, True])
def test_paper_projected_tool_definitions_only_disclose_selected_fields(indexed):
    router = _direct_router()
    view, index, selector = _prepare(router, indexed=indexed)
    definitions = selector.projected_tool_definitions(QUERY, view.visible_route_ids)
    assert len(definitions) == 1
    full = view.tool_definitions(["complete_0.read"])
    assert definitions[0]["name"] == full[0]["name"]
    assert definitions[0]["parameters"] == full[0]["parameters"]
    assert "status" in definitions[0]["description"]
    assert "owner" in definitions[0]["description"]
    assert "not execution authorization" in definitions[0]["description"]
    assert selector.last_status == "complete"
    assert len(json.dumps(definitions)) <= len(json.dumps(full)) + 120


def test_paper_projection_abstains_when_no_complete_field_plan():
    router = _direct_router(hidden=True)
    view, _, selector = _prepare(router)
    assert selector.projected_tool_definitions(QUERY, view.visible_route_ids) == []


def test_paper_projection_refuses_stale_source():
    router = _direct_router()
    view, _, selector = _prepare(router)
    router.add_tool(ToolSpec(
        name="new_source", endpoints=[EndpointSpec(name="read", read_only=True)],
    ))
    with pytest.raises(PolicyViolationError):
        selector.projected_tool_definitions(QUERY, view.visible_route_ids)


def test_paper_projection_never_mutates_original_model_surface():
    router = _direct_router()
    view, _, selector = _prepare(router)
    original = view.tool_definitions(["complete_0.read"])
    projected = selector.projected_tool_definitions(QUERY, view.visible_route_ids)
    projected[0]["parameters"]["required"].append("forged")
    assert view.tool_definitions(["complete_0.read"]) == original
