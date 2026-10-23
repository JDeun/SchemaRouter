"""A model must request schemas before choosing real read-only native calls."""

from __future__ import annotations

import json

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from scripts.research_codegraph_scoped_materializer import capture_surgical_episode

SCHEMA = (
    '<tool_call>{"name":"research__request_scoped_source_schema",'
    '"arguments":{"route_ids":["contacts.read","cases.read"]}}</tool_call>'
)
CONTACT = '<tool_call>{"name":"contacts__read","arguments":{}}</tool_call>'
CASE = (
    '<tool_call>{"name":"cases__read",'
    '"arguments":{"contact_id":"contact-4","region_id":"region-9"}}</tool_call>'
)
FINAL = '{"status":"ready"}'


class ScriptedAgent:
    def __init__(self, responses, *, mutate_at=None):
        self.responses = list(responses)
        self.mutate_at = mutate_at
        self.offered = []
        self.histories = []

    def generate(self, messages, tools):
        self.offered.append([row["name"] for row in tools])
        self.histories.append(json.loads(json.dumps(messages)))
        index = len(self.offered) - 1
        if index >= len(self.responses):
            raise AssertionError("unexpected extra model generation")
        if self.mutate_at and index == 2:
            self.mutate_at()
        return {
            "text": self.responses[index], "context_overflow": False,
            "latency_ms": 2.0, "input_tokens": 30 + index,
            "tool_tokens": 8, "output_tokens": 11,
        }


def _source():
    from scripts.research_codegraph_surgical_agent_e1 import SurgicalHostContext

    seen = []
    # The E0 synthetic source exposes a provider field literally named
    # `status`, which clashes with the existing host transport's `status`.
    # Register an equivalent two-step original source with a distinct field
    # name to assert the real provider result survives projection unchanged.
    aliases = ("case status", "문의 상태", "問い合わせ状態")
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.*", roles_any=("reader",),
        ),),
    ))
    router.add_tool(ToolSpec(
        name="contacts", source_type="crm", license="synthetic-owner-review",
        description="case status producer",
        endpoints=[EndpointSpec(
            name="read", description="contact source identifiers", read_only=True,
            output_fields=[FieldSpec(
                name=name, semantic_id=f"crm.{name}", identifier=True,
                json_schema={"type": "string"},
            ) for name in ("contact_id", "region_id")],
            output_schema={
                "type": "object",
                "properties": {name: {"type": "string"} for name in (
                    "contact_id", "region_id",
                )},
                "required": ["contact_id", "region_id"],
            },
        )],
    ))
    router.add_tool(ToolSpec(
        name="cases", source_type="crm", license="synthetic-owner-review",
        description="case status consumer",
        endpoints=[EndpointSpec(
            name="read", description="case status", read_only=True,
            parameters=[ParameterSpec(
                name=name, semantic_id=f"crm.{name}", required=True,
                json_schema={"type": "string"},
            ) for name in ("contact_id", "region_id")],
            output_fields=[FieldSpec(
                name="case_state", semantic_id="crm.status",
                json_schema={"type": "string"},
            )],
        )],
    ))
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="case_status", aliases=aliases,
        required_fields=(CapabilityFieldContract(
            semantic_id="crm.status", json_schema={"type": "string"},
        ),),
        source_type="crm", license="synthetic-owner-review",
    ),))
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))

    def contacts(_endpoint, args):
        seen.append(("contacts.read", dict(args)))
        return {"contact_id": "contact-4", "region_id": "region-9"}

    def cases(_endpoint, args):
        seen.append(("cases.read", dict(args)))
        return {"case_state": "ready" if args == {
            "contact_id": "contact-4", "region_id": "region-9",
        } else "invalid"}

    for name, callback in (("contacts", contacts), ("cases", cases)):
        tool = router.registry.get(name)
        router.executor.bind(tool.key, callback, expected_fingerprint=tool.fingerprint)

    principal = PrincipalContext(subject="reader", roles=("reader",))
    episode = capture_surgical_episode(
        router, "case status", principal=principal, catalog=catalog, index=index,
    )
    context = SurgicalHostContext(
        trusted_route_inputs={},
        required_output_fields={
            "contacts.read": ("contact_id", "region_id"),
            "cases.read": ("case_state",),
        },
        validate_final=lambda text, observed: (
            json.loads(text) == {"status": observed["case_state"]}
        ),
    )
    return router, episode, principal, context, seen


