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
