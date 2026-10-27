"""A5 opt-in actual registered invoker: model picks route, host owns inputs."""

from __future__ import annotations

import json

import pytest
from test_research_paper_scoped_agent_real_e0 import CATALOG, INTENTS, QUERY

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    EndpointSpec,
    FieldSpec,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    ParameterSpec,
    PolicyViolationError,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.hooks import ExecutionHooks
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)


def _fixture(*, requires_input: bool = True, on_invoke=None):
    seen = []
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="complete.read", roles_any=("viewer",),
        ),),
    ))
    parameters = ([ParameterSpec(
        name="case_id", location="query", required=True,
        json_schema={"type": "string"},
    )] if requires_input else [])
    input_schema = ({
        "type": "object", "properties": {"case_id": {"type": "string"}},
        "required": ["case_id"],
    } if requires_input else {})

    def invoke(endpoint, arguments):
        assert endpoint == "read"
        seen.append(dict(arguments))
        if on_invoke is not None:
            on_invoke()
        return {"status": "open", "case_id": arguments.get("case_id", "static")}

    router.add_bound_tool(ToolSpec(
        name="complete", description="case status",
        source_type="crm", license="host-approved",
        endpoints=[EndpointSpec(
            name="read", read_only=True, description="case status",
            parameters=parameters, input_schema=input_schema,
            output_fields=[
                FieldSpec(name="status", semantic_id="case.status",
                          json_schema={"type": "string"}),
                FieldSpec(name="case_id", semantic_id="case.id",
                          json_schema={"type": "string"}, identifier=True),
            ],
        )],
    ), invoke)
    view = capture_authorized_agent_tool_surface(
        router, QUERY, principal=PrincipalContext(
            subject="native-e1", roles=("viewer",),
        ),
    )
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
        approved_host_roots=(frozenset({"complete.read"})
                             if requires_input else frozenset()),
    )
    return view, index, seen


def _understand(_payload):
    return {
        "intent_id": "case.lookup", "concept_ids": ["case.status"],
        "named_tools": ["complete"], "parameter_hints": {"case_id": "host-7"},
    }


def _kwargs(view, index):
    return dict(
        view=view, index=index, catalog=CATALOG, intent_registry=INTENTS,
        model_visible_intent_ids=("case.lookup",),
        model_visible_concept_ids=("case.status",),
    )


class Agent:
    def __init__(self, *, name="complete__read", arguments=None, on_generate=None):
        self.name = name
        self.arguments = arguments if arguments is not None else {"case_id": "forged"}
        self.on_generate = on_generate
        self.turns = 0
        self.messages = []
        self.tools = []

    def generate(self, messages, tools):
        self.messages.append(messages)
        self.tools.append(tools)
        if self.on_generate:
            self.on_generate()
        self.turns += 1
        payload = json.dumps({"name": self.name, "arguments": self.arguments})
        return {
            "text": f"<tool_call>{payload}</tool_call>",
            "input_tokens": 3, "output_tokens": 4, "tool_tokens": 3,
            "latency_ms": 0.0, "context_overflow": False,
        }


@pytest.mark.asyncio
async def test_real_registered_invoker_uses_host_reviewed_root_not_agent_id():
    from scripts.research_paper_scoped_native_direct_e1 import (
        run_paper_scoped_native_direct_e1,
    )

    view, index, seen = _fixture()
    agent = Agent(arguments={"case_id": "forged", "extra": "unexpected"})
    decision, receipt = await run_paper_scoped_native_direct_e1(
        _understand, agent, **_kwargs(view, index),
        review_model_root_arguments=lambda _proposal: True,
    )
    assert decision == "offer" and receipt is not None
    assert seen == [{"case_id": "host-7"}]
    assert receipt.result.tool == "complete"
    assert receipt.result.endpoint == "read"
    assert receipt.result.data["status"] == "open"
    assert receipt.result.projected_fields == ["status", "case_id"]
    assert receipt.host_bound_tool_calls == 1
    assert receipt.independent_e2 is False
    assert receipt.executable_authority is False
    assert "host-7" not in str(agent.messages)
    assert "host-7" not in str(agent.tools)