@pytest.mark.asyncio
async def test_model_requests_schema_then_calls_two_registered_read_only_routes():
    from scripts.research_codegraph_surgical_agent_e1 import run_surgical_model_episode

    _, episode, _, context, seen = _source()
    agent = ScriptedAgent([SCHEMA, CONTACT, CASE, FINAL])
    result = await run_surgical_model_episode(agent, episode=episode, host_context=context)
    assert result["schema_requests"] == 1
    assert result["actual_source_calls"] == 2
    assert result["model_turns"] == 4
    assert result["full_task_correct"] is True
    assert result["termination_reason"] == "completed_final"
    assert [name for name, _ in seen] == ["contacts.read", "cases.read"]
    assert seen[1][1] == {"contact_id": "contact-4", "region_id": "region-9"}
    assert result["total_model_tokens"] == sum(30 + i + 11 for i in range(4))
    assert "contact-4" not in json.dumps(result)


@pytest.mark.asyncio
async def test_bare_schema_treatment_only_reparses_currently_offered_schema_request():
    from scripts.research_codegraph_surgical_agent_e1 import run_surgical_model_episode

    bare_schema = SCHEMA.removeprefix("<tool_call>").removesuffix("</tool_call>")
    _, episode, _, context, seen = _source()
    original = await run_surgical_model_episode(
        ScriptedAgent([bare_schema]), episode=episode, host_context=context,
        diagnose_model_actions=True,
    )
    assert original["schema_requests"] == original["actual_source_calls"] == 0
    assert original["termination_reason"] == "premature_final"
    assert original["action_structure_labels"] == [
        "bare_json_offered_schema_request_shape",
    ]
    assert "bare_schema_request_normalizations" not in original

    treated = await run_surgical_model_episode(
        ScriptedAgent([bare_schema, CONTACT, CASE, FINAL]),
        episode=episode, host_context=context, diagnose_model_actions=True,
        experimental_bare_schema_request=True,
    )
    assert treated["schema_requests"] == 1
    assert treated["actual_source_calls"] == len(seen) == 2
    assert treated["bare_schema_request_normalizations"] == 1
    assert treated["full_task_correct"] is True
    assert treated["model_turns"] == 4
    assert treated["termination_reason"] == "completed_final"
    assert "contact-4" not in json.dumps(treated)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", (
    '{"name":"research__request_scoped_source_schema",'
    '"arguments":{"route_ids":["contacts.read","contacts.read"]}}',
    '{"name":"research__request_scoped_source_schema",'
    '"arguments":{"route_ids":["contacts.read"]},"extra":true}',
    '{"name":"research__request_scoped_source_schema",'
    '"name":"research__request_scoped_source_schema",'
    '"arguments":{"route_ids":["contacts.read"]}}',
    '{"name":"contacts__read","arguments":{}}',
    '{"name":"research__request_scoped_source_schema",'
    '"arguments":{"route_ids":["unapproved.read"]}}',
))
async def test_bare_schema_treatment_never_executes_untrusted_or_unoffered_route(bad):
    from scripts.research_codegraph_surgical_agent_e1 import run_surgical_model_episode

    _, episode, _, context, seen = _source()
    result = await run_surgical_model_episode(
        ScriptedAgent([bad]), episode=episode, host_context=context,
        experimental_bare_schema_request=True,
    )
    assert result["schema_requests"] <= 1
    assert result["actual_source_calls"] == len(seen) == 0
    assert result["full_task_correct"] is False
    assert result["bare_schema_request_normalizations"] <= 1


@pytest.mark.asyncio
async def test_bare_schema_request_not_reaccepted_after_materialization():
    from scripts.research_codegraph_surgical_agent_e1 import run_surgical_model_episode

    _, episode, _, context, seen = _source()
    bare_schema = SCHEMA.removeprefix("<tool_call>").removesuffix("</tool_call>")
    result = await run_surgical_model_episode(
        ScriptedAgent([SCHEMA, bare_schema]), episode=episode, host_context=context,
        experimental_bare_schema_request=True,
    )
    assert result["schema_requests"] == 1
    assert result["bare_schema_request_normalizations"] == 0
    assert result["actual_source_calls"] == len(seen) == 0


