"""One A5 original-paper direct call per real native adapter, same G5 registry."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    ExecutionPolicy,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    PrincipalContext,
    SchemaRouter,
)
from schemarouter.adapters import review_optimade_paper_tool, tool_from_mcp, tool_from_openapi
from schemarouter.adapters.optimade import _tool_from_discovery
from schemarouter.paper_understood_direct_plan import (
    PaperIntentDeclaration,
    PaperIntentRegistry,
)
from schemarouter.semantic_attestations import (
    HostSemanticAttestation,
    HostSemanticMapping,
    apply_host_semantic_attestation,
)
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)


class ScriptedAgent:
    def __init__(self, *, force_route: str | None = None):
        self.turns = 0
        self.force_route = force_route

    def generate(self, messages: list[dict[str, str]],
                 tools: list[dict[str, Any]]) -> dict[str, Any]:
        del messages
        self.turns += 1
        tool_name = self.force_route or tools[0]["name"]
        # The agent proposes unapproved values; only host inputs can reach I/O.
        raw = {"name": tool_name, "arguments": {"item_id": "forged", "repoName": "wrong"}}
        return {"text": f"<tool_call>{json.dumps(raw)}</tool_call>",
                "context_overflow": False}


def _review(tool, endpoint_name: str, field_name: str, semantic_id: str,
            identifier_name: str, identifier_semantic: str, source: str):
    tool.source_type = source
    tool.license = "host-reviewed-e1"
    endpoint = tool.endpoint(endpoint_name)
    endpoint.read_only = True  # Explicit local review, never MCP readOnlyHint authority.
    endpoint.destructive = False
    original_id = next(f for f in endpoint.output_fields if f.name == identifier_name)
    original_id.identifier = True  # Approved source-declared response identity.
    return apply_host_semantic_attestation(tool, attestation=HostSemanticAttestation(
        expected_tool_key=tool.key,
        expected_tool_fingerprint=tool.fingerprint,
        source_type=tool.source_type,
        license=tool.license,
        reviewed_by="local-source-contract-review",
        mappings=(HostSemanticMapping(
            endpoint_name=endpoint_name,
            expected_endpoint_fingerprint=endpoint.fingerprint,
            member_kind="output_field", member_name=field_name,
            semantic_id=semantic_id,
        ), HostSemanticMapping(
            endpoint_name=endpoint_name,
            expected_endpoint_fingerprint=endpoint.fingerprint,
            member_kind="output_field", member_name=identifier_name,
            semantic_id=identifier_semantic,
        )),
    ))


def _fixtures(*, fail_second: bool = False,
              allow_unrequested_openapi: bool = False):
    openapi = tool_from_openapi("source_rest", {
        "openapi": "3.1.0", "info": {"title": "Public Metadata", "version": "1"},
        "paths": {"/items/{item_id}": {"get": {
            "operationId": "get_title",
            "parameters": [{"name": "item_id", "in": "path", "required": True,
                            "schema": {"type": "string"}}],
            "responses": {"200": {"description": "OK", "content": {
                "application/json": {"schema": {"type": "object", "properties": {
                    "title": {"type": "string"}, "id": {"type": "string"}},
                    "required": ["title", "id"]}}}}},
        }}},
    })
    mcp = tool_from_mcp("source_mcp", {"tools": [{
        "name": "read_wiki_structure",
        "annotations": {"readOnlyHint": True},
        "inputSchema": {"type": "object", "properties": {
            "repoName": {"type": "string"}}, "required": ["repoName"]},
        "outputSchema": {"type": "object", "properties": {
            "result": {"type": "string"}, "repoName": {"type": "string"}},
            "required": ["result", "repoName"]},
    }]})
    optimade = _tool_from_discovery(
        name="source_optimade", namespace=None,
        versioned_base_url="https://example.invalid/v1",
        base_info={"api_version": "1.2.0"},
        entries={"structures": {
            "properties": {"chemical_formula_descriptive": {"type": "string"}},
            "output_fields_by_format": {"json": ["chemical_formula_descriptive"]},
        }}, skipped=[],
    )
    optimade = review_optimade_paper_tool(
        optimade, expected_fingerprint=optimade.fingerprint,
        expected_versioned_base_url="https://example.invalid/v1",
        entry_type="structures", license="host-reviewed-e1",
        field_semantic_ids={"chemical_formula_descriptive": "materials.formula"},
        identifier_semantic_id="materials.entry_id",
    )
    descriptions = (
        (_review(openapi, "get_title", "title", "paper.title", "id",
                 "paper.record_id", "public_rest"),
         "source_rest.get_title", "paper.lookup", "paper.title", "title",
         {"item_id": "host-article"}, {"id": "host-article", "title": "Verified title"}),
        (_review(mcp, "read_wiki_structure", "result", "wiki.outline", "repoName",
                 "wiki.repository_id", "public_mcp"),
         "source_mcp.read_wiki_structure", "wiki.lookup", "wiki.outline", "result",
         {"repoName": "modelcontextprotocol/servers"},
         {"repoName": "modelcontextprotocol/servers", "result": "Verified wiki index"}),
        (optimade,
         "source_optimade.get_structures", "materials.lookup",
         "materials.formula", "chemical_formula_descriptive",
         {"id": "source-123"},
         {"type": "structures", "id": "source-123",
          "chemical_formula_descriptive": "O2Si"}),
    )
    router = SchemaRouter(
        policy=ExecutionPolicy(allow_unclassified_remote=True),
        authorization_policy=AuthorizationPolicy(
            default_effect="deny", rules=(AuthorizationRule(
                effect="allow", operation="*.*", roles_any=("reader",),
            ),),
        ),
    )
    seen: list[tuple[str, dict]] = []
    concepts = []
    intents = []
    for tool, route, intent, concept, field, _inputs, output in descriptions:
        def invoke(endpoint, arguments, *, route=route, output=output):
            seen.append((route, dict(arguments)))
            if fail_second and route == "source_mcp.read_wiki_structure":
                raise RuntimeError("simulated native MCP outage")
            return dict(output)

        router.add_bound_tool(tool, invoke)
        projected = tool.endpoint(route.rpartition(".")[2])
        contract = next(f for f in projected.output_fields if f.name == field)
        assert contract.semantic_id is not None
        assert tool.source_type is not None and tool.license is not None
        required_fields = [CapabilityFieldContract(
            semantic_id=contract.semantic_id, json_schema={"type": "string"},
        )]
        if tool.source_type == "optimade":
            # Both OPTIMADE search and get produce the formula; require the
            # source-reviewed identifier as well to prove the exact get route.
            required_fields.append(CapabilityFieldContract(
                semantic_id="materials.entry_id", json_schema={"type": "string"},
            ))
        concepts.append(NativeDeclaredConcept(
            concept_id=concept, aliases=(concept.replace(".", " "),),
            required_fields=tuple(required_fields),
            source_type=tool.source_type, license=tool.license,
        ))
        intents.append(PaperIntentDeclaration(
            intent_id=intent, required_concept_ids=(concept,),
        ))
    approved_routes = {route for _, route, *_ in descriptions}
    if allow_unrequested_openapi:
        for extra_name in ("source_rest_public", "source_rest_alt"):
            alternate = tool_from_openapi(extra_name, {
                "openapi": "3.1.0", "info": {"title": "Other Metadata", "version": "1"},
                "paths": {"/info": {"get": {
                    "operationId": "get_title",
                    "responses": {"200": {"description": "OK", "content": {
                        "application/json": {"schema": {"type": "object", "properties": {
                            "title": {"type": "string"}, "id": {"type": "string"}},
                            "required": ["title", "id"]}}}}},
                }}},
            })
            alternate = _review(alternate, "get_title", "title", "paper.title", "id",
                                "paper.record_id", "public_rest")

            def extra_native(endpoint, arguments, *, name=extra_name):
                del endpoint, arguments
                seen.append((f"{name}.get_title", {}))
                return {"id": "other", "title": "Unexpected alternative"}

            router.add_bound_tool(alternate, extra_native)
    view = capture_authorized_agent_tool_surface(
        router, "Run the three reviewed sources independently",
        principal=PrincipalContext(subject="e1-multi-reader", roles=("reader",)),
    )
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
        approved_host_roots=frozenset(approved_routes),
    )
    catalog = NativeConceptCatalog(concepts=tuple(concepts))
    intent_registry = PaperIntentRegistry(intents=tuple(intents))
    from scripts.research_paper_heterogeneous_native_e1 import PaperNativeSourceCase

    agents = [ScriptedAgent() for _ in descriptions]
    cases = tuple(PaperNativeSourceCase(
        case_id=f"case-{i}", route_id=route, intent_id=intent,
        concept_id=concept, host_arguments=inputs,
        model=(lambda _payload, intent=intent, concept=concept, tool=tool: {
            "intent_id": intent, "concept_ids": [concept],
            "named_tools": [tool.key], "parameter_hints": {},
        }),
        agent=agents[i],
    ) for i, (tool, route, intent, concept, _field, inputs, _output)
    in enumerate(descriptions))
    return view, index, catalog, intent_registry, cases, agents, seen


@pytest.mark.asyncio
async def test_one_original_e1_p2_toolcall_per_actual_adapter_in_same_native_registry():
    from scripts.research_paper_heterogeneous_native_e1 import (
        run_paper_heterogeneous_native_e1,
    )

    view, index, catalog, intents, cases, agents, seen = _fixtures()
    matrix = await run_paper_heterogeneous_native_e1(
        cases=cases, view=view, index=index, catalog=catalog,
        intent_registry=intents,
    )
    assert matrix.executed_routes == (
        "source_rest.get_title", "source_mcp.read_wiki_structure",
        "source_optimade.get_structures",
    )
    assert tuple(x.result.data for x in matrix.receipts) == (
        {"id": "host-article", "title": "Verified title"},
        {"repoName": "modelcontextprotocol/servers", "result": "Verified wiki index"},
        {"id": "source-123", "chemical_formula_descriptive": "O2Si"},
    )
    assert [entry[0] for entry in seen] == list(matrix.executed_routes)
    assert seen[0][1] == {"item_id": "host-article"}
    assert seen[1][1] == {"repoName": "modelcontextprotocol/servers"}
    assert seen[2][1] == {"id": "source-123"}
    assert [agent.turns for agent in agents] == [1, 1, 1]
    assert matrix.host_bound_tool_calls == 3
    assert matrix.registered_source_types == ("public_rest", "public_mcp", "optimade")
    assert matrix.heterogeneous_sources is True
    assert matrix.independent_e2 is False


@pytest.mark.asyncio
async def test_single_source_success_does_not_claim_heterogeneous_protocol_coverage():
    from scripts.research_paper_heterogeneous_native_e1 import (
        run_paper_heterogeneous_native_e1,
    )

    view, index, catalog, intents, cases, _agents, seen = _fixtures()
    result = await run_paper_heterogeneous_native_e1(
        cases=cases[:1], view=view, index=index, catalog=catalog,
        intent_registry=intents,
    )
    assert result.registered_source_types == ("public_rest",)
    assert result.heterogeneous_sources is False
    assert result.executed_routes == (cases[0].route_id,)
    assert len(seen) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["last_unknown", "last_wrong_concept", "duplicate_route",
                                       "duplicate_id", "last_missing_input"])
async def test_invalid_later_case_aborts_entire_matrix_before_any_native_invocation(invalid):
    from scripts.research_paper_heterogeneous_native_e1 import (
        run_paper_heterogeneous_native_e1,
    )

    view, index, catalog, intents, cases, agents, seen = _fixtures()
    last = cases[-1]
    altered = {
        "last_unknown": replace(last, route_id="hidden.write"),
        "last_wrong_concept": replace(last, concept_id="wiki.outline"),
        "duplicate_route": replace(last, route_id=cases[0].route_id),
        "duplicate_id": replace(last, case_id=cases[0].case_id),
        "last_missing_input": replace(last, host_arguments={"id": ""}),
    }[invalid]
    with pytest.raises((ValueError, PermissionError)):
        await run_paper_heterogeneous_native_e1(
            cases=cases[:-1] + (altered,), view=view, index=index,
            catalog=catalog, intent_registry=intents,
        )
    assert seen == []
    assert [a.turns for a in agents] == [0, 0, 0]


@pytest.mark.asyncio
async def test_unoffered_agent_tool_does_not_execute_any_source():
    from scripts.research_paper_heterogeneous_native_e1 import (
        run_paper_heterogeneous_native_e1,
    )

    view, index, catalog, intents, cases, _agents, seen = _fixtures()
    malicious = replace(cases[0], agent=ScriptedAgent(force_route="hidden__write"))
    with pytest.raises(ValueError, match="direct|offer|selection|abstain"):
        await run_paper_heterogeneous_native_e1(
            cases=(malicious,) + cases[1:], view=view, index=index,
            catalog=catalog, intent_registry=intents,
        )
    assert seen == []


@pytest.mark.asyncio
async def test_second_native_source_error_never_returns_successful_matrix():
    from scripts.research_paper_heterogeneous_native_e1 import (
        run_paper_heterogeneous_native_e1,
    )

    view, index, catalog, intents, cases, agents, seen = _fixtures(fail_second=True)
    with pytest.raises(RuntimeError, match="MCP outage"):
        await run_paper_heterogeneous_native_e1(
            cases=cases, view=view, index=index, catalog=catalog,
            intent_registry=intents,
        )
    assert [item[0] for item in seen] == [cases[0].route_id, cases[1].route_id]
    assert [a.turns for a in agents] == [1, 1, 0]


@pytest.mark.asyncio
async def test_graph_changed_between_cases_aborts_before_next_native_io(monkeypatch):
    import scripts.research_paper_heterogeneous_native_e1 as matrix_module

    view, index, catalog, intents, cases, agents, seen = _fixtures()
    original = matrix_module.run_paper_scoped_native_direct_e1
    completed = 0

    async def concurrent_source_change(*args, **kwargs):
        nonlocal completed
        result = await original(*args, **kwargs)
        completed += 1
        if completed == 1:
            # Emulate a source owner changing the owner graph during the
            # async gap between two separately executed read-only calls.
            index.graph.capability_ids += ("unreviewed.derived",)
        return result

    monkeypatch.setattr(matrix_module, "run_paper_scoped_native_direct_e1",
                        concurrent_source_change)
    with pytest.raises(Exception, match="source|graph|declaration|changed"):
        await matrix_module.run_paper_heterogeneous_native_e1(
            cases=cases, view=view, index=index, catalog=catalog,
            intent_registry=intents,
        )
    assert [item[0] for item in seen] == [cases[0].route_id]
    assert [a.turns for a in agents] == [1, 0, 0]


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["model", "agent", "model_wrong_arity",
                                       "agent_wrong_arity"])
async def test_invalid_later_generator_aborts_all_sources_in_preflight(invalid):
    from scripts.research_paper_heterogeneous_native_e1 import (
        run_paper_heterogeneous_native_e1,
    )

    view, index, catalog, intents, cases, agents, seen = _fixtures()
    class WrongAgent:
        def generate(self):
            return {}

    replacements = {
        "model": {"model": None},
        "agent": {"agent": None},
        "model_wrong_arity": {"model": lambda: {}},
        "agent_wrong_arity": {"agent": WrongAgent()},
    }
    last = replace(cases[-1], **replacements[invalid])
    with pytest.raises(ValueError, match="model|agent|generator"):
        await run_paper_heterogeneous_native_e1(
            cases=cases[:-1] + (last,), view=view, index=index,
            catalog=catalog, intent_registry=intents,
        )
    assert seen == []
    assert [a.turns for a in agents] == [0, 0, 0]


@pytest.mark.asyncio
async def test_unbound_last_provider_rejected_before_first_native_io():
    from scripts.research_paper_heterogeneous_native_e1 import (
        run_paper_heterogeneous_native_e1,
    )

    view, index, catalog, intents, cases, agents, seen = _fixtures()
    view.router.executor.unbind("source_optimade")
    with pytest.raises(Exception, match="binding|invoker|unavailable|unbound"):
        await run_paper_heterogeneous_native_e1(
            cases=cases, view=view, index=index, catalog=catalog,
            intent_registry=intents,
        )
    assert seen == []
    assert [a.turns for a in agents] == [0, 0, 0]


@pytest.mark.asyncio
async def test_next_provider_rebinding_after_first_call_aborts_matrix(monkeypatch):
    import scripts.research_paper_heterogeneous_native_e1 as matrix_module

    view, index, catalog, intents, cases, agents, seen = _fixtures()
    original = matrix_module.run_paper_scoped_native_direct_e1
    completed = 0

    async def rebound_between_calls(*args, **kwargs):
        nonlocal completed
        result = await original(*args, **kwargs)
        completed += 1
        if completed == 1:
            second_tool = view.router.registry.get("source_mcp")
            view.router.executor.bind(
                "source_mcp",
                lambda endpoint, arguments: {
                    "repoName": "modelcontextprotocol/servers",
                    "result": "REBOUND",
                },
                expected_fingerprint=second_tool.fingerprint,
            )
        return result

    monkeypatch.setattr(matrix_module, "run_paper_scoped_native_direct_e1",
                        rebound_between_calls)
    with pytest.raises(Exception, match="binding|invoker|changed"):
        await matrix_module.run_paper_heterogeneous_native_e1(
            cases=cases, view=view, index=index, catalog=catalog,
            intent_registry=intents,
        )
    assert [item[0] for item in seen] == [cases[0].route_id]
    assert [a.turns for a in agents] == [1, 0, 0]


@pytest.mark.asyncio
async def test_preflight_availability_cannot_replace_later_provider_binding():
    from scripts.research_paper_heterogeneous_native_e1 import (
        run_paper_heterogeneous_native_e1,
    )

    view, index, catalog, intents, cases, agents, seen = _fixtures()
    router = view.router
    armed = False
    rebounded = False

    def available(tool, _endpoint):
        nonlocal rebounded
        if armed and not rebounded and tool.key == "source_rest":
            rebounded = True
            contract = router.registry.get("source_mcp")
            router.executor.bind(
                "source_mcp", lambda endpoint, arguments: {
                    "repoName": "modelcontextprotocol/servers",
                    "result": "Unexpected new binding",
                }, expected_fingerprint=contract.fingerprint,
            )
        return True

    router.planner.availability_predicate = available
    view = capture_authorized_agent_tool_surface(
        router, "Run the three reviewed sources independently",
        principal=PrincipalContext(subject="e1-multi-reader", roles=("reader",)),
    )
    armed = True
    with pytest.raises(Exception, match="native binding|source|changed"):
        await run_paper_heterogeneous_native_e1(
            cases=cases, view=view, index=index, catalog=catalog,
            intent_registry=intents,
        )
    assert rebounded is True
    assert seen == []
    assert [a.turns for a in agents] == [0, 0, 0]


@pytest.mark.asyncio
async def test_model_cannot_dispatch_different_valid_source_before_route_mismatch_check():
    from scripts.research_paper_heterogeneous_native_e1 import (
        run_paper_heterogeneous_native_e1,
    )

    view, index, catalog, intents, cases, agents, seen = _fixtures(
        allow_unrequested_openapi=True,
    )
    class EmptyInputAgent:
        def __init__(self):
            self.turns = 0

        def generate(self, messages: list[dict[str, str]],
                     tools: list[dict[str, Any]]) -> dict[str, Any]:
            del messages
            self.turns += 1
            payload = json.dumps({"name": tools[0]["name"], "arguments": {}})
            return {"text": f"<tool_call>{payload}</tool_call>",
                    "context_overflow": False}

    chooser = EmptyInputAgent()
    first = replace(cases[0], route_id="source_rest_public.get_title",
                    host_arguments=None, agent=chooser, model=lambda _payload: {
        "intent_id": "paper.lookup", "concept_ids": ["paper.title"],
        "named_tools": ["source_rest_alt"], "parameter_hints": {},
    })
    with pytest.raises(ValueError, match="selection|abstain|direct"):
        await run_paper_heterogeneous_native_e1(
            cases=(first,) + cases[1:], view=view, index=index,
            catalog=catalog, intent_registry=intents,
        )
    assert seen == []
    assert chooser.turns == 0
    assert [a.turns for a in agents] == [0, 0, 0]