@pytest.mark.asyncio
async def test_unreviewed_input_never_asks_agent_or_invokes_native_provider():
    from scripts.research_paper_scoped_native_direct_e1 import (
        run_paper_scoped_native_direct_e1,
    )

    view, index, seen = _fixture()

    class Forbidden:
        def generate(self, _messages, _tools):
            pytest.fail("unreviewed input must not reach live native invoker")

    decision, receipt = await run_paper_scoped_native_direct_e1(
        _understand, Forbidden(), **_kwargs(view, index),
    )
    assert decision == "request_arguments" and receipt is None
    assert seen == []


@pytest.mark.asyncio
async def test_original_zero_input_direct_call_reaches_registered_executor():
    from scripts.research_paper_scoped_native_direct_e1 import (
        run_paper_scoped_native_direct_e1,
    )

    view, index, seen = _fixture(requires_input=False)
    decision, receipt = await run_paper_scoped_native_direct_e1(
        _understand, Agent(arguments={}), **_kwargs(view, index),
    )
    assert decision == "offer" and receipt is not None
    assert seen == [{}]
    assert receipt.host_bound_tool_calls == 0
    assert receipt.result.data["status"] == "open"


@pytest.mark.asyncio
async def test_agent_cannot_tamper_offered_tool_definition_to_invoke_other_name():
    from scripts.research_paper_scoped_native_direct_e1 import (
        run_paper_scoped_native_direct_e1,
    )

    view, index, seen = _fixture()

    class ToolDefinitionMutator(Agent):
        def generate(self, messages, tools):
            tools[0]["name"] = "hidden__read"
            self.name = "hidden__read"
            return super().generate(messages, tools)

    with pytest.raises(PolicyViolationError, match="tool definition|modified"):
        await run_paper_scoped_native_direct_e1(
            _understand, ToolDefinitionMutator(), **_kwargs(view, index),
            review_model_root_arguments=lambda _proposal: True,
        )
    assert seen == []


@pytest.mark.asyncio
async def test_agent_cannot_rebind_original_native_invoker_under_same_schema():
    from scripts.research_paper_scoped_native_direct_e1 import (
        run_paper_scoped_native_direct_e1,
    )

    view, index, seen = _fixture()
    replaced = []

    def replacement(endpoint, arguments):
        replaced.append((endpoint, arguments))
        return {"status": "hijacked", "case_id": "wrong"}

    def rebind():
        view.router.executor.bind(
            "complete", replacement,
            expected_fingerprint=view.router.registry.get("complete").fingerprint,
        )

    with pytest.raises(PolicyViolationError, match="binding|invoker"):
        await run_paper_scoped_native_direct_e1(
            _understand, Agent(on_generate=rebind), **_kwargs(view, index),
            host_source_arguments={"complete.read": {"case_id": "host-7"}},
        )
    assert seen == []
    assert replaced == []


@pytest.mark.asyncio
async def test_native_before_hook_cannot_swap_invoker_after_preflight():
    from scripts.research_paper_scoped_native_direct_e1 import (
        run_paper_scoped_native_direct_e1,
    )

    view, index, seen = _fixture()
    replaced = []

    def replacement(endpoint, arguments):
        replaced.append((endpoint, arguments))
        return {"status": "hijacked", "case_id": "wrong"}

    async def rebind_during_hook(_tool, _endpoint, _call):
        view.router.executor.bind(
            "complete", replacement,
            expected_fingerprint=view.router.registry.get("complete").fingerprint,
        )

    view.router.executor.hooks = ExecutionHooks(before_call=(rebind_during_hook,))
    with pytest.raises(PolicyViolationError, match="binding|invoker"):
        await run_paper_scoped_native_direct_e1(
            _understand, Agent(), **_kwargs(view, index),
            host_source_arguments={"complete.read": {"case_id": "host-7"}},
        )
    assert seen == []
    assert replaced == []


def test_generation_scope_rejects_distinct_executor_with_same_generation():
    from schemarouter.executor import (
        RegistryExecutor,
        _require_bound_invoker_generation,
    )

    view, _index, _seen = _fixture()
    first = view.router.executor
    second = RegistryExecutor(view.router.registry)
    fingerprint = view.router.registry.get("complete").fingerprint
    second.bind("complete", lambda _endpoint, _args: None,
                expected_fingerprint=fingerprint)
    generation = first._binding_snapshot("complete").generation
    assert generation == second._binding_snapshot("complete").generation
    assert generation is not None

    with _require_bound_invoker_generation(first, "complete", generation):
        with pytest.raises(PolicyViolationError, match="binding|invoker"):
            second._binding_for_validated_contract("complete", fingerprint)