@pytest.mark.asyncio
async def test_bare_schema_experiment_requires_boolean():
    from scripts.research_codegraph_surgical_agent_e1 import run_surgical_model_episode

    _, episode, _, context, _ = _source()
    with pytest.raises(ValueError, match="bare schema"):
        await run_surgical_model_episode(
            ScriptedAgent([SCHEMA]), episode=episode, host_context=context,
            experimental_bare_schema_request=1,
        )


@pytest.mark.asyncio
async def test_initial_menu_has_only_schema_request_and_no_provider_tool():
    from scripts.research_codegraph_surgical_agent_e1 import run_surgical_model_episode

    _, episode, _, context, seen = _source()
    agent = ScriptedAgent(["REQUEST_MORE_TOOLS"])
    result = await run_surgical_model_episode(agent, episode=episode, host_context=context)
    assert agent.offered[0] == ["research__request_scoped_source_schema"]
    assert "contacts__read" not in json.dumps(agent.histories[0])
    assert result["termination_reason"] == "premature_final"
    assert result["actual_source_calls"] == len(seen) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ("hidden_binding", "principal_swap"))
async def test_agent_aborts_hidden_binding_or_principal_swap_before_consumer(kind):
    from schemarouter import DataScopeRule
    from scripts.research_codegraph_surgical_agent_e1 import run_surgical_model_episode

    router, episode, principal, context, seen = _source()

    def mutate():
        if kind == "hidden_binding":
            policy = router.authorization_policy
            assert policy is not None
            object.__setattr__(policy, "data_rules", (
                DataScopeRule(operation="contacts.read", hidden_fields=("region_id",)),
            ))
        else:
            object.__setattr__(principal, "roles", ("viewer",))

    agent = ScriptedAgent([SCHEMA, CONTACT, CASE], mutate_at=mutate)
    result = await run_surgical_model_episode(agent, episode=episode, host_context=context)
    assert result["actual_source_calls"] == len(seen) == 1
    assert result["termination_reason"] == "authorization_changed"
    assert result["full_task_correct"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", (
    '<tool_call>{"name":"research__request_scoped_source_schema",'
    '"arguments":{"route_ids":["contacts.read",]}}</tool_call>',
    '<tool_call>{"name":"research__request_scoped_source_schema",'
    '"arguments":{"route_ids":["contacts.read","contacts.read"]}}</tool_call>',
    '<tool_call>{"name":"research__request_scoped_source_schema",'
    '"arguments":{"route_ids":["cases.*"]}}</tool_call>',
))
async def test_agent_rejects_malformed_or_repeated_schema_requests_without_source_call(bad):
    from scripts.research_codegraph_surgical_agent_e1 import run_surgical_model_episode

    _, episode, _, context, seen = _source()
    result = await run_surgical_model_episode(
        ScriptedAgent([bad]), episode=episode, host_context=context,
    )
    assert result["actual_source_calls"] == len(seen) == 0
    assert result["termination_reason"] in {"malformed_call", "schema_request_denied"}

    repeated = await run_surgical_model_episode(
        ScriptedAgent([SCHEMA, SCHEMA]), episode=episode, host_context=context,
    )
    assert repeated["schema_requests"] == 1
    assert repeated["actual_source_calls"] == len(seen) == 0
    assert repeated["termination_reason"] == "unoffered_or_repeated_schema_request"


@pytest.mark.asyncio
async def test_unmaterialized_route_is_refused_without_original_invocation():
    from scripts.research_codegraph_surgical_agent_e1 import run_surgical_model_episode

    _, episode, _, context, seen = _source()
    result = await run_surgical_model_episode(
        ScriptedAgent([CONTACT]), episode=episode, host_context=context,
    )
    assert result["schema_requests"] == 0
    assert result["actual_source_calls"] == len(seen) == 0
    assert result["termination_reason"] == "unoffered_native_route"


@pytest.mark.asyncio
async def test_premature_final_and_unbound_arguments_are_task_failures():
    from scripts.research_codegraph_surgical_agent_e1 import run_surgical_model_episode

    _, episode, _, context, seen = _source()
    early = await run_surgical_model_episode(
        ScriptedAgent([SCHEMA, FINAL]), episode=episode, host_context=context,
    )
    assert early["full_task_correct"] is False
    assert early["actual_source_calls"] == 0

    forged = CASE.replace("contact-4", "forged-contact")
    bad = await run_surgical_model_episode(
        ScriptedAgent([SCHEMA, CONTACT, forged]),
        episode=episode, host_context=context,
    )
    assert bad["actual_source_calls"] == 1
    assert bad["full_task_correct"] is False
    assert bad["termination_reason"] == "unbound_source_arguments"
    assert [route for route, _ in seen] == ["contacts.read"]


@pytest.mark.asyncio
@pytest.mark.parametrize(("responses", "expected_label", "source_calls"), (
    ([SCHEMA, '<tool_call>{"name":"contacts__read",'
     '"arguments":{"leak":"private-99"}}</tool_call>'],
     "unexpected_argument_keys", 0),
    ([SCHEMA, CONTACT, '<tool_call>{"name":"cases__read",'
     '"arguments":{"contact_id":"contact-4"}}</tool_call>'],
     "missing_argument_keys", 1),
    ([SCHEMA, CONTACT, CASE.replace("contact-4", "secret-99")],
     "argument_value_mismatch", 1),
    ([SCHEMA, CONTACT, '<tool_call>{"name":"cases__read",'
     '"arguments":{"region_id":"region-9",'
     '"leak":"secret-99"}}</tool_call>'],
     "unexpected_and_missing_argument_keys", 1),
))
async def test_unbound_argument_diagnostic_only_reports_private_safe_category(
    responses, expected_label, source_calls,
):
    from scripts.research_codegraph_surgical_agent_e1 import run_surgical_model_episode

    _, episode, _, context, seen = _source()
    result = await run_surgical_model_episode(
        ScriptedAgent(responses), episode=episode, host_context=context,
        diagnose_model_actions=True,
    )
    assert result["termination_reason"] == "unbound_source_arguments"
    assert result["argument_alignment_labels"] == [expected_label]
    assert result["actual_source_calls"] == len(seen) == source_calls
    assert result["full_task_correct"] is False
    serialized = json.dumps(result)
    assert "secret-99" not in serialized
    assert "private-99" not in serialized
    assert "leak" not in serialized


@pytest.mark.asyncio
async def test_argument_alignment_diagnostics_absent_by_default_and_empty_on_success():
    from scripts.research_codegraph_surgical_agent_e1 import run_surgical_model_episode

    _, episode, _, context, seen = _source()
    green = await run_surgical_model_episode(
        ScriptedAgent([SCHEMA, CONTACT, CASE, FINAL]),
        episode=episode, host_context=context, diagnose_model_actions=True,
    )
    assert green["argument_alignment_labels"] == []
    assert green["full_task_correct"] is True
    assert len(seen) == 2

    private = await run_surgical_model_episode(
        ScriptedAgent([SCHEMA, CONTACT, CASE, FINAL]),
        episode=episode, host_context=context,
    )
    assert "argument_alignment_labels" not in private


@pytest.mark.asyncio
async def test_graph_path_order_cue_is_model_only_and_cannot_execute_wrong_prefix():
    from scripts.research_codegraph_surgical_agent_e1 import (
        GRAPH_PATH_ORDER_CUE_E1,
        run_surgical_model_episode,
    )

    _, episode, _, context, seen = _source()
    treated_agent = ScriptedAgent([SCHEMA, CASE])
    treated = await run_surgical_model_episode(
        treated_agent, episode=episode, host_context=context,
        diagnose_model_actions=True, experimental_single_step_prompt=True,
        experimental_bare_schema_request=True,
        experimental_graph_path_order_prompt=True,
    )
    assert "route_sets" in GRAPH_PATH_ORDER_CUE_E1
    assert "first" in GRAPH_PATH_ORDER_CUE_E1
    assert GRAPH_PATH_ORDER_CUE_E1 in treated_agent.histories[0][0]["content"]
    assert "contact-4" not in GRAPH_PATH_ORDER_CUE_E1
    assert "contacts.read" not in GRAPH_PATH_ORDER_CUE_E1
    assert treated["termination_reason"] == "unbound_source_arguments"
    assert treated["argument_alignment_labels"] == ["unsupported_bound_path"]
    assert treated["actual_source_calls"] == len(seen) == 0

    default_agent = ScriptedAgent([SCHEMA, CASE])
    await run_surgical_model_episode(
        default_agent, episode=episode, host_context=context,
    )
    assert GRAPH_PATH_ORDER_CUE_E1 not in default_agent.histories[0][0]["content"]