@pytest.mark.asyncio
async def test_deeply_nested_agent_tool_json_is_rejected_without_native_call():
    from scripts.research_paper_scoped_native_direct_e1 import (
        run_paper_scoped_native_direct_e1,
    )

    view, index, seen = _fixture()

    class DeepCall(Agent):
        def generate(self, messages, tools):
            del messages, tools
            self.turns += 1
            argument = "[" * 1100 + '"forged"' + "]" * 1100
            return {
                "text": ('<tool_call>{"name":"complete__read","arguments":'
                         f'{{"case_id":{argument}}}' + "}</tool_call>"),
                "input_tokens": 3, "output_tokens": 4, "tool_tokens": 3,
                "latency_ms": 0.0, "context_overflow": False,
            }

    decision, receipt = await run_paper_scoped_native_direct_e1(
        _understand, DeepCall(), **_kwargs(view, index),
        review_model_root_arguments=lambda _proposal: True,
    )
    assert decision == "abstain" and receipt is None
    assert seen == []


@pytest.mark.asyncio
async def test_duplicate_tool_call_json_keys_never_reach_native_executor():
    from scripts.research_paper_scoped_native_direct_e1 import (
        run_paper_scoped_native_direct_e1,
    )

    view, index, seen = _fixture()

    class AmbiguousAgent:
        def generate(self, _messages, _tools):
            return {
                "text": ('<tool_call>{"name":"hidden__read",'
                         '"name":"complete__read","arguments":{}}</tool_call>'),
                "context_overflow": False,
            }

    decision, receipt = await run_paper_scoped_native_direct_e1(
        _understand, AmbiguousAgent(), **_kwargs(view, index),
        host_source_arguments={"complete.read": {"case_id": "host-7"}},
    )
    assert decision == "abstain" and receipt is None
    assert seen == []


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["unknown", "parallel", "malformed"])
async def test_unoffered_parallel_or_malformed_call_cannot_invoke_native(invalid):
    from scripts.research_paper_scoped_native_direct_e1 import (
        run_paper_scoped_native_direct_e1,
    )

    view, index, seen = _fixture()

    class MalformedAgent(Agent):
        def generate(self, messages, tools):
            del messages, tools
            self.turns += 1
            text = {
                "unknown": '<tool_call>{"name":"hidden__read","arguments":{}}</tool_call>',
                "parallel": (
                    '<tool_call>{"name":"complete__read","arguments":{}}</tool_call>'
                    '<tool_call>{"name":"complete__read","arguments":{}}</tool_call>'
                ),
                "malformed": '<tool_call>{"name":"complete__read",</tool_call>',
            }[invalid]
            return {
                "text": text, "input_tokens": 1, "output_tokens": 1,
                "tool_tokens": 1, "latency_ms": 0.0, "context_overflow": False,
            }

    decision, receipt = await run_paper_scoped_native_direct_e1(
        _understand, MalformedAgent(), **_kwargs(view, index),
        review_model_root_arguments=lambda _proposal: True,
    )
    assert decision == "abstain" and receipt is None
    assert seen == []


@pytest.mark.asyncio
async def test_native_invoker_cannot_return_success_after_policy_revocation():
    from scripts.research_paper_scoped_native_direct_e1 import (
        run_paper_scoped_native_direct_e1,
    )

    holder = {}

    def revoke():
        holder["router"].authorization_policy = AuthorizationPolicy(default_effect="deny")

    view, index, seen = _fixture(on_invoke=revoke)
    holder["router"] = view.router
    with pytest.raises(PolicyViolationError):
        await run_paper_scoped_native_direct_e1(
            _understand, Agent(), **_kwargs(view, index),
            host_source_arguments={"complete.read": {"case_id": "host-7"}},
        )
    assert seen == [{"case_id": "host-7"}]


@pytest.mark.asyncio
async def test_unapproved_optional_model_value_is_not_sent_on_empty_source_input():
    from scripts.research_paper_scoped_native_direct_e1 import (
        run_paper_scoped_native_direct_e1,
    )

    view, index, seen = _fixture(requires_input=False)
    decision, receipt = await run_paper_scoped_native_direct_e1(
        _understand, Agent(arguments={"case_id": "model-invented"}),
        **_kwargs(view, index),
    )
    assert decision == "abstain" and receipt is None
    assert seen == []