@pytest.mark.asyncio
async def test_graph_path_order_cue_preserves_strict_two_hop_valid_execution():
    from scripts.research_codegraph_surgical_agent_e1 import run_surgical_model_episode

    bare = SCHEMA.removeprefix("<tool_call>").removesuffix("</tool_call>")
    _, episode, _, context, seen = _source()
    result = await run_surgical_model_episode(
        ScriptedAgent([bare, CONTACT, CASE, FINAL]),
        episode=episode, host_context=context, diagnose_model_actions=True,
        experimental_single_step_prompt=True,
        experimental_bare_schema_request=True,
        experimental_graph_path_order_prompt=True,
    )
    assert result["full_task_correct"] is True
    assert result["schema_requests"] == 1
    assert result["actual_source_calls"] == len(seen) == 2
    assert result["bare_schema_request_normalizations"] == 1
    assert result["argument_alignment_labels"] == []


@pytest.mark.asyncio
async def test_graph_path_order_cue_requires_boolean():
    from scripts.research_codegraph_surgical_agent_e1 import run_surgical_model_episode

    _, episode, _, context, _ = _source()
    with pytest.raises(ValueError, match="graph path order"):
        await run_surgical_model_episode(
            ScriptedAgent([SCHEMA]), episode=episode, host_context=context,
            experimental_graph_path_order_prompt=1,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(("one_step", "bare_schema"), (
    (False, True),
    (True, False),
    (False, False),
))
async def test_graph_path_order_cue_requires_existing_research_protocols(
    one_step, bare_schema,
):
    from scripts.research_codegraph_surgical_agent_e1 import run_surgical_model_episode

    _, episode, _, context, seen = _source()
    with pytest.raises(ValueError, match="graph path order"):
        await run_surgical_model_episode(
            ScriptedAgent([SCHEMA]), episode=episode, host_context=context,
            experimental_single_step_prompt=one_step,
            experimental_bare_schema_request=bare_schema,
            experimental_graph_path_order_prompt=True,
        )
    assert seen == []


@pytest.mark.asyncio
async def test_schema_request_does_not_change_source_call_count():
    from scripts.research_codegraph_surgical_agent_e1 import run_surgical_model_episode

    _, episode, _, context, seen = _source()
    result = await run_surgical_model_episode(
        ScriptedAgent([SCHEMA, "REQUEST_MORE_TOOLS"]),
        episode=episode, host_context=context,
    )
    assert result["schema_requests"] == 1
    assert result["actual_source_calls"] == len(seen) == 0
    assert result["model_turns"] == 2


@pytest.mark.asyncio
async def test_optin_structure_labels_preserve_strict_original_execution():
    from scripts.research_codegraph_action_shape_e1 import CATEGORIES
    from scripts.research_codegraph_surgical_agent_e1 import run_surgical_model_episode

    _, episode, _, context, seen = _source()
    report = await run_surgical_model_episode(
        ScriptedAgent([SCHEMA, CONTACT, CASE, FINAL]),
        episode=episode, host_context=context, diagnose_model_actions=True,
    )
    assert report["termination_reason"] == "completed_final"
    assert report["full_task_correct"] is True
    assert report["actual_source_calls"] == 2
    assert report["action_structure_labels"] == [
        "valid_schema_request_shape",
        "valid_native_tool_call_shape",
        "valid_native_tool_call_shape",
        "bare_final_json",
    ]
    assert set(report["action_structure_labels"]) <= CATEGORIES
    assert "contact-4" not in json.dumps(report)
    assert len(seen) == 2

    no_diagnostics = await run_surgical_model_episode(
        ScriptedAgent([SCHEMA, CONTACT, CASE, FINAL]),
        episode=episode, host_context=context,
    )
    assert "action_structure_labels" not in no_diagnostics


@pytest.mark.asyncio
async def test_after_schema_malformed_label_is_fixed_and_private():
    from scripts.research_codegraph_surgical_agent_e1 import run_surgical_model_episode

    _, episode, _, context, seen = _source()
    bad = '<tool_call>{"name":"contacts__read","arguments":{"secret":[]}}</tool_call>'
    report = await run_surgical_model_episode(
        ScriptedAgent([SCHEMA, bad]),
        episode=episode, host_context=context, diagnose_model_actions=True,
    )
    assert report["termination_reason"] == "malformed_call"
    assert report["action_structure_labels"] == [
        "valid_schema_request_shape", "non_scalar_arguments",
    ]
    assert report["actual_source_calls"] == len(seen) == 0
    assert "secret" not in json.dumps(report)
